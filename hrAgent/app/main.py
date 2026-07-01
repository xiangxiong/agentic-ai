from fastapi import FastAPI
from app.core.config import settings
from app.core.exceptions.handlers import register_exception_handlers
from app.api.router import api_router

def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        description="基于功能领域混合模式的 FastAPI 工程化骨架",
        version="1.0.0"
    )
    
    # 1. 注册全局异常处理器
    register_exception_handlers(app) 

    # 2. 挂载路由聚合器
    app.include_router(api_router, prefix="/api")

    return app
    
app = create_app()