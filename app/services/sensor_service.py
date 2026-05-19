from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SensorReading, DeviceState, Threshold
from app.models.device_state import DoorStatus
from app.repositories.device_state import DeviceStateRepository
from app.repositories.sensor_reading import SensorRepository
from app.repositories.thresholds import ThresholdRepository
from app.repositories.user import UserRepository
from app.schemas.sensor import SensorDataRequest, SensorDataResponse, CurrentSensorResponse
from app.services import push_service
from app.services.mqtt_publisher import publish_sensor_to_app
from app.utils.sensor_status import get_temperature_status, get_humidity_status, get_light_status


async def sensor_data_service(data: SensorDataRequest, db: AsyncSession, user_id: int):
    new_sensor_data = SensorReading(
        temperature=data.temperature,
        humidity=data.humidity,
        light_level=data.light_level
    )
    created_sensor_data = await SensorRepository.create(new_sensor_data, db)

    threshold = await ThresholdRepository.get_active(db)
    if threshold is None:
        threshold = Threshold(
            t_comfort_min=18.0, t_comfort_max=24.0,
            t_low_on=10.0, t_low_off=12.0,
            t_high_on=30.0, t_high_off=28.0,
            t_critical_low=3.0, t_critical_high=35.0,
            h_normal_max=70.0, h_normal_min=60.0, h_critical=85.0,
            lux_day_on=200, lux_day_off=50,
            lux_light_on=300, lux_light_off=350,
        )

    user = await UserRepository.get_by_id(user_id, db)
    await push_service.check_and_notify(data.temperature, data.humidity, threshold, user, db)

    device_state = await DeviceStateRepository.get_first(db)
    if not device_state:
        device_state = DeviceState(
            heater=False, ventilation=False, lighting=False,
            door=DoorStatus.closed, feeder=False,
            recorded_at=datetime.now(timezone.utc)
        )
        await DeviceStateRepository.create(device_state, db)
    else:
        device_state.recorded_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(device_state)

    # Публикуем real-time данные в приложение
    await publish_sensor_to_app({
        "temperature":        float(data.temperature) if data.temperature is not None else None,
        "humidity":           float(data.humidity) if data.humidity is not None else None,
        "light_level":        data.light_level,
        "recorded_at":        created_sensor_data.recorded_at.isoformat(),
        "temperature_status": get_temperature_status(data.temperature, threshold).value,
        "humidity_status":    get_humidity_status(data.humidity, threshold).value,
        "light_status":       get_light_status(data.light_level, threshold).value,
    })

    return SensorDataResponse(
        status="ok",
        recorded_at=created_sensor_data.recorded_at
    )


async def sensor_current_service(db: AsyncSession):
    reading = await SensorRepository.get_last_reading(db)
    if reading is None:
        return None

    threshold = await ThresholdRepository.get_active(db)
    if threshold is None:
        threshold = Threshold(
            t_comfort_min=18.0, t_comfort_max=24.0,
            t_low_on=10.0, t_low_off=12.0,
            t_high_on=30.0, t_high_off=28.0,
            t_critical_low=3.0, t_critical_high=35.0,
            h_normal_max=70.0, h_normal_min=60.0, h_critical=85.0,
            lux_day_on=200, lux_day_off=50,
            lux_light_on=300, lux_light_off=350,
        )

    return CurrentSensorResponse(
        temperature=reading.temperature,
        humidity=reading.humidity,
        light_level=reading.light_level,
        recorded_at=reading.recorded_at,
        temperature_status=get_temperature_status(reading.temperature, threshold),
        humidity_status=get_humidity_status(reading.humidity, threshold),
        light_status=get_light_status(reading.light_level, threshold)
    )
