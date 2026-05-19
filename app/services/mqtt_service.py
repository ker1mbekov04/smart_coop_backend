import asyncio
import json

from gmqtt import Client as MQTTClient

from app.config.settings import settings
from app.database.session import async_session_local
from app.models.device_command import DeviceCommand
from app.models.event_log import EventLog, EventType, Severity
from app.repositories.device_command import DeviceCommandRepository
from app.repositories.device_state import DeviceStateRepository
from app.repositories.event_log import EventLogRepository
from app.repositories.feed_shedule import FeedScheduleRepository
from app.repositories.user import UserRepository
from app.schemas.device import DeviceStateRequest
from app.schemas.sensor import SensorDataRequest
from app.services.device_state import device_state_create_service
from app.services.mode_service import mode_current_create_service
from app.schemas.mode import ModeCurrentRequest
from app.services.mqtt_publisher import (
    set_mqtt_client,
    publish_config_to_device,
    publish_event_to_app,
    publish_mode_to_app,
    threshold_to_dict,
    feed_schedule_to_dict,
)
from app.services.sensor_service import sensor_data_service
from app.services.threshold_service import get_current_thresholds
from app.services import push_service

client = MQTTClient("backend-smart-coop")


def on_disconnect(client, packet, exc=None):
    print(f"[MQTT] Disconnected. Reconnecting...")


def on_connect(client, flags, rc, properties):
    print(f"[MQTT] Connected (rc={rc})")
    client.subscribe("coop/device/+/telemetry", qos=1)
    client.subscribe("coop/device/+/state",     qos=1)
    client.subscribe("coop/device/+/mode",      qos=1)
    client.subscribe("coop/device/+/ack",       qos=1)
    client.subscribe("coop/device/+/status",    qos=1)


# ── Хелперы разбора топика ────────────────────────────────────────────
def _parse_device_topic(topic: str):
    """'coop/device/{id}/{action}' → (device_id, action)"""
    parts = topic.split("/")
    if len(parts) == 4 and parts[0] == "coop" and parts[1] == "device":
        return parts[2], parts[3]
    return None, None


async def _get_user_id(db) -> int | None:
    user = await UserRepository.get_by_api_key(settings.DEVICE_API_KEY, db)
    return user.id if user else None


# ── Обработчики входящих сообщений ───────────────────────────────────
async def handle_telemetry(device_id: str, payload: bytes):
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        print(f"[MQTT] invalid JSON from {device_id}/telemetry")
        return

    async with async_session_local() as db:
        user_id = await _get_user_id(db)
        if user_id is None:
            print("[MQTT] DEVICE_API_KEY не найден в БД")
            return

        sensor = SensorDataRequest(
            temperature=data.get("temperature"),
            humidity=data.get("humidity"),
            light_level=data.get("light_level"),
        )
        await sensor_data_service(sensor, db, user_id)


async def handle_state(device_id: str, payload: bytes):
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return

    async with async_session_local() as db:
        old_state = await DeviceStateRepository.get_last(db)
        old_door = old_state.door if old_state else None

        device = DeviceStateRequest(**data)
        await device_state_create_service(device, db)

        if old_door is not None and old_door != device.door:
            user_id = await _get_user_id(db)
            if user_id:
                await push_service.send_push_to_user(user_id, "door_changed", db)


async def handle_mode(device_id: str, payload: bytes):
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return

    async with async_session_local() as db:
        mode_req = ModeCurrentRequest(
            mode_name=data.get("mode_name", "day_moderate"),
            is_auto=data.get("is_auto", True),
        )
        await mode_current_create_service(mode_req, db)

        user_id = await _get_user_id(db)
        if user_id:
            await push_service.send_push_to_user(user_id, "mode_changed", db)

    await publish_mode_to_app({
        "mode_name": data.get("mode_name", "day_moderate"),
        "is_auto":   data.get("is_auto", True),
    })


async def handle_ack(device_id: str, payload: bytes):
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return

    command_id = data.get("command_id")
    if not command_id:
        return

    async with async_session_local() as db:
        from datetime import datetime, timezone
        command = await DeviceCommandRepository.get_by_id(command_id, db)
        if command:
            command.is_executed = True
            command.executed_at = datetime.now(timezone.utc)
            await db.commit()
            print(f"[MQTT] cmd {command_id} executed")


async def handle_status(device_id: str, payload: bytes):
    status = payload.decode("utf-8", errors="ignore").strip().strip('"')

    async with async_session_local() as db:
        if status == "online":
            event = EventLog(
                event_type=EventType.device_online,
                severity=Severity.info,
                message=f"Устройство {device_id} подключено",
            )
            await EventLogRepository.create(event, db)
            await db.commit()

            # Отправляем актуальный конфиг устройству
            thresholds = await get_current_thresholds(db)
            schedules = await FeedScheduleRepository.get_active(db)
            await publish_config_to_device(
                threshold_to_dict(thresholds),
                [feed_schedule_to_dict(s) for s in schedules],
            )
            await publish_event_to_app({
                "event_type": "device_online",
                "severity": "info",
                "message": f"Устройство {device_id} в сети",
            })
            print(f"[MQTT] {device_id} ONLINE — config sent")

        elif status == "offline":
            event = EventLog(
                event_type=EventType.device_offline,
                severity=Severity.critical,
                message=f"Устройство {device_id} отключено",
            )
            await EventLogRepository.create(event, db)
            await db.commit()

            await publish_event_to_app({
                "event_type": "device_offline",
                "severity": "critical",
                "message": f"Устройство {device_id} не в сети",
            })

            user_id = await _get_user_id(db)
            if user_id:
                await push_service.send_push_to_user(user_id, "device_offline", db)
            print(f"[MQTT] {device_id} OFFLINE")


# ── Главный обработчик MQTT ───────────────────────────────────────────
def on_message(client, topic, payload, qos, properties):
    device_id, action = _parse_device_topic(topic)
    if device_id is None:
        return

    handlers = {
        "telemetry": handle_telemetry,
        "state":     handle_state,
        "mode":      handle_mode,
        "ack":       handle_ack,
        "status":    handle_status,
    }
    handler = handlers.get(action)
    if handler:
        asyncio.create_task(handler(device_id, payload))


# ── Запуск MQTT ───────────────────────────────────────────────────────
async def start_mqtt():
    client.on_message    = on_message
    client.on_connect    = on_connect
    client.on_disconnect = on_disconnect

    await client.connect(
        settings.MQTT_BROKER,
        settings.MQTT_PORT,
        keepalive=30,
        version=4,         # MQTT 3.1.1
    )
    set_mqtt_client(client)

    print(f"[MQTT] Connected to {settings.MQTT_BROKER}:{settings.MQTT_PORT}")
    print(f"[MQTT] Subscribed to coop/device/+/{{telemetry,state,mode,ack,status}}")
