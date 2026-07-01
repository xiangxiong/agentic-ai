from datetime import datetime,timedelta,timezone
import jwt
from passlib.context import CryptContext
from app.core.config import Settings

# 初始化密码哈希上下文 (使用 bcrypt 算法)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password:str) -> str:
    """ 明文密码哈希化 """
    return pwd_context.hash(password);

def verify_password(plain_password:str,hashed_password:str) -> bool:
    """验证明文密码与哈希密码是否匹配"""
    return pwd_context.verify(plain_password,hashed_password)

def create_access_token(data:dict) -> str:
    """生成带有过期时间的 JWT Access Token"""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=Settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp":expire})

    encoded_jwt = jwt.encode(
        to_encode,
        Settings.JWT_SECRET_KEY,
        algorithm=Settings.JWT_ALGORITHM
    )

    return encoded_jwt


