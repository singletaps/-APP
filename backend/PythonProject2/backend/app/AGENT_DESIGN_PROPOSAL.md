# 智能体（Agent）架构设计方案

## 一、现有架构分析

### 1.1 当前数据流
```
用户输入 
  → 路由层 (routes.py)
  → 服务层 (service.py)
    → 意图识别 (intent_detector.py) - 轻量级判断
    → 根据意图路由:
      - IMAGE_GENERATE → image_generator.py
      - NORMAL_CHAT → ai/service.py (直接调用大模型)
      - FILE_PARSE → ai/service.py
  → 数据库保存
  → 返回客户端
```

### 1.2 现有优势
- ✅ 已有意图识别模块，可以快速判断用户意图
- ✅ 支持流式响应和多模态（文本+图片）
- ✅ 已有图片生成功能独立模块
- ✅ 服务层已实现意图路由分发

### 1.3 可以改进的地方
- ⚠️ 意图识别后直接调用大模型，缺少中间层优化
- ⚠️ 查询prompt没有根据上下文和历史进行优化
- ⚠️ 大模型返回结果没有标准化处理层
- ⚠️ 缺少工具调用（Function Calling）机制

---

## 二、您提出的数据通路设计

```
用户输入 
  → 后端 
  → 智能体prompt（判断+生成查询prompt）  ← 阶段1：增强意图识别与查询优化
  → 大模型API 
  → 智能体prompt（标准化处理）          ← 阶段2：结果标准化
  → 后端 
  → 客户端
```

---

## 三、建议的扩展方案

### 3.1 方案A：渐进式扩展（推荐）⭐

**架构层级：**
```
用户输入
  ↓
路由层 (routes.py)
  ↓
服务层 (service.py)
  ↓
┌─────────────────────────────────────────┐
│  智能体编排层 (agent/orchestrator.py)   │ ← 新增
│  - 意图理解与分析                        │
│  - 上下文管理                            │
│  - Prompt优化生成                        │
│  - 结果标准化                            │
└─────────────────────────────────────────┘
  ↓
┌─────────────────────────────────────────┐
│  现有意图识别 (intent_detector.py)      │ ← 扩展
│  + 查询Prompt生成器                      │ ← 新增
│  + 上下文增强                            │ ← 新增
└─────────────────────────────────────────┘
  ↓
┌─────────────────────────────────────────┐
│  工具/能力路由层                         │ ← 扩展
│  - 图片生成工具                          │
│  - 文件解析工具                          │
│  - 对话工具                              │
│  - 其他工具...                           │
└─────────────────────────────────────────┘
  ↓
大模型API调用
  ↓
┌─────────────────────────────────────────┐
│  结果标准化层 (agent/post_processor.py) │ ← 新增
│  - 格式化输出                            │
│  - 结构化提取                            │
│  - 错误处理与重试                        │
└─────────────────────────────────────────┘
  ↓
数据库保存 & 返回客户端
```

**核心模块设计：**

#### 3.1.1 智能体编排器 (`agent/orchestrator.py`)
```python
class AgentOrchestrator:
    """
    智能体编排器：协调整个智能体流程
    """
    def process_user_input(
        self,
        user_message: str,
        context: ChatContext,  # 包含历史消息、用户信息等
        images: Optional[List[str]] = None
    ) -> AgentResponse:
        """
        主处理流程：
        1. 意图理解与分析（扩展现有意图识别）
        2. 生成优化的查询prompt
        3. 选择工具/能力
        4. 调用大模型或工具
        5. 标准化处理结果
        """
        pass
```

#### 3.1.2 查询Prompt生成器 (`agent/prompt_generator.py`)
```python
class PromptGenerator:
    """
    查询Prompt生成器：
    根据意图、上下文、用户输入生成优化的查询prompt
    """
    def generate_optimized_prompt(
        self,
        intent: IntentType,
        user_message: str,
        context: ChatContext,
        history: List[ChatMessage]
    ) -> OptimizedPrompt:
        """
        生成优化的查询prompt：
        - 根据意图添加上下文信息
        - 根据历史消息优化prompt
        - 根据用户偏好定制prompt
        """
        pass
```

