from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Threshold
from app.repositories.feed_shedule import FeedScheduleRepository
from app.repositories.thresholds import ThresholdRepository
from app.schemas.thresholds import ThresholdsResponse, ThresholdsUpdateRequest
from app.services.mqtt_publisher import (
    publish_config_to_device,
    threshold_to_dict,
    feed_schedule_to_dict,
)


async def get_current_thresholds(db: AsyncSession) -> Threshold:
    thresholds = await ThresholdRepository.get_active(db)
    if thresholds is None:
        return Threshold(
            t_comfort_min=18.0, t_comfort_max=24.0,
            t_low_on=10.0, t_low_off=12.0,
            t_high_on=30.0, t_high_off=28.0,
            t_critical_low=3.0, t_critical_high=35.0,
            h_normal_max=70.0, h_normal_min=60.0, h_critical=85.0,
            lux_day_on=200, lux_day_off=150,
            lux_light_on=300, lux_light_off=350,
        )
    return thresholds


async def thresholds_update_service(data: ThresholdsUpdateRequest, db: AsyncSession):
    thresholds = await ThresholdRepository.get_active(db)
    if thresholds is None:
        thresholds = Threshold(
            t_comfort_min=18.0, t_comfort_max=24.0,
            t_low_on=10.0, t_low_off=12.0,
            t_high_on=30.0, t_high_off=28.0,
            t_critical_low=3.0, t_critical_high=35.0,
            h_normal_max=70.0, h_normal_min=60.0, h_critical=85.0,
            lux_day_on=200, lux_day_off=150,
            lux_light_on=300, lux_light_off=350,
        )
        await ThresholdRepository.create(thresholds, db)

    full_data = {
        field: getattr(data, field) if getattr(data, field) is not None else getattr(thresholds, field)
        for field in ThresholdsResponse.model_fields
    }

    try:
        validated = ThresholdsResponse(**full_data)
    except ValidationError as e:
        raise HTTPException(status_code=422,
                            detail=[error["msg"] for error in e.errors()])

    updated_thresholds = await ThresholdRepository.update(thresholds, data, db)
    await db.commit()
    await db.refresh(updated_thresholds)

    # Публикуем обновлённый конфиг устройству
    schedules = await FeedScheduleRepository.get_active(db)
    await publish_config_to_device(
        threshold_to_dict(updated_thresholds),
        [feed_schedule_to_dict(s) for s in schedules],
    )

    return ThresholdsResponse.model_validate(updated_thresholds)
