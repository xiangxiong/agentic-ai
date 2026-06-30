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