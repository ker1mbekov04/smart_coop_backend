from pydantic import BaseModel


class CameraStatusResponse(BaseModel):
    is_online: bool
    last_frame_size_bytes: int | None
    last_frame_age_seconds: float | None
