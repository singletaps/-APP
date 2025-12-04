# backend/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.database.session import Base, engine
from backend.app.auth.routes import router as auth_router
from backend.app.ai.routes import router as ai_router
from backend.app.chat.routes import router as chat_router

# 创建数据库表（确保所有模型已被导入）
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Chatbot Backend - CORS TEST")

# 👉 先用最开放的配置，把所有 Origin 都放行
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_origin_regex=".*",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(auth_router)
app.include_router(ai_router)
app.include_router(chat_router)


@app.get("/")
def read_root():
    # 为了方便确认你改的文件真的被用到了，这里加一行特别的文字
    return {"message": "Chatbot backend is running (CORS TEST)"}
