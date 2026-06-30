from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # 通过 pydantic 自动校验类型
    APP_NAME: str = "FastAPI App"
    APP_ENV: str = "prod"
    DATABASE_URL: str
    
    # 读取根目录下的 .env 文件
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8",
        extra="ignore"
    )

# 全局单例配置对象
settings = Settings()