# backend/models/agent.py
"""
Agent数据模型

定义Agent相关的所有数据库表：
- Agent: Agent主表
- AgentChatSession: Agent聊天会话（单会话模式）
- AgentChatMessage: Agent聊天消息
- AgentPromptHistory: Prompt历史记录
- AgentKnowledgeIndex: 知识库索引
"""

import logging
from typing import List
from datetime import date

from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    Text,
    JSON,
    Boolean,
    Date,
    func,
)
from sqlalchemy.orm import relationship

from backend.app.database.session import Base

logger = logging.getLogger(__name__)


class Agent(Base):
    """
    Agent实体：代表用户创建的一个智能体
    """
    __tablename__ = "agents"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Agent基本信息
    name = Column(String(255), nullable=False)  # Agent名称（用户可修改）
    initial_prompt = Column(Text, nullable=False)  # 初始prompt（创建后不可修改）
    current_prompt = Column(Text, nullable=False)  # 当前prompt（包含初始prompt + 累计总结）

    # 元数据
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
    last_summarized_at = Column(DateTime(timezone=True), nullable=True)  # 上次总结时间

    # 关联关系
    user = relationship("User", back_populates="agents")
    chat_session = relationship(
        "AgentChatSession",
        back_populates="agent",
        uselist=False,  # 一对一关系
        cascade="all, delete-orphan",
    )
    prompt_history = relationship(
        "AgentPromptHistory",
        back_populates="agent",
        cascade="all, delete-orphan",
        order_by="AgentPromptHistory.created_at.asc()",
    )
    knowledge_indexes = relationship(
        "AgentKnowledgeIndex",
        back_populates="agent",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<Agent(id={self.id}, name='{self.name}', user_id={self.user_id})>"


class AgentChatSession(Base):
    """
    Agent聊天会话：每个Agent只有一个会话（单会话模式）
    """
    __tablename__ = "agent_chat_sessions"

    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(
        Integer,
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,  # 确保每个Agent只有一个会话
        index=True,
    )

    # 会话信息
    title = Column(String(255), nullable=True)  # 会话标题（可选，可以自动生成）
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # 关联关系
    agent = relationship("Agent", back_populates="chat_session")
    messages = relationship(
        "AgentChatMessage",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="AgentChatMessage.created_at.asc()",
    )

    def __repr__(self):
        return f"<AgentChatSession(id={self.id}, agent_id={self.agent_id})>"


class AgentChatMessage(Base):
    """
    Agent聊天消息：与日常聊天的消息类似，但属于Agent会话
    """
    __tablename__ = "agent_chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(
        Integer,
        ForeignKey("agent_chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    role = Column(String(20), nullable=False)  # user / assistant
    content = Column(Text, nullable=False)
    reasoning_content = Column(Text, nullable=True)  # 深度思考内容（可选）
    images = Column(JSON, nullable=True)  # 用户上传的图片
    generated_images = Column(JSON, nullable=True)  # Agent生成的图片

    # 多消息批次管理
    batch_id = Column(String(50), nullable=True, index=True)  # 批次ID（同一次"等待-回复"周期）
    batch_index = Column(Integer, nullable=True)  # 批次内的顺序（用户消息或AI回复的序号）

    # 发送时间控制（仅AI消息）
    send_delay_seconds = Column(Integer, nullable=True)  # 延迟秒数（从第一条回复开始计算）

    # 元数据
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # 关联关系
    session = relationship("AgentChatSession", back_populates="messages")

    def __repr__(self):
        return f"<AgentChatMessage(id={self.id}, role='{self.role}', batch_id='{self.batch_id}')>"


class AgentPromptHistory(Base):
    """
    Agent Prompt历史：记录prompt的演进过程
    每次追加总结时，创建一条历史记录
    支持硬删除（直接删除记录）
    """
    __tablename__ = "agent_prompt_history"

    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(
        Integer,
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Prompt内容
    added_prompt = Column(Text, nullable=False)  # 本次追加的prompt内容（总结内容）
    full_prompt_before = Column(Text, nullable=False)  # 追加前的完整prompt
    full_prompt_after = Column(Text, nullable=False)  # 追加后的完整prompt

    # 时间信息
    summary_date = Column(Date, nullable=False, index=True)  # 总结的日期（对应哪天的聊天）
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # 关联关系
    agent = relationship("Agent", back_populates="prompt_history")
    knowledge_index = relationship(
        "AgentKnowledgeIndex",
        back_populates="prompt_history",
        uselist=False,  # 一对一关系
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<AgentPromptHistory(id={self.id}, agent_id={self.agent_id}, summary_date={self.summary_date})>"


class AgentKnowledgeIndex(Base):
    """
    Agent知识库索引：建立总结内容与具体聊天日期的索引关系
    """
    __tablename__ = "agent_knowledge_indexes"

    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(
        Integer,
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    prompt_history_id = Column(
        Integer,
        ForeignKey("agent_prompt_history.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,  # 一个prompt_history对应一个knowledge_index
        index=True,
    )

    # 索引信息
    summary_date = Column(Date, nullable=False, index=True)  # 对应的聊天日期
    summary_summary = Column(Text, nullable=False)  # 总结摘要（冗余存储，方便检索）

    # 扩展信息（用于检索）
    topics = Column(JSON, nullable=True)  # 讨论话题列表
    key_points = Column(JSON, nullable=True)  # 关键点列表
    keywords = Column(JSON, nullable=True)  # 关键词列表（用于全文检索）

    # 统计信息
    message_count = Column(Integer, nullable=False, default=0)  # 当天消息总数
    user_message_count = Column(Integer, nullable=False, default=0)  # 用户消息数

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # 关联关系
    agent = relationship("Agent", back_populates="knowledge_indexes")
    prompt_history = relationship("AgentPromptHistory", back_populates="knowledge_index")

    def __repr__(self):
        return f"<AgentKnowledgeIndex(id={self.id}, agent_id={self.agent_id}, summary_date={self.summary_date})>"

