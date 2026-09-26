import pytest

from app.core.ingestion import (
    MAX_JSON_DEPTH,
    MAX_JSON_NODES,
    MAX_STRING_LENGTH, validate_ingestion_payload,
)
from app.exceptions import InvalidSubmissionPayloadError


def test_empty_payload_is_valid():
    validate_ingestion_payload({})


def test_flat_payload_is_valid():
    payload = {
        "name": "Alice",
        "email": "alice@example.com",
        "age": 25,
        "subscribed": True,
        "comment": None,
    }

    validate_ingestion_payload(payload)


def test_nested_payload_is_valid():
    payload = {
        "customer": {
            "name": "Alice",
            "contact": {
                "email": "alice@example.com",
            },
        },
    }

    validate_ingestion_payload(payload)


def test_payload_with_list_is_valid():
    payload = {
        "tags": [
            "lead",
            "website",
            "priority",
        ],
    }

    validate_ingestion_payload(payload)


def test_root_must_be_object():
    with pytest.raises(InvalidSubmissionPayloadError):
        validate_ingestion_payload(["Alice", "Bob"])


def test_string_at_max_length_is_valid():
    payload = {
        "message": "a" * MAX_STRING_LENGTH,
    }

    validate_ingestion_payload(payload)


def test_string_over_max_length_is_rejected():
    payload = {
        "message": "a" * (MAX_STRING_LENGTH + 1),
    }

    with pytest.raises(InvalidSubmissionPayloadError):
        validate_ingestion_payload(payload)


def test_nested_string_over_max_length_is_rejected():
    payload = {
        "customer": {
            "message": "a" * (MAX_STRING_LENGTH + 1),
        },
    }

    with pytest.raises(InvalidSubmissionPayloadError):
        validate_ingestion_payload(payload)


def test_key_over_max_length_is_rejected():
    payload = {
        "a" * (MAX_STRING_LENGTH + 1): "value",
    }

    with pytest.raises(InvalidSubmissionPayloadError):
        validate_ingestion_payload(payload)


def test_payload_at_max_nodes_is_valid():
    # Root dict = 1 node.
    # Each primitive value = 1 node.
    payload = {
        f"field_{i}": i
        for i in range(MAX_JSON_NODES - 1)
    }

    validate_ingestion_payload(payload)


def test_payload_over_max_nodes_is_rejected():
    # Root dict = 1 node.
    # MAX_JSON_NODES primitive values make the total MAX_JSON_NODES + 1.
    payload = {
        f"field_{i}": i
        for i in range(MAX_JSON_NODES)
    }

    with pytest.raises(InvalidSubmissionPayloadError):
        validate_ingestion_payload(payload)


def test_array_elements_count_toward_node_limit():
    # root dict = 1
    # list = 1
    # list elements = MAX_JSON_NODES - 1
    # total = MAX_JSON_NODES + 1
    payload = {
        "items": list(range(MAX_JSON_NODES - 1)),
    }

    with pytest.raises(InvalidSubmissionPayloadError):
        validate_ingestion_payload(payload)


def test_payload_at_max_depth_is_valid():
    value = "leaf"

    for _ in range(MAX_JSON_DEPTH):
        value = {"nested": value}

    validate_ingestion_payload(value)


def test_payload_over_max_depth_is_rejected():
    value = "leaf"

    for _ in range(MAX_JSON_DEPTH + 1):
        value = {"nested": value}

    with pytest.raises(InvalidSubmissionPayloadError):
        validate_ingestion_payload(value)