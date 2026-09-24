from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import User
from app.database.session import get_db
from app.schemas.auth import RegisterRequest, UserRead
from app.services.auth import (
    InvalidCredentialsError,
    UserAlreadyExistsError,
    create_session,
    get_user_by_session_token,
    login_user,
    logout_session,
    register_user,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register_handler(
    user_cred: RegisterRequest, response: Response, db: AsyncSession = Depends(get_db)
):
    try:
        user = await register_user(db, user_cred.email, user_cred.password)
    except UserAlreadyExistsError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="User already exists"
        )

    session_token = await create_session(db, user)

    response.set_cookie(
        value=session_token,
        key="ackvia_session",
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=30 * 24 * 3600,
        path="/",
    )
    return user


@router.post("/login", response_model=UserRead, status_code=status.HTTP_200_OK)
async def login_handler(
    user_cred: RegisterRequest, response: Response, db: AsyncSession = Depends(get_db)
):
    try:
        user, session_token = await login_user(db, user_cred.email, user_cred.password)
    except InvalidCredentialsError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Username or password incorrect",
        )

    response.set_cookie(
        value=session_token,
        key="ackvia_session",
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=30 * 24 * 3600,
        path="/",
    )
    return user


async def get_current_user(
    ackvia_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
) -> User:
    if ackvia_session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User is not authenticated"
        )
    user = await get_user_by_session_token(db, ackvia_session)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User is not authenticated"
        )

    return user


@router.get("/me", response_model=UserRead, status_code=status.HTTP_200_OK)
async def get_current_user_handler(user: User = Depends(get_current_user)):
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout_handler(
    res: Response,
    ackvia_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    if ackvia_session is not None:
        await logout_session(db, ackvia_session)

    res.delete_cookie(
        key="ackvia_session", httponly=True, secure=True, samesite="lax", path="/"
    )
