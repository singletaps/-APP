# backend/config/settings.py
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "Chatbot Backend"
    SECRET_KEY: str = "change_me_to_a_random_secret"  # 生产环境务必改成随机长字符串！
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # token 有效期：7天
    SQLALCHEMY_DATABASE_URL: str = "sqlite:///E:/PythonProject2/chatbot.db"  # 使用根目录的数据库文件（绝对路径）

    class Config:
        env_file = ".env"  # 可以用 .env 覆盖这些配置


settings = Settings()
