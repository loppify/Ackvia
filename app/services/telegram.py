import html
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

http_client = httpx.AsyncClient(
    timeout=httpx.Timeout(10.0, connect=5.0),
    limits=httpx.Limits(max_keepalive_connections=20, max_connections=50),
)

LOCALES_PATH = Path(__file__).resolve().parent.parent / "translations"


def format_submission_message(
    form_title: str, payload: dict, t: Callable[[str], str]
) -> str:
    current_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    lines = [
        f"⚡ <b>{t('tg_new_submission')}</b>",
        f"{t('tg_form')}: <b>{html.escape(form_title)}</b>",
        f"{t('tg_time')}: <code>{current_time}</code>",
        "—" * 15,
        "",
    ]

    for key, val in payload.items():
        if key.startswith("_"):
            continue

        raw_key = str(key).strip().replace("_", " ").title()
        raw_val = str(val).strip()

        clean_key = html.escape(raw_key)
        clean_val = html.escape(raw_val)

        lines.append(f"• <b>{clean_key}:</b> <code>{clean_val}</code>")

    lines.append("")
    lines.append("—" * 15)
    lines.append(f"<i>{t('tg_footer')}</i>")

    return "\n".join(lines)


async def send_telegram_alert(chat_id: int, message: str) -> dict:
    if not settings.TELEGRAM_BOT_TOKEN:
        logger.error("Telegram bot token is not set in settings.")
        return {"success": False, "error": "Bot token not configured"}
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
    }

    try:
        response = await http_client.post(url, json=payload)

        if response.status_code == 400 and "can't parse entities" in response.text:
            logger.warning("HTML parse error. Retrying without formatting.")
            payload.pop("parse_mode")
            response = await http_client.post(url, json=payload)

        if response.status_code == 200:
            return {"success": True}

        logger.error(
            f"Failed to send Telegram message to {chat_id}: "
            f"Status {response.status_code}, Body: {response.text}"
        )
        if response.status_code == 429:
            return {"success": False, "error": "Rate limit exceeded"}
        if response.status_code == 400 and "chat not found" in response.text:
            return {"success": False, "error": "Chat not found"}
        if (
            response.status_code == 400
            and "bot was blocked by the user" in response.text
        ):
            return {"success": False, "error": "Bot blocked by user"}
        if response.status_code == 400 and "user is deactivated" in response.text:
            return {"success": False, "error": "User is deactivated"}
        if (
            response.status_code == 400
            and "user is not a member of the chat" in response.text
        ):
            return {"success": False, "error": "User not a member of the chat"}
        if response.status_code == 408:
            return {"success": False, "error": "Request timeout"}
        if response.status_code == 500:
            return {"success": False, "error": "Internal server error"}
        if response.status_code == 502:
            return {"success": False, "error": "Bad gateway"}
        if response.status_code == 503:
            return {"success": False, "error": "Service unavailable"}
        if response.status_code == 504:
            return {"success": False, "error": "Gateway timeout"}
        return {"success": False, "error": f"HTTP {response.status_code}"}

    except httpx.RequestError as exc:
        logger.error(
            f"Network error while sending Telegram message to {chat_id}: {exc}"
        )

        return {"success": False, "error": "Network error"}
