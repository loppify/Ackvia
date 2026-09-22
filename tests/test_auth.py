from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Session, User
from app.services.auth import get_user_by_session_token, login_user, InvalidCredentialsError, logout_session
from app.services.auth import (
    UserAlreadyExistsError,
    create_session,
    generate_session_token,
    hash_password,
    hash_session_token,
    register_user,
    verify_password,
)


def test_hash_password_does_not_store_plaintext():
    password = "correct-horse-battery-staple"

    password_hash = hash_password(password)

    assert password_hash != password
    assert password not in password_hash


def test_hash_password_uses_different_salt_each_time():
    password = "same-password"

    first_hash = hash_password(password)
    second_hash = hash_password(password)

    assert first_hash != second_hash


def test_verify_password_accepts_correct_password():
    password = "very-secret-password"
    password_hash = hash_password(password)

    assert verify_password(password, password_hash) is True


def test_verify_password_rejects_wrong_password():
    password_hash = hash_password("correct-password")

    assert verify_password("wrong-password", password_hash) is False


def test_verify_password_rejects_invalid_hash():
    assert verify_password("some-password", "not-an-argon2-hash") is False


def test_generate_session_token_returns_unique_tokens():
    first_token = generate_session_token()
    second_token = generate_session_token()

    assert first_token != second_token


def test_generate_session_token_is_not_empty():
    token = generate_session_token()

    assert isinstance(token, str)
    assert token


def test_hash_session_token_is_deterministic():
    token = generate_session_token()

    first_hash = hash_session_token(token)
    second_hash = hash_session_token(token)

    assert first_hash == second_hash


def test_hash_session_token_returns_sha256_hex_digest():
    token = generate_session_token()

    token_hash = hash_session_token(token)

    assert len(token_hash) == 64

    # SHA-256 hex digest may contain only hexadecimal characters.
    int(token_hash, 16)


def test_different_session_tokens_have_different_hashes():
    first_token = generate_session_token()
    second_token = generate_session_token()

    assert hash_session_token(first_token) != hash_session_token(second_token)


def test_session_token_is_not_stored_as_its_hash():
    token = generate_session_token()

    token_hash = hash_session_token(token)

    assert token_hash != token
    assert token not in token_hash


async def test_create_session_stores_hashed_token(db: AsyncSession):
    user = User(email="test@example.com")
    db.add(user)
    await db.flush()

    token = await create_session(db, user)

    result = await db.execute(
        select(Session).where(Session.user_id == user.id)
    )
    session = result.scalar_one()

    assert token
    assert session.token_hash != token
    assert session.token_hash == hash_session_token(token)


async def test_create_session_sets_expiration(db: AsyncSession):
    user = User(email="test@example.com")
    db.add(user)
    await db.flush()

    before = datetime.now(UTC)

    await create_session(db, user)

    after = datetime.now(UTC)

    result = await db.execute(
        select(Session).where(Session.user_id == user.id)
    )
    session = result.scalar_one()

    assert before + timedelta(days=30) <= session.expires_at
    assert session.expires_at <= after + timedelta(days=30)


async def test_get_user_by_session_token_returns_user(db: AsyncSession):
    user = User(email="test@example.com")
    db.add(user)
    await db.flush()

    token = await create_session(db, user)

    result = await get_user_by_session_token(db, token)

    assert result is not None
    assert result.id == user.id


async def test_get_user_by_session_token_returns_none_for_unknown_token(
        db: AsyncSession,
):
    result = await get_user_by_session_token(
        db,
        "this-is-not-a-real-session-token",
    )

    assert result is None


async def test_get_user_by_session_token_rejects_expired_session(
        db: AsyncSession,
):
    user = User(email="test@example.com")
    db.add(user)
    await db.flush()

    token = generate_session_token()

    session = Session(
        user=user,
        token_hash=hash_session_token(token),
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
    )
    db.add(session)
    await db.flush()

    result = await get_user_by_session_token(db, hash_session_token(token))

    assert result is None


async def test_register_user_creates_user(db: AsyncSession):
    user = await register_user(
        db,
        "test@example.com",
        "strong-password",
    )

    stored_user = await db.scalar(
        select(User).where(User.id == user.id)
    )

    assert stored_user is not None
    assert stored_user.email == "test@example.com"


async def test_register_user_normalizes_email(db: AsyncSession):
    user = await register_user(
        db,
        "  Test@Example.COM  ",
        "strong-password",
    )

    assert user.email == "test@example.com"


async def test_register_user_hashes_password(db: AsyncSession):
    password = "strong-password"

    user = await register_user(
        db,
        "test@example.com",
        password,
    )

    assert user.password_hash is not None
    assert user.password_hash != password
    assert verify_password(password, user.password_hash) is True


