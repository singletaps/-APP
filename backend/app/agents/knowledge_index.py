# backend/app/agents/knowledge_index.py
"""
Agent知识库索引服务

提供知识库检索功能：
- 根据日期查询
- 根据关键词查询
- 组合查询
"""

import logging
import re
from typing import List, Optional, Tuple
from datetime import date, timedelta

from sqlalchemy.orm import Session

from backend.app.models.agent import AgentKnowledgeIndex

logger = logging.getLogger(__name__)


def search_agent_knowledge(
    db: Session,
    agent_id: int,
    dates: Optional[List[date]] = None,
    keywords: Optional[List[str]] = None,
    limit: int = 5,
) -> List[AgentKnowledgeIndex]:
    """
    检索Agent知识库
    
    Args:
        db: 数据库会话
        agent_id: Agent ID
        dates: 日期列表（可选）
        keywords: 关键词列表（可选）
        limit: 返回结果数量限制
    
    Returns:
        知识库索引列表（按相关性排序）
    """
    logger.info(f"[知识库检索] 开始检索: agent_id={agent_id}, dates={dates}, keywords={keywords}")
    
    try:
        query = db.query(AgentKnowledgeIndex).filter(
            AgentKnowledgeIndex.agent_id == agent_id
        )
        
        # 日期过滤
        if dates:
            query = query.filter(AgentKnowledgeIndex.summary_date.in_(dates))
            logger.debug(f"[知识库检索] 应用日期过滤: {len(dates)} 个日期")
        
        # 执行查询
        results = query.order_by(AgentKnowledgeIndex.summary_date.desc()).all()
        
        logger.debug(f"[知识库检索] 找到 {len(results)} 条记录")
        
        # 如果有关键词，进行关键词匹配和排序
        if keywords and results:
            results = _filter_and_score_by_keywords(results, keywords)
            logger.debug(f"[知识库检索] 关键词过滤后: {len(results)} 条记录")
        
        # 限制返回数量
        results = results[:limit]
        
        logger.info(f"[知识库检索] ✅ 检索完成，返回 {len(results)} 条记录")
        
        return results
        
    except Exception as e:
        logger.error(f"[知识库检索] ❌ 检索失败: {e}", exc_info=True)
        return []


def parse_date_query(query: str) -> List[date]:
    """
    解析日期查询字符串
    
    支持：
    - "昨天"、"前天"
    - "上周"、"最近7天"、"最近30天"
    - 具体日期："2024-01-15"
    
    Args:
        query: 查询字符串
    
    Returns:
        日期列表
    """
    logger.debug(f"[知识库检索] 解析日期查询: {query}")
    
    today = date.today()
    dates = []
    query_lower = query.lower()
    
    try:
        # 简单日期关键词
        if "昨天" in query_lower or "yesterday" in query_lower:
            dates.append(today - timedelta(days=1))
        elif "前天" in query_lower:
            dates.append(today - timedelta(days=2))
        elif "今天" in query_lower or "today" in query_lower:
            dates.append(today)
        elif "上周" in query_lower or "last week" in query_lower:
            # 上周的所有日期
            last_week_start = today - timedelta(days=today.weekday() + 7)
            dates.extend([last_week_start + timedelta(days=i) for i in range(7)])
        elif "最近7天" in query_lower or "最近一周" in query_lower:
            dates.extend([today - timedelta(days=i) for i in range(7)])
        elif "最近30天" in query_lower or "最近一月" in query_lower:
            dates.extend([today - timedelta(days=i) for i in range(30)])
        
        # 提取具体日期 YYYY-MM-DD
        date_pattern = r'(\d{4})-(\d{1,2})-(\d{1,2})'
        matches = re.findall(date_pattern, query)
        for match in matches:
            try:
                parsed_date = date(int(match[0]), int(match[1]), int(match[2]))
                dates.append(parsed_date)
            except ValueError:
                pass
        
        # 去重并排序
        dates = sorted(list(set(dates)))
        
        logger.debug(f"[知识库检索] 解析到 {len(dates)} 个日期")
        
        return dates
        
    except Exception as e:
        logger.error(f"[知识库检索] 解析日期查询失败: {e}", exc_info=True)
        return []


