from sqlalchemy import select, desc, func, text
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from app.models import SensorReading
from app.repositories.base import BaseRepository


# Bucket size in seconds per period — gives ~100-200 chart points
_BUCKET_SECONDS = {
    '24h': 15 * 60,    # 15 min → 96 buckets
    '7d':  60 * 60,    # 1 hour → 168 buckets
    '30d': 3 * 60 * 60,  # 3 hours → 240 buckets
}


class SensorRepository(BaseRepository):
    model = SensorReading

    @classmethod
    async def get_last_reading(cls, db: AsyncSession) -> SensorReading | None:
        result = await db.execute(
            select(cls.model)
            .order_by(desc(cls.model.recorded_at))
            .limit(1)
        )
        return result.scalar_one_or_none()

    @classmethod
    async def get_data_by_period(
            cls,
            period_start: datetime,
            period_key: str,
            db: AsyncSession):
        bucket_secs = _BUCKET_SECONDS.get(period_key, 15 * 60)

        # Aggregate into time buckets and return averaged sensor values
        sql = text("""
            SELECT
                to_timestamp(
                    floor(extract(epoch from recorded_at) / :bucket_secs) * :bucket_secs
                ) AS recorded_at,
                round(avg(temperature)::numeric, 1)   AS temperature,
                round(avg(humidity)::numeric, 1)      AS humidity,
                round(avg(light_level)::numeric, 0)::int AS light_level
            FROM sensor_readings
            WHERE recorded_at >= :period_start
            GROUP BY floor(extract(epoch from recorded_at) / :bucket_secs)
            ORDER BY 1 ASC
        """)

        result = await db.execute(sql, {
            'bucket_secs': bucket_secs,
            'period_start': period_start,
        })
        rows = result.all()

        class _Row:
            __slots__ = ('recorded_at', 'temperature', 'humidity', 'light_level')
            def __init__(self, recorded_at, temperature, humidity, light_level):
                self.recorded_at = recorded_at
                self.temperature = float(temperature) if temperature is not None else None
                self.humidity = float(humidity) if humidity is not None else None
                self.light_level = int(light_level) if light_level is not None else None

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
