"""Server-side SQLModel models for Postgres persistence.

These models are used ONLY by the server (pokedo/server.py) and are
separate from the client-side SQLite schema in data/database.py.
They store user accounts, battle records, and leaderboard data.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from sqlmodel import JSON, Column, Field, Session, SQLModel, create_engine, select


# ---------------------------------------------------------------------------
# Database connection
# ---------------------------------------------------------------------------

DATABASE_URL = os.getenv(
    "POKEDO_DATABASE_URL",
    "postgresql://pokedo:pokedopass@localhost:5432/pokedo",
)

engine = create_engine(DATABASE_URL, echo=False)


def init_server_db() -> None:
    """Create all server-side tables."""
    SQLModel.metadata.create_all(engine)


def get_session():
    """Yield a new database session (use as a dependency in FastAPI)."""
    with Session(engine) as session:
        yield session


# ---------------------------------------------------------------------------
# User model (replaces fake_users_db)
# ---------------------------------------------------------------------------

class ServerUser(SQLModel, table=True):
    """Persistent user account on the server."""

    __tablename__ = "users"  # type: ignore[assignment]

    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    email: str | None = None
    full_name: str | None = None
    hashed_password: str
    disabled: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Link to the user's local trainer name (set on first sync or registration)
    trainer_name: str | None = None

    # PvP stats (server-authoritative copy)
    elo_rating: int = 1000
    battle_wins: int = 0
    battle_losses: int = 0
    battle_draws: int = 0
    pvp_rank: str = "Unranked"

    # Snapshot of stats for leaderboard (updated on sync or battle)
    total_xp: int = 0
    trainer_level: int = 1
    pokemon_caught: int = 0
    pokedex_caught: int = 0
    tasks_completed: int = 0
    daily_streak_best: int = 0


# ---------------------------------------------------------------------------
# Battle record
# ---------------------------------------------------------------------------

class BattleRecord(SQLModel, table=True):
    """Persistent record of a battle (past or in-progress)."""

    __tablename__ = "battles"  # type: ignore[assignment]

    id: int | None = Field(default=None, primary_key=True)
    battle_id: str = Field(index=True, unique=True)  # UUID
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Format
    format: str = "singles_3v3"  # BattleFormat value

    # Status
    status: str = "pending"  # BattleStatus value

    # Players (usernames)
    challenger_username: str = Field(index=True)
    opponent_username: str = Field(index=True)

    # Battle state (full JSON blob -- loaded into BattleState model)
    state_json: dict = Field(default_factory=dict, sa_column=Column(JSON))

    # Result (filled when battle finishes)
    winner_username: str | None = None
    loser_username: str | None = None
    winner_elo_delta: int = 0
    loser_elo_delta: int = 0
    turn_count: int = 0


# ---------------------------------------------------------------------------
# Leaderboard helpers (queries, not separate tables)
# ---------------------------------------------------------------------------

class LeaderboardEntry(SQLModel):
    """Read-only model for leaderboard API responses (not a table)."""

    rank: int = 0
    username: str
    trainer_name: str | None = None
    elo_rating: int = 1000
    battle_wins: int = 0
    battle_losses: int = 0
    win_rate: float = 0.0
    pvp_rank: str = "Unranked"
    total_xp: int = 0
    trainer_level: int = 1
    pokemon_caught: int = 0
    tasks_completed: int = 0
    daily_streak_best: int = 0


def get_leaderboard(
    session: Session,
    sort_by: str = "elo_rating",
    limit: int = 20,
    offset: int = 0,
) -> list[LeaderboardEntry]:
    """Query the leaderboard from the users table.

    Supported sort_by values:
        elo_rating, battle_wins, total_xp, pokemon_caught,
        tasks_completed, daily_streak_best
    """
    allowed_columns = {
        "elo_rating": ServerUser.elo_rating,
        "battle_wins": ServerUser.battle_wins,
        "total_xp": ServerUser.total_xp,
        "pokemon_caught": ServerUser.pokemon_caught,
        "tasks_completed": ServerUser.tasks_completed,
        "daily_streak_best": ServerUser.daily_streak_best,
    }

    order_col = allowed_columns.get(sort_by, ServerUser.elo_rating)

    stmt = (
        select(ServerUser)
        .where(ServerUser.disabled == False)  # noqa: E712
        .order_by(order_col.desc())  # type: ignore[union-attr]
        .offset(offset)
        .limit(limit)
    )
    users = session.exec(stmt).all()

    entries = []
    for i, user in enumerate(users, start=offset + 1):
        total = user.battle_wins + user.battle_losses
        win_rate = (user.battle_wins / total * 100) if total > 0 else 0.0
        entries.append(
            LeaderboardEntry(
                rank=i,
                username=user.username,
                trainer_name=user.trainer_name,
                elo_rating=user.elo_rating,
                battle_wins=user.battle_wins,
                battle_losses=user.battle_losses,
                win_rate=round(win_rate, 1),
                pvp_rank=user.pvp_rank,
                total_xp=user.total_xp,
                trainer_level=user.trainer_level,
                pokemon_caught=user.pokemon_caught,
                tasks_completed=user.tasks_completed,
                daily_streak_best=user.daily_streak_best,
            )
        )
    return entries
