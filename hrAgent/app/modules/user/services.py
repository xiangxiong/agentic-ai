from app.modules.user.repositories import UserRepository
from app.modules.user.schemas import UserCreate, UserLogin;
from app.core.exceptions.handlers import BusinessException;
from app.modules.user.security import create_access_token, hash_password, verify_password;

class UserService:
    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo
        
    async def register_user(self, user_in: UserCreate):
        # 1. 业务逻辑校验
        existing_user = await self.user_repo.get_by_email(user_in.email)
        if existing_user:
            raise BusinessException(code=4001, message="该邮箱已被注册")

        # 1、提取除密码外的参数并转换为字典
        user_data = user_in.model_dump()
        # 2、将明文密码哈希化后覆盖写入
        user_data["hashed_password"] = hash_password(user_data["password"])
        # 3. 调用仓储层持久化
        return await self.user_repo.create(user_in.model_dump())


    async def login_user(self,credentials:UserLogin) -> str:
        """ 用户登录服务 """
        # 1. 查找用户是否存在
        user = await self.user_repo.get_by_email(credentials.email)
        if not user:
            raise BusinessException(code=4002, message="邮箱或密码错误")
        # 2. 校验密码是否正确
        if not verify_password(credentials.password,user.hashed_password):
            raise BusinessException(code=4002, message="邮箱或密码错误")
        # 3、登录成功
        token = create_access_token(data={"sub":str(user.id),"email":user.email})
        return token
