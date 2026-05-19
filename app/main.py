import asyncio

from fastapi import FastAPI
from app.routers.auth import router as auth_router
from app.routers.sensor import router as sensor_router
from app.routers.device import router as device_state_router
from app.routers.mode import router as system_mode_router
from app.routers.thresholds import router as thresholds_router
from app.routers.feed_schedule import router as feed_schedule_router
from app.routers.command import router as command_router
from app.routers.history import router as history_router
from app.routers.event import router as event_router
from app.routers.notification import router as notification_router
from app.routers.camera import router as camera_router
from app.routers.system import router as system_router
from app.routers.push import router as push_router

from fastapi.middleware.cors import CORSMiddleware

from app.services.mqtt_service import start_mqtt
from app.services.push_service import init_firebase, send_push_to_user
from app.services.camera_runtime import camera_runtime
from app.database.session import async_session_local
from app.config.settings import settings
from app.repositories.user import UserRepository
import time

app = FastAPI()


async def _camera_offline_monitor():
    """Проверяет камеру каждые 60 сек, шлёт push если оффлайн."""
    CAMERA_TIMEOUT = 60
    while True:
        await asyncio.sleep(60)
        frame_time = camera_runtime.frame_time
        if frame_time is None or time.time() - frame_time > CAMERA_TIMEOUT:
            try:
                async with async_session_local() as db:
                    user = await UserRepository.get_by_api_key(settings.DEVICE_API_KEY, db)
                    if user:
                        await send_push_to_user(user.id, "camera_offline", db)
            except Exception:
                pass


@app.on_event("startup")
async def startup():
    init_firebase()
    asyncio.create_task(start_mqtt())
    asyncio.create_task(_camera_offline_monitor())

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(auth_router, prefix="/api/v1")
app.include_router(sensor_router, prefix="/api/v1")
app.include_router(device_state_router, prefix="/api/v1")
app.include_router(system_mode_router, prefix="/api/v1")
app.include_router(thresholds_router, prefix="/api/v1")
app.include_router(feed_schedule_router, prefix="/api/v1")
app.include_router(command_router, prefix="/api/v1")
app.include_router(history_router, prefix="/api/v1")
app.include_router(event_router, prefix="/api/v1")
app.include_router(notification_router, prefix="/api/v1")
app.include_router(camera_router, prefix="/api/v1")
app.include_router(system_router, prefix="/api/v1")
app.include_router(push_router, prefix="/api/v1")