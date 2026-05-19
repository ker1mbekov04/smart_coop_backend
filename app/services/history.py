from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.device_state import DeviceStateRepository
from app.repositories.sensor_reading import SensorRepository
from app.repositories.system_mode import SystemModeRepository
from app.schemas.history import SensorHistoryResponse, PeriodValue, ParameterValue, HistoryDataResponse


def get_period_start(period: PeriodValue):
    now = datetime.now(timezone.utc)

    if period == PeriodValue.h24:
        return now - timedelta(hours=24)
    elif period == PeriodValue.d7:
        return now - timedelta(days=7)
    elif period == PeriodValue.d30:
        return now - timedelta(days=30)


def filter_by_parameter(data, parameter: ParameterValue):
    if parameter == ParameterValue.all:
        return data
    for item in data:
        if parameter != ParameterValue.temperature:
            item.temperature = None
        if parameter != ParameterValue.humidity:
            item.humidity = None
        if parameter != ParameterValue.light_level:
            item.light_level = None
    return data



async def get_history_sensor_service(period: PeriodValue,
                             parameter: ParameterValue,
                             limit: int,
                             offset: int,
                             db: AsyncSession):
    period_start = get_period_start(period)

    data = await SensorRepository.get_data_by_period(period_start, limit, offset, db)

    data = filter_by_parameter(data, parameter)

    count = await SensorRepository.get_count(period_start, db)

    stats_row = await SensorRepository.get_stats(period_start, db)
    def _f(v):
        return float(v) if v is not None else None

    stats = {
        "temperature": {
            "min": _f(stats_row[0]),
            "max": _f(stats_row[1]),
            "avg": _f(stats_row[2]),
        },
        "humidity": {
            "min": _f(stats_row[3]),
            "max": _f(stats_row[4]),
            "avg": _f(stats_row[5]),
        },
        "light_level": {
            "min": _f(stats_row[6]),
            "max": _f(stats_row[7]),
            "avg": _f(stats_row[8]),
        },
    }

    return SensorHistoryResponse(
        data=data,
        count=count,
        period=period.value,
        stats=stats,
    )


async def get_history_device_service(
        period: PeriodValue,
        limit: int,
        offset: int,
        db: AsyncSession
):
    period_start = get_period_start(period)

    data = await DeviceStateRepository.get_data_by_period(period_start, limit, offset, db)

    count = await DeviceStateRepository.get_count(period_start, db)

    return HistoryDataResponse(
        data=data,
        count=count
    )


async def get_history_modes_service(
        period: PeriodValue,
        limit: int,
        offset: int,
        db: AsyncSession
):
    period_start = get_period_start(period)

    data = await SystemModeRepository.get_data_by_period(period_start, limit, offset, db)

    count = await SystemModeRepository.get_count(period_start, db)

    return HistoryDataResponse(
        data=data,
        count=count
    )