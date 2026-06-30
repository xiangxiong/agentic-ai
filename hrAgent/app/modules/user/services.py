from app.modules.user.repositories import UserRepository
from app.modules.user.schemas import UserCreate
from app.core.exceptions.handlers import BusinessException

class UserService:
    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo

    async def register_user(self, user_in: UserCreate):
        # 1. 业务逻辑校验
        existing_user = await self.user_repo.get_by_email(user_in.email)
        if existing_user:
            raise BusinessException(code=4001, message="该邮箱已被注册")
        
        # 2. 调用仓储层持久化
        return await self.user_repo.create(user_in.model_dump())