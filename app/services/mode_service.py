from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SystemMode, DeviceCommand, EventLog
from app.models.device_command import CommandType
from app.models.event_log import EventType, Severity
from app.models.system_mode import ChangeSource
from app.repositories.device_command import DeviceCommandRepository
from app.repositories.event_log import EventLogRepository
from app.repositories.system_mode import SystemModeRepository
from app.schemas.mode import ModeCurrentRequest, ModeCurrentResponse, ModeResponse, SetModeRequest
from app.services.mqtt_publisher import publish_command_to_device, publish_mode_to_app
from app.services import push_service


async def mode_current_create_service(data: ModeCurrentRequest, db: AsyncSession):
    last_mode = await SystemModeRepository.get_last(db)

    if last_mode and not last_mode.is_auto:
        return ModeCurrentResponse(status="ignored_manual_mode")

    new_system_mode = SystemMode(
        mode_name=data.mode_name,
        is_auto=data.is_auto,
        changed_by=ChangeSource.system
    )
    created_system_mode = await SystemModeRepository.create(new_system_mode, db)
    await db.commit()
    await db.refresh(created_system_mode)
    return ModeCurrentResponse(status="ok")


async def mode_current_get_service(db: AsyncSession):
    last_mode = await SystemModeRepository.get_last(db)
    if last_mode is None:
        # Нет данных — возвращаем дефолтный режим
        from datetime import datetime, timezone
        from app.schemas.mode import ModeResponse
        from app.models.system_mode import ChangeSource
        return ModeResponse(
            mode_name="day_moderate",
            is_auto=True,
            changed_at=datetime.now(timezone.utc),
            changed_by=ChangeSource.system,
        )
    return last_mode


async def mode_set_service(data: SetModeRequest, db: AsyncSession, user_id: int = None):
    new_mode = SystemMode(
        mode_name=data.mode_name,
        is_auto=data.is_auto,
        changed_by=ChangeSource.user,
    )
    created_mode = await SystemModeRepository.create(new_mode, db)

    # Сохраняем команды в БД (для истории / совместимости)
    cmd_mode = await DeviceCommandRepository.create(
        DeviceCommand(command_type=CommandType.set_mode,
                      payload={"mode_name": data.mode_name.value}), db
    )
    await db.flush()

    if not data.is_auto:
        cmd_auto = await DeviceCommandRepository.create(
            DeviceCommand(command_type=CommandType.set_auto,
                          payload={"is_auto": False}), db
        )
        await db.flush()

    await EventLogRepository.create(
        EventLog(event_type=EventType.mode_change, severity=Severity.info, message="Mode set"), db
    )

    await db.commit()
    await db.refresh(created_mode)
    await db.refresh(cmd_mode)

    # Публикуем команды в MQTT
    await publish_command_to_device({
        "command_id":   cmd_mode.id,
        "command_type": "set_mode",
        "payload":      {"mode_name": data.mode_name.value},
    })

    if not data.is_auto:
        await db.refresh(cmd_auto)
        await publish_command_to_device({
            "command_id":   cmd_auto.id,
            "command_type": "set_auto",
            "payload":      {"is_auto": False},
        })

    await publish_mode_to_app({
        "mode_name": data.mode_name.value,
        "is_auto":   data.is_auto,
    })

    if user_id:
        await push_service.send_push_to_user(user_id, "mode_changed", db)

    return created_mode
