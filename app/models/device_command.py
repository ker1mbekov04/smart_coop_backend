import datetime
import enum
from typing import Optional, Any

from sqlalchemy import BigInteger, Enum, Boolean, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class CommandType(enum.Enum):
    door_open  = "door_open"
    door_close = "door_close"
    set_mode   = "set_mode"
    set_auto   = "set_auto"
    feed_now   = "feed_now"
    set_heater = "set_heater"
    set_vent   = "set_vent"
    set_light  = "set_light"


class DeviceCommand(Base):
    __tablename__ = "device_commands"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    command_type: Mapped[CommandType] = mapped_column(
        Enum(CommandType, native_enum=False, length=50), nullable=False)
    payload: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB, nullable=True,
        comment='Дополнительные параметры команды в JSON. Примеры: {"mode_name": "day_frost"}')
    is_executed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false")
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now())
    executed_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True)
