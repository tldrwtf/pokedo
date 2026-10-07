"""PvP battle endpoints.

Mutating handlers follow a read -> validate -> CAS-write -> retry loop:
``_save_battle_state`` only commits when the row's optimistic-lock ``version``
is unchanged, so concurrent team/action submissions retry from fresh state
instead of clobbering each other's ``state_json`` (lost-update).
"""

import json
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import update
from sqlmodel import Session, and_, desc, or_, select

from pokedo.core.battle import (
    BattleActionType,
    BattleEngine,
    BattleFormat,
    BattlePokemon,
    BattleState,
    BattleStatus,
    BattleTeam,
)
from pokedo.data.server_models import BattleRecord, ServerUser
from pokedo.server.deps import _get_db, get_current_active_user, get_user_from_db
from pokedo.server.schemas import ActionSubmission, BattleSummary, ChallengeRequest, TeamSubmission
from pokedo.server.services.battle import StatUpdateError, apply_elo_changes, censor_team

router = APIRouter(prefix="/battles", tags=["battles"])

# Bounded retries for the optimistic-lock loop before giving up with 409.
MAX_BATTLE_WRITE_ATTEMPTS = 3

# Cheap sanity bound on client-supplied Pokemon payloads. Full server-side
# roster validation (anti-cheat) is deferred; this only stops absurd blobs.
MAX_POKEMON_JSON_BYTES = 8192


def _json_bytes(obj: object) -> int:
    return len(json.dumps(obj, separators=(",", ":")).encode("utf-8"))


def _save_battle_state(session: Session, record: BattleRecord, expected_version: int) -> bool:
    """Compare-and-swap write of all mutable battle fields.

    Commits (including any pending ServerUser stat updates from ELO
    application) only when no concurrent write happened; rolls back
    otherwise. Returns False on version conflict.
    """
    stmt = (
        update(BattleRecord)
        .where(BattleRecord.id == record.id)
        .where(BattleRecord.version == expected_version)
        .values(
            status=record.status,
            state_json=record.state_json,
            turn_count=record.turn_count,
            winner_username=record.winner_username,
            loser_username=record.loser_username,
            winner_elo_delta=record.winner_elo_delta,
            loser_elo_delta=record.loser_elo_delta,
            updated_at=datetime.now(timezone.utc),
            version=expected_version + 1,
        )
    )
    ok = session.execute(stmt).rowcount == 1  # type: ignore[union-attr]
    if ok:
        record.version = expected_version + 1
        session.commit()
    else:
        session.rollback()
    return ok


def _battle_summary(record: BattleRecord) -> BattleSummary:
    return BattleSummary(
        battle_id=record.battle_id,
        status=record.status,
        format=record.format,
        challenger=record.challenger_username,
        opponent=record.opponent_username,
        turn_number=record.turn_count,
        winner=record.winner_username,
        created_at=str(record.created_at),
    )


@router.post("/challenge", response_model=BattleSummary)
def challenge_player(
    req: ChallengeRequest,
    current_user: Annotated[ServerUser, Depends(get_current_active_user)],
    session: Session = Depends(_get_db),
):
    """Send a battle challenge to another player."""
    if req.opponent_username == current_user.username:
        raise HTTPException(status_code=400, detail="You cannot challenge yourself")

    opponent = get_user_from_db(req.opponent_username, session)
    if not opponent:
        raise HTTPException(status_code=404, detail="Opponent not found")

    # Validate format
    try:
        fmt = BattleFormat(req.format)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid format: {req.format}") from None

    # Create initial battle state
    battle_state = BattleState(
        challenger_id=current_user.username,
        opponent_id=req.opponent_username,
        format=fmt,
        status=BattleStatus.PENDING,
    )

    record = BattleRecord(
        battle_id=battle_state.battle_id,
        format=fmt.value,
        status=BattleStatus.PENDING.value,
        challenger_username=current_user.username,
        opponent_username=req.opponent_username,
        state_json=battle_state.model_dump(mode="json"),
    )
    session.add(record)
    session.commit()
    session.refresh(record)

    return _battle_summary(record)


