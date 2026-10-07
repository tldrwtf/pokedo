"""Hardening tests: secrets, rate limiting, validation, optimistic locking, draws."""

import os
import subprocess
import sys
import threading

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

from pokedo.core.battle import BattleFormat, BattleState, BattleStatus
from pokedo.data.server_models import BattleRecord, ServerUser
from pokedo.server import AUTH_RATE_LIMIT, _get_db, app
from pokedo.server.routers import battles as battles_router
from pokedo.server.services.battle import apply_elo_changes

# ---------------------------------------------------------------------------
# Helpers (mirrored from test_server.py; not importable across test modules)
# ---------------------------------------------------------------------------


@pytest.fixture(name="session")
def session_fixture():
    """Create a fresh in-memory SQLite database for each test."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(session: Session):
    """Return a TestClient whose DB dependency is overridden with the test session."""

    def override_get_db():
        yield session

    app.dependency_overrides[_get_db] = override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


def _register(client: TestClient, username: str = "ash", password: str = "pikachu123"):
    return client.post(
        "/register",
        json={
            "username": username,
            "password": password,
            "trainer_name": username.capitalize(),
        },
    )


def _login(client: TestClient, username: str = "ash", password: str = "pikachu123") -> str:
    _register(client, username, password)
    resp = client.post("/token", data={"username": username, "password": password})
    return resp.json()["access_token"]


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _make_battle_pokemon_dict(
    name="pikachu",
    pokemon_id=1,
    pokedex_id=25,
    type1="electric",
    type2=None,
    hp=100,
    level=50,
):
    """Return a dict that can be validated as a BattlePokemon."""
    return {
        "pokemon_id": pokemon_id,
        "pokedex_id": pokedex_id,
        "name": name,
        "type1": type1,
        "type2": type2,
        "max_hp": hp,
        "current_hp": hp,
        "atk": 55,
        "defense": 40,
        "spa": 50,
        "spd": 50,
        "spe": 90,
        "level": level,
        "is_fainted": False,
        "moves": [
            {
                "name": "tackle",
                "type": "normal",
                "damage_class": "physical",
                "power": 40,
                "accuracy": 100,
                "pp": 35,
                "current_pp": 35,
            },
        ],
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _setup_team_select_battle(client: TestClient, fmt: str = "singles_3v3") -> str:
    """Create users, challenge, and accept; return the battle_id (team_select phase)."""
    ash_token = _login(client, "ash", "pikachu123")
    _register(client, "gary", "eevee456")
    gary_token = _login(client, "gary", "eevee456")
    resp = client.post(
        "/battles/challenge",
        json={"opponent_username": "gary", "format": fmt},
        headers=_auth_header(ash_token),
    )
    assert resp.status_code == 200, resp.text
    battle_id = resp.json()["battle_id"]
    resp = client.post(f"/battles/{battle_id}/accept", headers=_auth_header(gary_token))
    assert resp.status_code == 200, resp.text
    return battle_id


# ---------------------------------------------------------------------------
# Secret key handling
# ---------------------------------------------------------------------------


class TestSecretKey:
    def test_missing_secret_key_fails_fast(self):
        """Importing pokedo.core.auth without a key or dev flag must raise."""
        env = {k: v for k, v in os.environ.items() if k not in ("POKEDO_SECRET_KEY", "POKEDO_DEV")}
        proc = subprocess.run(
            [sys.executable, "-c", "import pokedo.core.auth"],
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert proc.returncode != 0
        assert "POKEDO_SECRET_KEY" in proc.stderr

    def test_dev_mode_allows_missing_secret_key(self):
        """POKEDO_DEV=1 permits startup with an ephemeral key."""
        env = {k: v for k, v in os.environ.items() if k not in ("POKEDO_SECRET_KEY", "POKEDO_DEV")}
        env["POKEDO_DEV"] = "1"
        proc = subprocess.run(
            [sys.executable, "-c", "import pokedo.core.auth"],
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert proc.returncode == 0, proc.stderr


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------


class TestRateLimit:
    def test_rate_limit_returns_429(self, client: TestClient, monkeypatch):
        """Requests to credential endpoints beyond the budget get 429."""
        monkeypatch.setattr(AUTH_RATE_LIMIT, "limit", 2)
        assert _register(client, "rluser", "password123").status_code == 200  # 1st request
        ok = client.post("/token", data={"username": "rluser", "password": "password123"})
        assert ok.status_code == 200  # 2nd request
        blocked = client.post("/token", data={"username": "rluser", "password": "password123"})
        assert blocked.status_code == 429
        assert "Retry-After" in blocked.headers

    def test_other_paths_unlimited(self, client: TestClient, monkeypatch):
        """Only credential endpoints are rate limited."""
        monkeypatch.setattr(AUTH_RATE_LIMIT, "limit", 1)
        for _ in range(5):
            assert client.get("/health").status_code == 200


# ---------------------------------------------------------------------------
# Registration validation
# ---------------------------------------------------------------------------


class TestRegistrationValidation:
    def test_short_password_rejected(self, client: TestClient):
        resp = _register(client, "shortypass", "short")
        assert resp.status_code == 422

    def test_bad_username_rejected(self, client: TestClient):
        resp = _register(client, "ab", "password123")  # too short
        assert resp.status_code == 422
        resp = _register(client, "bad name!", "password123")  # illegal chars
        assert resp.status_code == 422

    def test_duplicate_register_still_400(self, client: TestClient):
        assert _register(client, "dupuser", "password123").status_code == 200
        resp = _register(client, "dupuser", "otherpass99")
        assert resp.status_code == 400
        assert resp.json()["detail"] == "Username already registered"


# ---------------------------------------------------------------------------
# Disabled user handling
# ---------------------------------------------------------------------------


def test_disabled_user_gets_403(client: TestClient, session: Session):
    token = _login(client, "disabled1", "password123")
    user = session.exec(select(ServerUser).where(ServerUser.username == "disabled1")).first()
    user.disabled = True
    session.add(user)
    session.commit()
    resp = client.get("/users/me", headers=_auth_header(token))
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Optimistic locking / CAS
# ---------------------------------------------------------------------------


class TestBattleCAS:
    def _make_record(self, session: Session, battle_id: str) -> BattleRecord:
        record = BattleRecord(
            battle_id=battle_id,
            challenger_username="a",
            opponent_username="b",
            state_json={},
        )
        session.add(record)
        session.commit()
        session.refresh(record)
        return record

    def test_stale_version_rejected(self, session: Session):
        record = self._make_record(session, "cas-stale")
        record.status = "team_select"
        assert battles_router._save_battle_state(session, record, 99) is False
        fresh = session.exec(
            select(BattleRecord).where(BattleRecord.battle_id == "cas-stale")
        ).first()
        assert fresh.version == 0
        assert fresh.status == "pending"

    def test_matching_version_writes_and_bumps(self, session: Session):
        record = self._make_record(session, "cas-ok")
        record.status = "team_select"
        assert battles_router._save_battle_state(session, record, record.version) is True
        fresh = session.exec(select(BattleRecord).where(BattleRecord.battle_id == "cas-ok")).first()
        assert fresh.version == 1
        assert fresh.status == "team_select"

    def test_team_submit_retries_after_conflict(
        self, client: TestClient, session: Session, monkeypatch
    ):
        """A CAS conflict mid-request must be retried, not fail the submission."""
        battle_id = _setup_team_select_battle(client)
        real_save = battles_router._save_battle_state
        calls = {"n": 0}

        def flaky_save(s, rec, ver):
            calls["n"] += 1
            if calls["n"] == 1:
                s.rollback()
                return False  # simulate a concurrent writer winning the CAS
            return real_save(s, rec, ver)

        monkeypatch.setattr(battles_router, "_save_battle_state", flaky_save)
        ash_token = _login(client, "ash", "pikachu123")
        resp = client.post(
            f"/battles/{battle_id}/team",
            json={"pokemon": [_make_battle_pokemon_dict()]},
            headers=_auth_header(ash_token),
        )
        assert resp.status_code == 200, resp.text
        assert calls["n"] == 2

    def test_concurrent_team_submissions_both_preserved(self, tmp_path):
        """Two simultaneous team submissions must not lose either team."""
        engine = create_engine(
            f"sqlite:///{tmp_path / 'conc.db'}",
            connect_args={"check_same_thread": False},
        )
        SQLModel.metadata.create_all(engine)

        def override():
            with Session(engine) as s:
                yield s

        app.dependency_overrides[_get_db] = override
        try:
            setup = TestClient(app)
            battle_id = _setup_team_select_battle(setup, fmt="singles_1v1")
            ash_token = _login(setup, "ash", "pikachu123")
            gary_token = _login(setup, "gary", "eevee456")

            barrier = threading.Barrier(2)
            results: dict[str, int] = {}

            def submit(name: str, token: str):
                c = TestClient(app)
                barrier.wait()
                resp = c.post(
                    f"/battles/{battle_id}/team",
                    json={"pokemon": [_make_battle_pokemon_dict(name=name)]},
                    headers=_auth_header(token),
                )
                results[name] = resp.status_code

            t1 = threading.Thread(target=submit, args=("ash", ash_token))
            t2 = threading.Thread(target=submit, args=("gary", gary_token))
            t1.start()
            t2.start()
            t1.join(timeout=30)
            t2.join(timeout=30)

            assert results == {"ash": 200, "gary": 200}, results
            state = setup.get(f"/battles/{battle_id}", headers=_auth_header(ash_token)).json()
            assert state["status"] == "active"
            assert state["your_team"] is not None
            assert state["opponent_team"] is not None
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Draw accounting
# ---------------------------------------------------------------------------


def test_draw_increments_battle_draws(session: Session):
    """A finished battle with no winner counts as a draw for both players."""
    for username in ("drawA", "drawB"):
        session.add(ServerUser(username=username, hashed_password="x", trainer_name=username))
    session.commit()

    state = BattleState(
        challenger_id="drawA",
        opponent_id="drawB",
        format=BattleFormat.SINGLES_3V3,
        status=BattleStatus.FINISHED,
        winner_id=None,
        loser_id=None,
    )
    apply_elo_changes(state, session)

    a = session.exec(select(ServerUser).where(ServerUser.username == "drawA")).first()
    b = session.exec(select(ServerUser).where(ServerUser.username == "drawB")).first()
    assert a.battle_draws == 1 and b.battle_draws == 1
    assert a.battle_wins == 0 and b.battle_losses == 0
    assert a.elo_rating == 1000 and b.elo_rating == 1000
