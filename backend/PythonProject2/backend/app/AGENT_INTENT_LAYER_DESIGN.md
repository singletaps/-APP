# Agent意图识别中间层设计方案

## 一、需求分析

### 1.1 问题场景

**用户场景：** 用户问"昨天发生了什么"

**当前设计的问题：**
- 需要在Agent聊天中判断是否是知识库查询
- 查询逻辑分散在业务代码中
- 不够智能和自动化

**您的建议：**
- 添加意图识别AI中间层
- 自动识别"查询本地知识库"意图
- 向后端发送可解析的JSON
- 后端自动检索并注入知识

---

## 二、设计分析

### 2.1 架构对比

#### 方案A：当前设计（无意图识别层）

```
用户消息："昨天发生了什么"
  ↓
直接发送到Agent处理
  ↓
Agent在回复时判断是否需要查询知识库
  ↓
如果需要，查询知识库
  ↓
将查询结果注入prompt
  ↓
生成回复
```

**问题：**
- 判断逻辑分散
- 可能漏掉查询意图
- 不够智能

#### 方案B：添加意图识别中间层（推荐）⭐

```
用户消息："昨天发生了什么"
  ↓
意图识别AI层
  ↓
识别意图：KNOWLEDGE_QUERY
  ↓
生成结构化JSON：
{
    "intent": "KNOWLEDGE_QUERY",
    "query_params": {
        "date": "yesterday",
        "keywords": ["发生", "什么"]
    }
}
  ↓
后端解析JSON，调用知识库检索
  ↓
将检索结果注入Agent的prompt
  ↓
Agent生成回复（包含历史信息）
```

**优势：**
- ✅ 统一处理流程
- ✅ 自动识别意图
- ✅ 结构化数据，易于处理
- ✅ 可以扩展更多意图类型

---

## 三、详细设计方案

### 3.1 意图类型定义

```python
class AgentIntentType:
    """
    Agent聊天中的意图类型
    """
    NORMAL_CHAT = "NORMAL_CHAT"  # 普通对话
    KNOWLEDGE_QUERY = "KNOWLEDGE_QUERY"  # 知识库查询
    # 未来可以扩展：
    # PROMPT_MANAGEMENT = "PROMPT_MANAGEMENT"  # Prompt管理
    # AGENT_SETTINGS = "AGENT_SETTINGS"  # Agent设置
```

### 3.2 意图识别AI Prompt设计

```python
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
    "confidence": 0.0-1.0,  // 置信度
    "query_params": {        // 如果是KNOWLEDGE_QUERY，包含查询参数
        "date": "yesterday" | "last_week" | "2024-01-15" | null,  // 日期信息
        "keywords": ["关键词1", "关键词2"],  // 提取的关键词
        "date_range": {      // 可选：日期范围
            "from": "2024-01-01",
            "to": "2024-01-15"
        }
    },
    "reason": "简要说明判断理由"
}

只返回JSON，不要其他内容。"""
```

### 3.3 意图识别实现

```python
# agents/intent_detector.py
"""
Agent意图识别模块
专门用于Agent聊天场景的意图识别
"""

import json
import logging
from typing import Dict, Any, Optional
from datetime import date, timedelta
import re

from backend.app.ai.client import client
from backend.app.ai.service import ask_with_messages

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
    model: str = "doubao-seed-1-6-lite-251015",  # 使用轻量模型
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
    if "昨天" in text or "yesterday" in text:
        return "yesterday"
    elif "前天" in text:
        return "day_before_yesterday"
    elif "上周" in text or "last week" in text:
        return "last_week"
    elif "最近7天" in text:
        return "last_7_days"
    elif "最近30天" in text:
        return "last_30_days"
    
    # 尝试提取具体日期 YYYY-MM-DD
    date_pattern = r'(\d{4})-(\d{1,2})-(\d{1,2})'
    match = re.search(date_pattern, text)
    if match:
        return match.group(0)
    
    return None
```

