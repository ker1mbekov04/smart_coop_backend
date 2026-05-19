from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status
from typing import List

from app.models.feed_schedule import FeedSchedule
from app.models.device_command import DeviceCommand, CommandType
from app.models.event_log import EventLog, EventType, Severity
from app.repositories.event_log import EventLogRepository
from app.schemas.feed_shedule import (
    FeedScheduleItem,
    FeedScheduleCreateRequest,
    FeedScheduleUpdateRequest,
    FeedTriggerRequest,
    FeedTriggerResponse,
)
from app.repositories.feed_shedule import FeedScheduleRepository
from app.repositories.device_command import DeviceCommandRepository
from app.services.mqtt_publisher import (
    publish_command_to_device,
    publish_config_to_device,
    threshold_to_dict,
    feed_schedule_to_dict,
)
from app.services.threshold_service import get_current_thresholds
from app.services import push_service


async def _push_config(db: AsyncSession):
    """Публикует актуальный конфиг (пороги + расписание) на устройство."""
    thresholds = await get_current_thresholds(db)
    schedules = await FeedScheduleRepository.get_active(db)
    await publish_config_to_device(
        threshold_to_dict(thresholds),
        [feed_schedule_to_dict(s) for s in schedules],
    )


async def get_feed_schedules(db: AsyncSession) -> List[FeedScheduleItem]:
    return await FeedScheduleRepository.get_all(db)


async def create_feed_schedule(data: FeedScheduleCreateRequest, db: AsyncSession) -> FeedScheduleItem:
    if data.duration_seconds < 1 or data.duration_seconds > 60:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Duration must be between 1 and 60 seconds")

    schedule = FeedSchedule(
        feed_time=data.feed_time,
        duration_seconds=data.duration_seconds,
        is_active=data.is_active,
    )
    created = await FeedScheduleRepository.create(schedule, db)
    await db.commit()
    await db.refresh(created)

    await _push_config(db)
    return created


async def update_feed_schedule(schedule_id: int, data: FeedScheduleUpdateRequest,
                                db: AsyncSession) -> FeedScheduleItem:
    schedule = await FeedScheduleRepository.get_by_id(schedule_id, db)
    if not schedule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found")

    if data.duration_seconds < 1 or data.duration_seconds > 60:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Duration must be between 1 and 60 seconds")

    updated = await FeedScheduleRepository.update(schedule, data, db)
    await db.commit()
    await db.refresh(updated)

    await _push_config(db)
    return updated


async def delete_feed_schedule(schedule_id: int, db: AsyncSession) -> None:
    schedule = await FeedScheduleRepository.get_by_id(schedule_id, db)
    if not schedule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found")

    await FeedScheduleRepository.delete(schedule, db)
    await db.commit()

    await _push_config(db)


async def trigger_feed(data: FeedTriggerRequest, user_id: int, db: AsyncSession) -> FeedTriggerResponse:
    if data.duration_seconds < 1 or data.duration_seconds > 60:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Duration must be between 1 and 60 seconds")

    command = DeviceCommand(
        command_type=CommandType.feed_now,
        payload={"duration_seconds": data.duration_seconds},
    )
    created_command = await DeviceCommandRepository.create(command, db)
    await db.flush()

    event = EventLog(
        event_type=EventType.feed_triggered,
        severity=Severity.info,
        message=f"Feed triggered manually by user {user_id}",
    )
    await EventLogRepository.create(event, db)
    await db.commit()
    await db.refresh(created_command)

    await publish_command_to_device({
        "command_id":   created_command.id,
        "command_type": "feed_now",
        "payload":      {"duration_seconds": data.duration_seconds},
    })

    # Push-уведомление о выполнении кормления
    try:
        await push_service.send_push_to_user(user_id, "feeding_done", db)
    except Exception:
        pass

    return FeedTriggerResponse(status="command_queued", command_id=created_command.id)