@router.get("/pending", response_model=list[BattleSummary])
def list_pending_battles(
    current_user: Annotated[ServerUser, Depends(get_current_active_user)],
    session: Session = Depends(_get_db),
):
    """List battles waiting for the current user to accept or take action."""
    stmt = select(BattleRecord).where(
        and_(
            BattleRecord.status.in_(["pending", "team_select", "active"]),  # type: ignore[union-attr]
            or_(
                BattleRecord.challenger_username == current_user.username,
                BattleRecord.opponent_username == current_user.username,
            ),
        )
    )
    records = session.exec(stmt).all()
    return [_battle_summary(r) for r in records]


@router.post("/{battle_id}/accept", response_model=BattleSummary)
def accept_challenge(
    battle_id: str,
    current_user: Annotated[ServerUser, Depends(get_current_active_user)],
    session: Session = Depends(_get_db),
):
    """Accept a pending battle challenge."""
    for _ in range(MAX_BATTLE_WRITE_ATTEMPTS):
        record = session.exec(
            select(BattleRecord).where(BattleRecord.battle_id == battle_id)
        ).first()
        if not record:
            raise HTTPException(status_code=404, detail="Battle not found")
        if record.opponent_username != current_user.username:
            raise HTTPException(status_code=403, detail="Only the challenged player can accept")
        if record.status != "pending":
            raise HTTPException(
                status_code=400, detail=f"Battle is not pending (status={record.status})"
            )

        # Advance to team selection
        state = BattleState.model_validate(record.state_json)
        state.status = BattleStatus.TEAM_SELECT
        record.status = BattleStatus.TEAM_SELECT.value
        record.state_json = state.model_dump(mode="json")

        if _save_battle_state(session, record, record.version):
            return _battle_summary(record)
    raise HTTPException(status_code=409, detail="Battle is being modified concurrently; retry")


@router.post("/{battle_id}/decline", response_model=BattleSummary)
def decline_challenge(
    battle_id: str,
    current_user: Annotated[ServerUser, Depends(get_current_active_user)],
    session: Session = Depends(_get_db),
):
    """Decline a pending battle challenge."""
    for _ in range(MAX_BATTLE_WRITE_ATTEMPTS):
        record = session.exec(
            select(BattleRecord).where(BattleRecord.battle_id == battle_id)
        ).first()
        if not record:
            raise HTTPException(status_code=404, detail="Battle not found")
        if record.opponent_username != current_user.username:
            raise HTTPException(status_code=403, detail="Only the challenged player can decline")
        if record.status != "pending":
            raise HTTPException(status_code=400, detail="Battle is not pending")

        state = BattleState.model_validate(record.state_json)
        state.status = BattleStatus.CANCELLED
        record.status = BattleStatus.CANCELLED.value
        record.state_json = state.model_dump(mode="json")

        if _save_battle_state(session, record, record.version):
            return _battle_summary(record)
    raise HTTPException(status_code=409, detail="Battle is being modified concurrently; retry")


