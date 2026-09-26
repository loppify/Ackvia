from typing import Any

from app.exceptions import InvalidSubmissionPayloadError

MAX_JSON_NODES = 100
MAX_JSON_DEPTH = 5
MAX_STRING_LENGTH = 10_000


def validate_ingestion_payload(payload: Any) -> None:
    if not isinstance(payload, dict):
        raise InvalidSubmissionPayloadError()

    nodes = _validate_json_value(payload, depth=0)

    if nodes > MAX_JSON_NODES:
        raise InvalidSubmissionPayloadError()


def _validate_json_value(value: Any, *, depth: int) -> int:
    if depth > MAX_JSON_DEPTH:
        raise InvalidSubmissionPayloadError()

    if isinstance(value, str):
        if len(value) > MAX_STRING_LENGTH:
            raise InvalidSubmissionPayloadError()
        return 1

    if value is None or isinstance(value, (bool, int, float)):
        return 1

    if isinstance(value, dict):
        nodes = 1

        for key, child in value.items():
            if not isinstance(key, str):
                raise InvalidSubmissionPayloadError()

            if len(key) > MAX_STRING_LENGTH:
                raise InvalidSubmissionPayloadError()

            nodes += _validate_json_value(
                child,
                depth=depth + 1,
            )

            if nodes > MAX_JSON_NODES:
                raise InvalidSubmissionPayloadError()

        return nodes

    if isinstance(value, list):
        nodes = 1

        for child in value:
            nodes += _validate_json_value(
                child,
                depth=depth + 1,
            )

            if nodes > MAX_JSON_NODES:
                raise InvalidSubmissionPayloadError()

        return nodes

    raise InvalidSubmissionPayloadError()
