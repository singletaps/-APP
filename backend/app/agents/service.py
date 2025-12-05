# backend/app/agents/service.py
"""
Agent服务层

提供Agent相关的业务逻辑：
- Agent创建和管理
- Agent会话管理
- Agent Prompt管理
- 批量消息处理（已实现）
"""

import logging
import uuid
import json
import re
import random
from typing import List, Optional, Tuple, Dict, Any
from datetime import datetime, date

from sqlalchemy.orm import Session

from backend.app.models.agent import (
    Agent,
    AgentChatSession,
    AgentChatMessage,
    AgentPromptHistory,
    AgentKnowledgeIndex,
)
from backend.app.models.user import User

logger = logging.getLogger(__name__)


# ==================== Agent管理 ====================

def create_agent(
    db: Session,
    user: User,
    name: str,
    initial_prompt: str,
) -> Agent:
    """
    创建Agent
    
    Args:
        db: 数据库会话
        user: 用户对象
        name: Agent名称
        initial_prompt: 初始prompt（创建后不可修改）
    
    Returns:
        创建的Agent对象
    """
    logger.info(f"[Agent服务] 开始创建Agent: 用户={user.username}, 名称={name}")
    
    try:
        # 创建Agent
        agent = Agent(
            user_id=user.id,
            name=name,
            initial_prompt=initial_prompt,
            current_prompt=initial_prompt,  # 初始时current_prompt等于initial_prompt
        )
        db.add(agent)
        db.flush()  # 先获取agent.id
        
        logger.info(f"[Agent服务] Agent创建成功: agent_id={agent.id}")
        
        # 创建Agent的单会话
        session = AgentChatSession(
            agent_id=agent.id,
            title=f"{name}的对话",
        )
        db.add(session)
        db.flush()
        
        logger.info(f"[Agent服务] Agent会话创建成功: session_id={session.id}")
        
        db.commit()
        db.refresh(agent)
        db.refresh(session)
        
        logger.info(f"[Agent服务] ✅ Agent创建完成: agent_id={agent.id}, session_id={session.id}")
        
        return agent
        
    except Exception as e:
        db.rollback()
        logger.error(f"[Agent服务] ❌ 创建Agent失败: {e}", exc_info=True)
        raise


