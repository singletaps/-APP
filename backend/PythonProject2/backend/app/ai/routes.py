# backend/app/ai/routes.py
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import json
import logging

from backend.app.ai.service import ask_bot, ask_bot_stream
from backend.app.auth.deps import get_current_user
from backend.app.models.user import User

# 配置日志
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

router = APIRouter(prefix="/ai", tags=["ai"])


class AIQuestion(BaseModel):
    question: str
    thinking: str = "disabled"  # "disabled", "enabled" (注意：当前模型不支持 "auto")


class AIAnswer(BaseModel):
    answer: str


@router.post("/ask", response_model=AIAnswer)
def ask_ai(
    payload: AIQuestion,
    current_user: User = Depends(get_current_user),
):

    try:
        answer = ask_bot(payload.question, thinking=payload.thinking)
    except Exception as e:
        # 生产环境可以在这里打日志
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI service error",
        )

    return AIAnswer(answer=answer)


@router.post("/ask/stream")
def ask_ai_stream(
    payload: AIQuestion,
    current_user: User = Depends(get_current_user),
):
    """
    流式调用 AI，使用 SSE (Server-Sent Events) 格式返回。

    前端可以使用 EventSource 或 fetch + ReadableStream 来接收：
    - 每个数据块格式：data: {content}\\n\\n
    - 开始事件：event: start\\ndata: {}\\n\\n
    - 结束事件：event: end\\ndata: {}\\n\\n
    - 错误事件：event: error\\ndata: {error_message}\\n\\n
    """

    def sse_generator():
        try:
            logger.debug(f"[SSE] 开始流式输出，问题: {payload.question[:50]}...")
            # 发送开始事件
            start_event = "event: start\n"
            start_data = f"data: {json.dumps({}, ensure_ascii=False)}\n\n"
            logger.debug(f"[SSE] 发送开始事件: {start_event.strip()}")
            yield start_event
            yield start_data
            
            chunk_count = 0
            # 流式返回 AI 回答的每个 chunk
            for chunk_data in ask_bot_stream(payload.question, thinking=payload.thinking):
                chunk_count += 1
                chunk_content = chunk_data.get("content", "")
                chunk_reasoning = chunk_data.get("reasoning_content")
                
                if chunk_content:
                    logger.debug(f"[SSE] 收到chunk #{chunk_count}, 长度: {len(chunk_content)}, 内容预览: {repr(chunk_content[:50])}")
                    # SSE 格式：使用JSON格式与chat接口保持一致
                    # data: {"content": "chunk内容"}\n\n
                    chunk_event = f"event: chunk\n"
                    chunk_data_json = f"data: {json.dumps({'content': chunk_content}, ensure_ascii=False)}\n\n"
                    logger.debug(f"[SSE] 发送chunk事件 #{chunk_count}")
                    yield chunk_event
                    yield chunk_data_json
                
                if chunk_reasoning:
                    logger.debug(f"[SSE] ⭐ 收到reasoning_content片段 #{chunk_count}, 长度: {len(chunk_reasoning)}, 预览: {repr(chunk_reasoning[:50])}")
                    reasoning_event = f"event: reasoning\n"
                    reasoning_data = f"data: {json.dumps({'reasoning_content': chunk_reasoning}, ensure_ascii=False)}\n\n"
                    logger.debug(f"[SSE] ⭐ 发送reasoning事件 #{chunk_count}")
                    yield reasoning_event
                    yield reasoning_data
            
            logger.debug(f"[SSE] 流式输出完成，共发送 {chunk_count} 个chunk")
            # 发送结束事件
            end_event = "event: end\n"
            end_data = f"data: {json.dumps({}, ensure_ascii=False)}\n\n"
            logger.debug(f"[SSE] 发送结束事件")
            yield end_event
            yield end_data
        except Exception as e:
            logger.error(f"[SSE] 流式输出错误: {e}", exc_info=True)
            # 发送错误事件
            yield f"event: error\n"
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        sse_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 Nginx 缓冲
        },
    )
