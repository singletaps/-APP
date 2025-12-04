# Agent系统设计方案 V2.0

## 一、需求更新与分析

### 1.1 核心需求更新

基于您的反馈，需求更新如下：

1. **Prompt删除机制**：
   - ✅ 只能删除最新追加的prompt（最后一条总结）
   - ✅ 可以依次删除，直到删回初始prompt
   - ✅ 不能跳跃删除（因为记忆有连续性）

2. **Prompt累积策略**：
   - ✅ 开发阶段：直接累积（简单实现）
   - ✅ 后续优化：可考虑摘要合并

3. **知识库索引用途**：
   - ✅ 超长期记忆检索
   - ✅ 支持"昨天发生了什么"这类查询
   - ✅ 需要实现检索功能

4. **功能范围**：
   - ✅ 暂不支持图片生成，仅文字对话

5. **多消息机制（核心创新）** ⭐：
   - ✅ 用户发送消息后，系统等待5-15秒（随机）
   - ✅ 等待期间如果用户有输入，重置等待时间
   - ✅ 用户发送多条消息后，Agent连续给出多条回复
   - ✅ API返回一整段JSON，通过中间体AI拆分成多段消息
   - ✅ 每段消息可以设置发送延迟
   - ✅ 非流式输入输出

6. **核心理念**：
   - ✅ 模拟真实"人"的聊天方式
   - ✅ 不必一问一答，可以多问多答
   - ✅ 自然的对话节奏

---

## 二、关键设计调整

### 2.1 Prompt删除机制设计

**数据结构调整：**

需要为每条Prompt历史记录添加"可删除"标记，并记录删除状态。

```python
class AgentPromptHistory(Base):
    """
    Agent Prompt历史：记录prompt的演进过程
    """
    __tablename__ = "agent_prompt_history"
    
    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(Integer, ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Prompt内容
    added_prompt = Column(Text, nullable=False)  # 本次追加的prompt内容
    full_prompt_before = Column(Text, nullable=False)  # 追加前的完整prompt
    full_prompt_after = Column(Text, nullable=False)  # 追加后的完整prompt
    
    # 删除状态
    is_deleted = Column(Boolean, default=False, nullable=False)  # 是否已删除
    deleted_at = Column(DateTime(timezone=True), nullable=True)  # 删除时间
    deleted_by_user_id = Column(Integer, nullable=True)  # 删除用户（审计）
    
    # 时间信息
    summary_date = Column(Date, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # 关联关系
    agent = relationship("Agent", back_populates="prompt_history")
    knowledge_index = relationship("AgentKnowledgeIndex", back_populates="prompt_history", uselist=False)
```

**Agent模型的current_prompt计算：**

```python
# 计算当前有效prompt（排除已删除的）
def get_current_prompt(agent: Agent) -> str:
    """
    计算当前有效prompt：
    1. 初始prompt
    2. + 所有未删除的总结（按顺序）
    """
    prompt_parts = [agent.initial_prompt]
    
    # 按创建时间顺序获取未删除的总结
    valid_summaries = (
        db.query(AgentPromptHistory)
        .filter(
            AgentPromptHistory.agent_id == agent.id,
            AgentPromptHistory.is_deleted == False
        )
        .order_by(AgentPromptHistory.created_at.asc())
        .all()
    )
    
    for summary in valid_summaries:
        prompt_parts.append(summary.added_prompt)
    
    return "\n\n".join(prompt_parts)
```

**删除逻辑：**

