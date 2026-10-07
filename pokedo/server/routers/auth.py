"""Authentication and user endpoints."""

import logging
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from pokedo.core.auth import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    create_access_token,
    get_password_hash,
    verify_password,
)
from pokedo.data.server_models import ServerUser
from pokedo.server.deps import _get_db, get_current_active_user, get_user_from_db
from pokedo.server.schemas import Token, UserCreate, UserPublic, user_public_from

logger = logging.getLogger(__name__)

router = APIRouter(tags=["auth"])


@router.post("/register", response_model=UserPublic)
def register(user: UserCreate, session: Session = Depends(_get_db)):
    existing = get_user_from_db(user.username, session)
    if existing:
        raise HTTPException(status_code=400, detail="Username already registered")
    hashed_password = get_password_hash(user.password)
    db_user = ServerUser(
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        hashed_password=hashed_password,
        trainer_name=user.trainer_name or user.username,
    )
    try:
        session.add(db_user)
        session.commit()
    except IntegrityError:
        # Two concurrent registrations for the same username race past the
        # check above; the unique constraint is the source of truth.
        session.rollback()
        logger.info("Registration race for username %s", user.username)
        raise HTTPException(status_code=400, detail="Username already registered") from None
    session.refresh(db_user)
    return user_public_from(db_user)


@router.post("/token", response_model=Token)
def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: Session = Depends(_get_db),
):
    user = get_user_from_db(form_data.username, session)
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/users/me", response_model=UserPublic)
def read_users_me(current_user: Annotated[ServerUser, Depends(get_current_active_user)]):
    return user_public_from(current_user)
