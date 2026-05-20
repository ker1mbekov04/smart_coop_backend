import json
from datetime import datetime, timezone
from typing import Any

from app.config.settings import settings

_client = None


def set_mqtt_client(mqtt_client):
    global _client
    _client = mqtt_client


def _publish(topic: str, payload: Any, qos: int = 1, retain: bool = False):
    if _client is None:
        return
    try:
        _client.publish(topic, json.dumps(payload), qos=qos, retain=retain)
    except Exception as e:
        print(f"[MQTT publish error] {topic}: {e}")


# ── Device → команда конкретному устройству ──────────────────────────
async def publish_command_to_device(command: dict):
    topic = f"coop/device/{settings.DEVICE_ID}/command"
    _publish(topic, command, qos=1, retain=False)


# ── Device → конфиг (thresholds + feed_schedule) ────────────────────
async def publish_config_to_device(thresholds_dict: dict, feed_schedules: list[dict]):
    topic = f"coop/device/{settings.DEVICE_ID}/config"
    payload = {
        "thresholds": thresholds_dict,
        "feed_schedules": feed_schedules,
    }
    _publish(topic, payload, qos=1, retain=True)


# ── App → real-time сенсоры ──────────────────────────────────────────
async def publish_sensor_to_app(data: dict):
    _publish("coop/app/sensor", data, qos=1, retain=True)


# ── App → real-time состояние устройств ─────────────────────────────
async def publish_state_to_app(data: dict):
    _publish("coop/app/state", data, qos=1, retain=True)


# ── App → события (алармы, онлайн/офлайн) ───────────────────────────
async def publish_event_to_app(data: dict):
    _publish("coop/app/event", data, qos=1, retain=False)


# ── App → текущий режим ──────────────────────────────────────────────
async def publish_mode_to_app(data: dict):
    _publish("coop/app/mode", data, qos=1, retain=True)


# ── Хелпер: Threshold ORM → dict ─────────────────────────────────────
def threshold_to_dict(t) -> dict:
    return {
        "t_comfort_min":   float(t.t_comfort_min),
        "t_comfort_max":   float(t.t_comfort_max),
        "t_low_on":        float(t.t_low_on),
        "t_low_off":       float(t.t_low_off),
        "t_high_on":       float(t.t_high_on),
        "t_high_off":      float(t.t_high_off),
        "t_critical_low":  float(t.t_critical_low),
        "t_critical_high": float(t.t_critical_high),
        "h_normal_min":    float(t.h_normal_min),
        "h_normal_max":    float(t.h_normal_max),
        "h_critical":      float(t.h_critical),
        "lux_day_on":      int(t.lux_day_on),
        "lux_day_off":     int(t.lux_day_off),
        "lux_light_on":    int(t.lux_light_on),
        "lux_light_off":   int(t.lux_light_off),
    }


# ── Хелпер: FeedSchedule ORM → dict ─────────────────────────────────
def feed_schedule_to_dict(s) -> dict:
    return {
        "feed_time":        str(s.feed_time),
        "duration_seconds": s.duration_seconds,
        "is_active":        s.is_active,
    }
