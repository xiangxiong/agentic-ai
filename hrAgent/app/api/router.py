from fastapi import APIRouter
from app.modules.user.routers import router as user_router

api_router = APIRouter()

# 统一为所有业务模块加上 /api 前缀和标签
api_router.include_router(user_router, prefix="/users", tags=["用户管理"])