@router.post("/{battle_id}/team")
def submit_team(
    battle_id: str,
    team_data: TeamSubmission,
    current_user: Annotated[ServerUser, Depends(get_current_active_user)],
    session: Session = Depends(_get_db),
):
    """Submit your Pokemon team for a battle (during team_select phase)."""
    max_roster = 6
    if len(team_data.pokemon) > max_roster:
        raise HTTPException(status_code=400, detail=f"Team cannot exceed {max_roster} Pokemon")
    if any(_json_bytes(p) > MAX_POKEMON_JSON_BYTES for p in team_data.pokemon):
        raise HTTPException(status_code=400, detail="Pokemon entry too large")

    for _ in range(MAX_BATTLE_WRITE_ATTEMPTS):
        record = session.exec(
            select(BattleRecord).where(BattleRecord.battle_id == battle_id)
        ).first()
        if not record:
            raise HTTPException(status_code=404, detail="Battle not found")
        if record.status != "team_select":
            raise HTTPException(status_code=400, detail="Battle is not in team selection phase")
        if current_user.username not in (record.challenger_username, record.opponent_username):
            raise HTTPException(status_code=403, detail="You are not a participant in this battle")

        state = BattleState.model_validate(record.state_json)

        # Validate team size based on format
        max_pokemon = {"singles_1v1": 1, "singles_3v3": 3, "singles_6v6": 6}.get(
            state.format.value, 3
        )
        if len(team_data.pokemon) < 1 or len(team_data.pokemon) > max_pokemon:
            raise HTTPException(
                status_code=400,
                detail=f"Team must have 1-{max_pokemon} Pokemon for {state.format.value}",
            )

        # Build the BattleTeam
        try:
            roster = [BattlePokemon.model_validate(p) for p in team_data.pokemon]
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"Invalid Pokemon data: {exc}") from None
        team = BattleTeam(
            player_id=current_user.username,
            trainer_name=current_user.trainer_name or current_user.username,
            roster=roster,
        )

        if current_user.username == state.challenger_id:
            state.team1 = team
        else:
            state.team2 = team

        # If both teams submitted, advance to active
        if state.team1 is not None and state.team2 is not None:
            state.status = BattleStatus.ACTIVE
            record.status = BattleStatus.ACTIVE.value

        record.state_json = state.model_dump(mode="json")

        if _save_battle_state(session, record, record.version):
            return {
                "result": "team_submitted",
                "battle_id": battle_id,
                "status": record.status,
                "your_team_size": len(roster),
            }
    raise HTTPException(status_code=409, detail="Battle is being modified concurrently; retry")


@router.post("/{battle_id}/action")
def submit_action(
    battle_id: str,
    action: ActionSubmission,
    current_user: Annotated[ServerUser, Depends(get_current_active_user)],
    session: Session = Depends(_get_db),
):
    """Submit a battle action for the current turn.

    When both players have submitted, the turn is resolved automatically.
    """
    from pokedo.core.battle import BattleAction

    for _ in range(MAX_BATTLE_WRITE_ATTEMPTS):
        record = session.exec(
            select(BattleRecord).where(BattleRecord.battle_id == battle_id)
        ).first()
        if not record:
            raise HTTPException(status_code=404, detail="Battle not found")
        if record.status != "active":
            raise HTTPException(
                status_code=400, detail=f"Battle is not active (status={record.status})"
            )
        if current_user.username not in (record.challenger_username, record.opponent_username):
            raise HTTPException(status_code=403, detail="You are not a participant")

        state = BattleState.model_validate(record.state_json)
        team = state.get_team(current_user.username)
        if not team:
            raise HTTPException(status_code=400, detail="Could not find your team")
        if team.action is not None:
            raise HTTPException(
                status_code=400, detail="You already submitted an action for this turn"
            )

        # Validate action
        try:
            action_type = BattleActionType(action.action_type)
        except ValueError:
            raise HTTPException(
                status_code=400, detail=f"Invalid action type: {action.action_type}"
            ) from None

        battle_action = BattleAction(
            action_type=action_type,
            move_index=action.move_index,
            switch_to=action.switch_to,
            player_id=current_user.username,
        )

        # Validate switch target
        if action_type == BattleActionType.SWITCH:
            if action.switch_to is None:
                raise HTTPException(
                    status_code=400, detail="switch_to is required for SWITCH action"
                )
            if action.switch_to < 0 or action.switch_to >= len(team.roster):
                raise HTTPException(status_code=400, detail="Invalid switch target index")
            if team.roster[action.switch_to].is_fainted:
                raise HTTPException(status_code=400, detail="Cannot switch to a fainted Pokemon")
            if action.switch_to == team.active_index:
                raise HTTPException(status_code=400, detail="That Pokemon is already active")

        # Validate move index
        if action_type == BattleActionType.ATTACK:
            mon = team.active_pokemon
            if mon and action.move_index is not None:
                if action.move_index < 0 or action.move_index >= len(mon.moves):
                    raise HTTPException(status_code=400, detail="Invalid move index")

        team.action = battle_action

        # Check if both players have submitted -- resolve the turn
        turn_events = []
        if state.both_actions_submitted():
            turn_events = BattleEngine.resolve_turn(state)

            # If battle finished, update ELO/draw stats (CAS on user rows)
            if state.status in (BattleStatus.FINISHED, BattleStatus.FORFEIT):
                try:
                    apply_elo_changes(state, session)
                except StatUpdateError:
                    session.rollback()
                    continue  # retry from fresh state
                record.winner_username = state.winner_id
                record.loser_username = state.loser_id
                record.winner_elo_delta = state.winner_elo_delta
                record.loser_elo_delta = state.loser_elo_delta

            record.turn_count = state.turn_number

        record.status = state.status.value
        record.state_json = state.model_dump(mode="json")

        if _save_battle_state(session, record, record.version):
            return {
                "result": "action_submitted",
                "battle_id": battle_id,
                "both_submitted": len(turn_events) > 0,
                "turn_number": state.turn_number,
                "status": state.status.value,
                "events": [e.model_dump() for e in turn_events],
                "winner": state.winner_id,
            }
    raise HTTPException(status_code=409, detail="Battle is being modified concurrently; retry")


