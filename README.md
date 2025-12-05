# AI 聊天应用（前后端一体概览）

一个集成 FastAPI 后端与 Jetpack Compose Android 客户端的智能聊天/Agent 应用。此文档聚焦整体特色与快速上手，详细实现请参考前后端各自的 README。

## 项目亮点
- **全链路 AI 体验**：支持文本对话、SSE 流式回复、图片理解与生成、深度思考展示。
- **Agent 能力**：自定义 Agent、对话记忆与总结、知识库索引检索、批量消息调度。
- **多终端一致体验**：Android 客户端提供 Markdown 渲染、图片预览、会话搜索与管理。
- **即开即用**：后端默认 SQLite，可切换 PostgreSQL/MySQL；前端可运行时配置 API 地址。
- **安全与弹性**：JWT 认证、CORS 控制、可根据环境替换 AI 服务与数据库。

## 目录结构
- `app/`：FastAPI 后端，API、认证、聊天、Agent、AI 能力等。详见 `app/README.md`。
- `AndroidProject/`：Android 客户端（Jetpack Compose + MVVM）。详见 `AndroidProject/README.md`。

## 快速上手（摘要）
1) **启动后端**  
   - Python 3.8+，安装依赖并运行 `python app/run_server.py`（可 `--reload` / 指定 host:port）。  
   - 配置 `.env`（数据库、SECRET_KEY）及 AI API Key，更多细节见后端 README。
2) **运行前端**  
   - 用 Android Studio 打开 `AndroidProject/`，在 `AppConfig.kt` 配置后端地址（真机用局域网 IP，模拟器用 `10.0.2.2`）。  
   - 同步依赖后直接运行，登录/注册后即可体验聊天与 Agent。

## 典型场景
- 个人助理/知识库问答：结合 Agent 记忆与检索，持续对话。
- 多模态创作：文本生成图片、以图生图、图片分析。
- 团队演示/原型：快速搭建前后端联调的 AI 体验。

## 进一步阅读
- 后端实现与 API 列表：`app/README.md`
- Android 客户端说明：`AndroidProject/README.md`


