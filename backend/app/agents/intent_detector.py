# backend/app/agents/intent_detector.py
"""
Agent意图识别模块

专门用于Agent聊天场景的意图识别
- NORMAL_CHAT: 普通对话
- KNOWLEDGE_QUERY: 知识库查询
"""

import json
import re
import logging
from typing import Dict, Any, Optional

from backend.app.ai.client import client

logger = logging.getLogger(__name__)


class AgentIntentType:
    """Agent意图类型"""
    NORMAL_CHAT = "NORMAL_CHAT"
    KNOWLEDGE_QUERY = "KNOWLEDGE_QUERY"


AGENT_INTENT_SYSTEM_PROMPT = """你是一个意图识别助手，专门分析用户在Agent对话中的意图。

可能的意图类型：
1. NORMAL_CHAT - 普通对话，Agent正常回复即可
2. KNOWLEDGE_QUERY - 查询Agent的历史记忆/知识库，包括：
   - 询问过去发生的事情（如："昨天发生了什么"、"上周我们讨论了什么"）
   - 询问历史对话内容（如："之前聊过什么"、"还记得我们说过..."）
   - 询问特定日期的事情（如："2024-01-15那天"）
   - 任何涉及查询Agent记忆的请求

请只返回JSON格式，格式如下：
{
    "intent": "NORMAL_CHAT" | "KNOWLEDGE_QUERY",
    "confidence": 0.0-1.0,
    "query_params": {
        "date": "yesterday" | "last_week" | "2024-01-15" | null,
        "keywords": ["关键词1", "关键词2"],
        "date_range": {
            "from": "2024-01-01",
            "to": "2024-01-15"
        }
    },
    "reason": "简要说明判断理由"
}

只返回JSON，不要其他内容。"""


def detect_agent_intent(
    user_message: str,
    agent_context: Optional[Dict] = None,
    model: str = "doubao-seed-1-6-lite-251015",
    max_tokens: int = 300,
    temperature: float = 0.1
) -> Dict[str, Any]:
    """
    检测Agent聊天中的用户意图
    
    Args:
        user_message: 用户消息
        agent_context: Agent上下文信息（可选，未来可以用于更精确的意图识别）
        model: 意图识别模型
        max_tokens: 最大token数
        temperature: 温度参数
    
    Returns:
        Dict包含:
            - intent: 意图类型
            - confidence: 置信度
            - query_params: 查询参数（如果是KNOWLEDGE_QUERY）
            - reason: 判断理由
            - raw_response: 原始响应
    """
    logger.info(f"[Agent意图识别] 开始识别: {user_message[:50]}...")
    
    try:
        messages = [
            {"role": "system", "content": AGENT_INTENT_SYSTEM_PROMPT},
            {"role": "user", "content": user_message}
        ]
        
        completion = client.chat.completions.create(
            model=model,
            messages=messages,
            thinking={"type": "disabled"},  # 关闭深度思考，快速响应
            max_tokens=max_tokens,
            temperature=temperature,
        )
        
        response_text = completion.choices[0].message.content.strip()
        logger.debug(f"[Agent意图识别] 模型原始响应: {response_text}")
        
        # 解析JSON响应
        intent_result = parse_intent_json(response_text)
        
        logger.info(f"[Agent意图识别] ✅ 识别结果: {intent_result['intent']}, 置信度: {intent_result.get('confidence', 0)}")
        
        return intent_result
        
    except Exception as e:
        logger.error(f"[Agent意图识别] ❌ 识别失败: {e}", exc_info=True)
        # 失败时降级为普通对话
        return {
            "intent": AgentIntentType.NORMAL_CHAT,
            "confidence": 0.0,
            "query_params": None,
            "reason": f"识别失败，降级为普通对话: {str(e)}",
            "raw_response": None
        }


def parse_intent_json(response_text: str) -> Dict[str, Any]:
    """
    解析意图识别的JSON响应
    """
    # 提取JSON部分（可能包含markdown代码块）
    if "```json" in response_text:
        json_start = response_text.find("```json") + 7
        json_end = response_text.find("```", json_start)
        response_text = response_text[json_start:json_end].strip()
    elif "```" in response_text:
        json_start = response_text.find("```") + 3
        json_end = response_text.find("```", json_start)
        response_text = response_text[json_start:json_end].strip()
    
    try:
        intent_result = json.loads(response_text)
        
        # 验证和标准化
        intent = intent_result.get("intent", AgentIntentType.NORMAL_CHAT)
        confidence = float(intent_result.get("confidence", 0.0))
        query_params = intent_result.get("query_params") if intent == AgentIntentType.KNOWLEDGE_QUERY else None
        reason = intent_result.get("reason", "")
        
        return {
            "intent": intent,
            "confidence": confidence,
            "query_params": query_params,
            "reason": reason,
            "raw_response": response_text
        }
        
    except json.JSONDecodeError as e:
        logger.warning(f"[Agent意图识别] JSON解析失败，尝试关键词匹配: {e}")
        
        # 降级：关键词匹配
        return fallback_keyword_match(response_text)


def fallback_keyword_match(response_text: str) -> Dict[str, Any]:
    """
    降级策略：关键词匹配
    """
    text_lower = response_text.lower()
    
    # 检查是否是知识库查询
    knowledge_keywords = [
        "昨天", "前天", "上周", "之前", "以前", "过去",
        "发生了什么", "讨论了什么", "聊了什么", "记得",
        "查询", "查找", "搜索"
    ]
    
    has_knowledge_keyword = any(keyword in text_lower for keyword in knowledge_keywords)
    
    if has_knowledge_keyword:
        return {
            "intent": AgentIntentType.KNOWLEDGE_QUERY,
            "confidence": 0.6,  # 较低置信度
            "query_params": {
                "date": extract_date_keyword(text_lower),
                "keywords": []
            },
            "reason": "关键词匹配",
            "raw_response": response_text
        }
    else:
        return {
            "intent": AgentIntentType.NORMAL_CHAT,
            "confidence": 0.5,
            "query_params": None,
            "reason": "关键词匹配（普通对话）",
            "raw_response": response_text
        }


def extract_date_keyword(text: str) -> Optional[str]:
    """
    从文本中提取日期关键词
    """
    text_lower = text.lower()
    
    if "昨天" in text_lower or "yesterday" in text_lower:
        return "yesterday"
    elif "前天" in text_lower:
        return "day_before_yesterday"
    elif "上周" in text_lower or "last week" in text_lower:
        return "last_week"
    elif "最近7天" in text_lower or "最近一周" in text_lower:
        return "last_7_days"
    elif "最近30天" in text_lower or "最近一月" in text_lower:
        return "last_30_days"
    
    # 尝试提取具体日期 YYYY-MM-DD
    date_pattern = r'(\d{4})-(\d{1,2})-(\d{1,2})'
    match = re.search(date_pattern, text)
    if match:
        return match.group(0)
    
    return None

