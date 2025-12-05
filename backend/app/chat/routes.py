# backend/app/chat/routes.py
from typing import List
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend.app.auth.deps import get_current_user
from backend.app.database.session import get_db
from backend.app.models.user import User
from backend.app.chat import schemas as chat_schemas
from backend.app.chat import service as chat_service

# 配置日志
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

router = APIRouter(prefix="/chat", tags=["chat"])


@router.get(
    "/sessions",
    response_model=List[chat_schemas.ChatSessionSummary],
)
def list_sessions(
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    获取当前用户的所有会话列表
    """
    sessions = chat_service.list_sessions_for_user(
        db, current_user, skip=skip, limit=limit
    )
    return sessions


@router.post(
    "/sessions",
    response_model=chat_schemas.ChatSessionCreatedResponse,
)
def create_session(
    payload: chat_schemas.ChatSessionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    创建一个新会话，并发送首条问题。
    返回：会话信息 + （用户问题 + AI 回复）两条消息。
    """
    session, msgs = chat_service.create_session_and_ask(
        db=db,
        user=current_user,
        question=payload.question,
        title=payload.title,
        thinking=payload.thinking,
        images=payload.images,
    )
    return chat_schemas.ChatSessionCreatedResponse(
        session=session,
        messages=msgs,
    )


@router.post("/sessions/stream")
def create_session_stream(
    payload: chat_schemas.ChatSessionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    创建会话并流式返回 AI 回答（SSE 格式）。
    
    事件类型：
    - session_created: 会话已创建
    - user_msg_created: 用户消息已保存
    - chunk: AI 回答的文本块
    - complete: 流结束，所有数据已保存
    - error: 发生错误
    """
    # DEBUG 1: 检查前端是否传递了thinking参数
    logger.debug(f"[Chat Routes] ========== 收到流式请求 ==========")
    logger.debug(f"[Chat Routes] 问题: {payload.question[:50]}...")
    logger.debug(f"[Chat Routes] thinking参数: {payload.thinking}")
    logger.debug(f"[Chat Routes] thinking类型: {type(payload.thinking)}")
    logger.debug(f"[Chat Routes] payload完整内容: {payload.model_dump_json()}")
    
    def sse_generator():
        try:
            for event_type, data in chat_service.create_session_and_ask_stream(
                db=db,
                user=current_user,
                question=payload.question,
                title=payload.title,
                thinking=payload.thinking,
                images=payload.images,
            ):
                # DEBUG 3: 打印发送给前端的JSON
                data_json = json.dumps(data, ensure_ascii=False)
                logger.debug(f"[Chat Routes] 发送事件到前端: event={event_type}, data长度={len(data_json)}")
                logger.debug(f"[Chat Routes] 发送的JSON内容: {data_json[:500]}...")  # 只打印前500字符
                if event_type == "reasoning":
                    logger.debug(f"[Chat Routes] ⭐ reasoning事件 - reasoning_content长度: {len(data.get('reasoning_content', ''))}")
                yield f"event: {event_type}\n"
                yield f"data: {data_json}\n\n"
        except Exception as e:
            logger.error(f"[Chat Routes] 流式处理错误: {e}", exc_info=True)
            yield f"event: error\n"
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(
        sse_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get(
    "/sessions/{session_id}/messages",
    response_model=chat_schemas.ChatSessionWithMessages,
)
def get_session_messages(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    查看某个会话的所有消息
    """
    session, messages = chat_service.get_session_with_messages_for_user(
        db, current_user, session_id
    )
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )
    return chat_schemas.ChatSessionWithMessages(
        session=session,
        messages=messages,
    )


@router.post(
    "/sessions/{session_id}/messages",
    response_model=chat_schemas.ChatTurnResponse,
)
def send_message(
    session_id: int,
    payload: chat_schemas.ChatMessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    在已有会话中继续提问。
    返回本轮的两条消息：用户问题 + AI 回复。
    """
    try:
        msgs = chat_service.send_message_in_session(
            db=db,
            user=current_user,
            session_id=session_id,
            question=payload.question,
            thinking=payload.thinking,
            images=payload.images,
        )
    except ValueError as e:
        if str(e) == "session_not_found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found",
            )
        raise

    return chat_schemas.ChatTurnResponse(messages=msgs)


@router.delete("/sessions/{session_id}")
def delete_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    删除指定的会话（级联删除所有消息）。
    """
    success = chat_service.delete_session_for_user(
        db=db,
        user=current_user,
        session_id=session_id,
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )
    return {"message": "Session deleted successfully"}


@router.put(
    "/sessions/{session_id}",
    response_model=chat_schemas.ChatSessionSummary,
)
def update_session(
    session_id: int,
    payload: chat_schemas.ChatSessionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    更新指定会话的标题。
    """
    session = chat_service.update_session_title_for_user(
        db=db,
        user=current_user,
        session_id=session_id,
        new_title=payload.title,
    )
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )
    return session


@router.post("/sessions/{session_id}/messages/stream")
def send_message_stream(
    session_id: int,
    payload: chat_schemas.ChatMessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    在已有会话中流式发送消息（SSE 格式）。
    
    事件类型：
    - user_msg_created: 用户消息已保存
    - chunk: AI 回答的文本块
    - complete: 流结束，所有数据已保存
    - error: 发生错误
    """
    # DEBUG 1: 检查前端是否传递了thinking参数
    logger.debug(f"[Chat Routes] ========== 收到流式请求（已有会话） ==========")
    logger.debug(f"[Chat Routes] session_id: {session_id}")
    logger.debug(f"[Chat Routes] 问题: {payload.question[:50]}...")
    logger.debug(f"[Chat Routes] thinking参数: {payload.thinking}")
    logger.debug(f"[Chat Routes] thinking类型: {type(payload.thinking)}")
    logger.debug(f"[Chat Routes] payload完整内容: {payload.model_dump_json()}")
    
    def sse_generator():
        try:
            for event_type, data in chat_service.send_message_in_session_stream(
                db=db,
                user=current_user,
                session_id=session_id,
                question=payload.question,
                thinking=payload.thinking,
                images=payload.images,
            ):
                # DEBUG 3: 打印发送给前端的JSON
                data_json = json.dumps(data, ensure_ascii=False)
                logger.debug(f"[Chat Routes] 发送事件到前端: event={event_type}, data长度={len(data_json)}")
                logger.debug(f"[Chat Routes] 发送的JSON内容: {data_json[:500]}...")  # 只打印前500字符
                if event_type == "reasoning":
                    logger.debug(f"[Chat Routes] ⭐ reasoning事件 - reasoning_content长度: {len(data.get('reasoning_content', ''))}")
                yield f"event: {event_type}\n"
                yield f"data: {data_json}\n\n"
        except Exception as e:
            logger.error(f"[Chat Routes] 流式处理错误: {e}", exc_info=True)
            yield f"event: error\n"
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(
        sse_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
