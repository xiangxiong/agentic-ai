from pydantic import BaseModel, EmailStr

class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str  # 注册时接收明文密码

class UserLogin(BaseModel):
    """ 新增用户登录请求模型 """
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: int
    username: str
    email: str

    class Config:
        from_attributes = True

class TokenResponse(BaseModel):
    """ 新增Token 返回模型 """
    access_token:str
    token_type:str = "bearer"