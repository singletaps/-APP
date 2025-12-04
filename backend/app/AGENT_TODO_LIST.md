# Agent系统实施 TODO List

## 一、项目结构确认 ✅

### 1.1 目录结构

```
backend/app/
├── agents/                  # 新增：Agent模块（完全独立）
│   ├── __init__.py
│   ├── routes.py           # Agent API路由
│   ├── service.py          # Agent业务逻辑
│   ├── intent_detector.py  # Agent意图识别
│   ├── summarizer.py       # 每日总结服务
│   ├── knowledge_index.py  # 知识库索引服务
│   └── schemas.py          # Agent相关Schema
│
├── chat/                    # 现有：日常聊天模块（完全不变）
│   ├── routes.py           # 不变
│   ├── service.py          # 不变
│   └── schemas.py          # 不变
│
├── models/
│   ├── chat.py             # 现有模型（不变）
│   └── agent.py            # 新增：Agent数据模型（独立数据库表）
│
├── ai/                      # 现有：AI服务层（不变，只复用）
│   ├── client.py           # 不变
│   ├── service.py          # 不变，Agent可以调用
│   └── intent_detector.py  # 不变，Agent创建独立的intent_detector
│
└── main.py                  # 需要添加Agent路由（最小修改）
```

### 1.2 数据库独立性

**确认：**
- Agent使用独立的数据库表（不与chat表混合）
- 表名前缀：`agent_*`（如 `agents`, `agent_chat_sessions`, `agent_chat_messages`）
- 独立的模型文件：`models/agent.py`

---

## 二、TODO List

### 阶段1：数据库模型（优先级：高）

#### ✅ TODO 1.1: 创建Agent数据模型文件
- [ ] 创建 `models/agent.py`
- [ ] 定义 `Agent` 模型
  - [ ] id, user_id, name
  - [ ] initial_prompt (不可修改)
  - [ ] current_prompt (可动态计算)
  - [ ] created_at, updated_at, last_summarized_at
  - [ ] 与User的关联关系
- [ ] 定义 `AgentChatSession` 模型
  - [ ] id, agent_id (unique)
  - [ ] title, created_at, updated_at
  - [ ] 与Agent的一对一关系
- [ ] 定义 `AgentChatMessage` 模型
  - [ ] id, session_id, role
  - [ ] content, reasoning_content
  - [ ] batch_id, batch_index (多消息批次)
  - [ ] send_delay_seconds (AI消息延迟)
  - [ ] created_at
- [ ] 定义 `AgentPromptHistory` 模型
  - [ ] id, agent_id
  - [ ] added_prompt (本次追加的总结)
  - [ ] full_prompt_before (追加前)
  - [ ] full_prompt_after (追加后)
  - [ ] summary_date (总结日期)
  - [ ] created_at
- [ ] 定义 `AgentKnowledgeIndex` 模型
  - [ ] id, agent_id, prompt_history_id
  - [ ] summary_date
  - [ ] summary_summary (总结内容)
  - [ ] topics, key_points, keywords (JSON)
  - [ ] message_count, user_message_count
  - [ ] created_at

**注意事项：**
- ✅ 所有表名使用 `agent_*` 前缀
- ✅ 使用独立的模型文件，不影响现有chat模型
- ✅ 外键关系只关联users表（不关联chat表）

#### ✅ TODO 1.2: 更新User模型（最小修改）
- [ ] 在 `models/user.py` 中添加agents关联关系
  - [ ] 在文件末尾添加：`agents = relationship("Agent", back_populates="user", cascade="all, delete-orphan")`
  - [ ] 确保不影响现有的chat_sessions关系

**注意事项：**
- ✅ 只添加新的relationship，不修改现有代码
- ✅ 使用cascade删除，保持数据一致性
- ✅ 需要导入Agent模型（可以使用字符串形式："Agent"，避免循环导入）

#### ✅ TODO 1.3: 确保Agent模型被导入（重要）
- [ ] 确认项目使用 `Base.metadata.create_all` 创建表（不是Alembic）
- [ ] 在 `main.py` 中添加导入Agent模型
  - [ ] 添加：`from backend.app.models.agent import *`
  - [ ] 确保在 `Base.metadata.create_all(bind=engine)` 之前导入