#### 3.1.3 结果标准化处理器 (`agent/post_processor.py`)
```python
class ResultPostProcessor:
    """
    结果标准化处理器：
    对大模型返回的结果进行标准化处理
    """
    def standardize_response(
        self,
        raw_response: str,
        intent: IntentType,
        context: ChatContext
    ) -> StandardizedResponse:
        """
        标准化处理：
        - 格式化输出（Markdown、代码块等）
        - 结构化提取（如果是结构化数据）
        - 错误检测与纠正
        - 敏感信息过滤
        """
        pass
```

#### 3.1.4 扩展的意图识别 (`agent/enhanced_intent_detector.py`)
```python
class EnhancedIntentDetector:
    """
    增强的意图识别：
    基于现有意图识别，添加更细粒度的意图分析
    """
    def detect_intent_with_context(
        self,
        user_message: str,
        context: ChatContext,
        has_files: bool = False
    ) -> EnhancedIntentResult:
        """
        返回：
        - intent: 基础意图类型
        - sub_intent: 子意图（如：图片生成 → 文生图/图生图/改图）
        - entities: 实体提取（如：颜色、尺寸、风格等）
        - confidence: 置信度
        - suggested_tools: 建议使用的工具列表
        """
        pass
```

---

### 3.2 方案B：完全重构为Agent框架

使用成熟的Agent框架（如LangChain、AutoGen等），但这可能改动较大，暂不建议。

---

## 四、具体实施建议

### 4.1 第一阶段：扩展意图识别与Prompt优化（最小改动）

**新增文件：**
- `agent/__init__.py`
- `agent/prompt_generator.py` - 查询Prompt生成器
- `agent/enhanced_intent_detector.py` - 扩展意图识别

**修改文件：**
- `chat/service.py` - 在意图识别后调用Prompt生成器

**功能：**
1. 扩展意图识别，提取更多信息（实体、参数等）
2. 根据意图和历史消息生成优化的查询prompt
3. 保持现有架构，最小改动

**示例流程：**
```python
# chat/service.py 中
intent_result = detect_intent(question, has_files=has_files)
enhanced_intent = enhanced_intent_detector.analyze(question, intent_result, history)

if enhanced_intent.intent == IntentType.NORMAL_CHAT:
    # 生成优化的prompt
    optimized_prompt = prompt_generator.generate(
        user_message=question,
        intent=enhanced_intent,
        history=history,
        context=context
    )
    # 使用优化的prompt调用大模型
    answer = ask_bot(optimized_prompt, ...)
```

### 4.2 第二阶段：添加结果标准化处理

**新增文件：**
- `agent/post_processor.py` - 结果标准化处理器

**功能：**
1. 对大模型返回结果进行格式化
2. 提取结构化信息（如果需要）
3. 错误检测与纠正

### 4.3 第三阶段：完整智能体编排器

**新增文件：**
- `agent/orchestrator.py` - 智能体编排器
- `agent/context_manager.py` - 上下文管理器
- `agent/tools/` - 工具目录

**功能：**
1. 统一的智能体编排入口
2. 上下文管理（会话状态、用户偏好等）
3. 工具链支持（未来可扩展）

---

## 五、关键讨论点

### 5.1 关于"判断+生成查询prompt"阶段

**问题：** 这个阶段与现有意图识别的关系是什么？

**建议：**
- **选项A（推荐）**：扩展现有意图识别
  - 在现有意图识别后，增加一个"Prompt优化"环节
  - 意图识别：判断要做什么（IMAGE_GENERATE/NORMAL_CHAT）
  - Prompt优化：优化具体怎么做（生成更好的查询prompt）
  
- **选项B**：合并为一个环节
  - 意图识别同时输出意图和优化后的prompt
  - 但这样会让意图识别变得复杂

### 5.2 关于"标准化处理"阶段

**问题：** 标准化处理具体要处理什么？

**建议考虑：**
1. **格式化输出**
   - Markdown格式化
   - 代码块高亮
   - 表格格式化

