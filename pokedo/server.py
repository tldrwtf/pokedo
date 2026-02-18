"""PokeDo server -- FastAPI application.

Provides:
  - User registration and JWT authentication (Postgres-backed)
  - Async turn-based PvP battle API
  - Leaderboard queries
  - Health check and sync stub
"""

from contextlib import asynccontextmanager
from datetime import timedelta
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlmodel import Session, select, and_, or_, desc

from pokedo.core.auth import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    ALGORITHM,
    SECRET_KEY,
    create_access_token,
    get_password_hash,
    verify_password,
)
from pokedo.core.battle import (
    BattleActionType,
    BattleEngine,
    BattleFormat,
    BattleState,
    BattleStatus,
    BattleTeam,
    calculate_elo_change,
    compute_rank,
)
from pokedo.data.server_models import (
    BattleRecord,
    LeaderboardEntry,
    ServerUser,
    get_leaderboard,
    get_session,
    init_server_db,
)


# ---------------------------------------------------------------------------
# Startup / shutdown via lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Create DB tables on startup."""
    init_server_db()
    yield


app = FastAPI(title="PokeDo Server", version="0.4.0", lifespan=lifespan)


# ---------------------------------------------------------------------------
# Request/response models
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


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
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str | None = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception from None
    user = get_user_from_db(username, session)
    if user is None:
        raise credentials_exception
    return user


async def get_current_active_user(
    current_user: Annotated[ServerUser, Depends(get_current_user)],
) -> ServerUser:
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------


@app.post("/register", response_model=UserPublic)
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
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return UserPublic(
        username=db_user.username,
        email=db_user.email,
        full_name=db_user.full_name,
        disabled=db_user.disabled,
        trainer_name=db_user.trainer_name,
        elo_rating=db_user.elo_rating,
        pvp_rank=db_user.pvp_rank,
    )


@app.post("/token", response_model=Token)
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


# ---------------------------------------------------------------------------
# General endpoints
# ---------------------------------------------------------------------------


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/users/me", response_model=UserPublic)
def read_users_me(current_user: Annotated[ServerUser, Depends(get_current_active_user)]):
    return UserPublic(
        username=current_user.username,
        email=current_user.email,
        full_name=current_user.full_name,
        disabled=current_user.disabled,
        trainer_name=current_user.trainer_name,
        elo_rating=current_user.elo_rating,
        pvp_rank=current_user.pvp_rank,
    )


@app.post("/sync")
def sync(
    changes: list[ChangeItem],
    current_user: Annotated[ServerUser, Depends(get_current_active_user)],
):
    # Minimal validation; LWW/CRDT logic is a future milestone
    processed = []
    for c in changes:
        if c.action not in {"CREATE", "UPDATE", "DELETE"}:
            raise HTTPException(status_code=400, detail=f"Invalid action: {c.action}")
        processed.append({"id": c.entity_id, "entity_type": c.entity_type, "action": c.action})
    return {"result": "success", "processed": processed, "user": current_user.username}


# ---------------------------------------------------------------------------
# Battle endpoints
# ---------------------------------------------------------------------------


@app.post("/battles/challenge", response_model=BattleSummary)
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
        raise HTTPException(status_code=400, detail=f"Invalid format: {req.format}")

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

    return BattleSummary(
        battle_id=record.battle_id,
        status=record.status,
        format=record.format,
        challenger=record.challenger_username,
        opponent=record.opponent_username,
        created_at=str(record.created_at),
    )


@app.get("/battles/pending", response_model=list[BattleSummary])
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
    return [
        BattleSummary(
            battle_id=r.battle_id,
            status=r.status,
            format=r.format,
            challenger=r.challenger_username,
            opponent=r.opponent_username,
            turn_number=r.turn_count,
            winner=r.winner_username,
            created_at=str(r.created_at),
        )
        for r in records
    ]


