# backend/app/agents/schemas.py
"""
Agent模块的Pydantic Schema定义

定义所有API的请求和响应模型
"""

import logging
from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# --- 基本输出模型 ---

class AgentSummary(BaseModel):
    """Agent摘要信息"""
    id: int
    name: str
    created_at: datetime
    updated_at: datetime
    last_summarized_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AgentDetail(AgentSummary):
    """Agent详细信息"""
    initial_prompt: str
    current_prompt: str

    class Config:
        from_attributes = True


class AgentChatMessageOut(BaseModel):
    """Agent聊天消息输出"""
    id: int
    role: str
    content: str
    reasoning_content: Optional[str] = None
    batch_id: Optional[str] = None
    batch_index: Optional[int] = None
    send_delay_seconds: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class AgentChatSessionOut(BaseModel):
    """Agent聊天会话输出"""
    id: int
    agent_id: int
    title: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AgentChatSessionWithMessages(BaseModel):
    """Agent会话及其消息"""
    session: AgentChatSessionOut
    messages: List[AgentChatMessageOut]


class AgentPromptHistoryOut(BaseModel):
    """Agent Prompt历史输出"""
    id: int
    agent_id: int
    added_prompt: str
    summary_date: date
    created_at: datetime

    class Config:
        from_attributes = True


class AgentKnowledgeIndexOut(BaseModel):
    """Agent知识库索引输出"""
    id: int
    agent_id: int
    summary_date: date
    summary_summary: str
    topics: Optional[List[str]] = None
    key_points: Optional[List[str]] = None
    keywords: Optional[List[str]] = None
    message_count: int
    user_message_count: int
    created_at: datetime

    class Config:
        from_attributes = True


# --- 输入模型 ---

class AgentCreate(BaseModel):
    """创建Agent的请求"""
    name: str = Field(..., min_length=1, max_length=255, description="Agent名称")
    initial_prompt: str = Field(..., min_length=1, description="Agent的初始prompt")


class AgentUpdate(BaseModel):
    """更新Agent的请求（只能更新名称）"""
    name: str = Field(..., min_length=1, max_length=255, description="Agent名称")


class AgentBatchMessageCreate(BaseModel):
    """批量发送消息的请求"""
    messages: List[str] = Field(..., min_items=1, max_items=20, description="用户消息列表（最多20条）")


class AgentReply(BaseModel):
    """Agent回复"""
    id: Optional[int] = None
    content: str
    send_delay_seconds: int = Field(default=0, ge=0, le=10, description="发送延迟（秒）")
    order: int = Field(default=0, description="回复顺序")


class AgentBatchMessageResponse(BaseModel):
    """批量消息响应"""
    batch_id: str
    replies: List[AgentReply]


class KnowledgeSearchRequest(BaseModel):
    """知识库搜索请求"""
    query: str = Field(..., min_length=1, description="搜索查询（可以包含日期和关键词）")
    date_from: Optional[date] = None
    date_to: Optional[date] = None


class KnowledgeSearchResult(BaseModel):
    """知识库搜索结果"""
    summary_date: date
    summary: str
    topics: Optional[List[str]] = None
    message_count: int


class KnowledgeSearchResponse(BaseModel):
    """知识库搜索响应"""
    results: List[KnowledgeSearchResult]
    total: int


# --- 复合输出模型 ---

class AgentCreatedResponse(BaseModel):
    """Agent创建响应"""
    agent: AgentDetail
    session: AgentChatSessionOut


class AgentPromptHistoryResponse(BaseModel):
    """Agent Prompt历史响应"""
    histories: List[AgentPromptHistoryOut]
    total: int


class AgentKnowledgeIndexResponse(BaseModel):
    """Agent知识库索引响应"""
    indexes: List[AgentKnowledgeIndexOut]
    total: int


class DeletePromptSummaryResponse(BaseModel):
    """删除Prompt总结的响应"""
    success: bool
    deleted_summary_date: Optional[date] = None
    remaining_count: int
    current_prompt_preview: Optional[str] = None


class ClearAndSummarizeResponse(BaseModel):
    """清空聊天并总结记忆的响应"""
    success: bool
    summary: Optional[str] = None