2. **结构化提取**
   - 如果返回JSON，验证格式
   - 提取关键信息

3. **错误处理**
   - 检测不完整回答
   - 检测格式错误
   - 自动纠正或提示

4. **内容过滤**
   - 敏感信息过滤
   - 内容安全检查

5. **上下文补充**
   - 添加相关链接
   - 添加后续建议

### 5.3 关于性能与成本

**问题：** 增加这些环节会增加延迟和成本吗？

**分析：**
- 意图识别：已有，使用轻量模型（成本低、延迟低）
- Prompt优化：可以使用同一个轻量模型（如果只是简单优化）
- 标准化处理：可以后处理，不需要调用API（无额外成本）

**建议：**
- 意图识别和Prompt优化可以合并为一个API调用
- 标准化处理可以是纯代码逻辑，不需要API调用

### 5.4 关于现有功能的兼容性

**问题：** 如何保证现有功能（图片生成、文件解析等）不受影响？

**建议：**
- 采用装饰器模式，在现有流程上"包裹"新功能
- 新功能作为可选层，可以开关
- 逐步迁移，保持向后兼容

---

## 六、推荐的实施路径

### 6.1 最小可行方案（MVP）

**目标：** 在不破坏现有功能的前提下，添加智能体能力

**步骤：**
1. 创建 `agent/prompt_generator.py`
   - 基于现有意图识别结果，生成优化的查询prompt
   - 只在NORMAL_CHAT场景使用（不影响图片生成）

2. 创建 `agent/post_processor.py`
   - 对大模型返回结果进行基本格式化
   - 可选启用（通过配置）

3. 在 `chat/service.py` 中集成
   - 在调用 `ask_bot` 前，先优化prompt
   - 在获取结果后，进行标准化处理

**优势：**
- 改动最小
- 风险最低
- 可以快速验证效果

### 6.2 完整方案

在MVP验证成功后，逐步扩展为完整的智能体架构。

---

## 七、代码结构建议

```
backend/app/
├── agent/                          # 新增：智能体模块
│   ├── __init__.py
│   ├── orchestrator.py            # 智能体编排器（第三阶段）
│   ├── enhanced_intent_detector.py # 扩展意图识别（第一阶段）
│   ├── prompt_generator.py        # Prompt生成器（第一阶段）
│   ├── post_processor.py          # 结果标准化（第二阶段）
│   ├── context_manager.py         # 上下文管理（第三阶段）
│   └── tools/                      # 工具目录（未来）
│       ├── __init__.py
│       ├── image_tool.py          # 图片生成工具
│       └── file_tool.py           # 文件解析工具
├── ai/                             # 现有AI服务层（保持不变）
│   ├── intent_detector.py         # 现有意图识别（可扩展）
│   ├── service.py                 # 现有AI服务
│   └── ...
└── chat/                           # 现有聊天模块（部分修改）
    ├── service.py                 # 集成智能体编排器
    └── ...
```

---

## 八、需要您确认的问题

1. **"判断+生成查询prompt"的具体需求：**
   - 是否需要提取用户意图中的实体信息（如：颜色、尺寸、风格）？
   - 是否需要根据历史对话上下文优化prompt？
   - 是否需要根据用户偏好定制prompt？

2. **"标准化处理"的具体需求：**
   - 主要处理哪些方面？（格式化、结构化、错误纠正等）
   - 是否需要支持多种输出格式？
   - 是否需要内容安全检查？

3. **实施优先级：**
   - 先做哪个部分？（Prompt优化 vs 结果标准化）
   - 是否需要完整方案，还是先做MVP？

4. **性能与成本：**
   - 可以接受多少额外的延迟？（每个环节100-200ms？）
   - 可以接受多少额外的成本？（每轮对话多调用一次轻量模型？）

---

## 九、下一步行动建议

1. **先讨论确定需求细节**（基于本文档的问题）
2. **选择一个最小方案开始实施**（建议先做Prompt优化）
3. **逐步扩展功能**（根据使用反馈）

---

**期待您的反馈和讨论！** 🚀
