import datetime
import enum

from pydantic import BaseModel, ConfigDict

from app.models.device_command import CommandType
from app.schemas.thresholds import ThresholdsResponse


class CommandStatusResponse(BaseModel):
    status: str


class CommandAutoRequest(BaseModel):
    is_auto: bool


class CommandRelayRequest(BaseModel):
    state: bool


class FeedScheduleValue(BaseModel):
    feed_time: datetime.time
    duration_seconds: int
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class CommandItem(BaseModel):
    id: int
    command_type: CommandType
    payload: dict | None

    model_config = ConfigDict(from_attributes=True)


class PendingCommandsResponse(BaseModel):
    commands: list[CommandItem]
    thresholds: ThresholdsResponse
    feed_schedule: list[FeedScheduleValue]


class ActionItem(enum.Enum):
    open = "open"
    close = "close"


class CommandDoorRequest(BaseModel):
    action: ActionItem


class CommandDoorResponse(BaseModel):
    status: str
    command_id: int
