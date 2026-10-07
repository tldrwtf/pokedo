"""Authentication utilities for PokeDo server."""

import logging
import os
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

logger = logging.getLogger(__name__)


def _load_secret_key() -> str:
    """Resolve the JWT signing key.

    Refuses to run with a known fallback key: a hardcoded secret lets anyone
    with repo access forge tokens for any user. Local development can opt out
    with POKEDO_DEV=1, which uses a random per-process key instead.
    """
    key = os.getenv("POKEDO_SECRET_KEY")
    if key:
        return key
    if os.getenv("POKEDO_DEV", "").lower() in ("1", "true", "yes"):
        key = secrets.token_urlsafe(32)
        logger.warning(
            "POKEDO_SECRET_KEY is not set; using an ephemeral dev key "
            "(POKEDO_DEV=1). All tokens are invalidated on restart."
        )
        return key
    raise RuntimeError(
        "POKEDO_SECRET_KEY is not set. Generate one with "
        '`python -c "import secrets; print(secrets.token_urlsafe(32))"` and '
        "export it, or set POKEDO_DEV=1 for local development."
    )


# Configuration constants
SECRET_KEY = _load_secret_key()
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash."""
    # bcrypt.checkpw requires bytes
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def get_password_hash(password: str) -> str:
    """Hash a password."""
    # bcrypt.hashpw requires bytes and returns bytes
    pwd_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(pwd_bytes, salt)
    return hashed.decode("utf-8")


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> str | None:
    """Decode a JWT access token and return the subject (username).

    Returns None if the token is invalid or missing a subject.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None
    username: str | None = payload.get("sub")
    return username