- [ ] 或者：在 `models/__init__.py` 中导入（如果存在且被使用）
- [ ] 测试表创建：运行应用，检查数据库表是否创建成功

**注意事项：**
- ✅ 只需要导入Agent模型，Base会自动创建表
- ✅ 不影响现有chat表的创建
- ✅ 最小修改：只在main.py添加一行导入

---

### 阶段2：Agent核心功能（优先级：高）

#### ✅ TODO 2.1: 创建Agent模块基础结构
- [ ] 创建 `agents/__init__.py`
- [ ] 创建 `agents/schemas.py`
  - [ ] AgentCreate schema
  - [ ] AgentUpdate schema (只能更新name)
  - [ ] AgentResponse schema
  - [ ] AgentBatchMessageCreate schema
  - [ ] AgentBatchMessageResponse schema
  - [ ] AgentReply schema
  - [ ] AgentPromptHistoryResponse schema
  - [ ] AgentKnowledgeIndexResponse schema

#### ✅ TODO 2.2: 创建Agent服务层
- [ ] 创建 `agents/service.py`
- [ ] 实现Agent管理功能
  - [ ] `create_agent(db, user, name, initial_prompt)` - 创建Agent
  - [ ] `list_agents_for_user(db, user, skip, limit)` - 列表查询
  - [ ] `get_agent_for_user(db, user, agent_id)` - 获取单个Agent
  - [ ] `update_agent_name(db, user, agent_id, new_name)` - 更新名称（只能改名称）
  - [ ] `delete_agent(db, user, agent_id)` - 删除Agent（级联删除）
- [ ] 实现Agent会话管理
  - [ ] `get_or_create_agent_session(db, agent_id)` - 获取或创建会话（单会话）
  - [ ] `get_agent_session_messages(db, session_id)` - 获取会话消息
- [ ] 实现Agent Prompt管理
  - [ ] `calculate_current_prompt(db, agent)` - 计算当前prompt（动态）
  - [ ] `delete_latest_prompt_summary(db, user, agent_id)` - 删除最新总结

**注意事项：**
- ✅ 所有函数都是新函数，不修改现有chat/service.py
- ✅ 函数命名清晰，避免与chat模块冲突

#### ✅ TODO 2.3: 创建Agent意图识别模块
- [ ] 创建 `agents/intent_detector.py`
- [ ] 实现意图识别功能
  - [ ] `detect_agent_intent(user_message, agent_context)` - 主函数
  - [ ] `parse_intent_json(response_text)` - JSON解析
  - [ ] `fallback_keyword_match(text)` - 降级策略
  - [ ] `extract_date_keyword(text)` - 日期关键词提取
- [ ] 定义AgentIntentType枚举
  - [ ] NORMAL_CHAT
  - [ ] KNOWLEDGE_QUERY

**注意事项：**
- ✅ 独立的意图识别模块，不修改ai/intent_detector.py
- ✅ 复用ai/client.py和ai/service.py的基础设施

#### ✅ TODO 2.4: 创建知识库索引服务
- [ ] 创建 `agents/knowledge_index.py`
- [ ] 实现知识库检索功能
  - [ ] `search_agent_knowledge(db, agent_id, dates, keywords)` - 主查询函数
  - [ ] `parse_date_query(query)` - 日期解析
  - [ ] `extract_keywords(query)` - 关键词提取
  - [ ] `calculate_match_score(index, keywords)` - 匹配分数计算
- [ ] 实现日期解析逻辑
  - [ ] 支持"昨天"、"前天"、"上周"
  - [ ] 支持"最近7天"、"最近30天"
  - [ ] 支持具体日期"2024-01-15"

**注意事项：**
- ✅ 独立的服务模块
- ✅ 与现有chat模块完全隔离

---

### 阶段3：批量消息处理（优先级：高）

#### ✅ TODO 3.1: 实现批量消息处理核心逻辑
- [ ] 在 `agents/service.py` 中添加批量消息处理
  - [ ] `send_batch_messages_to_agent(db, user, agent_id, user_messages)` - 主函数
  - [ ] `process_batch_messages_with_intent(agent, user_messages, history)` - 带意图识别的处理
  - [ ] `query_knowledge_base(db, agent_id, query_params)` - 查询知识库
  - [ ] `build_agent_prompt(agent, knowledge_context, session_id, db)` - 构建增强prompt