```python
def delete_latest_prompt_summary(
    db: Session,
    user: User,
    agent_id: int
) -> bool:
    """
    删除最新的prompt总结（只能删除最后一条）
    
    规则：
    - 只能删除最后一条（按创建时间）
    - 必须按顺序删除，不能跳跃
    """
    # 1. 验证Agent归属
    agent = get_agent_for_user(db, user, agent_id)
    if not agent:
        raise ValueError("Agent not found")
    
    # 2. 查找最新的未删除总结
    latest_summary = (
        db.query(AgentPromptHistory)
        .filter(
            AgentPromptHistory.agent_id == agent.id,
            AgentPromptHistory.is_deleted == False
        )
        .order_by(AgentPromptHistory.created_at.desc())
        .first()
    )
    
    if not latest_summary:
        # 没有可删除的总结（只有初始prompt）
        raise ValueError("No summary to delete")
    
    # 3. 检查是否是最新的一条（不能跳跃删除）
    # 如果有更新的未删除总结，则不允许删除
    newer_summaries = (
        db.query(AgentPromptHistory)
        .filter(
            AgentPromptHistory.agent_id == agent.id,
            AgentPromptHistory.created_at > latest_summary.created_at,
            AgentPromptHistory.is_deleted == False
        )
        .count()
    )
    
    if newer_summaries > 0:
        raise ValueError("Cannot delete: must delete summaries in order")
    
    # 4. 标记为已删除
    latest_summary.is_deleted = True
    latest_summary.deleted_at = func.now()
    latest_summary.deleted_by_user_id = user.id
    
    # 5. 同时标记对应的知识库索引为已删除
    if latest_summary.knowledge_index:
        latest_summary.knowledge_index.is_deleted = True
    
    db.commit()
    
    return True
```

**删除API：**

```python
# DELETE /agents/{agent_id}/prompt-history/{history_id}
# 删除指定的prompt总结（只能删除最新的）
def delete_latest_prompt_summary(
    db: Session,
    current_user: User,
    agent_id: int
) -> Dict:
    """
    删除最新的prompt总结
    返回：
    - success: 是否成功
    - deleted_summary_date: 被删除的总结日期
    - remaining_count: 剩余总结数量
    """
    pass
```

---

### 2.2 多消息机制设计（核心创新）

这是一个非常有趣的设计！模拟真实人类聊天的节奏。

#### 2.2.1 业务流程

```
用户发送消息1
  ↓
系统开始等待（随机5-15秒）
  ↓
┌─────────────────────────────┐
│ 等待期间：                     │
│ - 如果用户发送消息2 → 重置等待时间 │
│ - 如果用户发送消息3 → 再次重置   │
│ - ...                        │
└─────────────────────────────┘
  ↓
等待时间到（用户没有新输入）
  ↓
收集所有待处理消息（消息1、2、3...）
  ↓
调用大模型API（一次性处理所有消息）
  ↓
大模型返回一整段JSON（包含多条回复和延迟）
  ↓
通过中间体AI拆分成多段消息
  ↓
后端按顺序发送，每段消息按照JSON中的延迟发送
  ↓
完成
```

#### 2.2.2 数据模型调整

```python
class AgentChatMessage(Base):
    """
    Agent聊天消息
    """
    __tablename__ = "agent_chat_messages"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("agent_chat_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    
    role = Column(String(20), nullable=False)  # user / assistant
    
    # 消息内容
    content = Column(Text, nullable=False)
    
    # 多消息批次管理
    batch_id = Column(String(50), nullable=True, index=True)  # 批次ID（同一次"等待-回复"周期）
    batch_index = Column(Integer, nullable=True)  # 批次内的顺序（用户消息或AI回复的序号）
    
    # 发送时间控制（仅AI消息）
    scheduled_send_at = Column(DateTime(timezone=True), nullable=True)  # 计划发送时间
    actual_sent_at = Column(DateTime(timezone=True), nullable=True)  # 实际发送时间
    send_delay_seconds = Column(Integer, nullable=True)  # 延迟秒数（从第一条回复开始计算）
    
    # 元数据
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    session = relationship("AgentChatSession", back_populates="messages")
```

#### 2.2.3 消息等待机制实现

**前端实现（建议）：**
- 用户发送消息后，前端显示"Agent正在思考..."
- 前端启动倒计时（5-15秒随机）
- 如果用户在等待期间发送新消息，重置倒计时
- 等待时间到后，前端发送所有待处理消息到后端

**后端实现：**

