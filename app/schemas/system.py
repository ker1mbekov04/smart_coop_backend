import datetime

from pydantic import BaseModel

from app.schemas.device import DeviceStateResponse
from app.schemas.event_log import EventItem
from app.schemas.mode import ModeResponse
from app.schemas.sensor import CurrentSensorResponse


class SystemHealthConnResponse(BaseModel):
    status: str
    database: str
    version: str
    uptime_seconds: int


class CameraItems(BaseModel):
    is_online: bool
    last_frame_size_bytes: int | None = None
    last_frame_age_seconds: float | None


class SystemStatusResponse(BaseModel):
    last_sensor: CurrentSensorResponse | None
    last_device: DeviceStateResponse | None
    active_mode: ModeResponse | None
    recent_events: list[EventItem]
    is_device_online: bool
    device_last_seen: datetime.datetime | None
    camera_status: CameraItems