async def test_register_user_rejects_duplicate_email(db: AsyncSession):
    await register_user(
        db,
        "test@example.com",
        "first-password",
    )

    with pytest.raises(UserAlreadyExistsError):
        await register_user(
            db,
            "test@example.com",
            "second-password",
        )


async def test_register_user_rejects_duplicate_normalized_email(
        db: AsyncSession,
):
    await register_user(
        db,
        "Test@Example.COM",
        "first-password",
    )

    with pytest.raises(UserAlreadyExistsError):
        await register_user(
            db,
            "  test@example.com  ",
            "second-password",
        )


async def test_login_user_returns_user_and_session_token(db: AsyncSession):
    password = "strong-password"

    user = await register_user(
        db,
        "test@example.com",
        password,
    )

    user, token = await login_user(
        db,
        "test@example.com",
        password,
    )

    assert isinstance(token, str)
    assert isinstance(user, User)
    assert token

    session = await db.scalar(
        select(Session).where(Session.user_id == user.id)
    )

    assert session is not None
    assert session.token_hash == hash_session_token(token)


async def test_login_user_normalizes_email(db: AsyncSession):
    password = "strong-password"

    await register_user(
        db,
        "test@example.com",
        password,
    )

    token = await login_user(
        db,
        "  Test@Example.COM  ",
        password,
    )

    assert token


async def test_login_user_rejects_wrong_password(db: AsyncSession):
    await register_user(
        db,
        "test@example.com",
        "correct-password",
    )

    with pytest.raises(InvalidCredentialsError):
        await login_user(
            db,
            "test@example.com",
            "wrong-password",
        )


async def test_login_user_rejects_unknown_email(db: AsyncSession):
    with pytest.raises(InvalidCredentialsError):
        await login_user(
            db,
            "missing@example.com",
            "some-password",
        )


async def test_login_user_rejects_user_without_password(db: AsyncSession):
    user = User(
        email="oauth@example.com",
        password_hash=None,
    )
    db.add(user)
    await db.flush()

    with pytest.raises(InvalidCredentialsError):
        await login_user(
            db,
            "oauth@example.com",
            "some-password",
        )


async def test_logout_session_deletes_session(db: AsyncSession):
    user = await register_user(
        db,
        "test@example.com",
        "strong-password",
    )
    token = await create_session(db, user)

    await logout_session(db, token)

    session = await db.scalar(
        select(Session).where(
            Session.token_hash == hash_session_token(token)
        )
    )

    assert session is None


async def test_logout_session_does_not_delete_other_sessions(
        db: AsyncSession,
):
    user = await register_user(
        db,
        "test@example.com",
        "strong-password",
    )

    first_token = await create_session(db, user)
    second_token = await create_session(db, user)

    await logout_session(db, first_token)

    first_session = await db.scalar(
        select(Session).where(
            Session.token_hash == hash_session_token(first_token)
        )
    )
    second_session = await db.scalar(
        select(Session).where(
            Session.token_hash == hash_session_token(second_token)
        )
    )

    assert first_session is None
    assert second_session is not None


async def test_logout_session_accepts_unknown_token(
        db: AsyncSession,
):
    await logout_session(
        db,
        "unknown-session-token",
    )