```python
class MessageBuffer:
    """
    消息缓冲区：管理用户发送的多条消息
    """
    def __init__(self, agent_id: int, session_id: int):
        self.agent_id = agent_id
        self.session_id = session_id
        self.messages = []  # 待处理的消息列表
        self.wait_start_time = None  # 等待开始时间
        self.wait_duration = random.randint(5, 15)  # 随机等待时间（秒）
    
    def add_message(self, message: str):
        """添加消息，重置等待时间"""
        self.messages.append(message)
        self.wait_start_time = datetime.now()
        # 重置等待时间
        self.wait_duration = random.randint(5, 15)
    
    def should_process(self) -> bool:
        """判断是否应该处理消息"""
        if not self.messages:
            return False
        
        if not self.wait_start_time:
            return False
        
        elapsed = (datetime.now() - self.wait_start_time).total_seconds()
        return elapsed >= self.wait_duration
```

#### 2.2.4 API设计

**方案A：前端控制等待（推荐）**

前端负责等待逻辑，后端提供批量消息处理API。

```python
# POST /agents/{agent_id}/chat/messages/batch
# 批量发送多条消息，返回多条AI回复
def send_batch_messages(
    db: Session,
    current_user: User,
    agent_id: int,
    payload: AgentBatchMessageCreate
) -> AgentBatchMessageResponse:
    """
    payload包含：
    - messages: List[str]  # 多条用户消息
    
    返回：
    - batch_id: 批次ID
    - replies: List[AgentReply]  # 多条AI回复
      - content: 回复内容
      - send_delay_seconds: 发送延迟（秒）
      - order: 顺序
    """
    # 1. 收集所有用户消息
    user_messages = payload.messages
    
    # 2. 保存用户消息到数据库
    batch_id = str(uuid.uuid4())
    for idx, msg in enumerate(user_messages):
        user_msg = AgentChatMessage(
            session_id=session.id,
            role="user",
            content=msg,
            batch_id=batch_id,
            batch_index=idx
        )
        db.add(user_msg)
    
    # 3. 调用AI处理所有消息
    agent_replies = process_batch_messages(
        agent=agent,
        user_messages=user_messages,
        context_messages=history  # 历史上下文
    )
    
    # 4. 保存AI回复到数据库
    for idx, reply in enumerate(agent_replies):
        ai_msg = AgentChatMessage(
            session_id=session.id,
            role="assistant",
            content=reply.content,
            batch_id=batch_id,
            batch_index=idx,
            send_delay_seconds=reply.send_delay_seconds
        )
        db.add(ai_msg)
    
    db.commit()
    
    return {
        "batch_id": batch_id,
        "replies": agent_replies
    }
```

**方案B：后端控制等待（复杂）**

后端维护等待队列，使用WebSocket或长轮询。

不推荐，复杂度高。

#### 2.2.5 批量消息处理逻辑

```python
def process_batch_messages(
    agent: Agent,
    user_messages: List[str],
    context_messages: List[AgentChatMessage]
) -> List[AgentReply]:
    """
    处理批量消息，返回多条AI回复（带延迟信息）
    """
    # 1. 构建上下文
    current_prompt = get_current_prompt(agent)
    
    messages = [
        {"role": "system", "content": current_prompt}
    ]
    
    # 添加历史消息
    for msg in context_messages:
        messages.append({
            "role": msg.role,
            "content": msg.content
        })
    
    # 添加当前多条用户消息
    for user_msg in user_messages:
        messages.append({
            "role": "user",
            "content": user_msg
        })
    
    # 2. 调用大模型（一次性处理所有消息）
    # 使用特殊的prompt，让模型生成多条回复
    batch_prompt = """
你是一个自然的对话助手。用户可能发送了多条消息，请像真人聊天一样，连续给出多条回复。

用户消息：
{user_messages}

请按照以下JSON格式返回你的回复：
{
    "replies": [
        {
            "content": "第一条回复内容",
            "send_delay_seconds": 0  // 从第一条回复开始计算的延迟（秒）
        },
        {
            "content": "第二条回复内容",
            "send_delay_seconds": 3  // 延迟3秒后发送
        }
    ]
}

注意：
- 回复要自然，就像真人聊天一样
- 可以针对不同的用户消息给出不同的回复
- 延迟要合理，模拟真实的打字和思考时间（0-10秒之间）
- 回复数量应该与用户消息数量或话题数量匹配
"""
    
    # 调用大模型
    response = ask_with_messages(messages, ...)
    
    # 3. 解析JSON响应
    try:
        replies_data = json.loads(response)
        replies = replies_data.get("replies", [])
    except json.JSONDecodeError:
        # JSON解析失败，使用中间体AI拆分
        replies = split_response_with_ai(response)
    
    return replies
```

