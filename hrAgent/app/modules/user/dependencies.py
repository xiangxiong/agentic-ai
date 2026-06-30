from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.connection import get_db
from app.modules.user.repositories import UserRepository
from app.modules.user.services import UserService

def get_user_repo(db: AsyncSession = Depends(get_db)) -> UserRepository:
    return UserRepository(db)

def get_user_service(user_repo: UserRepository = Depends(get_user_repo)) -> UserService:
    return UserService(user_repo)