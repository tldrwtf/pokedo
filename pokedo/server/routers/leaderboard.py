"""Leaderboard endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlmodel import Session, select

from pokedo.data.server_models import LeaderboardEntry, ServerUser, get_leaderboard
from pokedo.server.deps import _get_db, get_user_from_db

router = APIRouter(prefix="/leaderboard", tags=["leaderboard"])


@router.get("", response_model=list[LeaderboardEntry])
def leaderboard(
    sort_by: str = Query("elo_rating", description="Sort field"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: Session = Depends(_get_db),
):
    """Get the global leaderboard."""
    return get_leaderboard(session, sort_by=sort_by, limit=limit, offset=offset)


@router.get("/{username}")
def leaderboard_user(
    username: str,
    session: Session = Depends(_get_db),
):
    """Get a specific user's ranking and stats."""
    user = get_user_from_db(username, session)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Calculate rank (position among all users by ELO) via a COUNT query --
    # materializing every higher-ranked user would be an unauthenticated O(N) cost.
    higher_count = session.exec(
        select(func.count())
        .select_from(ServerUser)
        .where(
            ServerUser.elo_rating > user.elo_rating,
            ServerUser.disabled == False,  # noqa: E712
        )
    ).one()
    rank = higher_count + 1

    total = user.battle_wins + user.battle_losses
    win_rate = (user.battle_wins / total * 100) if total > 0 else 0.0

    return LeaderboardEntry(
        rank=rank,
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
