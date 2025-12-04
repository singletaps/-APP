# backend/models/chat.py
from typing import List

from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    Text,
    JSON,
    func,
)
from sqlalchemy.orm import relationship

from backend.app.database.session import Base


class ChatSession(Base):
    """
    一组聊天会话（一个“对话窗口”）
    """
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title = Column(String(255), nullable=True)  # 对话标题，可用首条问题生成
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    user = relationship("User", back_populates="chat_sessions")
    messages = relationship(
        "ChatMessage",
        back_populates="session",
        cascade="all, delete-orphan",
    )


class ChatMessage(Base):
    """
    一条聊天消息
    """
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(
        Integer,
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role = Column(String(20), nullable=False)  # user / assistant / system
    content = Column(Text, nullable=False)
    reasoning_content = Column(Text, nullable=True)  # 深度思考内容（可选）
    images = Column(JSON, nullable=True)  # 图片Base64编码列表（可选，仅用户消息，用于用户上传的图片）
    generated_images = Column(JSON, nullable=True)  # 模型生成的图片URL列表（可选，仅assistant消息，用于存储图片生成、图生图等功能生成的图片）
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    session = relationship("ChatSession", back_populates="messages")


