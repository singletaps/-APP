# backend/app/ai/service.py
from typing import List, Dict, Iterator, Optional, Any
import logging

from backend.app.ai.client import client

# 配置日志
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

DEFAULT_SYSTEM_PROMPT = (
    "你是一个专业的AI助手。请使用深度思考来分析和回答问题。"
    "在回答时，你可以使用 Markdown 和 LaTeX 格式来更好地展示内容。"
    "对于复杂问题，请先进行深入思考，然后给出清晰的答案。"
)


def build_multimodal_content(text: str, image_base64_list: Optional[List[str]] = None) -> Any:
    """
    构建多模态消息内容格式。
    
    如果提供了图片（Base64编码或URL），返回列表格式（多模态）：
    [
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,..." 或 "https://..."}},
        {"type": "text", "text": "..."}
    ]
    
    如果没有图片，返回字符串格式（纯文本）：
    "文本内容"
    
    Args:
        text: 文本内容
        image_base64_list: 图片列表，可选
                          - 可以是Base64编码字符串（data:image/... 格式或纯base64）
                          - 也可以是HTTP/HTTPS URL（用于生成的图片）
    
    Returns:
        多模态内容列表或纯文本字符串
    """
    if not image_base64_list or len(image_base64_list) == 0:
        return text
    
    # 构建多模态内容
    content = []
    # 先添加所有图片
    for image_str in image_base64_list:
        # 判断是URL还是Base64
        if image_str.startswith("http://") or image_str.startswith("https://"):
            # HTTP/HTTPS URL，直接使用
            image_url = image_str
        elif image_str.startswith("data:image/"):
            # 已经是完整的data:image格式，直接使用
            image_url = image_str
        else:
            # 纯base64字符串，添加前缀
            # 默认使用png格式，如果需要可以后续优化识别格式
            image_url = f"data:image/png;base64,{image_str}"
        
        content.append({
            "type": "image_url",
            "image_url": {
                "url": image_url
            }
        })
    # 最后添加文本
    content.append({
        "type": "text",
        "text": text
    })
    
    return content


def ask_with_messages(
    messages: List[Dict[str, Any]],
    model: str = "doubao-seed-1-6-251015",
    thinking: str = "disabled",
) -> str:
    completion = client.chat.completions.create(
        model=model,
        messages=messages,
        thinking={
            "type": thinking,  # "disabled", "enabled" (注意：当前模型不支持 "auto")
        },
        max_tokens=5000,
        temperature=0.3,
    )
    return completion.choices[0].message.content.strip()


def ask_with_messages_stream(
    messages: List[Dict[str, Any]], 
    model: str = "doubao-seed-1-6-251015",
    thinking: str = "disabled",
) -> Iterator[Dict[str, str]]:
    """
    流式调用 Ark Chat API，按增量 token 迭代返回文本。
    返回格式：{"content": "文本内容", "reasoning_content": "思考内容"或None}
    注意：具体字段（如 delta.content）依赖 Ark SDK 的返回结构，如果有出入，请按实际文档调整。
    """
    logger.debug(f"[AI Service] ========== 开始流式调用API ==========")
    logger.debug(f"[AI Service] 模型: {model}, 消息数: {len(messages)}, 深度思考: {thinking}")
    logger.debug(f"[AI Service] thinking参数值: {repr(thinking)}")
    
    # DEBUG 2: 打印API请求参数
    api_params = {
        "model": model,
        "messages": messages,
        "thinking": {"type": thinking},
        "max_tokens": 5000,
        "temperature": 0.3,
        "stream": True
    }
    logger.debug(f"[AI Service] API请求参数: {api_params}")
    
    stream = client.chat.completions.create(
        model=model,
        messages=messages,
        thinking={
            "type": thinking,  # "disabled", "enabled" (注意：当前模型不支持 "auto")
        },
        max_tokens=5000,
        temperature=0.3,
        stream=True,
    )
    chunk_count = 0
    
    for chunk in stream:
        chunk_count += 1
        
        # 处理流式响应，支持深度思考模型的输出
        # Ark SDK 兼容 OpenAI 格式：choices[0].delta.content
        choice = chunk.choices[0]
        
        # 尝试获取 delta 或 message_delta
        delta = getattr(choice, "delta", None) or getattr(
            choice, "message_delta", None
        ) or getattr(choice, "message", None)
        
        if not delta:
            continue
        
        # 检查delta中是否有reasoning_content（流式返回，立即发送）
        # 根据测试结果：reasoning_content在delta中，是流式返回的，每个chunk只有一小部分
        # 应该像content一样，每个片段都立即流式发送给客户端
        if hasattr(delta, "reasoning_content"):
            delta_reasoning = getattr(delta, "reasoning_content")
            if delta_reasoning:
                # reasoning_content是流式返回的，每个chunk只有一小部分，立即发送
                reasoning_str = str(delta_reasoning)
                logger.debug(f"[AI Service] chunk #{chunk_count}: 发送reasoning_content片段，长度: {len(reasoning_str)}")
                yield {"content": "", "reasoning_content": reasoning_str}
        
        # 获取内容，可能是思考过程或最终答案
        # 根据测试结果，content在reasoning_content全部输出完成后才开始出现
        content = getattr(delta, "content", None)
        if content:
            # content 可能是 str 或 List[ContentPart]，这里只处理 str 场景
            if isinstance(content, str):
                logger.debug(f"[AI Service] chunk #{chunk_count}: 发送content片段，长度: {len(content)}")
                yield {"content": content, "reasoning_content": None}
    
    logger.debug(f"[AI Service] ========== 流式调用完成 ==========")
    logger.debug(f"[AI Service] 共处理 {chunk_count} 个chunk")


def ask_bot(
    user_question: str,
    system_prompt: str = DEFAULT_SYSTEM_PROMPT,
    model: str = "doubao-seed-1-6-251015",
    thinking: str = "disabled",
    images: Optional[List[str]] = None,
) -> str:
    """
    非流式调用，支持图像理解。
    
    Args:
        user_question: 用户问题文本
        system_prompt: 系统提示词
        model: 模型名称
        thinking: 深度思考模式
        images: 图片Base64编码字符串列表，可选
    """
    user_content = build_multimodal_content(user_question, images)
    
    messages = [
        {
            "role": "system",
            "content": system_prompt,
        },
        {
            "role": "user",
            "content": user_content,
        },
    ]

    return ask_with_messages(messages, model=model, thinking=thinking)


def ask_bot_stream(
    user_question: str,
    system_prompt: str = DEFAULT_SYSTEM_PROMPT,
    model: str = "doubao-seed-1-6-251015",
    thinking: str = "disabled",
    images: Optional[List[str]] = None,
) -> Iterator[Dict[str, str]]:
    """
    流式版本：返回一个可迭代对象，逐块输出模型回答。
    支持图像理解。
    
    返回格式：{"content": "文本内容", "reasoning_content": "思考内容"或None}
    
    Args:
        user_question: 用户问题文本
        system_prompt: 系统提示词
        model: 模型名称
        thinking: 深度思考模式
        images: 图片Base64编码字符串列表，可选
    """
    user_content = build_multimodal_content(user_question, images)
    
    messages = [
        {
            "role": "system",
            "content": system_prompt,
        },
        {
            "role": "user",
            "content": user_content,
        },
    ]

    return ask_with_messages_stream(messages, model=model, thinking=thinking)