# --- History (completed battles) -- MUST be registered before /{battle_id} ---


@router.get("/history/me", response_model=list[BattleSummary])
def my_battle_history(
    current_user: Annotated[ServerUser, Depends(get_current_active_user)],
    limit: int = Query(20, ge=1, le=100),
    session: Session = Depends(_get_db),
):
    """Get the current user's completed battle history."""
    stmt = (
        select(BattleRecord)
        .where(
            and_(
                BattleRecord.status.in_(["finished", "forfeit"]),  # type: ignore[union-attr]
                or_(
                    BattleRecord.challenger_username == current_user.username,
                    BattleRecord.opponent_username == current_user.username,
                ),
            )
        )
        .order_by(desc(BattleRecord.updated_at))
        .limit(limit)
    )
    records = session.exec(stmt).all()
    return [_battle_summary(r) for r in records]


@router.get("/{battle_id}")
def get_battle(
    battle_id: str,
    current_user: Annotated[ServerUser, Depends(get_current_active_user)],
    session: Session = Depends(_get_db),
):
    """Get the full battle state (as the requesting player sees it)."""
    record = session.exec(select(BattleRecord).where(BattleRecord.battle_id == battle_id)).first()
    if not record:
        raise HTTPException(status_code=404, detail="Battle not found")
    if current_user.username not in (record.challenger_username, record.opponent_username):
        raise HTTPException(status_code=403, detail="You are not a participant")

    state = BattleState.model_validate(record.state_json)

    # Return a filtered view so each player only sees their own team's HP details
    my_team = state.get_team(current_user.username)
    opp_team = state.get_opponent_team(current_user.username)

    return {
        "battle_id": state.battle_id,
        "status": state.status.value,
        "format": state.format.value,
        "turn_number": state.turn_number,
        "your_team": my_team.model_dump(mode="json") if my_team else None,
        "opponent_team": censor_team(opp_team) if opp_team else None,
        "winner": state.winner_id,
        "turn_log": [[e.model_dump() for e in turn] for turn in state.turn_log],
    }


@router.get("/{battle_id}/history")
def get_battle_history_endpoint(
    battle_id: str,
    current_user: Annotated[ServerUser, Depends(get_current_active_user)],
    session: Session = Depends(_get_db),
):
    """Get the turn-by-turn event log for a battle."""
    record = session.exec(select(BattleRecord).where(BattleRecord.battle_id == battle_id)).first()
    if not record:
        raise HTTPException(status_code=404, detail="Battle not found")
    if current_user.username not in (record.challenger_username, record.opponent_username):
        raise HTTPException(status_code=403, detail="You are not a participant")

    state = BattleState.model_validate(record.state_json)
    return {
        "battle_id": battle_id,
        "turns": [[e.model_dump() for e in turn] for turn in state.turn_log],
        "status": state.status.value,
        "winner": state.winner_id,
    }
