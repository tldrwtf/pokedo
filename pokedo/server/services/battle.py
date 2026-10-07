"""Battle service helpers (ELO application, opponent team censoring).

ELO/stat updates use compare-and-swap on ``ServerUser.version`` so two battles
finishing concurrently that share a player cannot lose an update. Callers that
fail CAS should retry from a fresh read.
"""

from sqlalchemy import update
from sqlmodel import Session

from pokedo.core.battle import (
    BattleState,
    BattleTeam,
    calculate_elo_change,
    compute_rank,
)
from pokedo.data.server_models import ServerUser
from pokedo.server.deps import get_user_from_db

# Bounded retries for concurrent stat updates on the same user row.
MAX_STAT_ATTEMPTS = 3


class StatUpdateError(Exception):
    """Raised when a player's stats cannot be updated without losing a write."""


def censor_team(team: BattleTeam | None) -> dict:
    """Return a team dict with limited info (hide exact HP, moves of non-active Pokemon)."""
    if not team:
        return {}
    data = team.model_dump(mode="json")
    for i, poke in enumerate(data.get("roster", [])):
        if i != data.get("active_index", 0):
            # Hide non-active Pokemon's current_hp (show only that they exist)
            poke["current_hp"] = None
            poke["moves"] = []
    return data


def _cas_update_user(
    session: Session,
    username: str,
    *,
    elo_delta: int,
    result: str,
) -> bool:
    """Atomically apply one battle result to a user's stats.

    ``result`` is "win", "loss", or "draw". Returns False on version conflict.
    """
    user = get_user_from_db(username, session)
    if not user:
        return True  # Nothing to update; do not block battle resolution.

    new_elo = max(0, user.elo_rating + elo_delta)
    values: dict = {
        "elo_rating": new_elo,
        "pvp_rank": compute_rank(new_elo),
        "version": user.version + 1,
    }
    if result == "win":
        values["battle_wins"] = user.battle_wins + 1
    elif result == "loss":
        values["battle_losses"] = user.battle_losses + 1
    else:
        values["battle_draws"] = user.battle_draws + 1

    stmt = (
        update(ServerUser)
        .where(ServerUser.id == user.id)
        .where(ServerUser.version == user.version)
        .values(**values)
    )
    return session.execute(stmt).rowcount == 1  # type: ignore[union-attr]


def apply_elo_changes(state: BattleState, session: Session) -> None:
    """Update both players' stats after a battle finishes.

    Finished battles with no winner are draws: both players get
    battle_draws + 1 and no ELO change. Raises StatUpdateConflict when a
    concurrent write on a player row was detected on every attempt.
    """
    finished_with_winner = bool(state.winner_id and state.loser_id)
    is_draw = not finished_with_winner and state.status.value == "finished"
    if not finished_with_winner and not is_draw:
        return

    if is_draw:
        outcomes = (
            (state.challenger_id, 0, "draw"),
            (state.opponent_id, 0, "draw"),
        )
    else:
        winner = get_user_from_db(state.winner_id, session)  # type: ignore[arg-type]
        loser = get_user_from_db(state.loser_id, session)  # type: ignore[arg-type]
        if not winner or not loser:
            return
        w_delta, l_delta = calculate_elo_change(winner.elo_rating, loser.elo_rating)
        outcomes = (
            (state.winner_id, w_delta, "win"),  # type: ignore[list-item]
            (state.loser_id, l_delta, "loss"),  # type: ignore[list-item]
        )
        state.winner_elo_delta = w_delta
        state.loser_elo_delta = l_delta

    for _ in range(MAX_STAT_ATTEMPTS):
        if all(
            _cas_update_user(session, username, elo_delta=delta, result=result)
            for username, delta, result in outcomes
        ):
            return
        session.rollback()
    raise StatUpdateError(
        f"Could not update stats for {[o[0] for o in outcomes]} without losing a write"
    )
