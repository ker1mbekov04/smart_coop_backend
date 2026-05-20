import asyncio
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Optional

import firebase_admin
from firebase_admin import credentials, messaging
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings

logger = logging.getLogger(__name__)

# ── Firebase инициализация ─────────────────────────────────────────────
_firebase_app: Optional[firebase_admin.App] = None

def init_firebase():
    global _firebase_app
    if _firebase_app is not None:
        return
    cred_path = settings.FIREBASE_CREDENTIALS_PATH
    if not os.path.exists(cred_path):
        logger.warning(f"Firebase credentials not found at {cred_path}. Push disabled.")
        return
    try:
        cred = credentials.Certificate(cred_path)
        _firebase_app = firebase_admin.initialize_app(cred)
        logger.info("Firebase initialized OK")
    except Exception as e:
        logger.error(f"Firebase init error: {e}")

def is_firebase_ready() -> bool:
    return _firebase_app is not None

# ── Дедупликация (антиспам 10 мин) ────────────────────────────────────
# key: (user_id, event_type) -> last_sent datetime
_dedup_cache: dict[tuple, datetime] = {}
DEDUP_WINDOW = timedelta(minutes=10)

def _can_send(user_id: int, event_type: str) -> bool:
    key = (user_id, event_type)
    last = _dedup_cache.get(key)
    if last is None:
        return True
    return datetime.now(timezone.utc) - last > DEDUP_WINDOW

def _mark_sent(user_id: int, event_type: str):
    _dedup_cache[(user_id, event_type)] = datetime.now(timezone.utc)

# ── Push-шаблоны ───────────────────────────────────────────────────────
PUSH_TEMPLATES = {
    "critical_high_temp": {
        "title": "🔥 Опасный перегрев",
        "body": "Температура превысила критический уровень!",
        "navigate_to": "/dashboard",
    },
    "critical_low_temp": {
        "title": "❄ Критическое охлаждение",
        "body": "Температура опустилась ниже критического уровня!",
        "navigate_to": "/dashboard",
    },
    "high_temp": {
        "title": "🌡 Высокая температура",
        "body": "Температура превысила допустимый порог.",
        "navigate_to": "/dashboard",
    },
    "low_temp": {
        "title": "🌡 Низкая температура",
        "body": "Температура ниже допустимого порога.",
        "navigate_to": "/dashboard",
    },
    "critical_humidity": {
        "title": "💧 Высокая влажность",
        "body": "Влажность превысила критический уровень!",
        "navigate_to": "/dashboard",
    },
    "high_humidity": {
        "title": "💧 Повышенная влажность",
        "body": "Влажность выше нормы.",
        "navigate_to": "/dashboard",
    },
    "device_offline": {
        "title": "📡 Устройство оффлайн",
        "body": "ESP32 не выходит на связь более 5 минут.",
        "navigate_to": "/dashboard",
    },
    "camera_offline": {
        "title": "📷 Камера недоступна",
        "body": "Камера не отправляла кадры более 60 секунд.",
        "navigate_to": "/profile",
    },
    "sensor_error": {
        "title": "⚠ Ошибка датчика",
        "body": "Датчик DHT22/BH1750 выдаёт ошибки чтения.",
        "navigate_to": "/dashboard",
    },
    "door_opened": {
        "title": "🚪 Дверь открылась",
        "body": "Дверь выгула полностью открылась.",
        "navigate_to": "/devices",
    },
    "door_closed": {
        "title": "🚪 Дверь закрылась",
        "body": "Дверь выгула полностью закрылась.",
        "navigate_to": "/devices",
    },
    "feeding_done": {
        "title": "🍗 Кормление выполнено",
        "body": "Кормление выполнено по расписанию.",
        "navigate_to": "/devices",
    },
    "mode_changed": {
        "title": "🔄 Режим изменён",
        "body": "Система сменила режим работы.",
        "navigate_to": "/modes",
        "_dynamic_body": True,
    },
    "system_recovered": {
        "title": "✅ Система восстановлена",
        "body": "Все параметры вернулись в норму.",
        "navigate_to": "/dashboard",
    },
}

