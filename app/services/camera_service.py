import time

from fastapi import HTTPException, Response
from fastapi.responses import StreamingResponse

from app.schemas.camera import CameraStatusResponse
from app.services.camera_runtime import camera_runtime

MAX_SIZE = 250 * 1024  # SVGA (800x600) кадры крупнее VGA
BOUNDARY = "smart_coop"
MAX_AGE = 2


async def camera_frame_service(frame: bytes):
    if not frame:
        raise HTTPException(status_code=400, detail="Empty frame")
    if len(frame) > MAX_SIZE:
        raise HTTPException(status_code=413, detail="Frame too large")
    if not frame.startswith(b"\xff\xd8"):
        raise HTTPException(status_code=400, detail="Invalid JPEG data")
    await camera_runtime.set_frame(frame)
    return {"status": "ok", "frame_size": len(frame)}


async def mjpeg_generator():
    while True:
        frame = await camera_runtime.wait_frame()
        if frame is None:
            continue
        yield (
            f"--{BOUNDARY}\r\n"
            "Content-Type: image/jpeg\r\n"
            f"Content-Length: {len(frame)}\r\n\r\n"
        ).encode() + frame + b"\r\n"


async def camera_stream_service():
    return StreamingResponse(
        mjpeg_generator(),
        media_type=f"multipart/x-mixed-replace; boundary={BOUNDARY}",
    )


async def camera_snapshot_service():
    frame = camera_runtime.frame
    frame_time = camera_runtime.frame_time

    if not frame or not frame_time:
        raise HTTPException(status_code=503, detail="Camera offline")
    if time.time() - frame_time > MAX_AGE:
        raise HTTPException(status_code=503, detail="Camera offline")

    return Response(content=frame, media_type="image/jpeg")


async def camera_status_service():
    if not camera_runtime.frame_time:
        return CameraStatusResponse(
            is_online=False,
            last_frame_size_bytes=None,
            last_frame_age_seconds=None,
        )
    age = time.time() - camera_runtime.frame_time
    return CameraStatusResponse(
        is_online=age < MAX_AGE,
        last_frame_size_bytes=camera_runtime.frame_size,
        last_frame_age_seconds=age,
    )
