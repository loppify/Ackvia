import httpx
import pytest

from app.services.telegram import send_telegram_alert


@pytest.mark.parametrize(
    ("status_code", "description", "expected_error", "expected_failure_type"),
    [
        (400, "Bad Request: chat not found", "Chat not found", "permanent_failure"),
        (
            403,
            "Forbidden: bot was blocked by the user",
            "Bot blocked by user",
            "permanent_failure",
        ),
        (
            400,
            "Bad Request: user is deactivated",
            "User is deactivated",
            "permanent_failure",
        ),
        (
            400,
            "Bad Request: user is not a member of the chat",
            "User not a member of the chat",
            "permanent_failure",
        ),
        (408, "Request Timeout", "Request timeout", "retryable_failure"),
        (429, "Too Many Requests", "Rate limit exceeded", "retryable_failure"),
        (500, "Internal Server Error", "Internal server error", "retryable_failure"),
        (502, "Bad Gateway", "Bad gateway", "retryable_failure"),
        (503, "Service Unavailable", "Service unavailable", "retryable_failure"),
        (504, "Gateway Timeout", "Gateway timeout", "retryable_failure"),
    ],
)
async def test_telegram_failure_is_classified(
    monkeypatch,
    status_code,
    description,
    expected_error,
    expected_failure_type,
):
    async def fake_post(url, json):
        return httpx.Response(
            status_code=status_code,
            json={
                "ok": False,
                "description": description,
            },
        )

    monkeypatch.setattr(
        "app.services.telegram.settings.TELEGRAM_BOT_TOKEN",
        "test-token",
    )
    monkeypatch.setattr(
        "app.services.telegram.http_client.post",
        fake_post,
    )

    result = await send_telegram_alert(123456, "Test message")

    assert result == {
        "success": False,
        "error": expected_error,
        "failure_type": expected_failure_type,
    }