#### 2.2.6 中间体AI拆分逻辑

```python
def split_response_with_ai(full_response: str) -> List[AgentReply]:
    """
    使用中间体AI将完整回复拆分成多段消息
    
    这个AI专门负责：
    1. 识别回复中的多个话题或段落
    2. 拆分成多条消息
    3. 为每条消息分配合理的延迟时间
    """
    split_prompt = f"""
你是一个消息拆分助手。请将以下AI回复拆分成多条独立的回复，模拟真实聊天场景。

完整回复：
{full_response}

请按照以下JSON格式返回：
{{
    "replies": [
        {{
            "content": "第一条回复",
            "send_delay_seconds": 0
        }},
        {{
            "content": "第二条回复",
            "send_delay_seconds": 2
        }}
    ]
}}

拆分规则：
1. 识别不同的 topics 或观点
2. 每个topic可以是一条独立回复
3. 保持每条回复的完整性
4. 延迟时间要合理（0-10秒）
"""
    
    messages = [
        {"role": "system", "content": "你是一个专业的消息拆分助手，擅长将长文本拆分成多条独立的回复消息。"},
        {"role": "user", "content": split_prompt}
    ]
    
    split_result = ask_with_messages(messages, ...)
    
    try:
        result_data = json.loads(split_result)
        return result_data.get("replies", [])
    except json.JSONDecodeError:
        # 如果还是失败，返回单条回复
        return [{
            "content": full_response,
            "send_delay_seconds": 0
        }]
```

---

### 2.3 知识库索引与检索设计

#### 2.3.1 检索需求分析

用户需求：
- "昨天发生了什么" → 查询昨天的总结
- "上周我们讨论了什么" → 查询上周的总结
- 超长期记忆检索

#### 2.3.2 知识库索引增强

```python
class AgentKnowledgeIndex(Base):
    """
    Agent知识库索引
    """
    __tablename__ = "agent_knowledge_indexes"
    
    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(Integer, ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    prompt_history_id = Column(Integer, ForeignKey("agent_prompt_history.id", ondelete="CASCADE"), nullable=False, unique=True)
    
    # 索引信息
    summary_date = Column(Date, nullable=False, index=True)  # 对应的聊天日期
    summary_summary = Column(Text, nullable=False)  # 总结摘要（冗余存储）
    
    # 扩展信息（用于检索）
    topics = Column(JSON, nullable=True)  # 讨论话题列表
    key_points = Column(JSON, nullable=True)  # 关键点列表
    keywords = Column(JSON, nullable=True)  # 关键词列表（用于全文检索）
    
    # 统计信息
    message_count = Column(Integer, nullable=False, default=0)
    user_message_count = Column(Integer, nullable=False, default=0)
    
    # 删除状态（与prompt_history同步）
    is_deleted = Column(Boolean, default=False, nullable=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    agent = relationship("Agent", back_populates="knowledge_indexes")
    prompt_history = relationship("AgentPromptHistory", back_populates="knowledge_index")
```

#### 2.3.3 检索功能实现

