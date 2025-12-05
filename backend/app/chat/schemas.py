# backend/app/chat/schemas.py
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


# --- 基本输出模型 ---

class ChatMessageOut(BaseModel):
    id: int
    role: str
    content: str
    reasoning_content: Optional[str] = None  # 深度思考内容（可选）
    images: Optional[List[str]] = None  # 图片Base64编码字符串列表（可选，仅用户消息，用于用户上传的图片）
    generated_images: Optional[List[str]] = None  # 模型生成的图片URL列表（可选，仅assistant消息，用于存储图片生成、图生图等功能生成的图片）
    created_at: datetime

    class Config:
        from_attributes = True


class ChatSessionSummary(BaseModel):
    id: int
    title: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ChatSessionWithMessages(BaseModel):
    session: ChatSessionSummary
    messages: List[ChatMessageOut]


# --- 输入模型 ---

class ChatSessionCreate(BaseModel):
    """
    新建会话 + 发送首条问题
    """
    question: str
    title: Optional[str] = None
    thinking: str = "disabled"  # "disabled", "enabled" (注意：当前模型不支持 "auto")
    images: Optional[List[str]] = None  # 图片Base64编码字符串列表，支持多张图片


class ChatMessageCreate(BaseModel):
    """
    在已有会话中继续发送问题
    """
    question: str
    thinking: str = "disabled"  # "disabled", "enabled" (注意：当前模型不支持 "auto")
    images: Optional[List[str]] = None  # 图片Base64编码字符串列表，支持多张图片


class ChatSessionUpdate(BaseModel):
    """
    更新会话标题
    """
    title: str


# --- 复合输出模型 ---

class ChatSessionCreatedResponse(BaseModel):
    session: ChatSessionSummary
    messages: List[ChatMessageOut]


class ChatTurnResponse(BaseModel):
    """
    一次往返（用户问题 + AI 回复）
    """
    messages: List[ChatMessageOut]