- [ ] 实现消息保存
  - [ ] `save_batch_user_messages(db, session_id, messages, batch_id)` - 保存用户消息
  - [ ] `save_batch_ai_replies(db, session_id, replies, batch_id)` - 保存AI回复

#### ✅ TODO 3.2: 实现JSON解析逻辑
- [ ] 在 `agents/service.py` 中添加JSON解析
  - [ ] `parse_nested_json(json_string)` - 解析嵌套JSON
  - [ ] `safe_parse_agent_reply(raw_response)` - 安全解析（带降级）
  - [ ] `normalize_replies(replies)` - 标准化回复格式
  - [ ] `clean_markdown_code_block(text)` - 清理Markdown代码块
- [ ] 实现降级策略
  - [ ] JSON解析失败时返回单条消息
  - [ ] 记录错误日志

#### ✅ TODO 3.3: 实现延迟计算逻辑
- [ ] 在 `agents/service.py` 中添加延迟计算
  - [ ] `calculate_reply_delay(reply_index, reply_length)` - 计算延迟
  - [ ] `normalize_delay(delay)` - 标准化延迟（0-10秒范围）

**注意事项：**
- ✅ 所有新函数，不修改现有代码
- ✅ 延迟配置使用常量，易于调整

---

### 阶段4：API路由（优先级：高）

#### ✅ TODO 4.1: 创建Agent路由文件
- [ ] 创建 `agents/routes.py`
- [ ] 实现Agent管理API
  - [ ] `GET /agents` - 获取Agent列表
  - [ ] `POST /agents` - 创建Agent
  - [ ] `GET /agents/{agent_id}` - 获取Agent详情
  - [ ] `PUT /agents/{agent_id}` - 更新Agent（只能改名称）
  - [ ] `DELETE /agents/{agent_id}` - 删除Agent
- [ ] 实现Agent聊天API
  - [ ] `GET /agents/{agent_id}/chat` - 获取Agent会话和消息
  - [ ] `POST /agents/{agent_id}/chat/messages/batch` - 批量发送消息（核心API）
- [ ] 实现Prompt管理API
  - [ ] `GET /agents/{agent_id}/prompt-history` - 获取Prompt历史
  - [ ] `DELETE /agents/{agent_id}/prompt-history/latest` - 删除最新总结
- [ ] 实现知识库API
  - [ ] `GET /agents/{agent_id}/knowledge/search` - 检索知识库
  - [ ] `GET /agents/{agent_id}/knowledge` - 获取所有知识库索引

**注意事项：**
- ✅ 所有路由使用 `/agents/*` 前缀
- ✅ 不影响现有的 `/chat/*` 路由
- ✅ 使用相同的认证机制（get_current_user）

#### ✅ TODO 4.2: 注册Agent路由（最小修改）
- [ ] 在 `main.py` 中注册Agent路由
  - [ ] 添加导入：`from backend.app.agents.routes import router as agents_router`
  - [ ] 添加注册：`app.include_router(agents_router)`
  - [ ] 确保不影响现有的路由（只添加，不修改）

**注意事项：**
- ✅ 只添加2行代码，不修改现有代码
- ✅ routes.py中已经定义了prefix="/agents"，不需要在include_router中再指定
- ✅ 参考现有的chat路由注册方式

---

### 阶段5：每日总结功能（优先级：中）

#### ✅ TODO 5.1: 创建总结服务
- [ ] 创建 `agents/summarizer.py`
- [ ] 实现总结生成功能
  - [ ] `summarize_agent_chats(db, agent_id, target_date)` - 总结指定日期的聊天
  - [ ] `generate_summary_prompt(agent, messages, date)` - 生成总结prompt
  - [ ] `create_prompt_history(db, agent, summary_content, summary_date)` - 创建Prompt历史
  - [ ] `create_knowledge_index(db, agent, prompt_history, summary_content)` - 创建知识库索引