### 3.4 集成到Agent聊天流程

```python
# agents/service.py

def send_batch_messages_to_agent(
    db: Session,
    user: User,
    agent_id: int,
    user_messages: List[str]
) -> List[Dict]:
    """
    发送批量消息到Agent（集成意图识别）
    """
    # 1. 获取Agent和会话
    agent = get_agent_for_user(db, user, agent_id)
    session = get_or_create_agent_session(db, agent_id)
    
    # 2. 保存用户消息
    batch_id = str(uuid.uuid4())
    for idx, msg in enumerate(user_messages):
        save_user_message(db, session.id, msg, batch_id, idx)
    
    # 3. 合并所有用户消息（用于意图识别）
    combined_message = " ".join(user_messages)
    
    # 4. 意图识别
    from backend.app.agents.intent_detector import detect_agent_intent, AgentIntentType
    
    intent_result = detect_agent_intent(combined_message)
    intent = intent_result["intent"]
    
    logger.info(f"[Agent服务] 意图识别结果: {intent}, 置信度: {intent_result.get('confidence', 0)}")
    
    # 5. 根据意图处理
    knowledge_context = None
    
    if intent == AgentIntentType.KNOWLEDGE_QUERY:
        # 查询知识库
        query_params = intent_result.get("query_params", {})
        knowledge_context = query_knowledge_base(
            db=db,
            agent_id=agent_id,
            query_params=query_params
        )
        
        logger.info(f"[Agent服务] 知识库查询完成，找到 {len(knowledge_context)} 条记录")
    
    # 6. 构建Agent的prompt（注入知识库上下文）
    enhanced_prompt = build_agent_prompt(
        agent=agent,
        knowledge_context=knowledge_context,
        session_id=session.id,
        db=db
    )
    
    # 7. 调用大模型处理批量消息
    ai_replies = process_batch_messages_with_prompt(
        enhanced_prompt=enhanced_prompt,
        user_messages=user_messages,
        history_messages=get_history_messages(db, session.id)
    )
    
    # 8. 保存AI回复
    for idx, reply in enumerate(ai_replies):
        save_ai_reply(db, session.id, reply, batch_id, idx)
    
    db.commit()
    
    return ai_replies


def build_agent_prompt(
    agent: Agent,
    knowledge_context: Optional[List[Dict]] = None,
    session_id: int = None,
    db: Session = None
) -> str:
    """
    构建Agent的prompt（包含知识库上下文）
    
    格式：
    {agent.current_prompt}
    
    [回复格式要求]
    {format_prompt}
    
    [当前对话上下文]
    {today_messages}
    
    [相关历史记忆]  ← 如果查询了知识库，这里会包含
    {knowledge_context}
    """
    prompt_parts = []
    
    # 1. Agent的基础prompt
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
- 回复要自然，就像真人聊天一样
- 可以针对不同的用户消息给出不同的回复
- 延迟要合理，模拟真实的打字和思考时间（0-10秒之间）
- 回复数量应该与用户消息数量或话题数量匹配"""
    
    prompt_parts.append(format_prompt)
    
    # 3. 当天聊天记录（如果有）
    if session_id and db:
        today_messages = get_today_messages(db, session_id)
        if today_messages:
            prompt_parts.append("[当前对话上下文]")
            for msg in today_messages:
                prompt_parts.append(f"{msg.role}: {msg.content}")
    
    # 4. 知识库上下文（如果查询了）
    if knowledge_context:
        prompt_parts.append("[相关历史记忆]")
        for knowledge in knowledge_context:
            prompt_parts.append(f"日期: {knowledge['summary_date']}")
            prompt_parts.append(f"内容: {knowledge['summary_summary']}")
            if knowledge.get('topics'):
                prompt_parts.append(f"话题: {', '.join(knowledge['topics'])}")
    
    return "\n\n".join(prompt_parts)


def query_knowledge_base(
    db: Session,
    agent_id: int,
    query_params: Dict[str, Any]
) -> List[Dict]:
    """
    查询知识库（根据意图识别的参数）
    """
    from backend.app.agents.knowledge_index import search_agent_knowledge, parse_date_query
    
    # 解析日期
    date_value = query_params.get("date")
    keywords = query_params.get("keywords", [])
    
    # 转换为日期范围
    if date_value:
        target_dates = parse_date_from_keyword(date_value)
    else:
        target_dates = None
    
    # 查询知识库
    results = search_agent_knowledge(
        db=db,
        agent_id=agent_id,
        dates=target_dates,
        keywords=keywords
    )
    
    # 转换为字典格式
    return [
        {
            "summary_date": str(result.summary_date),
            "summary_summary": result.summary_summary,
            "topics": result.topics or [],
            "key_points": result.key_points or []
        }
        for result in results
    ]


def parse_date_from_keyword(date_keyword: str) -> List[date]:
    """
    将日期关键词转换为具体的日期列表
    """
    today = date.today()
    dates = []
    
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
```

