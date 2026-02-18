"""Tests for the PokeDo FastAPI server.

Uses an in-memory SQLite database to avoid requiring Postgres in CI.
"""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from pokedo.server import app, _get_db


# ---------------------------------------------------------------------------
# Test-scoped SQLite engine + session override
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _register(client: TestClient, username: str = "ash", password: str = "pikachu123"):
    """Register a user and return the response."""
    return client.post(
        "/register",
        json={
            "username": username,
            "password": password,
            "trainer_name": username.capitalize(),
        },
    )


def _login(client: TestClient, username: str = "ash", password: str = "pikachu123") -> str:
    """Register (if needed), login, and return the Bearer token."""
    _register(client, username, password)
    resp = client.post(
        "/token",
        data={"username": username, "password": password},
    )
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
            {
                "name": "thunderbolt",
                "type": "electric",
                "damage_class": "special",
                "power": 90,
                "accuracy": 100,
                "pp": 15,
                "current_pp": 15,
            },
        ],
    }


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


class TestHealth:
    def test_health_check(self, client: TestClient):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


# ---------------------------------------------------------------------------
# Registration & auth
# ---------------------------------------------------------------------------


class TestRegistration:
    def test_register_success(self, client: TestClient):
        resp = _register(client, "ash", "pikachu123")
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == "ash"
        assert data["trainer_name"] == "Ash"
        assert data["elo_rating"] == 1000
        assert data["pvp_rank"] == "Unranked"

    def test_register_duplicate(self, client: TestClient):
        _register(client, "ash", "pikachu123")
        resp = _register(client, "ash", "pikachu123")
        assert resp.status_code == 400
        assert "already registered" in resp.json()["detail"].lower()

    def test_register_default_trainer_name(self, client: TestClient):
        resp = client.post(
            "/register",
            json={"username": "misty", "password": "staryu999"},
        )
        assert resp.status_code == 200
        assert resp.json()["trainer_name"] == "misty"


