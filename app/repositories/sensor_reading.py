from sqlalchemy import select, desc, func, text
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta

from app.models import SensorReading
from app.repositories.base import BaseRepository


# Points target per period — enough for a smooth chart without overloading
_BUCKET_MINUTES = {
    '24h': 15,    # 96 buckets
    '7d':  60,    # 168 buckets
    '30d': 180,   # 240 buckets
}


class SensorRepository(BaseRepository):
    model = SensorReading

    @classmethod
    async def get_last_reading(cls, db: AsyncSession) -> SensorReading | None:
        result = await db.execute(
            select(cls.model).
            order_by(desc(cls.model.recorded_at))
            .limit(1))
        return result.scalar_one_or_none()

    @classmethod
    async def get_data_by_period(
            cls,
            period_start: datetime,
            period_key: str,
            db: AsyncSession):
        bucket_minutes = _BUCKET_MINUTES.get(period_key, 15)

        # Bucket timestamp to a fixed interval and return averaged values per bucket
        # date_trunc rounds to the floor of the bucket using epoch arithmetic
        bucket_expr = text(
            f"to_timestamp(floor(extract(epoch from recorded_at) / {bucket_minutes * 60}) * {bucket_minutes * 60})"
        ).columns(name='bucket')

        stmt = (
            select(
                func.to_timestamp(
                    func.floor(
                        func.extract('epoch', cls.model.recorded_at) / (bucket_minutes * 60)
                    ) * (bucket_minutes * 60)
                ).label('recorded_at'),
                func.avg(cls.model.temperature).label('temperature'),
                func.avg(cls.model.humidity).label('humidity'),
                func.avg(cls.model.light_level).label('light_level'),
            )
            .where(cls.model.recorded_at >= period_start)
            .group_by(text(
                f"floor(extract(epoch from recorded_at) / {bucket_minutes * 60})"
            ))
            .order_by(text(
                f"floor(extract(epoch from recorded_at) / {bucket_minutes * 60})"
            ))
        )

        result = await db.execute(stmt)
        rows = result.all()

        # Convert raw rows to SensorReading-like objects the service expects
        class _Row:
            def __init__(self, recorded_at, temperature, humidity, light_level):
                self.recorded_at = recorded_at
                self.temperature = round(float(temperature), 1) if temperature is not None else None
                self.humidity = round(float(humidity), 1) if humidity is not None else None
                self.light_level = int(round(float(light_level))) if light_level is not None else None

        return [_Row(r.recorded_at, r.temperature, r.humidity, r.light_level) for r in rows]

    @classmethod
    async def get_count(cls, period_start: datetime, db: AsyncSession):
        count_stmt = select(func.count()).where(
            cls.model.recorded_at >= period_start
        )
        return await db.scalar(count_stmt)

    @classmethod
    async def get_stats(cls, period_start: datetime, db: AsyncSession):
        stats_stmt = select(
            func.min(cls.model.temperature),
            func.max(cls.model.temperature),
            func.round(func.avg(cls.model.temperature), 1),

            func.min(cls.model.humidity),
            func.max(cls.model.humidity),
            func.round(func.avg(cls.model.humidity), 1),

            func.min(cls.model.light_level),
            func.max(cls.model.light_level),
            func.round(func.avg(cls.model.light_level), 1),
        ).where(cls.model.recorded_at >= period_start)

        result = await db.execute(stats_stmt)
        return result.one()
