from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.models import Session, User


async def get_session_by_token_hash(
    db: AsyncSession, token_hash: str
) -> Session | None:
    session = await db.execute(
        select(Session)
        .options(selectinload(Session.user))
        .where(Session.token_hash == token_hash)
    )
    return session.scalar_one_or_none()


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    return await db.scalar(select(User).where(User.email == email))


async def delete_session_token_by_token_hash(db: AsyncSession, token_hash: str) -> bool:
    session = await db.scalar(select(Session).where(Session.token_hash == token_hash))
    if session is None:
        return False
    await db.delete(session)
    await db.flush()
    return True