- [ ] 实现总结内容处理
  - [ ] `extract_topics_from_summary(summary)` - 提取话题
  - [ ] `extract_keywords_from_summary(summary)` - 提取关键词
  - [ ] `extract_key_points_from_summary(summary)` - 提取关键点

#### ✅ TODO 5.2: 创建定时任务
- [ ] 创建 `tasks/__init__.py`
- [ ] 创建 `tasks/agent_summary.py`
  - [ ] `schedule_agent_summaries()` - 设置定时任务
  - [ ] `run_daily_summary()` - 执行每日总结
  - [ ] `summarize_all_agents(db)` - 总结所有Agent
- [ ] 在 `main.py` 中启动定时任务
  - [ ] `from backend.app.tasks.agent_summary import schedule_agent_summaries`
  - [ ] 在 `startup_event` 中调用 `schedule_agent_summaries()`

**注意事项：**
- ✅ 使用APScheduler（轻量级）
- ✅ 在应用启动时启动定时任务
- ✅ 确保定时任务不影响主应用

---

### 阶段6：错误处理与验证（优先级：中）

#### ✅ TODO 6.1: 实现输入验证
- [ ] 在 `agents/service.py` 中添加验证函数
  - [ ] `validate_batch_messages(messages)` - 验证批量消息
    - [ ] 消息数量上限（20条）
    - [ ] 单条消息长度限制（5000字符）
    - [ ] 空消息过滤
  - [ ] `validate_agent_name(name)` - 验证Agent名称
  - [ ] `validate_initial_prompt(prompt)` - 验证初始prompt

#### ✅ TODO 6.2: 实现错误处理
- [ ] 添加重试机制
  - [ ] `process_batch_messages_with_retry(agent, messages, max_retries)` - 带重试的处理
  - [ ] API调用失败重试3次
- [ ] 添加数据库事务处理
  - [ ] `save_batch_messages_safely(db, ...)` - 安全保存（带事务）
  - [ ] 失败时回滚
- [ ] 添加错误日志
  - [ ] 关键操作记录INFO日志
  - [ ] 错误记录ERROR日志（包含异常详情）

#### ✅ TODO 6.3: 实现并发控制
- [ ] 添加乐观锁（可选）
  - [ ] 在AgentChatSession中添加version字段
  - [ ] 更新时检查version

**注意事项：**
- ✅ 错误处理要完善，不影响现有功能
- ✅ 日志记录要详细，便于调试

---

### 阶段7：测试与文档（优先级：中）

#### ✅ TODO 7.1: 单元测试
- [ ] 创建 `tests/agents/` 目录
- [ ] 测试数据模型
  - [ ] Agent创建、查询、更新、删除
  - [ ] 会话创建（单会话模式）
  - [ ] Prompt历史管理
- [ ] 测试意图识别
  - [ ] 正常对话识别
  - [ ] 知识库查询识别
  - [ ] JSON解析
  - [ ] 降级策略
- [ ] 测试批量消息处理
  - [ ] JSON解析（标准、嵌套、失败）
  - [ ] 延迟计算
  - [ ] 知识库查询注入

#### ✅ TODO 7.2: 集成测试
- [ ] 测试完整流程
  - [ ] 创建Agent → 发送消息 → 接收回复
  - [ ] 批量消息处理
  - [ ] 知识库查询
  - [ ] Prompt删除
- [ ] 测试边界情况
  - [ ] 消息数量上限
  - [ ] 空消息过滤
  - [ ] 并发访问

#### ✅ TODO 7.3: API文档
- [ ] 添加API文档注释
- [ ] 测试所有API端点
- [ ] 验证请求/响应格式

---

### 阶段8：优化与扩展（优先级：低）

#### ✅ TODO 8.1: 性能优化
- [ ] 优化数据库查询
  - [ ] 添加必要的索引
  - [ ] 批量插入优化
- [ ] 优化意图识别
  - [ ] 缓存常见意图（可选）
  - [ ] 关键词匹配优先（可选）

#### ✅ TODO 8.2: 功能扩展
- [ ] Prompt摘要合并（防止prompt过长）
- [ ] 知识库向量检索（未来）
- [ ] 多模态支持（图片理解，未来）

---

## 三、关键约束与原则

