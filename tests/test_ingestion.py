import json
import math

import pytest

from app.core.ingestion import (
    MAX_JSON_DEPTH,
    MAX_JSON_NODES,
    MAX_REQUEST_BODY_BYTES,
    MAX_STRING_LENGTH,
    validate_ingestion_payload,
)
from app.exceptions import InvalidSubmissionPayloadError
from tests.conftest import get_ingestion_counts


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
    payload = {f"field_{i}": i for i in range(MAX_JSON_NODES - 1)}

    validate_ingestion_payload(payload)


def test_payload_over_max_nodes_is_rejected():
    # Root dict = 1 node.
    # MAX_JSON_NODES primitive values make the total MAX_JSON_NODES + 1.
    payload = {f"field_{i}": i for i in range(MAX_JSON_NODES)}

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


@pytest.mark.parametrize(
    "value",
    [
        float("nan"),
        float("inf"),
        float("-inf"),
    ],
)
def test_non_finite_numbers_are_rejected(value):
    with pytest.raises(InvalidSubmissionPayloadError):
        validate_ingestion_payload(
            {
                "value": value,
            }
        )
        if isinstance(value, float):
            if not math.isfinite(value):
                raise InvalidSubmissionPayloadError()
            return 1


@pytest.mark.asyncio
async def test_json_submission_is_accepted(
    client,
    form_with_destination,
):
    response = await client.post(
        f"/f/{form_with_destination.id}",
        json={
            "name": "Alice",
            "email": "alice@example.com",
            "message": "Hello",
        },
        headers={"Accept": "application/json"},
    )

    assert response.status_code == 202
    assert response.json()["status"] == "accepted"


@pytest.mark.asyncio
async def test_json_content_type_with_charset_is_accepted(
    client,
    form_with_destination,
):
    response = await client.post(
        f"/f/{form_with_destination.id}",
        content=json.dumps({"name": "Alice"}),
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Accept": "application/json",
        },
    )

    assert response.status_code == 202


@pytest.mark.asyncio
async def test_unsupported_content_type_returns_415(
    client,
    form_with_destination,
):
    response = await client.post(
        f"/f/{form_with_destination.id}",
        content="hello",
        headers={"Content-Type": "text/plain"},
    )

    assert response.status_code == 415


@pytest.mark.asyncio
async def test_malformed_json_returns_422(
    client,
    form_with_destination,
):
    response = await client.post(
        f"/f/{form_with_destination.id}",
        content='{"name":',
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_json_root_array_returns_422(
    client,
    form_with_destination,
):
    response = await client.post(
        f"/f/{form_with_destination.id}",
        json=["Alice", "Bob"],
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_too_long_string_returns_422(
    client,
    form_with_destination,
):
    response = await client.post(
        f"/f/{form_with_destination.id}",
        json={
            "message": "a" * (MAX_STRING_LENGTH + 1),
        },
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_urlencoded_form_is_accepted(
    client,
    form_with_destination,
):
    response = await client.post(
        f"/f/{form_with_destination.id}",
        data={
            "name": "Alice",
            "email": "alice@example.com",
        },
        headers={"Accept": "application/json"},
    )

    assert response.status_code == 202


@pytest.mark.asyncio
async def test_request_body_over_limit_returns_413(
    client,
    form_with_destination,
):
    body = json.dumps(
        {
            "message": "a" * MAX_REQUEST_BODY_BYTES,
        }
    )

    assert len(body.encode()) > MAX_REQUEST_BODY_BYTES

    response = await client.post(
        f"/f/{form_with_destination.id}",
        content=body,
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 413


@pytest.mark.parametrize(
    ("content", "content_type", "expected_status"),
    [
        (
            '{"broken":',
            "application/json",
            422,
        ),
        (
            json.dumps(["not", "an", "object"]),
            "application/json",
            422,
        ),
        (
            "plain text",
            "text/plain",
            415,
        ),
    ],
)
@pytest.mark.asyncio
async def test_rejected_ingestion_does_not_create_database_records(
    db,
    client,
    form_with_destination,
    content,
    content_type,
    expected_status,
):
    before = await get_ingestion_counts(db)

    response = await client.post(
        f"/f/{form_with_destination.id}",
        content=content,
        headers={
            "Content-Type": content_type,
            "Accept": "application/json",
        },
    )

    assert response.status_code == expected_status

    after = await get_ingestion_counts(db)

    assert after == before


@pytest.mark.asyncio
async def test_oversized_ingestion_does_not_create_database_records(
    db,
    client,
    form_with_destination,
):
    before = await get_ingestion_counts(db)

    body = json.dumps(
        {
            "message": "a" * MAX_REQUEST_BODY_BYTES,
        }
    )

    response = await client.post(
        f"/f/{form_with_destination.id}",
        content=body,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )

    assert response.status_code == 413

    after = await get_ingestion_counts(db)

    assert after == before


@pytest.mark.asyncio
async def test_oversized_ingestion_creates_no_submission_or_delivery(
    client, db, form_with_destination
):
    before = await get_ingestion_counts(db)

    body = json.dumps(
        {
            "message": "a" * MAX_REQUEST_BODY_BYTES,
        }
    )

    response = await client.post(
        f"/f/{form_with_destination.id}",
        content=body,
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 413

    after = await get_ingestion_counts(db)

    assert after == before


@pytest.mark.parametrize(
    ("content", "content_type", "expected_status"),
    [
        (
            '{"broken":',
            "application/json",
            422,
        ),
        (
            json.dumps(["not", "object"]),
            "application/json",
            422,
        ),
        (
            "hello",
            "text/plain",
            415,
        ),
        (
            "{}",
            "application/json",
            400,
        ),
    ],
)
async def test_rejected_ingestion_creates_no_submission_or_delivery(
    client,
    db,
    form_with_destination,
    content,
    content_type,
    expected_status,
):
    before = await get_ingestion_counts(db)

    response = await client.post(
        f"/f/{form_with_destination.id}",
        content=content,
        headers={
            "Content-Type": content_type,
            "Accept": "application/json",
        },
    )

    assert response.status_code == expected_status

    after = await get_ingestion_counts(db)

    assert after == before
