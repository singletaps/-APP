# Agent系统设计方案

## 一、需求分析

### 1.1 核心需求

1. **独立的Agent模块**：与现有日常聊天完全隔离
2. **Agent创建与管理**：
   - 用户可以创建Agent，设置初始prompt
   - 创建后初始prompt不可修改
   - 每个Agent只有一个聊天入口（单会话模式）
3. **自动记忆更新机制**：
   - 每天晚上12点，后端自动总结当天Agent与用户的聊天
   - 总结内容追加到Agent的prompt中（形成累积记忆）
4. **知识库索引系统**：
   - 对聊天进行总结索引
   - 记录新增的prompt对应到具体哪天的聊天
   - 建立简易的本地知识库

### 1.2 与现有系统的关系

```
现有系统（日常聊天）
  ├── ChatSession（多会话）
  ├── ChatMessage（消息）
  └── 意图识别 + 路由分发

Agent系统（独立模块）✨
  ├── Agent（每个Agent独立）
  ├── AgentChat（单会话，每个Agent只有一个）
  ├── AgentPromptHistory（prompt演进历史）
  └── AgentKnowledgeIndex（知识库索引）
```

---

## 二、架构设计

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────┐
│                     用户界面层                           │
│  - 日常聊天界面                                          │
│  - Agent管理界面（创建、列表、删除）                      │
│  - Agent聊天界面（每个Agent独立）                         │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│                     API路由层                            │
│  - /chat/* (现有日常聊天)                                 │
│  - /agents/* (新增Agent管理)                              │
│  - /agents/{agent_id}/chat/* (新增Agent聊天)              │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│                   服务层                                 │
│  ┌──────────────┐         ┌──────────────┐             │
│  │ chat/        │         │ agents/      │  ← 新增模块  │
│  │ service.py   │         │ service.py   │             │
│  └──────────────┘         └──────────────┘             │
│                           ┌──────────────┐             │
│                           │ agents/      │             │
│                           │ summarizer.py│  ← 总结服务  │
│                           └──────────────┘             │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│                   定时任务层                             │
│  - 每日12点执行Agent聊天总结任务                          │
│  - 更新Agent prompt                                      │
│  - 建立知识库索引                                        │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│                   数据模型层                             │
│  - models/chat.py (现有，不变)                           │
│  - models/agent.py (新增)                                │
└─────────────────────────────────────────────────────────┘
```

### 2.2 模块隔离设计

**目录结构：**
```
backend/app/
├── chat/                    # 现有日常聊天模块（保持不变）
│   ├── routes.py
│   ├── service.py
│   └── schemas.py
│
├── agents/                  # 新增Agent模块（完全独立）
│   ├── __init__.py
│   ├── routes.py           # Agent管理路由 + Agent聊天路由
│   ├── service.py          # Agent业务逻辑
│   ├── summarizer.py       # 每日总结服务
│   ├── knowledge_index.py  # 知识库索引服务
│   └── schemas.py          # Agent相关Schema
│
├── models/
│   ├── chat.py             # 现有模型（不变）
│   └── agent.py            # 新增Agent模型
│
└── tasks/                   # 新增定时任务模块
    ├── __init__.py
    └── agent_summary.py     # 每日总结定时任务
```

---

## 三、数据模型设计

### 3.1 Agent模型

```python
class Agent(Base):
    """
    Agent实体：代表用户创建的一个智能体
    """
    __tablename__ = "agents"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Agent基本信息
    name = Column(String(255), nullable=False)  # Agent名称（用户可修改）
    initial_prompt = Column(Text, nullable=False)  # 初始prompt（创建后不可修改）
    current_prompt = Column(Text, nullable=False)  # 当前prompt（包含初始prompt + 累计总结）
    
    # 元数据
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    last_summarized_at = Column(DateTime(timezone=True), nullable=True)  # 上次总结时间
    
    # 关联关系
    user = relationship("User", back_populates="agents")
    chat_session = relationship("AgentChatSession", back_populates="agent", uselist=False)  # 一对一
    prompt_history = relationship("AgentPromptHistory", back_populates="agent", cascade="all, delete-orphan")
    knowledge_indexes = relationship("AgentKnowledgeIndex", back_populates="agent", cascade="all, delete-orphan")
```

### 3.2 Agent聊天会话模型

```python
class AgentChatSession(Base):
    """
    Agent聊天会话：每个Agent只有一个会话（单会话模式）
    """
    __tablename__ = "agent_chat_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(Integer, ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    
    # 会话信息
    title = Column(String(255), nullable=True)  # 会话标题（可选，可以自动生成）
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # 关联关系
    agent = relationship("Agent", back_populates="chat_session")
    messages = relationship("AgentChatMessage", back_populates="session", cascade="all, delete-orphan")
```

### 3.3 Agent聊天消息模型

```python
class AgentChatMessage(Base):
    """
    Agent聊天消息：与日常聊天的消息类似，但属于Agent会话
    """
    __tablename__ = "agent_chat_messages"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("agent_chat_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    
    role = Column(String(20), nullable=False)  # user / assistant
    content = Column(Text, nullable=False)
    reasoning_content = Column(Text, nullable=True)  # 深度思考内容（可选）
    images = Column(JSON, nullable=True)  # 用户上传的图片
    generated_images = Column(JSON, nullable=True)  # Agent生成的图片
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # 关联关系
    session = relationship("AgentChatSession", back_populates="messages")
```

### 3.4 Agent Prompt历史模型

```python
class AgentPromptHistory(Base):
    """
    Agent Prompt历史：记录prompt的演进过程
    每次追加总结时，创建一条历史记录
    """
    __tablename__ = "agent_prompt_history"
    
    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(Integer, ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Prompt内容
    added_prompt = Column(Text, nullable=False)  # 本次追加的prompt内容（总结内容）
    full_prompt = Column(Text, nullable=False)  # 追加后的完整prompt
    
    # 时间信息
    summary_date = Column(Date, nullable=False, index=True)  # 总结的日期（对应哪天的聊天）
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # 关联关系
    agent = relationship("Agent", back_populates="prompt_history")
    knowledge_index = relationship("AgentKnowledgeIndex", back_populates="prompt_history", uselist=False)
```

### 3.5 Agent知识库索引模型

```python
class AgentKnowledgeIndex(Base):
    """
    Agent知识库索引：建立总结内容与具体聊天日期的索引关系
    """
    __tablename__ = "agent_knowledge_indexes"
    
    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(Integer, ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    prompt_history_id = Column(Integer, ForeignKey("agent_prompt_history.id", ondelete="CASCADE"), nullable=False, unique=True)
    
    # 索引信息
    summary_date = Column(Date, nullable=False, index=True)  # 对应的聊天日期
    summary_keywords = Column(JSON, nullable=True)  # 总结关键词（用于检索）
    summary_summary = Column(Text, nullable=False)  # 总结摘要（冗余存储，方便检索）
    
    # 统计信息
    message_count = Column(Integer, nullable=False, default=0)  # 当天消息总数
    user_message_count = Column(Integer, nullable=False, default=0)  # 用户消息数
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # 关联关系
    agent = relationship("Agent", back_populates="knowledge_indexes")
    prompt_history = relationship("AgentPromptHistory", back_populates="knowledge_index")
```

### 3.6 更新User模型

```python
# models/user.py 中添加
class User(Base):
    # ... 现有字段 ...
    
    # 一个用户可以创建多个Agent
    agents = relationship(
        "Agent",
        back_populates="user",
        cascade="all, delete-orphan",
    )
```

---

## 四、核心业务流程设计

### 4.1 Agent创建流程

```
用户输入Agent信息
  ↓
1. 创建Agent记录
   - name: Agent名称
   - initial_prompt: 初始prompt（用户输入）
   - current_prompt: 初始prompt（相同）
  ↓
2. 创建AgentChatSession（单会话）
   - agent_id: 关联到新创建的Agent
  ↓
3. 返回Agent信息给用户
```

### 4.2 Agent聊天流程

```
用户发送消息到Agent
  ↓
1. 获取Agent的current_prompt（包含初始prompt + 累计总结）
  ↓
2. 获取Agent会话的历史消息（构建上下文）
  ↓
3. 构建消息：
   - system: current_prompt（作为系统提示词）
   - history: 历史消息
   - user: 当前用户消息
  ↓
4. 调用大模型API
  ↓
5. 保存用户消息和Agent回复
  ↓
6. 流式返回给客户端
```

### 4.3 每日总结流程（定时任务，每天12点执行）

```
定时任务触发
  ↓
1. 查询所有Agent
  ↓
2. 对每个Agent：
   a. 查询当天的聊天消息（从last_summarized_at到现在，或从00:00到现在）
   b. 如果没有新消息，跳过
   c. 如果有新消息：
      - 调用大模型进行总结
      - 生成总结内容
      - 追加总结到Agent的current_prompt
      - 创建AgentPromptHistory记录
      - 创建AgentKnowledgeIndex索引
      - 更新Agent的last_summarized_at
```

### 4.4 总结生成逻辑

**总结Prompt设计：**
```
你是一个专业的对话总结助手。请总结以下Agent与用户在[日期]的对话内容。

Agent的当前身份和特点：
{agent_current_prompt}

对话内容：
{当日所有消息}

请生成一个简洁的总结，包括：
1. 讨论的主要话题
2. 用户的主要需求和偏好
3. Agent的表现和改进建议
4. 需要记住的关键信息

总结应该以第三人称描述，格式如下：
"在[日期]的对话中，用户主要讨论了[话题]。用户表现出[偏好/需求]。
Agent应该[建议]。需要记住：[关键信息]。"
```

---

## 五、API设计

### 5.1 Agent管理API

```python
# GET /agents
# 获取当前用户的所有Agent列表
def list_agents(
    db: Session,
    current_user: User,
    skip: int = 0,
    limit: int = 20
) -> List[AgentSummary]:
    pass

# POST /agents
# 创建新Agent
def create_agent(
    db: Session,
    current_user: User,
    payload: AgentCreate
) -> Agent:
    """
    payload包含：
    - name: Agent名称
    - initial_prompt: 初始prompt
    """
    pass

# GET /agents/{agent_id}
# 获取Agent详情
def get_agent(
    db: Session,
    current_user: User,
    agent_id: int
) -> Agent:
    pass

# PUT /agents/{agent_id}
# 更新Agent信息（只能修改name，不能修改initial_prompt）
def update_agent(
    db: Session,
    current_user: User,
    agent_id: int,
    payload: AgentUpdate
) -> Agent:
    pass

# DELETE /agents/{agent_id}
# 删除Agent（级联删除会话、消息、历史等）
def delete_agent(
    db: Session,
    current_user: User,
    agent_id: int
) -> bool:
    pass

# GET /agents/{agent_id}/history
# 获取Agent的prompt历史
def get_agent_prompt_history(
    db: Session,
    current_user: User,
    agent_id: int
) -> List[AgentPromptHistory]:
    pass

# GET /agents/{agent_id}/knowledge
# 获取Agent的知识库索引
def get_agent_knowledge_index(
    db: Session,
    current_user: User,
    agent_id: int
) -> List[AgentKnowledgeIndex]:
    pass
```

### 5.2 Agent聊天API

```python
# GET /agents/{agent_id}/chat
# 获取Agent的聊天会话和消息
def get_agent_chat(
    db: Session,
    current_user: User,
    agent_id: int
) -> AgentChatSessionWithMessages:
    pass

# POST /agents/{agent_id}/chat/messages
# 发送消息到Agent（非流式）
def send_message_to_agent(
    db: Session,
    current_user: User,
    agent_id: int,
    payload: AgentMessageCreate
) -> List[AgentChatMessage]:
    pass

# POST /agents/{agent_id}/chat/messages/stream
# 发送消息到Agent（流式）
def send_message_to_agent_stream(
    db: Session,
    current_user: User,
    agent_id: int,
    payload: AgentMessageCreate
) -> Iterator[Tuple[str, dict]]:
    """
    流式返回，事件类型：
    - chunk: AI回答的文本块
    - reasoning: 深度思考内容
    - complete: 流结束
    - error: 发生错误
    """
    pass
```

---

## 六、定时任务设计

### 6.1 定时任务框架选择

**选项A：APScheduler（推荐）**
- 轻量级，易于集成
- 支持多种调度方式
- 可以持久化任务

**选项B：Celery Beat**
- 功能强大，但需要Redis/RabbitMQ
- 适合分布式场景

**推荐：APScheduler**（先实现简单版本）

### 6.2 定时任务实现

```python
# tasks/agent_summary.py
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import logging

from backend.app.database.session import SessionLocal
from backend.app.agents.summarizer import summarize_agent_chats

logger = logging.getLogger(__name__)

def schedule_agent_summaries():
    """设置定时任务：每天12点执行Agent总结"""
    scheduler = BackgroundScheduler()
    
    # 每天00:00执行
    scheduler.add_job(
        func=run_daily_summary,
        trigger=CronTrigger(hour=0, minute=0),
        id='daily_agent_summary',
        name='每日Agent聊天总结',
        replace_existing=True
    )
    
    scheduler.start()
    logger.info("Agent每日总结定时任务已启动")

def run_daily_summary():
    """执行每日总结任务"""
    db = SessionLocal()
    try:
        logger.info("开始执行每日Agent聊天总结任务...")
        summarize_agent_chats(db)
        logger.info("每日Agent聊天总结任务完成")
    except Exception as e:
        logger.error(f"每日Agent聊天总结任务失败: {e}", exc_info=True)
    finally:
        db.close()
```

### 6.3 在应用启动时启动定时任务

```python
# main.py
from backend.app.tasks.agent_summary import schedule_agent_summaries

@app.on_event("startup")
async def startup_event():
    # ... 其他启动逻辑 ...
    
    # 启动Agent总结定时任务
    schedule_agent_summaries()
```

---

## 七、关键设计决策与讨论点

### 7.1 关于"初始prompt不可修改"

**需求：** 创建后用户不可修改初始prompt

**问题：**
1. 如果用户发现初始prompt有错误，如何纠正？
2. 是否允许删除Agent后重新创建？

**建议：**
- ✅ **严格模式（推荐）**：初始prompt创建后完全不可修改
  - 优点：保持Agent的"原始记忆"完整
  - 缺点：错误无法纠正
  - 解决方案：允许删除Agent，重新创建

- ⚠️ **宽松模式**：允许在Agent创建后24小时内修改初始prompt
  - 优点：可以纠正错误
  - 缺点：需要额外的时间判断逻辑

**推荐：严格模式**，因为Agent的核心价值在于"累积记忆"，初始prompt的错误可以通过后续对话和总结来纠正。

### 7.2 关于"每天12点总结"

**问题：**
1. 如果用户在12点前创建Agent，当天对话是否会被总结？
2. 如果某天没有对话，是否还需要执行总结？
3. 如果总结失败，如何重试？

**建议：**
- **总结时间范围**：从上次总结时间（或创建时间）到当前12点
- **空对话处理**：如果当天没有新消息，跳过总结
- **失败重试**：可以设置重试机制，或者记录失败日志，人工干预

### 7.3 关于"总结追加到初始prompt"

**问题：**
1. 如果总结内容过长，prompt会无限增长吗？
2. 如何平衡详细度与长度？

**建议方案：**

**方案A：直接追加（简单）**
```
current_prompt = initial_prompt + "\n\n" + summary1 + "\n\n" + summary2 + ...
```
- 优点：简单直接，保留所有历史
- 缺点：可能过长，影响性能

**方案B：摘要合并（推荐）**
- 保留初始prompt + 最近N天的详细总结
- 更早的总结进行二次摘要，合并成"长期记忆"
```
current_prompt = initial_prompt + "\n\n[长期记忆摘要]\n" + recent_summaries
```

**方案C：分段式**
- 初始prompt保持不变
- 总结作为"上下文记忆"，在调用API时动态组合
```
system_prompt = initial_prompt
context_memory = get_recent_summaries()  # 从数据库读取
```

**推荐：方案B**，平衡详细度与性能。

### 7.4 关于"知识库索引"

**问题：**
1. 索引的粒度是什么？（按天、按话题、按消息？）
2. 如何实现检索功能？

**建议：**
- **索引粒度**：按天索引（每天一个索引记录）
- **索引内容**：
  - summary_date: 日期
  - summary_summary: 总结内容（冗余存储，方便检索）
  - summary_keywords: 提取的关键词（JSON数组）
  - message_count: 消息统计

**未来扩展：**
- 可以添加向量数据库（如Milvus、Chroma）实现语义检索
- 可以使用全文搜索引擎（如Elasticsearch）

### 7.5 关于"每个Agent只有一个聊天入口"

**问题：**
1. 单会话模式是否限制太大？
2. 用户想要多个话题的对话怎么办？

**建议：**
- **保持单会话模式**（符合需求）
- 理由：
  - Agent的核心是"累积记忆"，单会话有助于记忆的连贯性
  - 如果用户需要多个话题，可以创建多个Agent
  - 简化设计，降低复杂度

### 7.6 关于与现有系统的集成

**问题：**
1. Agent聊天是否支持图片生成、文件解析等功能？
2. 是否复用现有的AI服务？

**建议：**
- **复用现有AI服务层**（`ai/service.py`）
- **Agent聊天简化功能**：
  - 支持文本对话
  - 支持多模态（图片理解）
  - 暂不支持图片生成（保持Agent的"对话"特性）
  - 可以后续扩展

---

## 八、实施建议

### 8.1 实施阶段

**第一阶段：核心功能（MVP）**
1. 创建Agent数据模型
2. 实现Agent管理API（创建、列表、删除）
3. 实现Agent聊天API（单会话）
4. 实现基本的prompt累积机制（手动触发总结）

**第二阶段：自动化总结**
1. 实现总结服务（`summarizer.py`）
2. 实现定时任务（每天12点）
3. 实现Prompt历史记录

**第三阶段：知识库索引**
1. 实现知识库索引模型
2. 实现索引创建逻辑
3. 实现索引查询API

**第四阶段：优化与扩展**
1. 优化总结质量（prompt优化）
2. 实现总结摘要合并（防止prompt过长）
3. 添加检索功能（如果需要）

### 8.2 技术栈

- **数据库**：SQLAlchemy（现有）
- **定时任务**：APScheduler
- **AI服务**：复用现有的 `ai/service.py`
- **API框架**：FastAPI（现有）

### 8.3 迁移策略

1. **数据库迁移**：使用Alembic创建新的表
2. **向后兼容**：现有聊天模块完全不变
3. **逐步上线**：先上线MVP，再逐步添加功能

---

## 九、潜在问题与解决方案

### 9.1 Prompt过长问题

**问题：** 随着时间推移，current_prompt可能变得很长

**解决方案：**
- 实现总结摘要机制（合并旧总结）
- 限制上下文长度（只使用最近N天的详细总结）
- 考虑使用向量数据库存储长期记忆

### 9.2 总结质量问题

**问题：** 自动总结可能不够准确或有用

**解决方案：**
- 优化总结prompt
- 添加人工审核机制（可选）
- 允许用户查看和反馈总结质量

### 9.3 时区问题

**问题：** 用户在不同时区，12点总结如何定义？

**解决方案：**
- 使用UTC时间（统一）
- 或者使用服务器时区
- 在文档中说明

### 9.4 性能问题

**问题：** 大量Agent同时总结可能导致性能问题

**解决方案：**
- 异步处理（使用任务队列）
- 分批处理（每次处理N个Agent）
- 添加限流机制

---

## 十、需要您确认的问题

### 10.1 功能确认

1. **初始prompt不可修改**：
   - 是否允许删除Agent后重新创建？
   - 如果发现错误，如何处理？

2. **总结机制**：
   - 总结的时间范围？（从上次总结到当前，还是从00:00到当前？）
   - 如果某天没有对话，是否还需要执行总结？

3. **Prompt累积**：
   - 如果总结内容过长，是否需要摘要合并机制？
   - 还是直接无限制追加？

4. **知识库索引**：
   - 索引的主要用途是什么？（检索、统计、分析？）
   - 是否需要检索功能？

### 10.2 技术确认

1. **定时任务**：
   - 是否接受使用APScheduler？
   - 还是需要分布式任务队列（Celery）？

2. **时区处理**：
   - 使用UTC还是服务器时区？

3. **与现有功能集成**：
   - Agent聊天是否需要支持图片生成？
   - 是否需要支持文件解析？

### 10.3 优先级确认

1. **MVP范围**：先实现哪些功能？
2. **上线时间**：是否有时间要求？
3. **扩展计划**：未来是否需要更高级的功能（如向量检索、多模态记忆等）？

---

## 十一、总结

这个Agent系统设计是一个**有趣的记忆累积机制**，类似于：
- 每个Agent有独立的"人格"（初始prompt）
- 通过每日总结形成"记忆"（累积prompt）
- 通过索引建立"知识库"（检索系统）

**核心优势：**
- ✅ 完全独立的模块，不影响现有系统
- ✅ 清晰的业务逻辑和数据模型
- ✅ 可扩展的架构设计

**关键挑战：**
- ⚠️ Prompt长度管理
- ⚠️ 总结质量保证
- ⚠️ 性能优化（大量Agent）

期待您的反馈和讨论！🚀

