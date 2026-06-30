既然你决定采用更适合中大型、长期维护项目的“混合模式（功能领域 + 技术层次）”，那我们就把《FastAPI 项目工程化结构设计指南》中的理论完全落地到代码上。

我们将用 `uv` 作为包管理器，从零开始搭建一个包含**核心配置、统一响应、异步数据库（仓储模式）以及完整的** `user` **模块**的生产级项目架构。

---

## 🗺️ 整体学习路线图

为了让你不至于被庞大的架构直接劝退，我们把整个项目拆解为 **5 个核心实验（Lab）**，每一个实验都是一个独立可运行的里程碑：


| 阶段        | 核心任务            | 学习目标                                                |
| --------- | --------------- | --------------------------------------------------- |
| **Lab 1** | 环境初始化与骨架搭建      | 掌握 `uv` 工具链，建立混合模式目录树                               |
| **Lab 2** | 全局基础设施层（Core）   | 搞定基于 Pydantic Settings 的配置与统一响应/异常拦截                |
| **Lab 3** | 数据库与基础仓储（DB）    | 实现异步 SQLAlchemy 连接与泛型仓储基类                           |
| **Lab 4** | 用户业务模块（Modules） | 编写 `user` 模块的 Model, Schema, Repo, Service 和 Router |
| **Lab 5** | 依赖注入与统一注册（API）  | 串联所有组件，让整个工程真正跑起来                                   |


---



## 🛠️ Lab 1: 环境初始化与骨架搭建

在这个实验中，我们使用当下最火的 Python 包管理工具 `uv` 来初始化项目，并手动建立符合文章规范的目录结构。

### Step 1: 安装 uv 并初始化项目

打开终端，执行以下命令：

```bash
# 安装 uv（如果尚未安装）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 创建并进入项目根目录
mkdir fastapi_enterprise && cd fastapi_enterprise

# 初始化项目（生成 pyproject.toml）
uv init

```



### Step 2: 安装核心依赖

我们需要 FastAPI 以及构建生产级工程所需的周边生态库：

```bash
uv add fastapi uvicorn "pydantic-settings>=2.0.0" "sqlalchemy[asyncio]" asyncpg

```



### Step 3: 手动创建“混合模式”目录树

在根目录下，按照文章推荐的结构，创建以下目录和空文件（你可以使用 IDE 或终端命令创建）：

```text
fastapi_enterprise/
├── app/
│   ├── __init__.py
│   ├── main.py                  # 应用唯一入口
│   ├── api/                     # 路由统一注册层
│   │   ├── __init__.py
│   │   └── router.py
│   ├── core/                    # 核心基础设施层（纯技术，无业务）
│   │   ├── __init__.py
│   │   ├── config.py            # 全局配置
│   │   ├── response.py          # 统一响应格式
│   │   └── exceptions/
│   │       ├── __init__.py
│   │       └── handlers.py      # 全局异常拦截
│   ├── db/                      # 数据库连接与公共仓储
│   │   ├── __init__.py
│   │   ├── base.py              # DeclarativeBase
│   │   ├── connection.py        # 异步 Session 管理
│   │   └── repositories/
│   │       ├── __init__.py
│   │       └── base.py          # 泛型仓储基类
│   └── modules/                 # 业务模块层（按功能领域划分）
│       └── user/
│           ├── __init__.py
│           ├── models.py        # 数据库模型
│           ├── schemas.py       # Pydantic 结构
│           ├── repositories.py  # 用户专属仓储
│           ├── services.py      # 核心业务逻辑
│           ├── routers.py       # 用户路由
│           └── dependencies.py  # 模块专属依赖
├── .env                         # 本地环境变量配置
└── pyproject.toml

```

---



## 🛠️ Lab 2: 全局基础设施层（Core）

现在开始编写代码。首先我们要把项目的“大后方”稳固下来：配置管理、统一响应结构、全局异常捕获。

### Step 1: 类型安全的配置管理

在本地根目录下创建一个 `.env` 文件：

```env
APP_NAME="FastAPI Enterprise"
APP_ENV="dev"
DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/fastapi_db"

```

编写 `app/core/config.py`。文章强调配置要**集中化、类型安全**：

```python
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

```



### Step 2: 规范化统一响应模型

前后端联调的痛苦往往来源于后端返回格式不统一。编写 `app/core/response.py`：

```python
from typing import Any, Generic, TypeVar, Optional
from pydantic import BaseModel

T = TypeVar("T")

class ResponseSchema(BaseModel, Generic[T]):
    """标准 API 响应结构"""
    code: int = 200
    message: str = "success"
    data: Optional[T] = None

def success_response(data: Any = None, message: str = "success") -> ResponseSchema:
    return ResponseSchema(code=200, message=message, data=data)

def fail_response(code: int, message: str, data: Any = None) -> ResponseSchema:
    return ResponseSchema(code=code, message=message, data=data)

```



### Step 3: 全局异常拦截器

当业务代码报错时，我们不希望抛出 500 堆栈给前端。编写 `app/core/exceptions/handlers.py`：

