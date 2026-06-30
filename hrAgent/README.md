
## 项目分层架构
hr-agent/
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

## 参考文献:
https://blog.mapin.net/posts/FastAPI%20%E9%A1%B9%E7%9B%AE%E5%B7%A5%E7%A8%8B%E5%8C%96%E7%BB%93%E6%9E%84%E8%AE%BE%E8%AE%A1%E6%8C%87%E5%8D%97#%E5%8D%95%E4%B8%80%E8%81%8C%E8%B4%A3%E5%8E%9F%E5%88%99-single-responsibility-principle


## 启动项目:
```

uv run uvicorn app.main:app --reload

```