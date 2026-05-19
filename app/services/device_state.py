from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DeviceState
from app.repositories.device_state import DeviceStateRepository
from app.schemas.device import DeviceStateRequest, DeviceResponse
from app.services.mqtt_publisher import publish_state_to_app


async def device_state_create_service(data: DeviceStateRequest, db: AsyncSession):
    new_device_state = DeviceState(
        heater=data.heater,
        ventilation=data.ventilation,
        lighting=data.lighting,
        door=data.door,
        feeder=data.feeder
    )
    created_device_state = await DeviceStateRepository.create(new_device_state, db)
    await db.commit()
    await db.refresh(created_device_state)

    # Публикуем real-time состояние в приложение
    door_val = data.door.value if hasattr(data.door, "value") else str(data.door)
    await publish_state_to_app({
        "heater":      data.heater,
        "ventilation": data.ventilation,
        "lighting":    data.lighting,
        "door":        door_val,
        "feeder":      data.feeder,
        "recorded_at": created_device_state.recorded_at.isoformat(),
    })

    return DeviceResponse(status="ok")


async def device_state_get_service(db: AsyncSession):
    last_device_state = await DeviceStateRepository.get_last(db)
    if last_device_state is None:
        # Нет данных от устройства — возвращаем дефолтное состояние
        from datetime import datetime, timezone
        from app.schemas.device import DeviceStateResponse
        return DeviceStateResponse(
            heater=False,
            ventilation=False,
            lighting=False,
            door=DoorStatus.closed,
            feeder=False,
            recorded_at=datetime.now(timezone.utc),
        )
    return last_device_state