@app.post("/battles/{battle_id}/accept", response_model=BattleSummary)
def accept_challenge(
    battle_id: str,
    current_user: Annotated[ServerUser, Depends(get_current_active_user)],
    session: Session = Depends(_get_db),
):
    """Accept a pending battle challenge."""
    record = session.exec(
        select(BattleRecord).where(BattleRecord.battle_id == battle_id)
    ).first()
    if not record:
        raise HTTPException(status_code=404, detail="Battle not found")
    if record.opponent_username != current_user.username:
        raise HTTPException(status_code=403, detail="Only the challenged player can accept")
    if record.status != "pending":
        raise HTTPException(status_code=400, detail=f"Battle is not pending (status={record.status})")

    # Advance to team selection
    state = BattleState.model_validate(record.state_json)
    state.status = BattleStatus.TEAM_SELECT
    record.status = BattleStatus.TEAM_SELECT.value
    record.state_json = state.model_dump(mode="json")
    session.add(record)
    session.commit()
    session.refresh(record)

    return BattleSummary(
        battle_id=record.battle_id,
        status=record.status,
        format=record.format,
        challenger=record.challenger_username,
        opponent=record.opponent_username,
        created_at=str(record.created_at),
    )


@app.post("/battles/{battle_id}/decline", response_model=BattleSummary)
def decline_challenge(
    battle_id: str,
    current_user: Annotated[ServerUser, Depends(get_current_active_user)],
    session: Session = Depends(_get_db),
):
    """Decline a pending battle challenge."""
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
    session.add(record)
    session.commit()

    return BattleSummary(
        battle_id=record.battle_id,
        status=record.status,
        format=record.format,
        challenger=record.challenger_username,
        opponent=record.opponent_username,
        created_at=str(record.created_at),
    )


@app.post("/battles/{battle_id}/team")
def submit_team(
    battle_id: str,
    team_data: TeamSubmission,
    current_user: Annotated[ServerUser, Depends(get_current_active_user)],
    session: Session = Depends(_get_db),
):
    """Submit your Pokemon team for a battle (during team_select phase)."""
    from pokedo.core.battle import BattlePokemon

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
    max_pokemon = {"singles_1v1": 1, "singles_3v3": 3, "singles_6v6": 6}.get(state.format.value, 3)
    if len(team_data.pokemon) < 1 or len(team_data.pokemon) > max_pokemon:
        raise HTTPException(
            status_code=400,
            detail=f"Team must have 1-{max_pokemon} Pokemon for {state.format.value}",
        )

    # Build the BattleTeam
    roster = [BattlePokemon.model_validate(p) for p in team_data.pokemon]
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
    session.add(record)
    session.commit()

    return {
        "result": "team_submitted",
        "battle_id": battle_id,
        "status": record.status,
        "your_team_size": len(roster),
    }