def extract_keywords(query: str) -> List[str]:
    """
    从查询字符串中提取关键词
    
    Args:
        query: 查询字符串
    
    Returns:
        关键词列表
    """
    logger.debug(f"[知识库检索] 提取关键词: {query}")
    
    # 停用词列表
    stop_words = {
        "的", "了", "在", "是", "我", "你", "他", "她", "它",
        "我们", "你们", "他们", "这个", "那个", "什么", "怎么",
        "发生", "讨论", "聊天", "记得", "之前", "之前", "之前"
    }
    
    keywords = []
    
    # 简单分词（按空格和标点分割）
    words = re.split(r'[，。！？\s]+', query)
    
    for word in words:
        word = word.strip()
        # 过滤停用词和单字符
        if word and len(word) > 1 and word not in stop_words:
            keywords.append(word)
    
    logger.debug(f"[知识库检索] 提取到 {len(keywords)} 个关键词: {keywords}")
    
    return keywords


def _filter_and_score_by_keywords(
    results: List[AgentKnowledgeIndex],
    keywords: List[str],
) -> List[AgentKnowledgeIndex]:
    """
    根据关键词过滤和评分结果
    
    Args:
        results: 知识库索引列表
        keywords: 关键词列表
    
    Returns:
        过滤和排序后的列表
    """
    scored_results = []
    
    for index in results:
        score = calculate_match_score(index, keywords)
        if score > 0:
            scored_results.append((score, index))
    
    # 按分数排序（降序）
    scored_results.sort(key=lambda x: x[0], reverse=True)
    
    return [index for _, index in scored_results]


def calculate_match_score(
    index: AgentKnowledgeIndex,
    keywords: List[str],
) -> int:
    """
    计算匹配分数
    
    Args:
        index: 知识库索引
        keywords: 关键词列表
    
    Returns:
        匹配分数（0表示不匹配）
    """
    score = 0
    text_lower = index.summary_summary.lower()
    
    # 在总结内容中搜索关键词
    for keyword in keywords:
        keyword_lower = keyword.lower()
        if keyword_lower in text_lower:
            score += 1
    
    # 在topics中搜索（权重更高）
    if index.topics:
        for topic in index.topics:
            topic_str = str(topic).lower()
            for keyword in keywords:
                if keyword.lower() in topic_str:
                    score += 2  # topics匹配权重更高
    
    # 在keywords字段中搜索（权重最高）
    if index.keywords:
        for index_keyword in index.keywords:
            index_keyword_str = str(index_keyword).lower()
            for keyword in keywords:
                if keyword.lower() == index_keyword_str:
                    score += 3  # 精确匹配权重最高
    
    return score


def parse_date_from_keyword(date_keyword: str) -> List[date]:
    """
    将日期关键词转换为具体的日期列表
    
    Args:
        date_keyword: 日期关键词（如"yesterday", "last_week"等）
    
    Returns:
        日期列表
    """
    today = date.today()
    dates = []
    
    try:
        if date_keyword == "yesterday":
            dates.append(today - timedelta(days=1))
        elif date_keyword == "day_before_yesterday":
            dates.append(today - timedelta(days=2))
        elif date_keyword == "last_week":
            last_week_start = today - timedelta(days=today.weekday() + 7)
            dates.extend([last_week_start + timedelta(days=i) for i in range(7)])
        elif date_keyword == "last_7_days":
            dates.extend([today - timedelta(days=i) for i in range(7)])
        elif date_keyword == "last_30_days":
            dates.extend([today - timedelta(days=i) for i in range(30)])
        elif re.match(r'^\d{4}-\d{1,2}-\d{1,2}$', date_keyword):
            try:
                dates.append(date.fromisoformat(date_keyword))
            except ValueError:
                pass
        
        return dates
        
    except Exception as e:
        logger.error(f"[知识库检索] 解析日期关键词失败: {date_keyword}, 错误: {e}")
        return []