```python
def search_agent_knowledge(
    db: Session,
    agent_id: int,
    query: str,
    date_range: Optional[Tuple[Date, Date]] = None
) -> List[AgentKnowledgeIndex]:
    """
    检索Agent知识库
    
    支持：
    - 日期查询："昨天"、"上周"、"2024-01-01"
    - 关键词查询：搜索总结内容
    - 组合查询
    """
    # 1. 解析日期查询
    target_dates = parse_date_query(query, date_range)
    
    # 2. 查询知识库索引
    query_obj = (
        db.query(AgentKnowledgeIndex)
        .filter(
            AgentKnowledgeIndex.agent_id == agent_id,
            AgentKnowledgeIndex.is_deleted == False
        )
    )
    
    # 日期过滤
    if target_dates:
        query_obj = query_obj.filter(
            AgentKnowledgeIndex.summary_date.in_(target_dates)
        )
    
    # 关键词搜索（简单实现，可以后续优化为全文搜索）
    if has_keywords(query):
        keywords = extract_keywords(query)
        # 在summary_summary中搜索关键词
        for keyword in keywords:
            query_obj = query_obj.filter(
                AgentKnowledgeIndex.summary_summary.contains(keyword)
            )
    
    results = query_obj.order_by(AgentKnowledgeIndex.summary_date.desc()).all()
    
    return results

def parse_date_query(query: str, date_range: Optional[Tuple[Date, Date]]) -> List[Date]:
    """
    解析日期查询
    
    支持：
    - "昨天"、"前天"
    - "上周"、"上上周"
    - "2024-01-01"
    - "最近7天"
    """
    today = date.today()
    dates = []
    
    # 简单的日期解析（可以后续优化为NLP解析）
    if "昨天" in query or "yesterday" in query.lower():
        dates.append(today - timedelta(days=1))
    elif "前天" in query:
        dates.append(today - timedelta(days=2))
    elif "上周" in query:
        # 上周的日期范围
        last_week_start = today - timedelta(days=today.weekday() + 7)
        dates.extend([last_week_start + timedelta(days=i) for i in range(7)])
    elif "最近7天" in query:
        dates.extend([today - timedelta(days=i) for i in range(7)])
    
    # 可以扩展更多日期解析逻辑
    
    return dates
```

#### 2.3.4 检索API

```python
# GET /agents/{agent_id}/knowledge/search
# 检索Agent知识库
def search_knowledge(
    db: Session,
    current_user: User,
    agent_id: int,
    query: str,
    date_from: Optional[Date] = None,
    date_to: Optional[Date] = None
) -> List[KnowledgeSearchResult]:
    """
    检索知识库
    
    query: 查询文本（可以包含日期和关键词）
    date_from/date_to: 可选的日期范围
    
    返回匹配的知识库条目
    """
    pass
```

#### 2.3.5 在Agent聊天中集成检索

```python
def process_user_query_with_knowledge(
    agent: Agent,
    user_message: str,
    context_messages: List[AgentChatMessage]
) -> str:
    """
    处理用户查询时，如果涉及历史查询，先检索知识库
    """
    # 1. 检测是否是历史查询
    if is_history_query(user_message):
        # 2. 检索知识库
        knowledge_results = search_agent_knowledge(
            db=db,
            agent_id=agent.id,
            query=user_message
        )
        
        # 3. 将知识库内容注入到上下文
        knowledge_context = format_knowledge_context(knowledge_results)
        
        # 4. 在prompt中包含知识库内容
        enhanced_prompt = f"""
{agent.current_prompt}

[相关历史记忆]
{knowledge_context}
"""
    else:
        enhanced_prompt = agent.current_prompt
    
    # 5. 调用大模型
    response = ask_with_messages(messages, system_prompt=enhanced_prompt)
    
    return response

def is_history_query(message: str) -> bool:
    """
    检测是否是历史查询
    
    关键词：
    - "昨天"、"前天"、"上周"
    - "发生了什么"、"讨论了什么"
    - "之前"、"以前"
    """
    history_keywords = [
        "昨天", "前天", "上周", "之前", "以前",
        "发生了什么", "讨论了什么", "聊了什么"
    ]
    
    return any(keyword in message for keyword in history_keywords)
```

---

## 三、API设计更新

### 3.1 Agent管理API（更新）