@app.post("/battles/{battle_id}/action")
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

    record = session.exec(
        select(BattleRecord).where(BattleRecord.battle_id == battle_id)
    ).first()
    if not record:
        raise HTTPException(status_code=404, detail="Battle not found")
    if record.status != "active":
        raise HTTPException(status_code=400, detail=f"Battle is not active (status={record.status})")
    if current_user.username not in (record.challenger_username, record.opponent_username):
        raise HTTPException(status_code=403, detail="You are not a participant")

    state = BattleState.model_validate(record.state_json)
    team = state.get_team(current_user.username)
    if not team:
        raise HTTPException(status_code=400, detail="Could not find your team")
    if team.action is not None:
        raise HTTPException(status_code=400, detail="You already submitted an action for this turn")

    # Validate action
    try:
        action_type = BattleActionType(action.action_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid action type: {action.action_type}")

    battle_action = BattleAction(
        action_type=action_type,
        move_index=action.move_index,
        switch_to=action.switch_to,
        player_id=current_user.username,
    )

    # Validate switch target
    if action_type == BattleActionType.SWITCH:
        if action.switch_to is None:
            raise HTTPException(status_code=400, detail="switch_to is required for SWITCH action")
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

        # If battle finished, update ELO
        if state.status in (BattleStatus.FINISHED, BattleStatus.FORFEIT):
            _apply_elo_changes(state, session)
            record.winner_username = state.winner_id
            record.loser_username = state.loser_id
            record.winner_elo_delta = state.winner_elo_delta
            record.loser_elo_delta = state.loser_elo_delta

        record.turn_count = state.turn_number

    record.status = state.status.value
    record.state_json = state.model_dump(mode="json")
    session.add(record)
    session.commit()

    return {
        "result": "action_submitted",
        "battle_id": battle_id,
        "both_submitted": len(turn_events) > 0,
        "turn_number": state.turn_number,
        "status": state.status.value,
        "events": [e.model_dump() for e in turn_events],
        "winner": state.winner_id,
    }


# ---------------------------------------------------------------------------
# Battle history (completed battles) -- MUST be before /battles/{battle_id}
# ---------------------------------------------------------------------------


@app.get("/battles/history/me", response_model=list[BattleSummary])
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
    return [
        BattleSummary(
            battle_id=r.battle_id,
            status=r.status,
            format=r.format,
            challenger=r.challenger_username,
            opponent=r.opponent_username,
            turn_number=r.turn_count,
            winner=r.winner_username,
            created_at=str(r.created_at),
        )
        for r in records
    ]


@app.get("/battles/{battle_id}")
def get_battle(
    battle_id: str,
    current_user: Annotated[ServerUser, Depends(get_current_active_user)],
    session: Session = Depends(_get_db),
):
    """Get the full battle state (as the requesting player sees it)."""
    record = session.exec(
        select(BattleRecord).where(BattleRecord.battle_id == battle_id)
    ).first()
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
        "opponent_team": _censor_team(opp_team) if opp_team else None,
        "winner": state.winner_id,
        "turn_log": [[e.model_dump() for e in turn] for turn in state.turn_log],
    }


@app.get("/battles/{battle_id}/history")
def get_battle_history_endpoint(
    battle_id: str,
    current_user: Annotated[ServerUser, Depends(get_current_active_user)],
    session: Session = Depends(_get_db),
):
    """Get the turn-by-turn event log for a battle."""
    record = session.exec(
        select(BattleRecord).where(BattleRecord.battle_id == battle_id)
    ).first()
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


# ---------------------------------------------------------------------------
# Leaderboard endpoints
# ---------------------------------------------------------------------------


@app.get("/leaderboard", response_model=list[LeaderboardEntry])
def leaderboard(
    sort_by: str = Query("elo_rating", description="Sort field"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: Session = Depends(_get_db),
):
    """Get the global leaderboard."""
    return get_leaderboard(session, sort_by=sort_by, limit=limit, offset=offset)


@app.get("/leaderboard/{username}")
def leaderboard_user(
    username: str,
    session: Session = Depends(_get_db),
):
    """Get a specific user's ranking and stats."""
    user = get_user_from_db(username, session)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Calculate rank (position among all users by ELO)
    stmt = select(ServerUser).where(
        ServerUser.elo_rating > user.elo_rating,
        ServerUser.disabled == False,  # noqa: E712
    )
    higher_count = len(session.exec(stmt).all())
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


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _censor_team(team: BattleTeam) -> dict:
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


def _apply_elo_changes(state: BattleState, session: Session) -> None:
    """Update both players' ELO ratings after a finished battle."""
    if not state.winner_id or not state.loser_id:
        return

    winner = get_user_from_db(state.winner_id, session)
    loser = get_user_from_db(state.loser_id, session)
    if not winner or not loser:
        return

    w_delta, l_delta = calculate_elo_change(winner.elo_rating, loser.elo_rating)

    winner.elo_rating += w_delta
    winner.battle_wins += 1
    winner.pvp_rank = compute_rank(winner.elo_rating)

    loser.elo_rating = max(0, loser.elo_rating + l_delta)
    loser.battle_losses += 1
    loser.pvp_rank = compute_rank(loser.elo_rating)

    state.winner_elo_delta = w_delta
    state.loser_elo_delta = l_delta

    session.add(winner)
    session.add(loser)
