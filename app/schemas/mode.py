import datetime

from pydantic import BaseModel, ConfigDict

from app.models.system_mode import FSMMode, ChangeSource


class ModeCurrentRequest(BaseModel):
    mode_name: FSMMode
    is_auto: bool


class ModeCurrentResponse(BaseModel):
    status: str


class ModeResponse(BaseModel):
    mode_name: FSMMode
    is_auto: bool
    changed_at: datetime.datetime
    changed_by: ChangeSource

    model_config = ConfigDict(from_attributes=True)


class SetModeRequest(BaseModel):
    mode_name: FSMMode
    is_auto: bool


class ModeHistoryItem(BaseModel):
    id: int
    mode_name: FSMMode
    is_auto: bool
    changed_at: datetime.datetime
    changed_by: ChangeSource

    model_config = ConfigDict(from_attributes=True)


class ModeHistoryResponse(BaseModel):
    items: list[ModeHistoryItem]
    count: int