import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Session, User
from app.database.queries.auth import (
    delete_session_token_by_token_hash,
    get_session_by_token_hash,
    get_user_by_email,
)

password_hasher = PasswordHasher()
SESSION_TTL = 30


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        password_hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False
    except InvalidHashError:
        return False
    return True


def generate_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def create_session(db: AsyncSession, user: User) -> str:
    token = generate_session_token()
    hashed_token = hash_session_token(token)

    session = Session(
        token_hash=hashed_token,
        expires_at=datetime.now(UTC) + timedelta(days=SESSION_TTL),
        user=user,
    )

    db.add(session)
    await db.flush()

    return token


class UserAlreadyExistsError(Exception):
    pass


def normalize_email(email: str) -> str:
    return email.strip().lower()


async def register_user(db: AsyncSession, email: str, password: str) -> User:
    normalized_email = normalize_email(email)
    if await get_user_by_email(db, normalized_email) is not None:
        raise UserAlreadyExistsError

    user = User(email=normalized_email, password_hash=hash_password(password))
    db.add(user)
    await db.flush()
    return user


async def get_user_by_session_token(db: AsyncSession, token: str) -> User | None:
    user_session = await get_session_by_token_hash(db, hash_session_token(token))
    if not user_session:
        return None

    if user_session.expires_at <= datetime.now(UTC):
        return None

    return user_session.user


class InvalidCredentialsError(Exception):
    pass


async def login_user(db, email, password) -> tuple[User, str]:
    normalized_email = normalize_email(email)
    user = await get_user_by_email(db, normalized_email)

    if user is None:
        raise InvalidCredentialsError
    if user.password_hash is None:
        raise InvalidCredentialsError
    if not verify_password(password, user.password_hash):
        raise InvalidCredentialsError

    token = await create_session(db, user)

    return user, token


async def logout_session(db: AsyncSession, token: str) -> None:
    await delete_session_token_by_token_hash(db, hash_session_token(token))
    return
