import time
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.device_state import DeviceStateRepository
from app.repositories.event_log import EventLogRepository
from app.repositories.system_mode import SystemModeRepository
from app.schemas.system import SystemHealthConnResponse, SystemStatusResponse, CameraItems
from app.services.camera_service import camera_status_service
from app.services.sensor_service import sensor_current_service

START_TIME = time.time()


async def system_health_service(db: AsyncSession):
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        raise HTTPException(status_code=503,
                            detail={"status":"unhealthy",
                                     "database": "disconnected"})
    return SystemHealthConnResponse(
        status="healthy",
        database="connected",
        version="1.0.0",
        uptime_seconds=int(time.time() - START_TIME)
    )


async def system_status_service(user_id: int, db: AsyncSession):
    last_sensor = await sensor_current_service(db)
    last_device = await DeviceStateRepository.get_last(db)
    active_mode = await SystemModeRepository.get_last(db)
    recent_events = await EventLogRepository.filter_for_history(
        period_start=datetime.now(timezone.utc) - timedelta(days=1), limit=5, offset=0, db=db)
    if last_sensor:
        diff = datetime.now(timezone.utc) - last_sensor.recorded_at
        is_device_online = diff.total_seconds() < 60
        device_last_seen = last_sensor.recorded_at
    else:
        is_device_online = False
        device_last_seen = None

    camera_status_data = await camera_status_service()
    camera_status = CameraItems(
        is_online=camera_status_data.is_online,
        last_frame_size_bytes=camera_status_data.last_frame_size_bytes,
        last_frame_age_seconds=camera_status_data.last_frame_age_seconds,
    )
    return SystemStatusResponse(
        last_sensor=last_sensor,
        last_device=last_device,
        active_mode=active_mode,
        recent_events=recent_events,
        is_device_online=is_device_online,
        device_last_seen=device_last_seen,
        camera_status=camera_status,
    )