```python
from fastapi import FastAPI, Request
from fastapi.responses import JSONResultResponse # 也可以用普通的 JSONResponse
from fastapi.exceptions import RequestValidationError
from app.core.response import fail_response

class BusinessException(Exception):
    """自定义业务异常基类"""
    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message

def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(BusinessException)
    async def business_exception_handler(request: Request, exc: BusinessException):
        """拦截主动抛出的业务错误"""
        return JSONResponse(
            status_code=200, # 业务错误通常用 200 状态码返回自定义 code
            content=fail_response(code=exc.code, message=exc.message).model_dump()
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """拦截 Pydantic 参数校验错误"""
        errors = exc.errors()
        msg = f"参数校验失败: {errors[0]['loc'][-1]} {errors[0]['msg']}" if errors else "参数错误"
        return JSONResponse(
            status_code=422,
            content=fail_response(code=422, message=msg).model_dump()
        )

```

---



## 🛠️ Lab 3: 数据库与基础仓储（DB）

这一步我们引入**仓储模式（Repository Pattern）**。它的核心作用是将“数据访问代码（SQL、ORM）”与“业务逻辑（Service）”彻底解耦。

### Step 1: 异步连接管理

编写 `app/db/base.py`：

```python
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    """所有 ORM 模型的基类"""
    pass

```

编写 `app/db/connection.py`，管理 SQLAlchemy 异步会话：

```python
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.core.config import settings

# 创建异步引擎
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=True, # 开启 SQL 日志打印
    pool_pre_ping=True
)

# 异步会话工厂
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 依赖注入使用的数据库 Session 生成器"""
    async with AsyncSessionLocal() as session:
        yield session

```



### Step 2: 抽象通用泛型仓储类

编写 `app/db/repositories/base.py`。通过泛型，我们可以把最基础的增删改查（CRUD）抽象出来，避免每个业务表都重复写一遍：

```python
from typing import Generic, Type, TypeVar, Optional, List
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.base import Base

ModelType = TypeVar("ModelType", bound=Base)

class BaseRepository(Generic[ModelType]):
    def __init__(self, model: Type[ModelType], db: AsyncSession):
        self.model = model
        self.db = db

    async def get(self, id: Any) -> Optional[ModelType]:
        return await self.db.get(self.model, id)

    async def create(self, obj_in: dict) -> ModelType:
        db_obj = self.model(**obj_in)
        self.db.add(db_obj)
        await self.db.commit()
        await self.db.refresh(db_obj)
        return db_obj

```

---



## 🛠️ Lab 4: 用户业务模块（Modules）

基础设施就绪后，我们进入业务开发。在混合模式下，`user` 相关的所有代码都是内聚在 `app/modules/user/` 目录中的。

### Step 1: 数据模型（Models）与结构（Schemas）

编写 `app/modules/user/models.py`：

```python
from sqlalchemy import String, Integer
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class UserModel(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

```

编写 `app/modules/user/schemas.py`：

```python
from pydantic import BaseModel, EmailStr

class UserCreate(BaseModel):
    username: str
    email: EmailStr

class UserResponse(BaseModel):
    id: int
    username: str
    email: str

    class Config:
        from_attributes = True

```



### Step 2: 用户仓储（Repository）与服务（Service）

编写 `app/modules/user/repositories.py`，继承自我们的 `BaseRepository`：

```python
from typing import Optional
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.repositories.base import BaseRepository
from app.modules.user.models import UserModel

class UserRepository(BaseRepository[UserModel]):
    def __init__(self, db: AsyncSession):
        super().__init__(UserModel, db)

    # 扩展专属的高级查询方法
    async def get_by_email(self, email: str) -> Optional[UserModel]:
        result = await self.db.execute(select(self.model).filter(self.model.email == email))
        return result.scalars().first()

```

编写 `app/modules/user/services.py`。**记住核心原则：Service 只专注核心业务逻辑，不碰 HTTP 请求，不直接写 SQL。**

```python
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

```



### Step 3: 用户专属依赖注入与路由

编写 `app/modules/user/dependencies.py`，负责将 DB Session 注入到 Repo，再注入到 Service：

```python
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.connection import get_db
from app.modules.user.repositories import UserRepository
from app.modules.user.services import UserService

def get_user_repo(db: AsyncSession = Depends(get_db)) -> UserRepository:
    return UserRepository(db)

def get_user_service(user_repo: UserRepository = Depends(get_user_repo)) -> UserService:
    return UserService(user_repo)

```

编写 `app/modules/user/routers.py`：

```python
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

```

---



## 🛠️ Lab 5: 依赖注入与统一注册（API Entry）

最后一步，我们要通过“统一路由注册”把各个零散的业务模块挂载到 FastAPI 实例上。

### Step 1: 聚合各模块路由

编写 `app/api/router.py`：

```python
from fastapi import APIRouter
from app.modules.user.routers import router as user_router

api_router = APIRouter()

# 统一为所有业务模块加上 /api 前缀和标签
api_router.include_router(user_router, prefix="/users", tags=["用户管理"])

```



### Step 2: 拼装主入口 [main.py](http://main.py)

编写 `app/main.py`：

```python
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

```

---



## 🏃 启动与验证

在根目录下使用 `uv` 运行服务：

```bash
uv run uvicorn app.main:app --reload

```

打开浏览器访问 `[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)`，你将看到一个结构异常精美、职责划分无比清晰的 Swagger UI 界面。

---



### 💡 思考与延伸

你现在已经亲手把这个工程化骨架搭起来了。在实际应用中，你可能还会遇到数据库迁移（Alembic）或者复杂的认证（JWT）。

你可以先尝试在你的本地把上面的代码跑通。**下一步，你是想让我带你模拟一次真实的请求走一遍调用链路，还是想在此基础上加上 JWT 安全认证模块？**