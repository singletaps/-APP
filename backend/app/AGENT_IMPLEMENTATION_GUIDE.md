# Agent系统实施指南

## 一、已确认的技术决策 ✅

1. **前端等待机制**：前端负责等待逻辑（5-15秒随机）
2. **消息累积**：用户新消息累积到下次Agent回复
3. **JSON格式**：大模型返回JSON，后端解析（支持嵌套JSON）
4. **知识库检索**：先使用关键词匹配
5. **删除策略**：删除后无法恢复（硬删除）
6. **延迟范围**：使用固定范围（0-10秒）

---

## 二、需要进一步讨论的技术细节

### 2.1 JSON解析的详细实现

#### 问题：如何处理嵌套JSON？

**场景：** 大模型返回的JSON中，可能包含嵌套的JSON字符串。

**建议方案：**

```python
def parse_nested_json(json_string: str) -> Dict:
    """
    解析嵌套的JSON字符串
    
    支持：
    1. 标准JSON：{"replies": [...]}
    2. Markdown代码块包裹：```json {...} ```
    3. 嵌套JSON字符串：{"replies": ["{\"content\": \"...\"}"]}
    4. 多层嵌套
    """
    # 1. 清理可能的Markdown代码块
    json_string = clean_markdown_code_block(json_string)
    
    # 2. 尝试直接解析
    try:
        data = json.loads(json_string)
        return parse_nested_replies(data)
    except json.JSONDecodeError:
        pass
    
    # 3. 尝试提取JSON部分
    json_match = re.search(r'\{.*\}', json_string, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group())
            return parse_nested_replies(data)
        except json.JSONDecodeError:
            pass
    
    # 4. 如果都失败，返回空结构
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

def clean_markdown_code_block(text: str) -> str:
    """清理Markdown代码块标记"""
    # 移除 ```json 和 ``` 标记
    text = re.sub(r'```json\s*', '', text)
    text = re.sub(r'```\s*', '', text)
    return text.strip()
```

#### 问题：JSON解析失败时的降级策略

**建议：**
1. 尝试提取JSON部分（使用正则）
2. 如果提取失败，尝试将整个回复作为单条消息
3. 记录错误日志，便于后续优化

```python
def safe_parse_agent_reply(raw_response: str) -> List[Dict]:
    """
    安全解析Agent回复，包含降级策略
    """
    try:
        # 尝试解析嵌套JSON
        data = parse_nested_json(raw_response)
        replies = data.get("replies", [])
        
        if replies:
            return normalize_replies(replies)
    except Exception as e:
        logger.error(f"JSON解析失败: {e}, 原始回复: {raw_response[:200]}")
    
    # 降级：返回单条消息
    return [{
        "content": raw_response,
        "send_delay_seconds": 0
    }]
```

---

### 2.2 消息累积的边界情况

#### 问题1：用户连续发送大量消息怎么办？

**场景：** 用户在等待期间连续发送10+条消息。

**建议：**
- 设置消息数量上限（如：最多20条）
- 超过上限后，提示用户等待处理
- 或者在服务端分批处理

```python
MAX_BATCH_MESSAGES = 20  # 最大批量消息数

def validate_batch_messages(messages: List[str]) -> Tuple[bool, str]:
    """
    验证批量消息
    """
    if len(messages) > MAX_BATCH_MESSAGES:
        return False, f"单次最多发送{MAX_BATCH_MESSAGES}条消息，请等待Agent回复后再发送"
    
    if len(messages) == 0:
        return False, "消息不能为空"
    
    # 检查消息长度
    for msg in messages:
        if len(msg) > 5000:  # 单条消息长度限制
            return False, "单条消息长度不能超过5000字符"
    
    return True, ""
```

#### 问题2：用户发送空消息或无效消息

**建议：**
- 前端过滤空消息
- 后端验证消息有效性
- 过滤纯空格、特殊字符等

#### 问题3：等待期间用户关闭页面或刷新

**建议：**
- 前端在localStorage保存待处理消息
- 页面恢复后继续等待或提示用户
- 或者：后端也保存待处理消息状态（但会增加复杂度）

---

### 2.3 并发处理与数据一致性

#### 问题：多用户同时使用同一Agent？

**场景：** Agent是用户私有的，但需要考虑同一用户的多设备访问。

**建议：**
- Agent会话是单会话模式，需要处理并发写入
- 使用数据库事务保证一致性
- 或者：使用乐观锁（version字段）

```python
class AgentChatSession(Base):
    # ... 现有字段 ...
    version = Column(Integer, default=0, nullable=False)  # 乐观锁版本号

def send_batch_messages_with_lock(...):
    """
    带锁的批量消息发送
    """
    # 使用数据库锁或乐观锁
    # 确保消息按顺序写入
    pass
