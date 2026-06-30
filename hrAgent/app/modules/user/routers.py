from fastapi import APIRouter, Depends
from app.modules.user.schemas import UserCreate, UserResponse
from app.modules.user.services import UserService
from app.modules.user.dependencies import get_user_service
from app.core.response import success_response, ResponseSchema

router = APIRouter()

@router.post("/", response_model=ResponseSchema[UserResponse])
async def create_user(
    user_in: UserCreate, 
    user_service: UserService = Depends(get_user_service)
):
    # 路由层极其干净，只负责接参数、调服务、回响应
    new_user = await user_service.register_user(user_in)
    return success_response(data=UserResponse.from_orm(new_user))