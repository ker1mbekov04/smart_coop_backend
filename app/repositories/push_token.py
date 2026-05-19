from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import PushToken
from app.repositories.base import BaseRepository


class PushTokenRepository(BaseRepository):
    model = PushToken

    @classmethod
    async def get_token(
            cls,
            token: str,
            db: AsyncSession):
        result = await db.execute(
            select(cls.model).
            where(cls.model.token == token))
        return result.scalar_one_or_none()

    @classmethod
    async def create_token(
            cls,
            user_id: int,
            token: str,
            platform: str,
            db: AsyncSession):
        new_token = cls.model(
            user_id=user_id,
            token=token,
            platform=platform)

        db.add(new_token)
        await db.flush()
        return new_token

    @classmethod
    async def get_active_tokens_by_user(cls, user_id: int, db: AsyncSession):
        result = await db.execute(
            select(cls.model).where(
                cls.model.user_id == user_id,
                cls.model.is_active == True
            )
        )
        return result.scalars().all()