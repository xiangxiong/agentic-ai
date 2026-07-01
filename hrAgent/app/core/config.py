from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # 通过 pydantic 自动校验类型
    APP_NAME: str = "FastAPI App"
    APP_ENV: str = "prod"
    DATABASE_URL: str

    # 追加 JWT 核心配置
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES:int = 60
    
    # 读取根目录下的 .env 文件
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8",
        extra="ignore"
    )

# 全局单例配置对象
settings = Settings()