---

## 四、数据流设计

### 4.1 完整数据流

```
用户发送消息："昨天发生了什么"
  ↓
前端：等待5-15秒，收集所有消息
  ↓
后端：接收批量消息
  ↓
意图识别AI层：
  - 识别意图：KNOWLEDGE_QUERY
  - 提取参数：date="yesterday", keywords=["发生", "什么"]
  - 返回JSON
  ↓
后端解析JSON：
  - intent: "KNOWLEDGE_QUERY"
  - query_params: {...}
  ↓
知识库检索：
  - 查询昨天的总结
  - 返回匹配的知识库条目
  ↓
构建增强Prompt：
  - Agent的current_prompt
  - 回复格式要求
  - 当天聊天记录
  - [相关历史记忆] ← 昨天聊天记录的总结
  ↓
调用大模型：
  - 使用增强prompt
  - 处理用户消息
  - 返回JSON格式回复
  ↓
解析JSON，返回多条回复
  ↓
前端按延迟依次显示
```

### 4.2 Prompt格式示例

```
{Agent的current_prompt}

[回复格式要求]
请按照以下JSON格式返回你的回复：
{
    "replies": [
        {
            "content": "回复内容",
            "send_delay_seconds": 0
        }
    ]
}
...

[当前对话上下文]
user: 你好
assistant: 你好！有什么可以帮助你的吗？

[相关历史记忆]
日期: 2024-01-15
内容: 在昨天的对话中，用户主要讨论了项目进度和团队协作问题。用户表现出对项目时间管理的关注。Agent提供了时间管理建议。需要记住：用户喜欢使用番茄工作法。
话题: 项目管理, 时间管理

用户消息：
昨天发生了什么
```

---

## 五、优势分析

### 5.1 架构优势

1. **自动化识别**：无需手动判断，AI自动识别查询意图
2. **统一处理**：所有意图识别都在一个地方处理
3. **易于扩展**：未来可以添加更多意图类型
4. **结构化数据**：JSON格式，易于解析和处理

### 5.2 用户体验优势

1. **智能识别**：用户说"昨天发生了什么"，自动查询
2. **上下文丰富**：Agent回复时已经知道历史信息
3. **自然对话**：用户不需要记住特殊命令

### 5.3 技术优势

1. **复用现有模块**：可以复用现有的意图识别基础设施
2. **性能优化**：使用轻量模型，快速响应
3. **降级策略**：如果AI识别失败，使用关键词匹配

---

## 六、与现有系统的集成

### 6.1 复用现有意图识别基础设施

可以复用 `ai/intent_detector.py` 的基础设施，但需要专门的Agent意图识别模块，因为：

- Agent场景的意图类型不同（KNOWLEDGE_QUERY vs IMAGE_GENERATE）
- 需要提取不同的参数（日期、关键词 vs 文件、图片）
- 处理逻辑不同（知识库查询 vs 图片生成）

