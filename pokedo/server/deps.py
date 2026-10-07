"""Shared FastAPI dependencies (DB session, current user)."""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import Session, select

from pokedo.core.auth import decode_access_token
from pokedo.data.server_models import ServerUser, get_session

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token")


def _get_db():
    """FastAPI dependency for a Postgres session."""
    yield from get_session()


def get_user_from_db(username: str, session: Session) -> ServerUser | None:
    stmt = select(ServerUser).where(ServerUser.username == username)
    return session.exec(stmt).first()


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    session: Session = Depends(_get_db),
) -> ServerUser:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    username = decode_access_token(token)
    if username is None:
        raise credentials_exception
    user = get_user_from_db(username, session)
    if user is None:
        raise credentials_exception
    return user


async def get_current_active_user(
    current_user: Annotated[ServerUser, Depends(get_current_user)],
) -> ServerUser:
    if current_user.disabled:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user")
    return current_user