# ── Отправка через Firebase FCM ────────────────────────────────────────
async def _send_fcm(token: str, title: str, body: str, data: dict) -> bool:
    if not is_firebase_ready():
        logger.warning("Firebase not ready, skipping push")
        return False
    try:
        message = messaging.Message(
            notification=messaging.Notification(title=title, body=body),
            data={k: str(v) for k, v in data.items()},
            token=token,
            android=messaging.AndroidConfig(
                priority="high",
                notification=messaging.AndroidNotification(
                    channel_id="smart_coop_alerts",
                    priority="max",
                    default_sound=True,
                ),
            ),
            apns=messaging.APNSConfig(
                payload=messaging.APNSPayload(
                    aps=messaging.Aps(
                        sound="default",
                        badge=1,
                    )
                )
            ),
        )
        # Firebase Admin SDK — синхронный, запускаем в executor
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, messaging.send, message)
        return True
    except messaging.UnregisteredError:
        logger.info(f"Token unregistered: {token[:20]}...")
        return False
    except Exception as e:
        logger.error(f"FCM send error: {e}")
        return False

MODE_DISPLAY_NAMES = {
    "day_moderate": "Дневной умеренный ☀️",
    "day_frost":    "Дневной морозный ❄️",
    "night_cold":   "Ночной холодный 🌙",
    "overheat":     "Режим перегрева 🔥",
}

# ── Публичный API ──────────────────────────────────────────────────────
async def send_push_to_user(user_id: int, event_type: str, db: AsyncSession,
                             extra_data: dict = None):
    """Отправить push всем активным токенам пользователя."""
    if not _can_send(user_id, event_type):
        return

    template = PUSH_TEMPLATES.get(event_type)
    if not template:
        logger.warning(f"Unknown push event: {event_type}")
        return

    from app.repositories.push_token import PushTokenRepository
    tokens = await PushTokenRepository.get_active_tokens_by_user(user_id, db)
    if not tokens:
        return

    # Build title/body — allow extra_data overrides
    title = extra_data.get("title", template["title"]) if extra_data else template["title"]
    body  = extra_data.get("body",  template["body"])  if extra_data else template["body"]

    data = {"navigate_to": template["navigate_to"], "event_type": event_type}
    if extra_data:
        data.update({k: v for k, v in extra_data.items() if k not in ("title", "body")})

    sent = 0
    for push_token in tokens:
        ok = await _send_fcm(push_token.token, title, body, data)
        if ok:
            sent += 1

    if sent > 0:
        _mark_sent(user_id, event_type)
        logger.info(f"Push '{event_type}' sent to user {user_id} ({sent} tokens)")

    # Save to per-user inbox regardless of FCM delivery
    severity = "critical" if "critical" in event_type else ("info" if event_type in ("feeding_done", "system_recovered", "mode_changed") else "warning")
    from app.repositories.user_notification import UserNotificationRepository
    await UserNotificationRepository.create(db, user_id, title, body, severity)


async def check_and_notify(temperature, humidity, thresholds, user, db: AsyncSession):
    """Проверка пороговых значений и отправка push."""
    if temperature is None:
        await send_push_to_user(user.id, "sensor_error", db)
    else:
        if temperature >= thresholds.t_critical_high and user.notif_alarm_temp_high:
            await send_push_to_user(user.id, "critical_high_temp", db)
        elif temperature <= thresholds.t_critical_low and user.notif_alarm_temp_low:
            await send_push_to_user(user.id, "critical_low_temp", db)
        elif temperature >= thresholds.t_high_on and user.notif_alarm_temp_high:
            await send_push_to_user(user.id, "high_temp", db)
        elif temperature <= thresholds.t_low_on and user.notif_alarm_temp_low:
            await send_push_to_user(user.id, "low_temp", db)

    if humidity is None:
        await send_push_to_user(user.id, "sensor_error", db)
    else:
        if humidity >= thresholds.h_critical and user.notif_alarm_humidity:
            await send_push_to_user(user.id, "critical_humidity", db)
        elif humidity > thresholds.h_normal_max and user.notif_alarm_humidity:
            await send_push_to_user(user.id, "high_humidity", db)