**建议：**
- 创建独立的 `agents/intent_detector.py`
- 复用基础框架（JSON解析、错误处理等）
- 使用相同的轻量模型

### 6.2 模块结构

```
backend/app/
├── ai/
│   ├── intent_detector.py      # 现有：日常聊天意图识别
│   └── ...
│
└── agents/
    ├── intent_detector.py      # 新增：Agent意图识别
    ├── service.py              # Agent服务（集成意图识别）
    ├── knowledge_index.py      # 知识库检索
    └── ...
```

---

## 七、实施建议

### 7.1 实施步骤

**第一阶段：基础意图识别**
1. 创建 `agents/intent_detector.py`
2. 实现意图识别逻辑
3. 测试意图识别准确性

**第二阶段：集成到Agent服务**
1. 在 `agents/service.py` 中集成意图识别
2. 实现知识库查询逻辑
3. 实现增强prompt构建

**第三阶段：优化和完善**
1. 优化意图识别prompt
2. 添加更多的日期解析逻辑
3. 完善错误处理和降级策略

### 7.2 关键代码位置

```
agents/
├── intent_detector.py          # 意图识别模块
│   ├── detect_agent_intent()   # 主函数
│   ├── parse_intent_json()     # JSON解析
│   └── fallback_keyword_match() # 降级策略
│
├── service.py                  # Agent服务
│   ├── send_batch_messages_to_agent()  # 集成意图识别
│   ├── build_agent_prompt()    # 构建增强prompt
│   └── query_knowledge_base()  # 查询知识库
│
└── knowledge_index.py          # 知识库检索
    └── search_agent_knowledge() # 检索函数
```

---

## 八、需要讨论的点

### 8.1 意图识别的位置

**问题：** 意图识别应该在哪里执行？

**选项A：后端执行（推荐）**
- 前端发送消息到后端
- 后端先进行意图识别
- 根据意图决定后续流程

**优势：**
- 统一逻辑在后端
- 前端不需要关心意图
- 更容易维护和优化

**选项B：前端执行**
- 前端先进行意图识别
- 根据意图调用不同API

**不推荐：**
- 增加前端复杂度
- 需要在前端维护AI调用

### 8.2 置信度阈值

**问题：** 置信度多高才执行知识库查询？

**建议：**
- 默认阈值：0.7
- 可以配置
- 低于阈值时，可以选择：
  - 仍然查询（但可能不相关）
  - 或降级为普通对话

### 8.3 知识库查询结果的限制

**问题：** 查询到很多结果，如何处理？

**建议：**
- 限制返回数量（如：最多5条）
- 按相关性排序
- 只选择最相关的结果注入prompt

### 8.4 性能考虑

**问题：** 每次都要调用意图识别AI，会增加延迟

**建议：**
- 使用轻量模型（已选择）
- 可以缓存常见意图（简单关键词匹配优先）
- 如果关键词明显匹配，可以直接查询，跳过AI识别

---

## 九、总结

### 9.1 推荐方案

**✅ 强烈推荐添加意图识别中间层！**

**理由：**
1. 自动化处理查询意图
2. 统一架构，易于扩展
3. 提升用户体验
4. 可以复用现有基础设施

### 9.2 核心设计

1. **意图识别模块**：`agents/intent_detector.py`
   - 使用轻量模型快速识别
   - 返回结构化JSON
   - 支持降级策略

2. **集成到Agent服务**：
   - 在批量消息处理前进行意图识别
   - 根据意图查询知识库
   - 将查询结果注入prompt

3. **Prompt构建**：
   - Agent的current_prompt
   - 回复格式要求
   - 当天聊天记录
   - 相关历史记忆（如果查询了）

### 9.3 实施优先级

**高优先级：**
1. 创建意图识别模块
2. 集成到Agent服务
3. 实现知识库查询注入

**中优先级：**
1. 优化意图识别准确性
2. 添加更多日期解析逻辑

**低优先级：**
1. 缓存机制
2. 性能优化

---

期待您的反馈！🚀