def list_agents_for_user(
    db: Session,
    user: User,
    skip: int = 0,
    limit: int = 20,
) -> List[Agent]:
    """
    获取用户的所有Agent列表
    
    Args:
        db: 数据库会话
        user: 用户对象
        skip: 跳过数量
        limit: 限制数量
    
    Returns:
        Agent列表
    """
    logger.debug(f"[Agent服务] 查询用户Agent列表: user_id={user.id}, skip={skip}, limit={limit}")
    
    try:
        agents = (
            db.query(Agent)
            .filter(Agent.user_id == user.id)
            .order_by(Agent.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        
        logger.info(f"[Agent服务] ✅ 查询到 {len(agents)} 个Agent")
        
        return agents
        
    except Exception as e:
        logger.error(f"[Agent服务] ❌ 查询Agent列表失败: {e}", exc_info=True)
        raise


def get_agent_for_user(
    db: Session,
    user: User,
    agent_id: int,
) -> Optional[Agent]:
    """
    获取用户指定的Agent（验证归属）
    
    Args:
        db: 数据库会话
        user: 用户对象
        agent_id: Agent ID
    
    Returns:
        Agent对象，如果不存在或不属于该用户则返回None
    """
    logger.debug(f"[Agent服务] 查询Agent: user_id={user.id}, agent_id={agent_id}")
    
    try:
        agent = (
            db.query(Agent)
            .filter(
                Agent.id == agent_id,
                Agent.user_id == user.id,
            )
            .first()
        )
        
        if agent:
            logger.debug(f"[Agent服务] ✅ 找到Agent: agent_id={agent_id}")
        else:
            logger.warning(f"[Agent服务] ⚠️ 未找到Agent或不属于该用户: agent_id={agent_id}")
        
        return agent
        
    except Exception as e:
        logger.error(f"[Agent服务] ❌ 查询Agent失败: {e}", exc_info=True)
        raise


def update_agent_name(
    db: Session,
    user: User,
    agent_id: int,
    new_name: str,
) -> Optional[Agent]:
    """
    更新Agent名称（只能更新名称，不能更新initial_prompt）
    
    Args:
        db: 数据库会话
        user: 用户对象
        agent_id: Agent ID
        new_name: 新名称
    
    Returns:
        更新后的Agent对象，如果不存在或不属于该用户则返回None
    """
    logger.info(f"[Agent服务] 更新Agent名称: agent_id={agent_id}, new_name={new_name}")
    
    try:
        agent = get_agent_for_user(db, user, agent_id)
        if not agent:
            logger.warning(f"[Agent服务] ⚠️ Agent不存在: agent_id={agent_id}")
            return None
        
        agent.name = new_name
        db.commit()
        db.refresh(agent)
        
        logger.info(f"[Agent服务] ✅ Agent名称更新成功: agent_id={agent_id}")
        
        return agent
        
    except Exception as e:
        db.rollback()
        logger.error(f"[Agent服务] ❌ 更新Agent名称失败: {e}", exc_info=True)
        raise


def delete_agent(
    db: Session,
    user: User,
    agent_id: int,
) -> bool:
    """
    删除Agent（级联删除会话、消息、历史等）
    
    Args:
        db: 数据库会话
        user: 用户对象
        agent_id: Agent ID
    
    Returns:
        True如果删除成功，False如果Agent不存在或不属于该用户
    """
    logger.info(f"[Agent服务] 删除Agent: agent_id={agent_id}")
    
    try:
        agent = get_agent_for_user(db, user, agent_id)
        if not agent:
            logger.warning(f"[Agent服务] ⚠️ Agent不存在: agent_id={agent_id}")
            return False
        
        db.delete(agent)
        db.commit()
        
        logger.info(f"[Agent服务] ✅ Agent删除成功: agent_id={agent_id}")
        
        return True
        
    except Exception as e:
        db.rollback()
        logger.error(f"[Agent服务] ❌ 删除Agent失败: {e}", exc_info=True)
        raise


# ==================== Agent会话管理 ====================

def get_or_create_agent_session(
    db: Session,
    agent_id: int,
) -> AgentChatSession:
    """
    获取或创建Agent会话（单会话模式）
    
    Args:
        db: 数据库会话
        agent_id: Agent ID
    
    Returns:
        AgentChatSession对象
    """
    logger.debug(f"[Agent服务] 获取Agent会话: agent_id={agent_id}")
    
    try:
        # 查找会话
        session = (
            db.query(AgentChatSession)
            .filter(AgentChatSession.agent_id == agent_id)
            .first()
        )
        
        if session:
            logger.debug(f"[Agent服务] ✅ 找到现有会话: session_id={session.id}")
            return session
        
        # 如果没有会话，创建新会话
        logger.info(f"[Agent服务] 创建新会话: agent_id={agent_id}")
        session = AgentChatSession(agent_id=agent_id)
        db.add(session)
        db.commit()
        db.refresh(session)
        
        logger.info(f"[Agent服务] ✅ 会话创建成功: session_id={session.id}")
        
        return session
        
    except Exception as e:
        db.rollback()
        logger.error(f"[Agent服务] ❌ 获取/创建会话失败: {e}", exc_info=True)
        raise


def get_agent_session_messages(
    db: Session,
    session_id: int,
    limit: Optional[int] = None,
) -> List[AgentChatMessage]:
    """
    获取Agent会话的消息列表
    
    Args:
        db: 数据库会话
        session_id: 会话ID
        limit: 限制数量（可选）
    
    Returns:
        消息列表
    """
    logger.debug(f"[Agent服务] 查询会话消息: session_id={session_id}, limit={limit}")
    
    try:
        query = (
            db.query(AgentChatMessage)
            .filter(AgentChatMessage.session_id == session_id)
            .order_by(AgentChatMessage.created_at.asc())
        )
        
        if limit:
            query = query.limit(limit)
        
        messages = query.all()
        
        logger.debug(f"[Agent服务] ✅ 查询到 {len(messages)} 条消息")
        
        return messages
        
    except Exception as e:
        logger.error(f"[Agent服务] ❌ 查询消息失败: {e}", exc_info=True)
        raise


# ==================== Agent Prompt管理 ====================

def calculate_current_prompt(
    db: Session,
    agent: Agent,
) -> str:
    """
    计算Agent的当前prompt（动态计算）
    
    格式：initial_prompt + 所有未删除的总结（按时间顺序）
    
    Args:
        db: 数据库会话
        agent: Agent对象
    
    Returns:
        完整的current_prompt字符串
    """
    logger.debug(f"[Agent服务] 计算Agent当前prompt: agent_id={agent.id}")
    
    try:
        prompt_parts = [agent.initial_prompt]
        
        # 获取所有prompt历史（按时间顺序，硬删除后记录就不存在了）
        prompt_histories = (
            db.query(AgentPromptHistory)
            .filter(AgentPromptHistory.agent_id == agent.id)
            .order_by(AgentPromptHistory.created_at.asc())
            .all()
        )
        
        for history in prompt_histories:
            prompt_parts.append(history.added_prompt)
        
        current_prompt = "\n\n".join(prompt_parts)
        
        logger.debug(f"[Agent服务] ✅ Prompt计算完成: 初始prompt长度={len(agent.initial_prompt)}, 总结数量={len(prompt_histories)}, 总长度={len(current_prompt)}")
        
        return current_prompt
        
    except Exception as e:
        logger.error(f"[Agent服务] ❌ 计算prompt失败: {e}", exc_info=True)
        raise


def delete_latest_prompt_summary(
    db: Session,
    user: User,
    agent_id: int,
) -> Tuple[bool, Optional[date], int, Optional[str]]:
    """
    删除最新的prompt总结（只能删除最后一条）
    
    Args:
        db: 数据库会话
        user: 用户对象
        agent_id: Agent ID
    
    Returns:
        (success, deleted_summary_date, remaining_count, current_prompt_preview)
    """
    logger.info(f"[Agent服务] 删除最新prompt总结: agent_id={agent_id}")
    
    try:
        # 验证Agent归属
        agent = get_agent_for_user(db, user, agent_id)
        if not agent:
            logger.warning(f"[Agent服务] ⚠️ Agent不存在: agent_id={agent_id}")
            return False, None, 0, None
        
        # 查找最新的prompt历史
        latest_history = (
            db.query(AgentPromptHistory)
            .filter(AgentPromptHistory.agent_id == agent.id)
            .order_by(AgentPromptHistory.created_at.desc())
            .first()
        )
        
        if not latest_history:
            logger.warning(f"[Agent服务] ⚠️ 没有可删除的总结: agent_id={agent_id}")
            return False, None, 0, None
        
        # 记录要删除的日期
        deleted_date = latest_history.summary_date
        
        # 删除对应的知识库索引（如果有）
        if latest_history.knowledge_index:
            db.delete(latest_history.knowledge_index)
            logger.debug(f"[Agent服务] 删除对应的知识库索引")
        
        # 删除prompt历史（硬删除）
        db.delete(latest_history)
        
        # 重新计算current_prompt
        agent.current_prompt = calculate_current_prompt(db, agent)
        
        # 统计剩余数量
        remaining_count = (
            db.query(AgentPromptHistory)
            .filter(AgentPromptHistory.agent_id == agent.id)
            .count()
        )
        
        db.commit()
        
        # 生成preview（前100字符）
        preview = agent.current_prompt[:100] + "..." if len(agent.current_prompt) > 100 else agent.current_prompt
        
        logger.info(f"[Agent服务] ✅ Prompt总结删除成功: 删除日期={deleted_date}, 剩余数量={remaining_count}")
        
        return True, deleted_date, remaining_count, preview
        
    except Exception as e:
        db.rollback()
        logger.error(f"[Agent服务] ❌ 删除prompt总结失败: {e}", exc_info=True)
        raise


# ==================== 批量消息处理 ====================

# 延迟配置常量
DELAY_CONFIG = {
    "first_reply": 0,  # 第一条回复延迟（秒）
    "min_delay": 1,    # 后续回复最小延迟（秒）
    "max_delay": 5,    # 后续回复最大延迟（秒）
    "long_reply_threshold": 200,  # 长回复阈值（字符数）
    "long_reply_extra_delay": 2   # 长回复额外延迟（秒）
}


def normalize_delay(delay: int) -> int:
    """标准化延迟时间（0-10秒范围）"""
    MIN_DELAY = 0
    MAX_DELAY = 10
    
    if delay < MIN_DELAY:
        return MIN_DELAY
    if delay > MAX_DELAY:
        return MAX_DELAY
    return delay


def calculate_reply_delay(reply_index: int, reply_length: int) -> int:
    """
    计算回复延迟
    
    Args:
        reply_index: 回复索引（0表示第一条）
        reply_length: 回复长度（字符数）
    
    Returns:
        延迟秒数
    """
    if reply_index == 0:
        return DELAY_CONFIG["first_reply"]
    
    # 基础延迟
    delay = random.randint(
        DELAY_CONFIG["min_delay"],
        DELAY_CONFIG["max_delay"]
    )
    
    # 长回复额外延迟
    if reply_length > DELAY_CONFIG["long_reply_threshold"]:
        delay += DELAY_CONFIG["long_reply_extra_delay"]
    
    return normalize_delay(delay)


def clean_markdown_code_block(text: str) -> str:
    """清理Markdown代码块标记"""
    text = re.sub(r'```json\s*', '', text)
    text = re.sub(r'```\s*', '', text)
    return text.strip()


def parse_nested_json(json_string: str) -> Dict[str, Any]:
    """
    解析嵌套的JSON字符串
    
    支持：
    1. 标准JSON：{"replies": [...]}
    2. Markdown代码块包裹：```json {...} ```
    3. 嵌套JSON字符串：{"replies": ["{\"content\": \"...\"}"]}
    """
    logger.debug(f"[JSON解析] 开始解析JSON: 长度={len(json_string)}")
    
    # 清理Markdown代码块
    json_string = clean_markdown_code_block(json_string)
    
    # 尝试直接解析
    try:
        data = json.loads(json_string)
        return parse_nested_replies(data)
    except json.JSONDecodeError:
        pass
    
    # 尝试提取JSON部分
    json_match = re.search(r'\{.*\}', json_string, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group())
            return parse_nested_replies(data)
        except json.JSONDecodeError:
            pass
    
    logger.warning(f"[JSON解析] 无法解析JSON，返回空结构")
    return {"replies": []}


def parse_nested_replies(data: Dict) -> Dict:
    """
    递归解析嵌套的JSON字符串
    """
    if "replies" in data:
        parsed_replies = []
        for reply in data["replies"]:
            if isinstance(reply, str):
                # 可能是JSON字符串
                try:
                    reply = json.loads(reply)
                except json.JSONDecodeError:
                    # 不是JSON，作为普通字符串处理
                    reply = {"content": reply, "send_delay_seconds": 0}
            
            # 递归处理嵌套结构
            if isinstance(reply, dict):
                reply = parse_nested_replies(reply)
            
            parsed_replies.append(reply)
        
        data["replies"] = parsed_replies
    
    return data


def safe_parse_agent_reply(raw_response: str) -> List[Dict[str, Any]]:
    """
    安全解析Agent回复，包含降级策略
    
    Args:
        raw_response: 原始响应文本
    
    Returns:
        回复列表，每个元素包含content和send_delay_seconds
    """
    logger.info(f"[JSON解析] 开始解析Agent回复: 长度={len(raw_response)}")
    
    try:
        # 尝试解析嵌套JSON
        data = parse_nested_json(raw_response)
        replies = data.get("replies", [])
        
        if replies:
            normalized_replies = normalize_replies(replies)
            logger.info(f"[JSON解析] ✅ 解析成功，共 {len(normalized_replies)} 条回复")
            return normalized_replies
    except Exception as e:
        logger.error(f"[JSON解析] JSON解析失败: {e}", exc_info=True)
    
    # 降级：返回单条消息
    logger.warning(f"[JSON解析] 降级为单条消息")
    return [{
        "content": raw_response,
        "send_delay_seconds": 0
    }]


def normalize_replies(replies: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    标准化回复格式
    
    Args:
        replies: 原始回复列表
    
    Returns:
        标准化后的回复列表
    """
    normalized = []
    
    for idx, reply in enumerate(replies):
        if isinstance(reply, dict):
            content = reply.get("content", "")
            delay = reply.get("send_delay_seconds", 0)
            
            # 标准化延迟
            if delay == 0 and idx > 0:
                # 如果没有指定延迟，自动计算
                delay = calculate_reply_delay(idx, len(content))
            else:
                delay = normalize_delay(delay)
            
            normalized.append({
                "content": content,
                "send_delay_seconds": delay
            })
        elif isinstance(reply, str):
            # 如果是字符串，转换为字典
            delay = calculate_reply_delay(idx, len(reply))
            normalized.append({
                "content": reply,
                "send_delay_seconds": delay
            })
    
    return normalized


# ==================== 批量消息处理核心逻辑 ====================

def validate_batch_messages(messages: List[str]) -> Tuple[bool, Optional[str]]:
    """
    验证批量消息
    
    Args:
        messages: 消息列表
    
    Returns:
        (是否有效, 错误信息)
    """
    MAX_MESSAGE_COUNT = 20
    MAX_MESSAGE_LENGTH = 5000
    
    if not messages:
        return False, "消息列表不能为空"
    
    if len(messages) > MAX_MESSAGE_COUNT:
        return False, f"单次最多发送{MAX_MESSAGE_COUNT}条消息"
    
    # 过滤空消息
    filtered_messages = [msg.strip() for msg in messages if msg.strip()]
    if not filtered_messages:
        return False, "所有消息都为空"
    
    # 检查消息长度
    for idx, msg in enumerate(filtered_messages):
        if len(msg) > MAX_MESSAGE_LENGTH:
            return False, f"第{idx+1}条消息长度超过{MAX_MESSAGE_LENGTH}字符"
    
    return True, None


def get_today_messages(
    db: Session,
    session_id: int,
) -> List[AgentChatMessage]:
    """
    获取当天的聊天消息（用于构建上下文）
    
    Args:
        db: 数据库会话
        session_id: 会话ID
    
    Returns:
        当天的消息列表
    """
    from datetime import date as date_type
    
    today = date_type.today()
    
    messages = (
        db.query(AgentChatMessage)
        .filter(AgentChatMessage.session_id == session_id)
        .order_by(AgentChatMessage.created_at.asc())
        .all()
    )
    
    # 过滤出当天的消息
    today_messages = [
        msg for msg in messages
        if msg.created_at.date() == today
    ]
    
    logger.debug(f"[Agent服务] 获取当天消息: session_id={session_id}, 总数={len(messages)}, 当天={len(today_messages)}")
    
    return today_messages


def query_knowledge_base_by_params(
    db: Session,
    agent_id: int,
    query_params: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    根据意图识别的参数查询知识库
    
    Args:
        db: 数据库会话
        agent_id: Agent ID
        query_params: 查询参数（从意图识别结果中获取）
    
    Returns:
        知识库结果列表
    """
    from backend.app.agents.knowledge_index import (
        search_agent_knowledge,
        parse_date_from_keyword,
    )
    
    dates = None
    keywords = None
    
    # 解析日期
    date_value = query_params.get("date")
    if date_value:
        dates = parse_date_from_keyword(date_value)
        logger.debug(f"[Agent服务] 解析日期关键词: {date_value} -> {dates}")
    
    # 获取关键词
    keywords = query_params.get("keywords", [])
    
    # 查询知识库
    results = search_agent_knowledge(
        db=db,
        agent_id=agent_id,
        dates=dates,
        keywords=keywords if keywords else None,
        limit=5,  # 最多返回5条
    )
    
    # 转换为字典格式
    knowledge_context = [
        {
            "summary_date": str(result.summary_date),
            "summary_summary": result.summary_summary,
            "topics": result.topics or [],
            "key_points": result.key_points or [],
        }
        for result in results
    ]
    
    logger.info(f"[Agent服务] 知识库查询完成: agent_id={agent_id}, 找到 {len(knowledge_context)} 条记录")
    
    return knowledge_context


def build_agent_prompt(
    agent: Agent,
    knowledge_context: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """
    构建Agent的增强prompt
    
    格式：
    {Agent的current_prompt}
    
    [回复格式要求]
    ...
    
    [相关历史记忆]
    ...（如果查询了知识库）
    
    Args:
        agent: Agent对象
        knowledge_context: 知识库上下文（可选）
    
    Returns:
        完整的prompt字符串
    """
    logger.debug(f"[Agent服务] 构建Agent prompt: agent_id={agent.id}")
    
    prompt_parts = []
    
    # 1. Agent的基础prompt（当前prompt，包含初始prompt和累积总结）
    prompt_parts.append(agent.current_prompt)
    
    # 2. 回复格式要求
    format_prompt = """请按照以下JSON格式返回你的回复：
{
    "replies": [
        {
            "content": "回复内容",
            "send_delay_seconds": 0
        }
    ]
}

注意：
- 回复要自然，就像真人聊天一样，根据你的人设特点来决定回复风格
- 回复数量应该根据你的人设和对话情境来决定：
  * 如果人设是高冷、话少的，可以多问一答（用户问很多句，你可能只回复一句简短的话）
  * 如果人设是热情、话多的，可以一问多答（用户问一句，你可以回复多句话）
  * 如果人设是理性、条理清晰的，可以根据话题数量来回复
- 延迟要合理，模拟真实的打字和思考时间（0-10秒之间）
- 第一条回复的延迟应该是0秒
- 最重要的是：回复要符合你的人设特点，自然地回应"""
    
    prompt_parts.append(format_prompt)
    
    # 3. 知识库上下文（如果查询了）
    if knowledge_context:
        prompt_parts.append("[相关历史记忆]")
        for knowledge in knowledge_context:
            prompt_parts.append(f"日期: {knowledge['summary_date']}")
            prompt_parts.append(f"内容: {knowledge['summary_summary']}")
            if knowledge.get('topics'):
                prompt_parts.append(f"话题: {', '.join(knowledge['topics'])}")
    
    full_prompt = "\n\n".join(prompt_parts)
    
    logger.debug(f"[Agent服务] ✅ Prompt构建完成: 总长度={len(full_prompt)} 字符")
    
    return full_prompt


def send_batch_messages_to_agent(
    db: Session,
    user: User,
    agent_id: int,
    user_messages: List[str],
) -> Tuple[str, List[Dict[str, Any]]]:
    """
    批量发送消息到Agent（核心函数）
    
    完整流程：
    1. 验证Agent归属
    2. 验证消息
    3. 保存用户消息
    4. 意图识别
    5. 知识库查询（如果需要）
    6. 构建增强prompt
    7. 调用大模型
    8. 解析JSON回复
    9. 保存AI回复
    10. 返回回复列表
    
    Args:
        db: 数据库会话
        user: 用户对象
        agent_id: Agent ID
        user_messages: 用户消息列表
    
    Returns:
        (batch_id, 回复列表)
        回复列表格式: [{"content": "...", "send_delay_seconds": 0}, ...]
    """
    logger.info(f"[Agent服务] ========== 开始批量消息处理 ==========")
    logger.info(f"[Agent服务] agent_id={agent_id}, 消息数量={len(user_messages)}")
    
    try:
        # 1. 验证Agent归属
        agent = get_agent_for_user(db, user, agent_id)
        if not agent:
            raise ValueError("Agent not found or does not belong to user")
        
        # 1.5. 确保使用最新的current_prompt（动态计算）
        agent.current_prompt = calculate_current_prompt(db, agent)
        logger.debug(f"[Agent服务] 使用最新prompt: 长度={len(agent.current_prompt)} 字符")
        
        # 2. 验证消息
        is_valid, error_msg = validate_batch_messages(user_messages)
        if not is_valid:
            raise ValueError(error_msg)
        
        # 过滤空消息
        filtered_messages = [msg.strip() for msg in user_messages if msg.strip()]
        
        # 3. 获取或创建会话
        session = get_or_create_agent_session(db, agent_id)
        
        # 4. 生成批次ID
        batch_id = str(uuid.uuid4())
        logger.info(f"[Agent服务] 批次ID: {batch_id}")
        
        # 5. 保存用户消息
        for idx, msg_content in enumerate(filtered_messages):
            user_msg = AgentChatMessage(
                session_id=session.id,
                role="user",
                content=msg_content,
                batch_id=batch_id,
                batch_index=idx,
            )
            db.add(user_msg)
        
        db.flush()
        logger.info(f"[Agent服务] ✅ 用户消息已保存: {len(filtered_messages)} 条")
        
        # 6. 合并所有用户消息（用于意图识别）
        combined_message = " ".join(filtered_messages)
        
        # 7. 意图识别
        from backend.app.agents.intent_detector import (
            detect_agent_intent,
            AgentIntentType,
        )
        
        intent_result = detect_agent_intent(combined_message)
        intent = intent_result["intent"]
        
        logger.info(f"[Agent服务] 意图识别结果: {intent}, 置信度: {intent_result.get('confidence', 0)}")
        
        # 8. 查询知识库（如果需要）
        knowledge_context = None
        if intent == AgentIntentType.KNOWLEDGE_QUERY:
            query_params = intent_result.get("query_params", {})
            if query_params:
                knowledge_context = query_knowledge_base_by_params(
                    db=db,
                    agent_id=agent_id,
                    query_params=query_params,
                )
                logger.info(f"[Agent服务] 知识库查询完成: 找到 {len(knowledge_context) if knowledge_context else 0} 条记录")
        
        # 9. 构建增强prompt
        enhanced_prompt = build_agent_prompt(
            agent=agent,
            knowledge_context=knowledge_context,
        )
        
        # 11. 构建消息列表
        messages = [
            {"role": "system", "content": enhanced_prompt}
        ]
        
        # 添加历史消息（除了当前这批）
        history_messages = get_agent_session_messages(db, session.id)
        for hist_msg in history_messages:
            # 排除当前批次的消息
            if hist_msg.batch_id != batch_id:
                messages.append({
                    "role": hist_msg.role,
                    "content": hist_msg.content,
                })
        
        # 添加当前多条用户消息
        for user_msg in filtered_messages:
            messages.append({
                "role": "user",
                "content": user_msg,
            })
        
        # 12. 调用大模型API（非流式）
        logger.info(f"[Agent服务] 开始调用大模型API: 消息总数={len(messages)}")
        
        from backend.app.ai.service import ask_with_messages
        
        raw_response = ask_with_messages(
            messages=messages,
            model="doubao-seed-1-6-251015",
            thinking="disabled",  # Agent不使用深度思考
        )
        
        logger.info(f"[Agent服务] ✅ 大模型API调用完成: 响应长度={len(raw_response)}")
        
        # 13. 解析JSON回复
        ai_replies = safe_parse_agent_reply(raw_response)
        
        logger.info(f"[Agent服务] JSON解析完成: 回复数量={len(ai_replies)}")
        
        # 14. 保存AI回复到数据库
        for idx, reply in enumerate(ai_replies):
            ai_msg = AgentChatMessage(
                session_id=session.id,
                role="assistant",
                content=reply["content"],
                batch_id=batch_id,
                batch_index=idx,
                send_delay_seconds=reply["send_delay_seconds"],
            )
            db.add(ai_msg)
        
        # 15. 更新会话的updated_at
        from sqlalchemy import func
        session.updated_at = func.now()
        
        db.commit()
        
        logger.info(f"[Agent服务] ✅ 批量消息处理完成: batch_id={batch_id}, 回复数量={len(ai_replies)}")
        
        return batch_id, ai_replies
        
    except Exception as e:
        db.rollback()
        logger.error(f"[Agent服务] ❌ 批量消息处理失败: {e}", exc_info=True)
        raise


# ==================== 清空聊天并总结记忆 ====================

def clear_chat_and_summarize(
    db: Session,
    user: User,
    agent_id: int,
) -> Tuple[bool, Optional[str]]:
    """
    清空聊天并总结记忆
    
    流程：
    1. 验证Agent归属
    2. 获取当前会话的所有消息
    3. 如果有消息，使用thinking进行深度思考总结
    4. 创建prompt历史记录
    5. 创建知识库索引（提取topics、key_points、keywords）
    6. 清空会话消息
    7. 更新agent的current_prompt
    
    Args:
        db: 数据库会话
        user: 用户对象
        agent_id: Agent ID
    
    Returns:
        (success, summary_text or error_message)
    """
    logger.info(f"[Agent服务] ========== 开始清空聊天并总结记忆 ==========")
    logger.info(f"[Agent服务] agent_id={agent_id}")
    
    try:
        # 1. 验证Agent归属
        agent = get_agent_for_user(db, user, agent_id)
        if not agent:
            logger.warning(f"[Agent服务] ⚠️ Agent不存在: agent_id={agent_id}")
            return False, "Agent not found"
        
        # 2. 获取或创建会话
        session = get_or_create_agent_session(db, agent_id)
        
        # 3. 获取所有消息
        all_messages = get_agent_session_messages(db, session.id)
        
        if not all_messages:
            logger.info(f"[Agent服务] ✅ 会话中没有消息，无需总结")
            return True, None
        
        # 4. 统计消息信息
        user_messages = [msg for msg in all_messages if msg.role == "user"]
        assistant_messages = [msg for msg in all_messages if msg.role == "assistant"]
        message_count = len(all_messages)
        user_message_count = len(user_messages)
        
        logger.info(f"[Agent服务] 消息统计: 总数={message_count}, 用户={user_message_count}, AI={len(assistant_messages)}")
        
        # 5. 构建总结prompt（以agent为主体，体现成长）
        summary_date = date.today()
        summary_prompt = f"""你是一个观察者和总结者，需要从Agent（{agent.name}）的角度，高度概括今天的对话经历，并将这些经历转化为Agent的成长记忆。

Agent的初始设定：{agent.initial_prompt}

今天（{summary_date}）的对话记录：
"""
        
        # 添加对话记录
        for msg in all_messages:
            role_name = "用户" if msg.role == "user" else "Agent"
            summary_prompt += f"\n{role_name}：{msg.content}\n"
        
        summary_prompt += f"""

请从Agent的角度，进行深度思考并生成总结。要求：

1. **高度概括**：用最简洁的语言（2-5句话）总结今天的对话核心内容
2. **Agent为主体**：总结要以"我"（Agent）的第一人称视角，描述"我"经历了什么
3. **体现成长**：简要描述这些对话对Agent的影响或改变
4. **简短精炼**：总结要尽可能简短，几句话概括即可，不要冗长

请返回JSON格式：
{{
    "summary": "总结内容（50-150字，2-5句话，高度概括，以Agent为主体）",
    "topics": ["话题1", "话题2", ...],
    "key_points": ["关键点1", "关键点2", ...],
    "keywords": ["关键词1", "关键词2", ...],
    "impact": "这段经历对Agent的影响（1-2句话，20-50字）"
}}

注意：
- summary应该以Agent的第一人称视角，用2-5句话简洁描述"我"今天经历了什么，学到了什么
- impact应该用1-2句话简洁描述这些经历如何影响了Agent
- 总结要简短精炼，不要冗长，几句话概括即可
- topics、key_points、keywords用于后续检索，请提取最重要的内容"""
        
        # 6. 使用thinking进行深度思考总结
        logger.info(f"[Agent服务] 开始使用深度思考总结对话...")
        
        from backend.app.ai.service import ask_with_messages
        
        summary_messages = [
            {"role": "system", "content": "你是一个专业的观察者和总结者，擅长从Agent的角度总结对话经历，并转化为Agent的成长记忆。"},
            {"role": "user", "content": summary_prompt}
        ]
        
        raw_summary = ask_with_messages(
            messages=summary_messages,
            model="doubao-seed-1-6-251015",
            thinking="enabled",  # 使用深度思考
        )
        
        logger.info(f"[Agent服务] ✅ 总结生成完成: 长度={len(raw_summary)} 字符")
        
        # 7. 解析总结JSON
        try:
            # 清理Markdown代码块
            summary_text = clean_markdown_code_block(raw_summary)
            
            # 尝试提取JSON
            json_match = re.search(r'\{.*\}', summary_text, re.DOTALL)
            if json_match:
                summary_data = json.loads(json_match.group())
            else:
                summary_data = json.loads(summary_text)
            
            summary_content = summary_data.get("summary", "")
            topics = summary_data.get("topics", [])
            key_points = summary_data.get("key_points", [])
            keywords = summary_data.get("keywords", [])
            impact = summary_data.get("impact", "")
            
            # 合并summary和impact作为added_prompt（尽可能简短）
            if impact and impact.strip():
                # 如果impact不为空，简洁地合并
                added_prompt = f"{summary_content} 这段经历让我：{impact}"
            else:
                added_prompt = summary_content
            
            logger.info(f"[Agent服务] ✅ 总结解析成功: topics={len(topics)}, key_points={len(key_points)}, keywords={len(keywords)}")
            
        except Exception as e:
            logger.warning(f"[Agent服务] ⚠️ JSON解析失败，使用原始文本: {e}")
            # 降级：使用原始文本作为总结
            added_prompt = raw_summary
            summary_content = raw_summary
            topics = []
            key_points = []
            keywords = []
        
        # 8. 获取当前prompt（用于记录）
        current_prompt_before = calculate_current_prompt(db, agent)
        
        # 9. 创建prompt历史记录
        prompt_history = AgentPromptHistory(
            agent_id=agent.id,
            added_prompt=added_prompt,
            full_prompt_before=current_prompt_before,
            full_prompt_after=current_prompt_before + "\n\n" + added_prompt,
            summary_date=summary_date,
        )
        db.add(prompt_history)
        db.flush()  # 获取ID
        
        logger.info(f"[Agent服务] ✅ Prompt历史记录已创建: history_id={prompt_history.id}")
        
        # 10. 创建知识库索引
        knowledge_index = AgentKnowledgeIndex(
            agent_id=agent.id,
            prompt_history_id=prompt_history.id,
            summary_date=summary_date,
            summary_summary=summary_content,
            topics=topics if topics else None,
            key_points=key_points if key_points else None,
            keywords=keywords if keywords else None,
            message_count=message_count,
            user_message_count=user_message_count,
        )
        db.add(knowledge_index)
        
        logger.info(f"[Agent服务] ✅ 知识库索引已创建: index_id={knowledge_index.id}")
        
        # 11. 清空会话消息
        for msg in all_messages:
            db.delete(msg)
        
        logger.info(f"[Agent服务] ✅ 已清空 {len(all_messages)} 条消息")
        
        # 12. 更新agent的current_prompt
        agent.current_prompt = calculate_current_prompt(db, agent)
        
        # 13. 更新agent的last_summarized_at
        from sqlalchemy import func
        agent.last_summarized_at = func.now()
        
        db.commit()
        
        logger.info(f"[Agent服务] ✅ 清空聊天并总结记忆完成")
        logger.info(f"[Agent服务] 总结预览: {summary_content[:100]}...")
        
        return True, summary_content
        
    except Exception as e:
        db.rollback()
        logger.error(f"[Agent服务] ❌ 清空聊天并总结记忆失败: {e}", exc_info=True)
        return False, str(e)