class TestLogin:
    def test_login_success(self, client: TestClient):
        _register(client, "ash", "pikachu123")
        resp = client.post(
            "/token",
            data={"username": "ash", "password": "pikachu123"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_wrong_password(self, client: TestClient):
        _register(client, "ash", "pikachu123")
        resp = client.post(
            "/token",
            data={"username": "ash", "password": "wrong"},
        )
        assert resp.status_code == 401

    def test_login_nonexistent_user(self, client: TestClient):
        resp = client.post(
            "/token",
            data={"username": "nobody", "password": "test"},
        )
        assert resp.status_code == 401


class TestUsersMe:
    def test_get_current_user(self, client: TestClient):
        token = _login(client)
        resp = client.get("/users/me", headers=_auth_header(token))
        assert resp.status_code == 200
        assert resp.json()["username"] == "ash"

    def test_no_auth_rejected(self, client: TestClient):
        resp = client.get("/users/me")
        assert resp.status_code == 401

    def test_bad_token_rejected(self, client: TestClient):
        resp = client.get("/users/me", headers=_auth_header("not.a.valid.token"))
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Battle challenge flow
# ---------------------------------------------------------------------------


class TestBattleChallenge:
    def test_challenge_success(self, client: TestClient):
        ash_token = _login(client, "ash", "pikachu123")
        _register(client, "gary", "eevee456")

        resp = client.post(
            "/battles/challenge",
            json={"opponent_username": "gary"},
            headers=_auth_header(ash_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "pending"
        assert data["challenger"] == "ash"
        assert data["opponent"] == "gary"

    def test_challenge_self_rejected(self, client: TestClient):
        token = _login(client)
        resp = client.post(
            "/battles/challenge",
            json={"opponent_username": "ash"},
            headers=_auth_header(token),
        )
        assert resp.status_code == 400
        assert "yourself" in resp.json()["detail"].lower()

    def test_challenge_nonexistent_opponent(self, client: TestClient):
        token = _login(client)
        resp = client.post(
            "/battles/challenge",
            json={"opponent_username": "doesnotexist"},
            headers=_auth_header(token),
        )
        assert resp.status_code == 404

    def test_challenge_invalid_format(self, client: TestClient):
        ash_token = _login(client, "ash", "pikachu123")
        _register(client, "gary", "eevee456")

        resp = client.post(
            "/battles/challenge",
            json={"opponent_username": "gary", "format": "invalid_format"},
            headers=_auth_header(ash_token),
        )
        assert resp.status_code == 400


class TestBattleAcceptDecline:
    def _create_pending_battle(self, client: TestClient):
        ash_token = _login(client, "ash", "pikachu123")
        _register(client, "gary", "eevee456")
        resp = client.post(
            "/battles/challenge",
            json={"opponent_username": "gary"},
            headers=_auth_header(ash_token),
        )
        battle_id = resp.json()["battle_id"]
        gary_token = _login(client, "gary", "eevee456")
        return battle_id, ash_token, gary_token

    def test_accept_success(self, client: TestClient):
        battle_id, _, gary_token = self._create_pending_battle(client)
        resp = client.post(
            f"/battles/{battle_id}/accept",
            headers=_auth_header(gary_token),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "team_select"

    def test_accept_wrong_player(self, client: TestClient):
        battle_id, ash_token, _ = self._create_pending_battle(client)
        resp = client.post(
            f"/battles/{battle_id}/accept",
            headers=_auth_header(ash_token),
        )
        assert resp.status_code == 403

    def test_accept_nonexistent_battle(self, client: TestClient):
        token = _login(client)
        resp = client.post(
            "/battles/fake-id/accept",
            headers=_auth_header(token),
        )
        assert resp.status_code == 404

    def test_decline_success(self, client: TestClient):
        battle_id, _, gary_token = self._create_pending_battle(client)
        resp = client.post(
            f"/battles/{battle_id}/decline",
            headers=_auth_header(gary_token),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"

    def test_decline_wrong_player(self, client: TestClient):
        battle_id, ash_token, _ = self._create_pending_battle(client)
        resp = client.post(
            f"/battles/{battle_id}/decline",
            headers=_auth_header(ash_token),
        )
        assert resp.status_code == 403


class TestPendingBattles:
    def test_list_pending_battles(self, client: TestClient):
        ash_token = _login(client, "ash", "pikachu123")
        _register(client, "gary", "eevee456")

        # Create a challenge
        client.post(
            "/battles/challenge",
            json={"opponent_username": "gary"},
            headers=_auth_header(ash_token),
        )

        resp = client.get("/battles/pending", headers=_auth_header(ash_token))
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_pending_visible_to_both(self, client: TestClient):
        ash_token = _login(client, "ash", "pikachu123")
        _register(client, "gary", "eevee456")
        gary_token = _login(client, "gary", "eevee456")

        client.post(
            "/battles/challenge",
            json={"opponent_username": "gary"},
            headers=_auth_header(ash_token),
        )

        resp = client.get("/battles/pending", headers=_auth_header(gary_token))
        assert resp.status_code == 200
        assert len(resp.json()) >= 1


# ---------------------------------------------------------------------------
# Team submission
# ---------------------------------------------------------------------------


class TestTeamSubmission:
    def _setup_team_select(self, client: TestClient):
        """Create a battle in team_select phase and return (battle_id, ash_token, gary_token)."""
        ash_token = _login(client, "ash", "pikachu123")
        _register(client, "gary", "eevee456")
        gary_token = _login(client, "gary", "eevee456")

        # Challenge + accept
        resp = client.post(
            "/battles/challenge",
            json={"opponent_username": "gary"},
            headers=_auth_header(ash_token),
        )
        battle_id = resp.json()["battle_id"]
        client.post(f"/battles/{battle_id}/accept", headers=_auth_header(gary_token))
        return battle_id, ash_token, gary_token

    def test_submit_team(self, client: TestClient):
        battle_id, ash_token, _ = self._setup_team_select(client)
        team = {"pokemon": [_make_battle_pokemon_dict()]}
        resp = client.post(
            f"/battles/{battle_id}/team",
            json=team,
            headers=_auth_header(ash_token),
        )
        assert resp.status_code == 200
        assert resp.json()["result"] == "team_submitted"

    def test_both_teams_activates_battle(self, client: TestClient):
        battle_id, ash_token, gary_token = self._setup_team_select(client)

        team = {"pokemon": [_make_battle_pokemon_dict()]}
        client.post(
            f"/battles/{battle_id}/team",
            json=team,
            headers=_auth_header(ash_token),
        )
        resp = client.post(
            f"/battles/{battle_id}/team",
            json=team,
            headers=_auth_header(gary_token),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "active"

    def test_team_nonparticipant_rejected(self, client: TestClient):
        battle_id, _, _ = self._setup_team_select(client)
        brock_token = _login(client, "brock", "onix789")

        team = {"pokemon": [_make_battle_pokemon_dict()]}
        resp = client.post(
            f"/battles/{battle_id}/team",
            json=team,
            headers=_auth_header(brock_token),
        )
        assert resp.status_code == 403

    def test_empty_team_rejected(self, client: TestClient):
        battle_id, ash_token, _ = self._setup_team_select(client)
        resp = client.post(
            f"/battles/{battle_id}/team",
            json={"pokemon": []},
            headers=_auth_header(ash_token),
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Action submission + turn resolution
# ---------------------------------------------------------------------------


class TestActionSubmission:
    def _setup_active_battle(self, client: TestClient):
        """Create a fully active battle (teams submitted) and return (battle_id, ash_token, gary_token)."""
        ash_token = _login(client, "ash", "pikachu123")
        _register(client, "gary", "eevee456")
        gary_token = _login(client, "gary", "eevee456")

        resp = client.post(
            "/battles/challenge",
            json={"opponent_username": "gary", "format": "singles_1v1"},
            headers=_auth_header(ash_token),
        )
        battle_id = resp.json()["battle_id"]
        client.post(f"/battles/{battle_id}/accept", headers=_auth_header(gary_token))

        team = {"pokemon": [_make_battle_pokemon_dict()]}
        client.post(f"/battles/{battle_id}/team", json=team, headers=_auth_header(ash_token))
        client.post(f"/battles/{battle_id}/team", json=team, headers=_auth_header(gary_token))
        return battle_id, ash_token, gary_token

    def test_submit_attack(self, client: TestClient):
        battle_id, ash_token, _ = self._setup_active_battle(client)
        resp = client.post(
            f"/battles/{battle_id}/action",
            json={"action_type": "attack", "move_index": 0},
            headers=_auth_header(ash_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["result"] == "action_submitted"
        assert data["both_submitted"] is False

    def test_both_actions_resolve_turn(self, client: TestClient):
        battle_id, ash_token, gary_token = self._setup_active_battle(client)

        client.post(
            f"/battles/{battle_id}/action",
            json={"action_type": "attack", "move_index": 0},
            headers=_auth_header(ash_token),
        )
        resp = client.post(
            f"/battles/{battle_id}/action",
            json={"action_type": "attack", "move_index": 0},
            headers=_auth_header(gary_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["both_submitted"] is True
        assert data["turn_number"] == 1
        assert len(data["events"]) > 0

    def test_double_action_rejected(self, client: TestClient):
        battle_id, ash_token, _ = self._setup_active_battle(client)

        client.post(
            f"/battles/{battle_id}/action",
            json={"action_type": "attack", "move_index": 0},
            headers=_auth_header(ash_token),
        )
        resp = client.post(
            f"/battles/{battle_id}/action",
            json={"action_type": "attack", "move_index": 0},
            headers=_auth_header(ash_token),
        )
        assert resp.status_code == 400
        assert "already submitted" in resp.json()["detail"].lower()

    def test_invalid_action_type(self, client: TestClient):
        battle_id, ash_token, _ = self._setup_active_battle(client)
        resp = client.post(
            f"/battles/{battle_id}/action",
            json={"action_type": "dance", "move_index": 0},
            headers=_auth_header(ash_token),
        )
        assert resp.status_code == 400

    def test_forfeit_action(self, client: TestClient):
        battle_id, ash_token, gary_token = self._setup_active_battle(client)

        client.post(
            f"/battles/{battle_id}/action",
            json={"action_type": "forfeit"},
            headers=_auth_header(ash_token),
        )
        resp = client.post(
            f"/battles/{battle_id}/action",
            json={"action_type": "attack", "move_index": 0},
            headers=_auth_header(gary_token),
        )
        data = resp.json()
        assert data["status"] == "forfeit"
        assert data["winner"] == "gary"

    def test_nonparticipant_rejected(self, client: TestClient):
        battle_id, _, _ = self._setup_active_battle(client)
        brock_token = _login(client, "brock", "onix789")
        resp = client.post(
            f"/battles/{battle_id}/action",
            json={"action_type": "attack", "move_index": 0},
            headers=_auth_header(brock_token),
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Battle state retrieval
# ---------------------------------------------------------------------------


class TestGetBattle:
    def _setup_active_battle(self, client: TestClient):
        ash_token = _login(client, "ash", "pikachu123")
        _register(client, "gary", "eevee456")
        gary_token = _login(client, "gary", "eevee456")

        resp = client.post(
            "/battles/challenge",
            json={"opponent_username": "gary", "format": "singles_1v1"},
            headers=_auth_header(ash_token),
        )
        battle_id = resp.json()["battle_id"]
        client.post(f"/battles/{battle_id}/accept", headers=_auth_header(gary_token))

        team = {"pokemon": [_make_battle_pokemon_dict()]}
        client.post(f"/battles/{battle_id}/team", json=team, headers=_auth_header(ash_token))
        client.post(f"/battles/{battle_id}/team", json=team, headers=_auth_header(gary_token))
        return battle_id, ash_token, gary_token

    def test_get_battle_state(self, client: TestClient):
        battle_id, ash_token, _ = self._setup_active_battle(client)
        resp = client.get(
            f"/battles/{battle_id}",
            headers=_auth_header(ash_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["battle_id"] == battle_id
        assert data["your_team"] is not None

    def test_opponent_team_censored(self, client: TestClient):
        """Opponent team should hide non-active Pokemon's HP and moves."""
        battle_id, ash_token, _ = self._setup_active_battle(client)
        resp = client.get(
            f"/battles/{battle_id}",
            headers=_auth_header(ash_token),
        )
        data = resp.json()
        opp = data.get("opponent_team")
        if opp and len(opp.get("roster", [])) > 1:
            # Non-active Pokemon should have HP censored
            non_active = opp["roster"][1]
            assert non_active["current_hp"] is None

    def test_nonparticipant_rejected(self, client: TestClient):
        battle_id, _, _ = self._setup_active_battle(client)
        brock_token = _login(client, "brock", "onix789")
        resp = client.get(
            f"/battles/{battle_id}",
            headers=_auth_header(brock_token),
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Battle history
# ---------------------------------------------------------------------------


class TestBattleHistory:
    def test_empty_history(self, client: TestClient):
        token = _login(client)
        resp = client.get("/battles/history/me", headers=_auth_header(token))
        assert resp.status_code == 200
        assert resp.json() == []

    def test_history_after_forfeit(self, client: TestClient):
        """After a forfeit, the battle should appear in history."""
        ash_token = _login(client, "ash", "pikachu123")
        _register(client, "gary", "eevee456")
        gary_token = _login(client, "gary", "eevee456")

        # Full battle setup
        resp = client.post(
            "/battles/challenge",
            json={"opponent_username": "gary", "format": "singles_1v1"},
            headers=_auth_header(ash_token),
        )
        battle_id = resp.json()["battle_id"]
        client.post(f"/battles/{battle_id}/accept", headers=_auth_header(gary_token))

        team = {"pokemon": [_make_battle_pokemon_dict()]}
        client.post(f"/battles/{battle_id}/team", json=team, headers=_auth_header(ash_token))
        client.post(f"/battles/{battle_id}/team", json=team, headers=_auth_header(gary_token))

        # Forfeit
        client.post(
            f"/battles/{battle_id}/action",
            json={"action_type": "forfeit"},
            headers=_auth_header(ash_token),
        )
        client.post(
            f"/battles/{battle_id}/action",
            json={"action_type": "attack", "move_index": 0},
            headers=_auth_header(gary_token),
        )

        # Check history
        resp = client.get("/battles/history/me", headers=_auth_header(gary_token))
        assert resp.status_code == 200
        history = resp.json()
        assert len(history) >= 1
        assert history[0]["winner"] == "gary"

    def test_route_ordering_history_before_battle_id(self, client: TestClient):
        """/battles/history/me must not be caught by /battles/{battle_id}."""
        token = _login(client)
        resp = client.get("/battles/history/me", headers=_auth_header(token))
        # Should hit the history endpoint, not the get-battle endpoint
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


# ---------------------------------------------------------------------------
# Leaderboard
# ---------------------------------------------------------------------------


class TestLeaderboard:
    def test_empty_leaderboard(self, client: TestClient):
        resp = client.get("/leaderboard")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_leaderboard_with_users(self, client: TestClient):
        _register(client, "ash", "pikachu123")
        _register(client, "gary", "eevee456")
        _register(client, "misty", "staryu999")

        resp = client.get("/leaderboard")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 3

    def test_leaderboard_sort_by(self, client: TestClient):
        _register(client, "ash", "pikachu123")
        _register(client, "gary", "eevee456")

        resp = client.get("/leaderboard?sort_by=battle_wins")
        assert resp.status_code == 200

    def test_leaderboard_limit_offset(self, client: TestClient):
        for i in range(5):
            _register(client, f"user{i}", f"pass{i}word")

        resp = client.get("/leaderboard?limit=2&offset=1")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["rank"] == 2  # offset=1 means start from rank 2

    def test_leaderboard_user_specific(self, client: TestClient):
        _register(client, "ash", "pikachu123")
        resp = client.get("/leaderboard/ash")
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == "ash"
        assert data["rank"] == 1
        assert data["elo_rating"] == 1000

    def test_leaderboard_user_not_found(self, client: TestClient):
        resp = client.get("/leaderboard/nobody")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# ELO updates after battle
# ---------------------------------------------------------------------------


class TestEloIntegration:
    def test_elo_updated_after_forfeit(self, client: TestClient):
        """Winner's ELO should go up and loser's down after a resolved battle."""
        ash_token = _login(client, "ash", "pikachu123")
        _register(client, "gary", "eevee456")
        gary_token = _login(client, "gary", "eevee456")

        resp = client.post(
            "/battles/challenge",
            json={"opponent_username": "gary", "format": "singles_1v1"},
            headers=_auth_header(ash_token),
        )
        battle_id = resp.json()["battle_id"]
        client.post(f"/battles/{battle_id}/accept", headers=_auth_header(gary_token))

        team = {"pokemon": [_make_battle_pokemon_dict()]}
        client.post(f"/battles/{battle_id}/team", json=team, headers=_auth_header(ash_token))
        client.post(f"/battles/{battle_id}/team", json=team, headers=_auth_header(gary_token))

        # Ash forfeits
        client.post(
            f"/battles/{battle_id}/action",
            json={"action_type": "forfeit"},
            headers=_auth_header(ash_token),
        )
        client.post(
            f"/battles/{battle_id}/action",
            json={"action_type": "attack", "move_index": 0},
            headers=_auth_header(gary_token),
        )

        # Check ELO via leaderboard
        gary_stats = client.get("/leaderboard/gary").json()
        ash_stats = client.get("/leaderboard/ash").json()

        assert gary_stats["elo_rating"] > 1000  # Winner gains
        assert ash_stats["elo_rating"] < 1000  # Loser drops
        assert gary_stats["battle_wins"] == 1
        assert ash_stats["battle_wins"] == 0


# ---------------------------------------------------------------------------
# Sync endpoint
# ---------------------------------------------------------------------------


class TestSync:
    def test_sync_basic(self, client: TestClient):
        token = _login(client)
        resp = client.post(
            "/sync",
            json=[
                {
                    "entity_id": "task-1",
                    "entity_type": "task",
                    "action": "CREATE",
                    "timestamp": "2024-01-01T00:00:00Z",
                    "payload": {"title": "Test task"},
                }
            ],
            headers=_auth_header(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["result"] == "success"
        assert len(data["processed"]) == 1

    def test_sync_invalid_action(self, client: TestClient):
        token = _login(client)
        resp = client.post(
            "/sync",
            json=[
                {
                    "entity_id": "task-1",
                    "entity_type": "task",
                    "action": "INVALID",
                    "timestamp": "2024-01-01T00:00:00Z",
                    "payload": {},
                }
            ],
            headers=_auth_header(token),
        )
        assert resp.status_code == 400

    def test_sync_requires_auth(self, client: TestClient):
        resp = client.post("/sync", json=[])
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Additional server validation tests
# ---------------------------------------------------------------------------


class TestBattleAcceptDeclineEdgeCases:
    """Edge cases for accept/decline that are not covered by the main tests."""

    def _create_pending_battle(self, client: TestClient):
        ash_token = _login(client, "ash", "pikachu123")
        _register(client, "gary", "eevee456")
        resp = client.post(
            "/battles/challenge",
            json={"opponent_username": "gary"},
            headers=_auth_header(ash_token),
        )
        battle_id = resp.json()["battle_id"]
        gary_token = _login(client, "gary", "eevee456")
        return battle_id, ash_token, gary_token

    def test_accept_already_accepted(self, client: TestClient):
        """Accepting a non-pending battle should return 400."""
        battle_id, _, gary_token = self._create_pending_battle(client)
        # Accept it first
        resp = client.post(f"/battles/{battle_id}/accept", headers=_auth_header(gary_token))
        assert resp.status_code == 200

        # Try to accept again
        resp = client.post(f"/battles/{battle_id}/accept", headers=_auth_header(gary_token))
        assert resp.status_code == 400
        assert "not pending" in resp.json()["detail"].lower()

    def test_decline_already_declined(self, client: TestClient):
        """Declining a non-pending battle should return 400."""
        battle_id, _, gary_token = self._create_pending_battle(client)
        # Decline it first
        client.post(f"/battles/{battle_id}/decline", headers=_auth_header(gary_token))

        # Try to decline again
        resp = client.post(f"/battles/{battle_id}/decline", headers=_auth_header(gary_token))
        assert resp.status_code == 400
        assert "not pending" in resp.json()["detail"].lower()


class TestTeamSubmissionEdgeCases:
    """Edge cases for team submission."""

    def _setup_team_select(self, client: TestClient, battle_format="singles_3v3"):
        ash_token = _login(client, "ash", "pikachu123")
        _register(client, "gary", "eevee456")
        gary_token = _login(client, "gary", "eevee456")
        resp = client.post(
            "/battles/challenge",
            json={"opponent_username": "gary", "format": battle_format},
            headers=_auth_header(ash_token),
        )
        battle_id = resp.json()["battle_id"]
        client.post(f"/battles/{battle_id}/accept", headers=_auth_header(gary_token))
        return battle_id, ash_token, gary_token

    def test_too_many_pokemon_for_1v1(self, client: TestClient):
        """Submitting 3 Pokemon for a 1v1 battle should fail."""
        battle_id, ash_token, _ = self._setup_team_select(client, "singles_1v1")
        team = {"pokemon": [
            _make_battle_pokemon_dict(name="a", pokemon_id=1),
            _make_battle_pokemon_dict(name="b", pokemon_id=2),
            _make_battle_pokemon_dict(name="c", pokemon_id=3),
        ]}
        resp = client.post(
            f"/battles/{battle_id}/team", json=team,
            headers=_auth_header(ash_token),
        )
        assert resp.status_code == 400
        assert "1-1" in resp.json()["detail"] or "pokemon" in resp.json()["detail"].lower()

    def test_submit_team_wrong_phase(self, client: TestClient):
        """Submitting a team to an already-active battle should fail."""
        battle_id, ash_token, gary_token = self._setup_team_select(client, "singles_1v1")

        team = {"pokemon": [_make_battle_pokemon_dict()]}
        # Submit both teams to activate the battle
        client.post(f"/battles/{battle_id}/team", json=team, headers=_auth_header(ash_token))
        client.post(f"/battles/{battle_id}/team", json=team, headers=_auth_header(gary_token))

        # Try to submit again (battle is now active, not team_select)
        resp = client.post(
            f"/battles/{battle_id}/team", json=team,
            headers=_auth_header(ash_token),
        )
        assert resp.status_code == 400
        assert "not in team selection" in resp.json()["detail"].lower()


class TestActionSubmissionEdgeCases:
    """Edge cases for action submission."""

    def _setup_active_battle(self, client: TestClient, battle_format="singles_1v1"):
        ash_token = _login(client, "ash", "pikachu123")
        _register(client, "gary", "eevee456")
        gary_token = _login(client, "gary", "eevee456")
        resp = client.post(
            "/battles/challenge",
            json={"opponent_username": "gary", "format": battle_format},
            headers=_auth_header(ash_token),
        )
        battle_id = resp.json()["battle_id"]
        client.post(f"/battles/{battle_id}/accept", headers=_auth_header(gary_token))
        team = {"pokemon": [_make_battle_pokemon_dict()]}
        client.post(f"/battles/{battle_id}/team", json=team, headers=_auth_header(ash_token))
        client.post(f"/battles/{battle_id}/team", json=team, headers=_auth_header(gary_token))
        return battle_id, ash_token, gary_token

    def _setup_3v3_battle(self, client: TestClient):
        ash_token = _login(client, "ash", "pikachu123")
        _register(client, "gary", "eevee456")
        gary_token = _login(client, "gary", "eevee456")
        resp = client.post(
            "/battles/challenge",
            json={"opponent_username": "gary", "format": "singles_3v3"},
            headers=_auth_header(ash_token),
        )
        battle_id = resp.json()["battle_id"]
        client.post(f"/battles/{battle_id}/accept", headers=_auth_header(gary_token))
        team = {"pokemon": [
            _make_battle_pokemon_dict(name="a", pokemon_id=1),
            _make_battle_pokemon_dict(name="b", pokemon_id=2),
            _make_battle_pokemon_dict(name="c", pokemon_id=3),
        ]}
        client.post(f"/battles/{battle_id}/team", json=team, headers=_auth_header(ash_token))
        client.post(f"/battles/{battle_id}/team", json=team, headers=_auth_header(gary_token))
        return battle_id, ash_token, gary_token

    def test_action_on_finished_battle_rejected(self, client: TestClient):
        """Submitting an action to a finished battle should return 400."""
        battle_id, ash_token, gary_token = self._setup_active_battle(client)

        # Forfeit to finish the battle
        client.post(
            f"/battles/{battle_id}/action",
            json={"action_type": "forfeit"},
            headers=_auth_header(ash_token),
        )
        client.post(
            f"/battles/{battle_id}/action",
            json={"action_type": "attack", "move_index": 0},
            headers=_auth_header(gary_token),
        )

        # Now try submitting another action
        resp = client.post(
            f"/battles/{battle_id}/action",
            json={"action_type": "attack", "move_index": 0},
            headers=_auth_header(ash_token),
        )
        assert resp.status_code == 400
        assert "not active" in resp.json()["detail"].lower()

    def test_switch_requires_switch_to(self, client: TestClient):
        """SWITCH action without switch_to should return 400."""
        battle_id, ash_token, _ = self._setup_active_battle(client)
        resp = client.post(
            f"/battles/{battle_id}/action",
            json={"action_type": "switch"},
            headers=_auth_header(ash_token),
        )
        assert resp.status_code == 400
        assert "switch_to" in resp.json()["detail"].lower()

    def test_switch_invalid_index(self, client: TestClient):
        """SWITCH with out-of-range index should return 400."""
        battle_id, ash_token, _ = self._setup_active_battle(client)
        resp = client.post(
            f"/battles/{battle_id}/action",
            json={"action_type": "switch", "switch_to": 99},
            headers=_auth_header(ash_token),
        )
        assert resp.status_code == 400
        assert "invalid" in resp.json()["detail"].lower()

    def test_switch_to_already_active(self, client: TestClient):
        """SWITCH to the already-active Pokemon should return 400."""
        battle_id, ash_token, _ = self._setup_3v3_battle(client)
        resp = client.post(
            f"/battles/{battle_id}/action",
            json={"action_type": "switch", "switch_to": 0},
            headers=_auth_header(ash_token),
        )
        assert resp.status_code == 400
        assert "already active" in resp.json()["detail"].lower()

    def test_invalid_move_index_rejected(self, client: TestClient):
        """Out-of-range move index should return 400."""
        battle_id, ash_token, _ = self._setup_active_battle(client)
        resp = client.post(
            f"/battles/{battle_id}/action",
            json={"action_type": "attack", "move_index": 99},
            headers=_auth_header(ash_token),
        )
        assert resp.status_code == 400
        assert "invalid move index" in resp.json()["detail"].lower()

    def test_negative_move_index_rejected(self, client: TestClient):
        """Negative move index should return 400."""
        battle_id, ash_token, _ = self._setup_active_battle(client)
        resp = client.post(
            f"/battles/{battle_id}/action",
            json={"action_type": "attack", "move_index": -1},
            headers=_auth_header(ash_token),
        )
        assert resp.status_code == 400
        assert "invalid move index" in resp.json()["detail"].lower()


class TestBattleHistoryEndpoint:
    """Tests for GET /battles/{id}/history (turn-by-turn log)."""

    def test_battle_history_endpoint(self, client: TestClient):
        """Turn-by-turn history should be retrievable for a battle."""
        ash_token = _login(client, "ash", "pikachu123")
        _register(client, "gary", "eevee456")
        gary_token = _login(client, "gary", "eevee456")

        resp = client.post(
            "/battles/challenge",
            json={"opponent_username": "gary", "format": "singles_1v1"},
            headers=_auth_header(ash_token),
        )
        battle_id = resp.json()["battle_id"]
        client.post(f"/battles/{battle_id}/accept", headers=_auth_header(gary_token))

        team = {"pokemon": [_make_battle_pokemon_dict()]}
        client.post(f"/battles/{battle_id}/team", json=team, headers=_auth_header(ash_token))
        client.post(f"/battles/{battle_id}/team", json=team, headers=_auth_header(gary_token))

        # Play a turn
        client.post(
            f"/battles/{battle_id}/action",
            json={"action_type": "attack", "move_index": 0},
            headers=_auth_header(ash_token),
        )
        client.post(
            f"/battles/{battle_id}/action",
            json={"action_type": "attack", "move_index": 0},
            headers=_auth_header(gary_token),
        )

        # Get history
        resp = client.get(
            f"/battles/{battle_id}/history",
            headers=_auth_header(ash_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["battle_id"] == battle_id
        assert "turns" in data
        assert len(data["turns"]) >= 1

    def test_battle_history_nonparticipant(self, client: TestClient):
        """Non-participant should be denied access to battle history."""
        ash_token = _login(client, "ash", "pikachu123")
        _register(client, "gary", "eevee456")
        gary_token = _login(client, "gary", "eevee456")

        resp = client.post(
            "/battles/challenge",
            json={"opponent_username": "gary", "format": "singles_1v1"},
            headers=_auth_header(ash_token),
        )
        battle_id = resp.json()["battle_id"]

        brock_token = _login(client, "brock", "onix789")
        resp = client.get(
            f"/battles/{battle_id}/history",
            headers=_auth_header(brock_token),
        )
        assert resp.status_code == 403

    def test_battle_history_not_found(self, client: TestClient):
        """Non-existent battle history should return 404."""
        token = _login(client)
        resp = client.get(
            "/battles/fake-battle-id/history",
            headers=_auth_header(token),
        )
        assert resp.status_code == 404


class TestCensorTeamMultiMon:
    """Test that _censor_team properly hides non-active Pokemon info."""

    def test_opponent_team_censored_multi_mon(self, client: TestClient):
        """With 3 Pokemon, non-active mons should have current_hp=None and moves=[]."""
        ash_token = _login(client, "ash", "pikachu123")
        _register(client, "gary", "eevee456")
        gary_token = _login(client, "gary", "eevee456")

        resp = client.post(
            "/battles/challenge",
            json={"opponent_username": "gary", "format": "singles_3v3"},
            headers=_auth_header(ash_token),
        )
        battle_id = resp.json()["battle_id"]
        client.post(f"/battles/{battle_id}/accept", headers=_auth_header(gary_token))

        team = {"pokemon": [
            _make_battle_pokemon_dict(name="a", pokemon_id=1),
            _make_battle_pokemon_dict(name="b", pokemon_id=2),
            _make_battle_pokemon_dict(name="c", pokemon_id=3),
        ]}
        client.post(f"/battles/{battle_id}/team", json=team, headers=_auth_header(ash_token))
        client.post(f"/battles/{battle_id}/team", json=team, headers=_auth_header(gary_token))

        # Ash looks at battle -- Gary's non-active mons should be censored
        resp = client.get(f"/battles/{battle_id}", headers=_auth_header(ash_token))
        assert resp.status_code == 200
        opp = resp.json()["opponent_team"]
        roster = opp["roster"]
        assert len(roster) == 3
        # Active Pokemon (index 0) should have its data
        assert roster[0]["current_hp"] is not None
        assert len(roster[0]["moves"]) > 0
        # Non-active Pokemon should be censored
        assert roster[1]["current_hp"] is None
        assert roster[1]["moves"] == []
        assert roster[2]["current_hp"] is None
        assert roster[2]["moves"] == []
