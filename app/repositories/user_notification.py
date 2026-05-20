from datetime import datetime, timezone, timedelta

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_notification import UserNotification


class UserNotificationRepository:

    @staticmethod
    async def create(db: AsyncSession, user_id: int, title: str, body: str, severity: str = "info") -> UserNotification:
        notif = UserNotification(user_id=user_id, title=title, body=body, severity=severity)
        db.add(notif)
        await db.commit()
        await db.refresh(notif)
        return notif

    @staticmethod
    async def get_for_user(db: AsyncSession, user_id: int, limit: int = 100, offset: int = 0) -> list[UserNotification]:
        result = await db.execute(
            select(UserNotification)
            .where(UserNotification.user_id == user_id)
            .order_by(UserNotification.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    @staticmethod
    async def delete_one(db: AsyncSession, notif_id: int, user_id: int) -> bool:
        result = await db.execute(
            delete(UserNotification)
            .where(UserNotification.id == notif_id, UserNotification.user_id == user_id)
        )
        await db.commit()
        return result.rowcount > 0

    @staticmethod
    async def delete_older_than(db: AsyncSession, days: int = 30) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        result = await db.execute(
            delete(UserNotification).where(UserNotification.created_at < cutoff)
        )
        await db.commit()
        return result.rowcount