```

#### 问题：定时任务与用户操作冲突

**场景：** 12点执行总结任务时，用户正在发送消息。

**建议：**
- 总结任务使用轻量级锁（避免长时间锁定）
- 或者：总结任务只读取，不影响用户操作
- 或者：在低峰期执行（如凌晨3点）

---

### 2.4 延迟时间的固定范围

#### 问题：固定范围的具体值？

**建议：**
```python
# 延迟时间配置
DELAY_CONFIG = {
    "first_reply": 0,  # 第一条回复延迟（秒）
    "min_delay": 1,    # 后续回复最小延迟（秒）
    "max_delay": 5,    # 后续回复最大延迟（秒）
    "long_reply_threshold": 200,  # 长回复阈值（字符数）
    "long_reply_extra_delay": 2   # 长回复额外延迟（秒）
}

def calculate_delay(reply_index: int, reply_length: int) -> int:
    """
    计算回复延迟
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
    
    return delay
```

#### 问题：延迟是否需要后端验证？

**建议：**
- 前端可以按照JSON中的延迟显示
- 后端也需要验证延迟范围（防止异常值）
- 如果延迟超出范围，使用默认值

```python
def normalize_delay(delay: int) -> int:
    """标准化延迟时间"""
    MIN_DELAY = 0
    MAX_DELAY = 10
    
    if delay < MIN_DELAY:
        return MIN_DELAY
    if delay > MAX_DELAY:
        return MAX_DELAY
    return delay
```

---

### 2.5 错误处理与降级策略

#### 问题：大模型API调用失败

**建议：**
- 重试机制（最多3次）
- 失败后返回友好错误提示
- 保存用户消息（即使AI回复失败）

```python
def process_batch_messages_with_retry(
    agent: Agent,
    user_messages: List[str],
    max_retries: int = 3
) -> Tuple[bool, List[Dict], str]:
    """
    带重试的批量消息处理
    """
    for attempt in range(max_retries):
        try:
            replies = process_batch_messages(agent, user_messages)
            return True, replies, ""
        except Exception as e:
            logger.error(f"处理消息失败 (尝试 {attempt + 1}/{max_retries}): {e}")
            if attempt == max_retries - 1:
                return False, [], f"处理消息失败，请稍后重试: {str(e)}"
            time.sleep(1)  # 等待1秒后重试
    
    return False, [], "处理消息失败"
```

#### 问题：数据库操作失败

**建议：**
- 使用数据库事务
- 失败后回滚
- 记录错误日志

```python
def save_batch_messages_safely(db: Session, ...):
    """
    安全保存批量消息
    """
    try:
        # 保存用户消息
        for msg in user_messages:
            db.add(msg)
        db.flush()
        
        # 保存AI回复
        for reply in ai_replies:
            db.add(reply)
        
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        logger.error(f"保存消息失败: {e}")
        return False
```

---

### 2.6 Prompt删除的详细逻辑

#### 问题：删除Prompt时的级联操作

**建议：**
- 删除Prompt历史时，同时删除对应的知识库索引
- 使用数据库外键级联删除
- 或者：手动删除关联数据

```python
def delete_latest_prompt_summary_with_cascade(
    db: Session,
    user: User,
    agent_id: int
) -> bool:
    """
    删除最新的prompt总结（级联删除）
    """
    # 1. 查找最新的总结
    latest_summary = find_latest_summary(db, agent_id)
    
    if not latest_summary:
        raise ValueError("No summary to delete")
    
    # 2. 删除对应的知识库索引
    if latest_summary.knowledge_index:
        db.delete(latest_summary.knowledge_index)
    
    # 3. 删除prompt历史（硬删除）
    db.delete(latest_summary)
    
    # 4. 重新计算Agent的current_prompt
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    agent.current_prompt = calculate_current_prompt(db, agent)
    
    db.commit()
    return True
```

#### 问题：删除后如何重新计算current_prompt？

**建议：**
- 删除后立即重新计算
- 或者：在查询时动态计算（性能考虑）

```python
def calculate_current_prompt(db: Session, agent: Agent) -> str:
    """
    重新计算Agent的current_prompt
    """
    prompt_parts = [agent.initial_prompt]
    
    # 获取所有未删除的总结（按时间顺序）
    valid_summaries = (
        db.query(AgentPromptHistory)
        .filter(
            AgentPromptHistory.agent_id == agent.id,
            # 硬删除后，数据库中没有is_deleted字段，直接查询存在的记录
        )
        .order_by(AgentPromptHistory.created_at.asc())
        .all()
    )
    
    for summary in valid_summaries:
        prompt_parts.append(summary.added_prompt)
    
    return "\n\n".join(prompt_parts)
```

**注意：** 既然采用硬删除，就不需要`is_deleted`字段了，直接从数据库删除记录即可。

---

### 2.7 知识库检索的实现细节

#### 问题：关键词匹配的算法

**建议：**
- 使用简单的字符串包含匹配
- 支持多个关键词的AND/OR逻辑
- 可以后续优化为全文搜索

```python
def search_by_keywords(
    query: str,
    knowledge_indexes: List[AgentKnowledgeIndex]
) -> List[AgentKnowledgeIndex]:
    """
    关键词搜索
    """
    # 提取关键词（简单实现）
    keywords = extract_keywords(query)
    
    results = []
    for index in knowledge_indexes:
        score = calculate_match_score(index, keywords)
        if score > 0:
            results.append((score, index))
    
    # 按分数排序
    results.sort(key=lambda x: x[0], reverse=True)
    
    return [index for _, index in results]

def extract_keywords(query: str) -> List[str]:
    """
    提取关键词（简单实现）
    可以后续优化为NLP分词
    """
    # 移除停用词
    stop_words = ["的", "了", "在", "是", "我", "你", "他", "她", "它", "我们", "你们", "他们"]
    
    keywords = []
    for word in query.split():
        if word not in stop_words and len(word) > 1:
            keywords.append(word)
    
    return keywords

def calculate_match_score(
    index: AgentKnowledgeIndex,
    keywords: List[str]
) -> int:
    """
    计算匹配分数
    """
    score = 0
    text = index.summary_summary.lower()
    
    for keyword in keywords:
        if keyword.lower() in text:
            score += 1
    
    # 也在topics和keywords中搜索
    if index.topics:
        for topic in index.topics:
            if any(kw in str(topic).lower() for kw in keywords):
                score += 2  # topics匹配权重更高
    
    return score
```

#### 问题：日期解析的实现

**建议：**
- 支持常见的日期表达
- 可以后续优化为NLP日期解析

```python
def parse_date_query(query: str) -> List[Date]:
    """
    解析日期查询
    """
    today = date.today()
    dates = []
    
    # 简单模式匹配
    if "昨天" in query or "yesterday" in query.lower():
        dates.append(today - timedelta(days=1))
    elif "前天" in query:
        dates.append(today - timedelta(days=2))
    elif "今天" in query or "today" in query.lower():
        dates.append(today)
    elif "上周" in query:
        # 上周的所有日期
        last_week_start = today - timedelta(days=today.weekday() + 7)
        dates.extend([last_week_start + timedelta(days=i) for i in range(7)])
    elif "最近7天" in query or "最近一周" in query:
        dates.extend([today - timedelta(days=i) for i in range(7)])
    elif "最近30天" in query or "最近一月" in query:
        dates.extend([today - timedelta(days=i) for i in range(30)])
    
    # 尝试解析具体日期（YYYY-MM-DD格式）
    date_pattern = r'(\d{4})-(\d{1,2})-(\d{1,2})'
    matches = re.findall(date_pattern, query)
    for match in matches:
        try:
            parsed_date = date(int(match[0]), int(match[1]), int(match[2]))
            dates.append(parsed_date)
        except ValueError:
            pass
    
    return list(set(dates))  # 去重
```

---

### 2.8 性能优化考虑

#### 问题：批量消息处理性能

**建议：**
- 如果消息很多，考虑异步处理
- 或者：限制单次处理的消息数量
- 优化数据库查询（批量插入）

#### 问题：知识库检索性能

**建议：**
- 为常用字段添加数据库索引
- 如果数据量大，考虑分页
- 可以缓存热门查询结果

```python
# 数据库索引
class AgentKnowledgeIndex(Base):
    # ... 字段 ...
    
    # 建议添加的索引（在迁移文件中）
    # CREATE INDEX idx_agent_knowledge_date ON agent_knowledge_indexes(agent_id, summary_date);
    # CREATE INDEX idx_agent_knowledge_keywords ON agent_knowledge_indexes USING GIN(keywords);
```

---

### 2.9 日志与监控

#### 建议：添加关键日志点

```python
# 日志记录点
logger.info(f"[Agent] 用户发送批量消息: agent_id={agent_id}, message_count={len(messages)}")
logger.info(f"[Agent] 开始处理批量消息: batch_id={batch_id}")
logger.info(f"[Agent] JSON解析结果: reply_count={len(replies)}")
logger.info(f"[Agent] 保存消息完成: batch_id={batch_id}")
logger.error(f"[Agent] 处理失败: agent_id={agent_id}, error={str(e)}")
```

#### 建议：添加性能监控

```python
import time

def process_with_monitoring(...):
    """
    带监控的处理函数
    """
    start_time = time.time()
    
    try:
        result = process_batch_messages(...)
        
        duration = time.time() - start_time
        logger.info(f"[Agent] 处理耗时: {duration:.2f}秒")
        
        # 如果耗时过长，记录警告
        if duration > 30:
            logger.warning(f"[Agent] 处理耗时过长: {duration:.2f}秒")
        
        return result
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"[Agent] 处理失败，耗时: {duration:.2f}秒, 错误: {str(e)}")
        raise
```

---

### 2.10 测试策略

#### 建议：单元测试覆盖

1. **JSON解析测试**
   - 标准JSON
   - Markdown包裹的JSON
   - 嵌套JSON
   - 解析失败的降级

2. **消息累积测试**
   - 正常累积
   - 超过上限
   - 空消息过滤

3. **Prompt删除测试**
   - 删除最新的一条
   - 尝试跳跃删除（应该失败）
   - 删除后重新计算prompt

4. **知识库检索测试**
   - 日期解析
   - 关键词匹配
   - 组合查询

#### 建议：集成测试

1. **完整流程测试**
   - 创建Agent → 发送消息 → 接收回复
   - 批量消息处理
   - Prompt删除流程

2. **边界情况测试**
   - 并发访问
   - 大量消息
   - 异常情况处理

---

## 三、最终确认的技术决策总结

### 3.1 已确认 ✅

1. **前端等待机制**：前端负责5-15秒随机等待
2. **消息累积**：新消息累积到下次回复
3. **JSON解析**：后端解析，支持嵌套JSON
4. **知识库检索**：关键词匹配 + 日期解析
5. **删除策略**：硬删除，无法恢复
6. **延迟范围**：固定范围（0-10秒）

### 3.2 建议的补充决策

1. **消息数量上限**：单次最多20条消息
2. **单条消息长度**：最多5000字符
3. **延迟配置**：
   - 第一条：0秒
   - 后续：1-5秒随机
   - 长回复（>200字符）：额外+2秒
4. **重试机制**：API调用失败最多重试3次
5. **日志级别**：关键操作记录INFO，错误记录ERROR
6. **性能监控**：处理耗时超过30秒记录警告

---

## 四、实施检查清单

### 4.1 数据库模型

- [ ] Agent模型（包含current_prompt）
- [ ] AgentChatSession模型（单会话）
- [ ] AgentChatMessage模型（包含batch_id, send_delay_seconds）
- [ ] AgentPromptHistory模型（硬删除，无is_deleted字段）
- [ ] AgentKnowledgeIndex模型（包含topics, keywords）
- [ ] 数据库迁移文件
- [ ] 索引优化（日期、关键词等）

### 4.2 API接口

- [ ] Agent管理API（创建、列表、删除）
- [ ] Prompt历史API（列表、删除最新）
- [ ] 批量消息API（POST /agents/{id}/chat/messages/batch）
- [ ] 知识库检索API（GET /agents/{id}/knowledge/search）
- [ ] 错误处理和返回格式

### 4.3 核心功能

- [ ] JSON解析（支持嵌套）
- [ ] 消息累积逻辑
- [ ] 批量消息处理
- [ ] Prompt删除逻辑（硬删除）
- [ ] 知识库检索（关键词+日期）
- [ ] 延迟计算逻辑

### 4.4 错误处理

- [ ] API调用重试机制
- [ ] JSON解析降级策略
- [ ] 数据库事务处理
- [ ] 异常日志记录

### 4.5 测试

- [ ] 单元测试
- [ ] 集成测试
- [ ] 边界情况测试

### 4.6 文档

- [ ] API文档
- [ ] 部署文档
- [ ] 开发文档

---

## 五、建议的下一步行动

1. **创建数据库模型**（优先级：高）
   - 定义所有表结构
   - 创建迁移文件

2. **实现核心API**（优先级：高）
   - Agent管理
   - 批量消息处理
   - JSON解析逻辑

3. **实现知识库检索**（优先级：中）
   - 关键词匹配
   - 日期解析

4. **实现Prompt删除**（优先级：中）
   - 删除逻辑
   - Prompt重新计算

5. **错误处理和测试**（优先级：高）
   - 完善错误处理
   - 编写测试用例

6. **定时任务**（优先级：低）
   - 可以先手动触发测试
   - 后续再实现自动化

---

## 六、潜在风险与应对

### 6.1 技术风险

1. **JSON解析失败率高**
   - 风险：大模型返回格式不标准
   - 应对：优化prompt，明确要求JSON格式；完善降级策略

2. **性能问题**
   - 风险：大量消息处理慢
   - 应对：设置消息上限；异步处理；性能监控

3. **并发冲突**
   - 风险：多设备同时访问
   - 应对：数据库事务；乐观锁

### 6.2 业务风险

1. **用户体验**
   - 风险：等待时间过长
   - 应对：优化等待时间范围；提供进度提示

2. **数据一致性**
   - 风险：删除Prompt后数据不一致
   - 应对：严格的事务处理；删除后重新计算

---

期待您的反馈！如有任何需要进一步讨论的点，请告知。🚀