```python
# DELETE /agents/{agent_id}/prompt-history/latest
# 删除最新的prompt总结
def delete_latest_prompt_summary(
    db: Session,
    current_user: User,
    agent_id: int
) -> Dict:
    """
    删除最新的prompt总结（只能删除最后一条）
    
    返回：
    {
        "success": true,
        "deleted_summary_date": "2024-01-15",
        "remaining_count": 5,
        "current_prompt_preview": "..."
    }
    """
    pass

# GET /agents/{agent_id}/prompt-history
# 获取prompt历史列表（包括删除状态）
def get_agent_prompt_history(
    db: Session,
    current_user: User,
    agent_id: int,
    include_deleted: bool = False
) -> List[AgentPromptHistory]:
    """
    获取prompt历史
    
    include_deleted: 是否包含已删除的记录
    """
    pass
```

### 3.2 Agent聊天API（更新）

```python
# POST /agents/{agent_id}/chat/messages/batch
# 批量发送多条消息（核心API）
def send_batch_messages(
    db: Session,
    current_user: User,
    agent_id: int,
    payload: AgentBatchMessageCreate
) -> AgentBatchMessageResponse:
    """
    payload:
    {
        "messages": ["消息1", "消息2", "消息3"]
    }
    
    response:
    {
        "batch_id": "uuid",
        "replies": [
            {
                "id": 1,
                "content": "第一条回复",
                "send_delay_seconds": 0,
                "order": 1
            },
            {
                "id": 2,
                "content": "第二条回复",
                "send_delay_seconds": 3,
                "order": 2
            }
        ]
    }
    """
    pass

# GET /agents/{agent_id}/chat
# 获取Agent聊天会话和消息（支持批次查询）
def get_agent_chat(
    db: Session,
    current_user: User,
    agent_id: int,
    batch_id: Optional[str] = None  # 可选：只查询某个批次的消息
) -> AgentChatSessionWithMessages:
    pass
```

### 3.3 知识库检索API（新增）

```python
# GET /agents/{agent_id}/knowledge/search
# 检索Agent知识库
def search_knowledge(
    db: Session,
    current_user: User,
    agent_id: int,
    query: str,
    date_from: Optional[Date] = None,
    date_to: Optional[Date] = None
) -> KnowledgeSearchResponse:
    """
    query: 查询文本（例如："昨天发生了什么"）
    
    response:
    {
        "results": [
            {
                "summary_date": "2024-01-15",
                "summary": "总结内容...",
                "topics": ["话题1", "话题2"],
                "message_count": 10
            }
        ],
        "total": 1
    }
    """
    pass

# GET /agents/{agent_id}/knowledge
# 获取Agent的所有知识库索引
def get_agent_knowledge_index(
    db: Session,
    current_user: User,
    agent_id: int,
    date_from: Optional[Date] = None,
    date_to: Optional[Date] = None
) -> List[AgentKnowledgeIndex]:
    pass
```

---

## 四、实施建议

### 4.1 实施阶段调整

**第一阶段：核心功能（MVP）**
1. ✅ Agent数据模型（包括删除标记）
2. ✅ Agent管理API（创建、列表、删除、删除prompt总结）
3. ✅ Agent单会话聊天（简单版本，单条消息）
4. ✅ 知识库索引模型

**第二阶段：多消息机制**
1. ✅ 消息批次管理（batch_id）
2. ✅ 批量消息处理API
3. ✅ 中间体AI拆分逻辑
4. ✅ 前端等待机制（前端实现）

**第三阶段：知识库检索**
1. ✅ 检索功能实现
2. ✅ 日期解析逻辑
3. ✅ 检索API
4. ✅ 在Agent聊天中集成检索

**第四阶段：自动化总结**
1. ✅ 定时任务
2. ✅ 总结服务
3. ✅ Prompt历史记录

**第五阶段：优化**
1. ✅ 总结质量优化
2. ✅ 检索性能优化
3. ✅ 多消息机制优化

### 4.2 关键技术点

1. **消息等待机制**：
   - 推荐：前端实现等待逻辑（简单、可控）
   - 后端只负责批量处理

2. **中间体AI拆分**：
   - 使用轻量模型（降低成本）
   - 添加重试机制（如果拆分失败）

