"""Request/response models for the PokeDo server API."""

import re
from typing import Any

from pydantic import BaseModel, field_validator

from pokedo.data.server_models import ServerUser

USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")
MAX_EMAIL_LENGTH = 254
MAX_NAME_LENGTH = 32
MAX_POKEMON_PER_TEAM = 6


class UserPublic(BaseModel):
    username: str
    email: str | None = None
    full_name: str | None = None
    disabled: bool | None = None
    trainer_name: str | None = None
    elo_rating: int = 1000
    pvp_rank: str = "Unranked"


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: str | None = None


class UserCreate(BaseModel):
    username: str
    password: str
    email: str | None = None
    full_name: str | None = None
    trainer_name: str | None = None

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        if not 3 <= len(v) <= 32:
            raise ValueError("username must be 3-32 characters")
        if not USERNAME_PATTERN.match(v):
            raise ValueError("username may only contain letters, digits, '_' and '-'")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("password must be at least 8 characters")
        if len(v) > 128:
            raise ValueError("password must be at most 128 characters")
        return v

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str | None) -> str | None:
        if v is not None and len(v) > MAX_EMAIL_LENGTH:
            raise ValueError("email is too long")
        return v

    @field_validator("full_name", "trainer_name")
    @classmethod
    def validate_name(cls, v: str | None) -> str | None:
        if v is not None and len(v) > MAX_NAME_LENGTH:
            raise ValueError(f"names must be at most {MAX_NAME_LENGTH} characters")
        return v


class ChangeItem(BaseModel):
    entity_id: str
    entity_type: str
    action: str
    timestamp: str
    payload: dict[str, Any]


class ChallengeRequest(BaseModel):
    opponent_username: str
    format: str = "singles_3v3"


class TeamSubmission(BaseModel):
    """Pokemon team data sent by the client for a battle."""

    pokemon: list[dict[str, Any]]  # Serialized BattlePokemon dicts

    @field_validator("pokemon")
    @classmethod
    def validate_roster_size(cls, v: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if len(v) > MAX_POKEMON_PER_TEAM:
            raise ValueError(f"team cannot exceed {MAX_POKEMON_PER_TEAM} Pokemon")
        return v


class ActionSubmission(BaseModel):
    """A battle action from one player."""

    action_type: str  # BattleActionType value
    move_index: int | None = None
    switch_to: int | None = None


class BattleSummary(BaseModel):
    battle_id: str
    status: str
    format: str
    challenger: str
    opponent: str
    turn_number: int = 0
    winner: str | None = None
    created_at: str = ""


def user_public_from(user: ServerUser) -> UserPublic:
    """Build a UserPublic response from a ServerUser row."""
    return UserPublic(
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        disabled=user.disabled,
        trainer_name=user.trainer_name,
        elo_rating=user.elo_rating,
        pvp_rank=user.pvp_rank,
    )
