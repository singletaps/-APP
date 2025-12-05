# backend/app/agents/routes.py
"""
Agent API路由

提供Agent相关的API端点
"""

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.auth.deps import get_current_user
from backend.app.database.session import get_db
from backend.app.models.user import User
from backend.app.agents import schemas as agent_schemas
from backend.app.agents import service as agent_service

# 配置日志
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

router = APIRouter(prefix="/agents", tags=["agents"])


# ==================== Agent管理API ====================

@router.get(
    "/",
    response_model=List[agent_schemas.AgentSummary],
)
def list_agents(
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    获取当前用户的所有Agent列表
    """
    logger.info(f"[Agent路由] 获取Agent列表: user_id={current_user.id}")
    
    try:
        agents = agent_service.list_agents_for_user(
            db=db,
            user=current_user,
            skip=skip,
            limit=limit,
        )
        return agents
    except Exception as e:
        logger.error(f"[Agent路由] ❌ 获取Agent列表失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取Agent列表失败: {str(e)}"
        )


@router.post(
    "/",
    response_model=agent_schemas.AgentCreatedResponse,
)
def create_agent(
    payload: agent_schemas.AgentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    创建新Agent
    """
    logger.info(f"[Agent路由] 创建Agent: user_id={current_user.id}, name={payload.name}")
    
    try:
        agent = agent_service.create_agent(
            db=db,
            user=current_user,
            name=payload.name,
            initial_prompt=payload.initial_prompt,
        )
        
        return agent_schemas.AgentCreatedResponse(
            agent=agent,
            session=agent.chat_session
        )
    except Exception as e:
        logger.error(f"[Agent路由] ❌ 创建Agent失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建Agent失败: {str(e)}"
        )


@router.get(
    "/{agent_id}",
    response_model=agent_schemas.AgentDetail,
)
def get_agent(
    agent_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    获取Agent详情
    """
    logger.info(f"[Agent路由] 获取Agent详情: agent_id={agent_id}")
    
    agent = agent_service.get_agent_for_user(db=db, user=current_user, agent_id=agent_id)
    
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found"
        )
    
    return agent


@router.put(
    "/{agent_id}",
    response_model=agent_schemas.AgentDetail,
)
def update_agent(
    agent_id: int,
    payload: agent_schemas.AgentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    更新Agent信息（只能更新名称）
    """
    logger.info(f"[Agent路由] 更新Agent: agent_id={agent_id}, new_name={payload.name}")
    
    agent = agent_service.update_agent_name(
        db=db,
        user=current_user,
        agent_id=agent_id,
        new_name=payload.name,
    )
    
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found"
        )
    
    return agent


@router.delete(
    "/{agent_id}",
)
def delete_agent(
    agent_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    删除Agent（级联删除会话、消息、历史等）
    """
    logger.info(f"[Agent路由] 删除Agent: agent_id={agent_id}")
    
    success = agent_service.delete_agent(
        db=db,
        user=current_user,
        agent_id=agent_id,
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found"
        )
    
    return {"message": "Agent deleted successfully"}


# ==================== Agent聊天API ====================

@router.get(
    "/{agent_id}/chat",
    response_model=agent_schemas.AgentChatSessionWithMessages,
)
def get_agent_chat(
    agent_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    获取Agent的聊天会话和消息
    """
    logger.info(f"[Agent路由] 获取Agent聊天: agent_id={agent_id}")
    
    agent = agent_service.get_agent_for_user(db=db, user=current_user, agent_id=agent_id)
    
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found"
        )
    
    session = agent_service.get_or_create_agent_session(db=db, agent_id=agent_id)
    messages = agent_service.get_agent_session_messages(db=db, session_id=session.id)
    
    return agent_schemas.AgentChatSessionWithMessages(
        session=session,
        messages=messages,
    )


@router.post(
    "/{agent_id}/chat/messages/batch",
    response_model=agent_schemas.AgentBatchMessageResponse,
)
def send_batch_messages(
    agent_id: int,
    payload: agent_schemas.AgentBatchMessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    批量发送消息到Agent（核心API）
    
    接收多条用户消息，返回多条AI回复（带延迟信息）
    """
    logger.info(f"[Agent路由] ========== 批量发送消息 ==========")
    logger.info(f"[Agent路由] agent_id={agent_id}, message_count={len(payload.messages)}")
    
    try:
        # 调用批量消息处理服务
        batch_id, ai_replies = agent_service.send_batch_messages_to_agent(
            db=db,
            user=current_user,
            agent_id=agent_id,
            user_messages=payload.messages,
        )
        
        # 转换为响应格式
        replies = [
            agent_schemas.AgentReply(
                content=reply["content"],
                send_delay_seconds=reply["send_delay_seconds"],
                order=idx,
            )
            for idx, reply in enumerate(ai_replies)
        ]
        
        logger.info(f"[Agent路由] ✅ 批量消息处理成功: batch_id={batch_id}, 回复数量={len(replies)}")
        
        return agent_schemas.AgentBatchMessageResponse(
            batch_id=batch_id,
            replies=replies,
        )
        
    except ValueError as e:
        logger.error(f"[Agent路由] ❌ 参数错误: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"[Agent路由] ❌ 批量消息处理失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"批量消息处理失败: {str(e)}"
        )


# ==================== Prompt管理API ====================

@router.get(
    "/{agent_id}/prompt-history",
    response_model=agent_schemas.AgentPromptHistoryResponse,
)
def get_agent_prompt_history(
    agent_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    获取Agent的prompt历史
    """
    logger.info(f"[Agent路由] 获取Prompt历史: agent_id={agent_id}")
    
    agent = agent_service.get_agent_for_user(db=db, user=current_user, agent_id=agent_id)
    
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found"
        )
    
    from backend.app.models.agent import AgentPromptHistory
    histories = (
        db.query(AgentPromptHistory)
        .filter(AgentPromptHistory.agent_id == agent_id)
        .order_by(AgentPromptHistory.created_at.desc())
        .all()
    )
    
    return agent_schemas.AgentPromptHistoryResponse(
        histories=histories,
        total=len(histories)
    )


@router.delete(
    "/{agent_id}/prompt-history/latest",
    response_model=agent_schemas.DeletePromptSummaryResponse,
)
def delete_latest_prompt_summary(
    agent_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    删除最新的prompt总结（只能删除最后一条）
    """
    logger.info(f"[Agent路由] 删除最新Prompt总结: agent_id={agent_id}")
    
    success, deleted_date, remaining_count, preview = agent_service.delete_latest_prompt_summary(
        db=db,
        user=current_user,
        agent_id=agent_id,
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No summary to delete"
        )
    
    return agent_schemas.DeletePromptSummaryResponse(
        success=True,
        deleted_summary_date=deleted_date,
        remaining_count=remaining_count,
        current_prompt_preview=preview,
    )


# ==================== 知识库API ====================

@router.get(
    "/{agent_id}/knowledge/search",
    response_model=agent_schemas.KnowledgeSearchResponse,
)
def search_knowledge(
    agent_id: int,
    query: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    检索Agent知识库
    
    query: 查询文本（可以包含日期和关键词，如"昨天发生了什么"）
    """
    logger.info(f"[Agent路由] 检索知识库: agent_id={agent_id}, query={query}")
    
    agent = agent_service.get_agent_for_user(db=db, user=current_user, agent_id=agent_id)
    
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found"
        )
    
    from backend.app.agents.knowledge_index import (
        search_agent_knowledge,
        parse_date_query,
        extract_keywords,
    )
    
    # 解析日期和关键词
    dates = parse_date_query(query)
    keywords = extract_keywords(query)
    
    # 搜索知识库
    results = search_agent_knowledge(
        db=db,
        agent_id=agent_id,
        dates=dates if dates else None,
        keywords=keywords if keywords else None,
        limit=5,
    )
    
    # 转换为响应格式
    search_results = [
        agent_schemas.KnowledgeSearchResult(
            summary_date=result.summary_date,
            summary=result.summary_summary,
            topics=result.topics or [],
            message_count=result.message_count,
        )
        for result in results
    ]
    
    return agent_schemas.KnowledgeSearchResponse(
        results=search_results,
        total=len(search_results)
    )


@router.get(
    "/{agent_id}/knowledge",
    response_model=agent_schemas.AgentKnowledgeIndexResponse,
)
def get_agent_knowledge_index(
    agent_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    获取Agent的所有知识库索引
    """
    logger.info(f"[Agent路由] 获取知识库索引: agent_id={agent_id}")
    
    agent = agent_service.get_agent_for_user(db=db, user=current_user, agent_id=agent_id)
    
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found"
        )
    
    from backend.app.models.agent import AgentKnowledgeIndex
    indexes = (
        db.query(AgentKnowledgeIndex)
        .filter(AgentKnowledgeIndex.agent_id == agent_id)
        .order_by(AgentKnowledgeIndex.summary_date.desc())
        .all()
    )
    
    return agent_schemas.AgentKnowledgeIndexResponse(
        indexes=indexes,
        total=len(indexes)
    )


# ==================== 清空聊天并总结记忆API ====================

@router.post(
    "/{agent_id}/chat/clear-and-summarize",
    response_model=agent_schemas.ClearAndSummarizeResponse,
)
def clear_and_summarize_chat(
    agent_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    清空聊天并总结记忆
    """
    logger.info(f"[Agent路由] 清空聊天并总结记忆: agent_id={agent_id}")
    
    success, result = agent_service.clear_chat_and_summarize(
        db=db,
        user=current_user,
        agent_id=agent_id,
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result or "清空聊天并总结记忆失败"
        )
    
    return agent_schemas.ClearAndSummarizeResponse(
        success=True,
        summary=result,
    )