3. **知识库检索**：
   - 第一阶段：简单关键词匹配
   - 未来：可以引入向量数据库（语义检索）

4. **Prompt删除机制**：
   - 使用软删除（is_deleted标记）
   - 保留审计信息（deleted_at, deleted_by）

---

## 五、关键讨论点

### 5.1 关于多消息机制

**问题1：前端等待机制的实现**

**建议：**
- 前端负责等待逻辑（5-15秒随机）
- 用户发送消息后，前端显示"Agent正在思考..."
- 如果用户在等待期间发送新消息，重置等待
- 等待时间到后，前端调用批量API

**优势：**
- 实现简单
- 用户体验好（实时反馈）
- 后端逻辑简单

**问题2：中间体AI拆分的可靠性**

**建议：**
- 第一版：直接让大模型返回JSON格式（在prompt中明确要求）
- 如果JSON解析失败，再用中间体AI拆分
- 添加重试机制

**问题3：延迟时间的合理性**

**建议：**
- 延迟范围：0-10秒（第一条0秒，后续2-5秒合理）
- 可以根据回复长度调整延迟（长回复延迟更长）
- 可以添加配置，让用户自定义延迟范围

### 5.2 关于知识库检索

**问题1：检索的准确性**

**建议：**
- 第一阶段：简单关键词匹配 + 日期解析
- 未来：引入向量数据库（如Milvus、Chroma）
- 支持语义检索

**问题2：检索性能**

**建议：**
- 为常用字段添加数据库索引（summary_date, keywords）
- 如果数据量大，考虑分页
- 可以缓存热门查询

### 5.3 关于Prompt删除

**问题1：删除后的数据恢复**

**建议：**
- 使用软删除，数据保留
- 可以提供"恢复"功能（恢复最后删除的一条）
- 但需要谨慎，因为会影响后续总结的连续性

**问题2：删除后的知识库索引**

**建议：**
- 知识库索引也使用软删除（与prompt_history同步）
- 删除prompt时，同时标记知识库索引为已删除
- 检索时过滤已删除的索引

---

## 六、前端交互设计建议

### 6.1 多消息等待UI

```
用户输入消息1 → 发送
  ↓
显示："Agent正在思考... (倒计时: 12秒)"
  ↓
用户在8秒时输入消息2 → 发送
  ↓
倒计时重置："Agent正在思考... (倒计时: 9秒)"
  ↓
用户在5秒时输入消息3 → 发送
  ↓
倒计时重置："Agent正在思考... (倒计时: 11秒)"
  ↓
倒计时到0
  ↓
显示："Agent正在回复..."
  ↓
依次显示Agent的多条回复（带延迟动画）
```

### 6.2 Prompt历史管理UI

```
Agent详情页面
  ├── 基本信息
  │   ├── Agent名称（可编辑）
  │   └── 初始Prompt（只读）
  │
  ├── Prompt历史
  │   ├── [2024-01-15] 总结内容... [删除] ← 只能删除最新的
  │   ├── [2024-01-14] 总结内容... [删除] ← 删除后，这变成最新的
  │   └── [2024-01-13] 总结内容...
  │
  └── 知识库索引
      └── 查看知识库条目
```

---

## 七、总结

### 7.1 核心创新点

1. **多消息机制**：模拟真实人类聊天，多问多答
2. **Prompt可删除**：用户可控，但保持连续性
3. **知识库检索**：超长期记忆，支持历史查询
4. **自然对话节奏**：延迟发送，更像真人

### 7.2 技术亮点

1. **批量消息处理**：一次性处理多条消息，提高效率
2. **中间体AI拆分**：将复杂回复拆分成多条自然消息
3. **软删除机制**：保留数据，支持恢复
4. **知识库索引**：为未来扩展打下基础

### 7.3 实施优先级

1. **高优先级**：核心功能 + 多消息机制
2. **中优先级**：知识库检索
3. **低优先级**：自动化总结（可以先用手动触发测试）

期待您的反馈！🚀