async def test_register_endpoint_creates_user(client):
    response = await client.post(
        "/api/auth/register",
        json={
            "email": "test@example.com",
            "password": "strong-password",
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["email"] == "test@example.com"
    assert data["email_verified"] is False
    assert "id" in data
    assert "password_hash" not in data


async def test_register_endpoint_sets_session_cookie(client):
    response = await client.post(
        "/api/auth/register",
        json={
            "email": "test@example.com",
            "password": "strong-password",
        },
    )

    assert response.status_code == 201
    assert "ackvia_session" in response.cookies

    cookie = response.headers["set-cookie"]

    assert "HttpOnly" in cookie
    assert "Secure" in cookie
    assert "SameSite=lax" in cookie


async def test_register_endpoint_normalizes_email(client):
    response = await client.post(
        "/api/auth/register",
        json={
            "email": "  Test@Example.COM  ",
            "password": "strong-password",
        },
    )

    assert response.status_code == 201
    assert response.json()["email"] == "test@example.com"


async def test_register_endpoint_rejects_duplicate_email(client):
    first = await client.post(
        "/api/auth/register",
        json={
            "email": "test@example.com",
            "password": "first-password",
        },
    )

    second = await client.post(
        "/api/auth/register",
        json={
            "email": "test@example.com",
            "password": "second-password",
        },
    )

    assert first.status_code == 201
    assert second.status_code == 409


async def test_register_endpoint_rejects_duplicate_normalized_email(client):
    first = await client.post(
        "/api/auth/register",
        json={
            "email": "Test@Example.COM",
            "password": "first-password",
        },
    )

    second = await client.post(
        "/api/auth/register",
        json={
            "email": "  test@example.com  ",
            "password": "second-password",
        },
    )

    assert first.status_code == 201
    assert second.status_code == 409


async def test_login_endpoint_returns_user(client):
    await client.post(
        "/api/auth/register",
        json={
            "email": "test@example.com",
            "password": "strong-password",
        },
    )

    response = await client.post(
        "/api/auth/login",
        json={
            "email": "test@example.com",
            "password": "strong-password",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["email"] == "test@example.com"
    assert data["email_verified"] is False
    assert "id" in data
    assert "password_hash" not in data


async def test_login_endpoint_sets_session_cookie(client):
    await client.post(
        "/api/auth/register",
        json={
            "email": "test@example.com",
            "password": "strong-password",
        },
    )

    response = await client.post(
        "/api/auth/login",
        json={
            "email": "test@example.com",
            "password": "strong-password",
        },
    )

    assert response.status_code == 200
    assert "ackvia_session" in response.cookies

    cookie = response.headers["set-cookie"]

    assert "HttpOnly" in cookie
    assert "Secure" in cookie
    assert "SameSite=lax" in cookie


async def test_login_endpoint_normalizes_email(client):
    await client.post(
        "/api/auth/register",
        json={
            "email": "test@example.com",
            "password": "strong-password",
        },
    )

    response = await client.post(
        "/api/auth/login",
        json={
            "email": "  Test@Example.COM  ",
            "password": "strong-password",
        },
    )

    assert response.status_code == 200
    assert response.json()["email"] == "test@example.com"


async def test_login_endpoint_rejects_wrong_password(client):
    await client.post(
        "/api/auth/register",
        json={
            "email": "test@example.com",
            "password": "correct-password",
        },
    )

    response = await client.post(
        "/api/auth/login",
        json={
            "email": "test@example.com",
            "password": "wrong-password",
        },
    )

    assert response.status_code == 401


async def test_login_endpoint_rejects_unknown_email(client):
    response = await client.post(
        "/api/auth/login",
        json={
            "email": "missing@example.com",
            "password": "some-password",
        },
    )

    assert response.status_code == 401


async def test_me_returns_authenticated_user(client):
    register_response = await client.post(
        "/api/auth/register",
        json={
            "email": "test@example.com",
            "password": "strong-password",
        },
    )

    assert register_response.status_code == 201

    response = await client.get("/api/auth/me")

    assert response.status_code == 200

    data = response.json()

    assert data["email"] == "test@example.com"
    assert data["email_verified"] is False
    assert "id" in data
    assert "password_hash" not in data


async def test_me_rejects_request_without_session_cookie(client):
    client.cookies.clear()

    response = await client.get("/api/auth/me")

    assert response.status_code == 401


async def test_me_rejects_invalid_session_cookie(client):
    client.cookies.set(
        "ackvia_session",
        "invalid-session-token",
    )

    response = await client.get("/api/auth/me")

    assert response.status_code == 401


async def test_me_rejects_expired_session(client, db: AsyncSession):
    user = User(
        email="expired@example.com",
        password_hash=hash_password("strong-password"),
    )
    db.add(user)
    await db.flush()

    token = generate_session_token()

    session = Session(
        user=user,
        token_hash=hash_session_token(token),
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
    )
    db.add(session)
    await db.flush()

    client.cookies.set(
        "ackvia_session",
        token,
    )

    response = await client.get("/api/auth/me")

    assert response.status_code == 401


async def test_logout_removes_session(client):
    await client.post(
        "/api/auth/register",
        json={
            "email": "test@example.com",
            "password": "strong-password",
        },
    )

    before = await client.get("/api/auth/me")
    assert before.status_code == 200

    response = await client.post("/api/auth/logout")

    assert response.status_code == 204

    after = await client.get("/api/auth/me")
    assert after.status_code == 401


async def test_logout_clears_session_cookie(client):
    await client.post(
        "/api/auth/register",
        json={
            "email": "test@example.com",
            "password": "strong-password",
        },
    )

    assert "ackvia_session" in client.cookies

    response = await client.post("/api/auth/logout")

    assert response.status_code == 204
    assert "ackvia_session" not in client.cookies


async def test_logout_without_session_is_idempotent(client):
    client.cookies.clear()

    first = await client.post("/api/auth/logout")
    second = await client.post("/api/auth/logout")

    assert first.status_code == 204
    assert second.status_code == 204


async def test_logout_with_invalid_session_is_idempotent(client):
    client.cookies.set("invalid_session_token",
                       "ackvia_session",
                       path="/")

    response = await client.post("/api/auth/logout")

    assert response.status_code == 204
    assert "ackvia_session" not in client.cookies