### 3.1 最小侵入性原则 ✅

**已确认的原则：**
- ✅ Agent模块完全独立，不影响现有chat模块
- ✅ 数据库表独立（agent_*前缀）
- ✅ 路由独立（/agents/*前缀）
- ✅ 模型文件独立（models/agent.py）
- ✅ 只添加新函数，不修改现有函数
- ✅ 复用现有基础设施（ai/client.py, ai/service.py）
- ✅ main.py只添加2行代码（导入和注册路由）

### 3.2 路径结构确认 ✅

**已确认的路径：**
```
backend/app/agents/xxx  ✅
```

**确认：** 
- 目录：`backend/app/agents/` （注意是agents，不是agent）
- 路由前缀：`/agents`
- 标签：`tags=["agents"]`

### 3.3 数据库共享Base，但表独立 ✅

**确认：**
- ✅ 使用相同的 `Base` (from backend.app.database.session import Base)
- ✅ 表名独立（agent_*前缀）
- ✅ 模型类独立（在models/agent.py中定义）
- ✅ 不修改models/__init__.py（或只添加导入）

### 3.3 数据库独立性确认 ✅

**Agent数据库表：**
- `agents` - Agent主表
- `agent_chat_sessions` - Agent会话表
- `agent_chat_messages` - Agent消息表
- `agent_prompt_history` - Prompt历史表
- `agent_knowledge_indexes` - 知识库索引表

**与现有chat表的区别：**
- chat表：`chat_sessions`, `chat_messages`
- agent表：`agent_chat_sessions`, `agent_chat_messages`
- 完全独立的表，不共享数据

---

## 四、实施优先级总结

### 高优先级（必须完成）
1. ✅ 阶段1：数据库模型
2. ✅ 阶段2：Agent核心功能
3. ✅ 阶段3：批量消息处理
4. ✅ 阶段4：API路由

### 中优先级（重要功能）
5. ✅ 阶段5：每日总结功能
6. ✅ 阶段6：错误处理与验证
7. ✅ 阶段7：测试与文档

### 低优先级（优化）
8. ✅ 阶段8：优化与扩展

---

## 五、关键细节确认

### 5.1 路径结构确认 ✅

**已确认：**
- ✅ 目录路径：`backend/app/agents/` （注意是agents复数）
- ✅ 路由前缀：`/agents`
- ✅ 标签：`tags=["agents"]`

### 5.2 数据库结构确认 ✅

**已确认：**
- ✅ 使用相同的Base（from backend.app.database.session import Base）
- ✅ 表名独立（agent_*前缀）
- ✅ 模型文件独立（models/agent.py）
- ✅ 外键只关联users表（不关联chat表）
- ✅ 使用Base.metadata.create_all自动创建表（不是Alembic）

**需要确保：**
- [ ] 在main.py中导入Agent模型，确保表被创建
- [ ] 或者创建models/agent.py后，在main.py中添加：`from backend.app.models.agent import *`

### 5.3 最小修改main.py ✅

**当前main.py结构：**
```python
from backend.app.chat.routes import router as chat_router

# 注册路由
app.include_router(chat_router)
```

**需要添加（只添加，不修改）：**
```python
from backend.app.agents.routes import router as agents_router  # 新增
from backend.app.models.agent import *  # 新增（确保Agent模型被导入）

# 注册路由
app.include_router(agents_router)  # 新增
```

### 5.4 需要确认的问题
- [ ] 确认路径是 `backend/app/agents/` ✅
- [ ] 确认路由前缀是 `/agents` ✅
- [ ] 确认Agent使用独立的数据库表 ✅
- [ ] 是否需要前端等待逻辑的文档说明？
- [ ] 是否需要API调用示例？
- [ ] 是否需要部署说明？

---

## 六、检查清单

### 实施前检查
- [ ] 确认所有TODO项已理解
- [ ] 确认路径结构
- [ ] 确认数据库设计
- [ ] 确认API设计

### 实施后检查
- [ ] 所有新功能不依赖现有chat模块
- [ ] 所有新函数不修改现有函数
- [ ] 所有新路由不影响现有路由
- [ ] 所有新表不影响现有表

---

期待您的确认和反馈！🚀
