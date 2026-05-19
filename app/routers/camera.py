from fastapi import APIRouter, Depends, Request

from app.dependencies.dependencies import verify_api_key, get_current_user, get_current_user_optional
from app.models import User
from app.schemas.camera import CameraStatusResponse
from app.services.camera_service import (
    camera_frame_service,
    camera_stream_service,
    camera_snapshot_service,
    camera_status_service,
)

router = APIRouter(prefix="/camera", tags=["Camera"])


@router.post("/frame")
async def post_camera_frame(request: Request, _: User = Depends(verify_api_key)):
    body = await request.body()
    return await camera_frame_service(body)


@router.get("/stream")
async def get_camera_stream():
    return await camera_stream_service()


@router.get("/snapshot")
async def get_camera_snapshot(user: User = Depends(get_current_user_optional)):
    return await camera_snapshot_service()


@router.get("/status", response_model=CameraStatusResponse)
async def get_camera_status(user: User = Depends(get_current_user)):
    return await camera_status_service()
