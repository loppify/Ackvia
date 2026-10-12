import html
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import httpx
from loguru import logger

from app.core.config import settings

http_client = httpx.AsyncClient(
    timeout=httpx.Timeout(10.0, connect=5.0),
    limits=httpx.Limits(max_keepalive_connections=20, max_connections=50),
)

LOCALES_PATH = Path(__file__).resolve().parent.parent / "translations"

PERMANENT_ERROR_MESSAGES = {
    "chat not found": "Chat not found",
    "bot was blocked by the user": "Bot blocked by user",
    "user is deactivated": "User is deactivated",
    "user is not a member of the chat": "User not a member of the chat",
}

RETRYABLE_STATUS_MESSAGES = {
    408: "Request timeout",
    429: "Rate limit exceeded",
    500: "Internal server error",
    502: "Bad gateway",
    503: "Service unavailable",
    504: "Gateway timeout",
}


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


def classify_telegram_failure(response: httpx.Response) -> dict:
    response_text = response.text.lower()

    for marker, error in PERMANENT_ERROR_MESSAGES.items():
        if marker in response_text:
            return {
                "success": False,
                "error": error,
                "failure_type": "permanent_failure",
            }

    return {
        "success": False,
        "error": RETRYABLE_STATUS_MESSAGES.get(
            response.status_code,
            f"HTTP {response.status_code}",
        ),
        "failure_type": "retryable_failure",
    }


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
        logger.debug("Telegram request started")
        response = await http_client.post(url, json=payload)

        if response.status_code == 400 and "can't parse entities" in response.text:
            logger.warning("HTML parse error. Retrying without formatting.")
            payload.pop("parse_mode")
            response = await http_client.post(url, json=payload)

        if response.status_code == 200:
            return {
                "success": True,
                "external_reference": str(
                    response.json().get("result", {}).get("message_id")
                ),
            }
        return_data = classify_telegram_failure(response)

    except httpx.RequestError:
        logger.error("Network error while sending Telegram message to {chat_id}: {exc}")

        return_data = {
            "success": False,
            "error": "Network error",
            "failure_type": "retryable_failure",
        }
    return return_data
