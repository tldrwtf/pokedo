"""Tests for the async turn-based battle engine."""

import random

import pytest

from pokedo.core.battle import (
    BattleAction,
    BattleActionType,
    BattleEngine,
    BattleFormat,
    BattlePokemon,
    BattleState,
    BattleStatus,
    BattleTeam,
    TurnEvent,
    calculate_elo_change,
    create_battle_pokemon,
)
from pokedo.core.moves import DamageClass, Move, StatusEffect


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_move(name="tackle", type_="normal", power=40, accuracy=100, pp=35, damage_class=DamageClass.PHYSICAL) -> Move:
    return Move(name=name, type=type_, damage_class=damage_class, power=power, accuracy=accuracy, pp=pp)


def _make_battle_pokemon(
    name="pikachu",
    pokemon_id=1,
    pokedex_id=25,
    type1="electric",
    type2=None,
    hp=100,
    atk=55,
    defense=40,
    spa=50,
    spd=50,
    spe=90,
    level=50,
    moves=None,
) -> BattlePokemon:
    if moves is None:
        moves = [_make_move(), _make_move("thunderbolt", "electric", 90, 100, 15, DamageClass.SPECIAL)]
    return BattlePokemon(
        pokemon_id=pokemon_id,
        pokedex_id=pokedex_id,
        name=name,
        type1=type1,
        type2=type2,
        max_hp=hp,
        current_hp=hp,
        atk=atk,
        defense=defense,
        spa=spa,
        spd=spd,
        spe=spe,
        level=level,
        moves=moves,
    )


def _make_team(pokemon_list=None, player_id="player1", trainer_name="Ash") -> BattleTeam:
    if pokemon_list is None:
        pokemon_list = [_make_battle_pokemon()]
    return BattleTeam(player_id=player_id, trainer_name=trainer_name, roster=pokemon_list)


def _make_active_battle(team1=None, team2=None) -> BattleState:
    """Create a battle state that's already in ACTIVE status with teams set."""
    t1 = team1 or _make_team(player_id="player1", trainer_name="Ash")
    t2 = team2 or _make_team(
        pokemon_list=[_make_battle_pokemon(name="charmander", type1="fire", pokedex_id=4, spe=65)],
        player_id="player2",
        trainer_name="Gary",
    )
    return BattleState(
        challenger_id="player1",
        opponent_id="player2",
        format=BattleFormat.SINGLES_1V1,
        status=BattleStatus.ACTIVE,
        team1=t1,
        team2=t2,
    )


# ---------------------------------------------------------------------------
# BattlePokemon
# ---------------------------------------------------------------------------


class TestBattlePokemon:
    """Tests for BattlePokemon model."""

    def test_display_name_uses_nickname(self):
        bp = _make_battle_pokemon()
        bp.nickname = "Sparky"
        assert bp.display_name == "Sparky"

    def test_display_name_capitalizes_name(self):
        bp = _make_battle_pokemon(name="bulbasaur")
        assert bp.display_name == "Bulbasaur"

    def test_hp_percent(self):
        bp = _make_battle_pokemon(hp=200)
        bp.current_hp = 100
        assert bp.hp_percent == 50.0

    def test_hp_percent_zero_max(self):
        bp = _make_battle_pokemon(hp=0)
        assert bp.hp_percent == 0.0

    def test_types_single(self):
        bp = _make_battle_pokemon(type1="fire", type2=None)
        assert bp.types == ["fire"]

    def test_types_dual(self):
        bp = _make_battle_pokemon(type1="fire", type2="flying")
        assert bp.types == ["fire", "flying"]

    def test_take_damage(self):
        bp = _make_battle_pokemon(hp=100)
        actual = bp.take_damage(30)
        assert actual == 30
        assert bp.current_hp == 70
        assert bp.is_fainted is False

    def test_take_damage_overkill(self):
        bp = _make_battle_pokemon(hp=100)
        bp.current_hp = 20
        actual = bp.take_damage(50)
        assert actual == 20
        assert bp.current_hp == 0
        assert bp.is_fainted is True

    def test_heal(self):
        bp = _make_battle_pokemon(hp=100)
        bp.current_hp = 50
        healed = bp.heal(30)
        assert healed == 30
        assert bp.current_hp == 80

    def test_heal_capped_at_max(self):
        bp = _make_battle_pokemon(hp=100)
        bp.current_hp = 90
        healed = bp.heal(50)
        assert healed == 10
        assert bp.current_hp == 100

    def test_heal_when_fainted(self):
        bp = _make_battle_pokemon(hp=100)
        bp.current_hp = 0
        bp.is_fainted = True
        healed = bp.heal(50)
        assert healed == 0


# ---------------------------------------------------------------------------
# BattleTeam
# ---------------------------------------------------------------------------


class TestBattleTeam:
    """Tests for BattleTeam model."""

    def test_active_pokemon(self):
        mon = _make_battle_pokemon()
        team = _make_team([mon])
        assert team.active_pokemon is mon

    def test_active_pokemon_out_of_range(self):
        team = _make_team([_make_battle_pokemon()])
        team.active_index = 5
        assert team.active_pokemon is None

    def test_has_usable_pokemon(self):
        mon = _make_battle_pokemon()
        team = _make_team([mon])
        assert team.has_usable_pokemon is True

    def test_no_usable_pokemon_all_fainted(self):
        mon = _make_battle_pokemon()
        mon.is_fainted = True
        mon.current_hp = 0
        team = _make_team([mon])
        assert team.has_usable_pokemon is False

    def test_alive_count(self):
        m1 = _make_battle_pokemon(name="a")
        m2 = _make_battle_pokemon(name="b")
        m3 = _make_battle_pokemon(name="c")
        m2.is_fainted = True
        team = _make_team([m1, m2, m3])
        assert team.alive_count == 2

    def test_next_alive_index(self):
        m1 = _make_battle_pokemon(name="a")
        m2 = _make_battle_pokemon(name="b")
        m1.is_fainted = True
        team = _make_team([m1, m2])
        team.active_index = 0
        assert team.next_alive_index() == 1

    def test_next_alive_index_none_when_all_fainted(self):
        m1 = _make_battle_pokemon(name="a")
        m1.is_fainted = True
        team = _make_team([m1])
        assert team.next_alive_index() is None


# ---------------------------------------------------------------------------
# BattleState
# ---------------------------------------------------------------------------


class TestBattleState:
    """Tests for BattleState model."""

    def test_default_status_pending(self):
        state = BattleState(challenger_id="a", opponent_id="b")
        assert state.status == BattleStatus.PENDING

    def test_battle_id_generated(self):
        state = BattleState(challenger_id="a", opponent_id="b")
        assert len(state.battle_id) > 0

    def test_get_team(self):
        state = _make_active_battle()
        assert state.get_team("player1") is state.team1
        assert state.get_team("player2") is state.team2
        assert state.get_team("nobody") is None

    def test_get_opponent_team(self):
        state = _make_active_battle()
        assert state.get_opponent_team("player1") is state.team2
        assert state.get_opponent_team("player2") is state.team1

    def test_both_actions_submitted_false_initially(self):
        state = _make_active_battle()
        assert state.both_actions_submitted() is False

    def test_both_actions_submitted_true(self):
        state = _make_active_battle()
        assert state.team1 is not None and state.team2 is not None
        state.team1.action = BattleAction(action_type=BattleActionType.ATTACK, move_index=0)
        state.team2.action = BattleAction(action_type=BattleActionType.ATTACK, move_index=0)
        assert state.both_actions_submitted() is True

    def test_both_actions_submitted_no_teams(self):
        state = BattleState(challenger_id="a", opponent_id="b")
        assert state.both_actions_submitted() is False


# ---------------------------------------------------------------------------
# create_battle_pokemon factory
# ---------------------------------------------------------------------------


class TestCreateBattlePokemon:
    """Tests for create_battle_pokemon factory function."""

    def test_basic_creation(self):
        bp = create_battle_pokemon(
            pokemon_id=1,
            pokedex_id=25,
            name="pikachu",
            nickname=None,
            type1="electric",
            type2=None,
            level=50,
            base_stats={"hp": 35, "atk": 55, "def": 40, "spa": 50, "spd": 50, "spe": 90},
            ivs={"hp": 15, "atk": 15, "def": 15, "spa": 15, "spd": 15, "spe": 15},
            evs={"hp": 0, "atk": 0, "def": 0, "spa": 0, "spd": 0, "spe": 0},
            nature="adamant",
        )
        assert bp.name == "pikachu"
        assert bp.current_hp == bp.max_hp
        assert bp.max_hp > 0
        assert bp.is_fainted is False
        assert len(bp.moves) > 0

    def test_nature_affects_stats(self):
        """Adamant should boost atk, lower spa compared to neutral."""
        stats_kwargs = dict(
            pokemon_id=1, pokedex_id=25, name="test", nickname=None,
            type1="normal", type2=None, level=50,
            base_stats={"hp": 80, "atk": 80, "def": 80, "spa": 80, "spd": 80, "spe": 80},
            ivs={"hp": 15, "atk": 15, "def": 15, "spa": 15, "spd": 15, "spe": 15},
            evs={"hp": 0, "atk": 0, "def": 0, "spa": 0, "spd": 0, "spe": 0},
        )
        adamant = create_battle_pokemon(**stats_kwargs, nature="adamant")  # type: ignore[arg-type]
        modest = create_battle_pokemon(**stats_kwargs, nature="modest")  # type: ignore[arg-type]

        assert adamant.atk > modest.atk  # Adamant boosts ATK
        assert adamant.spa < modest.spa  # Modest boosts SPA

    def test_moves_pp_reset(self):
        """PP should be reset to max for battle."""
        move = _make_move(pp=20)
        move.current_pp = 5
        bp = create_battle_pokemon(
            pokemon_id=1, pokedex_id=25, name="test", nickname=None,
            type1="normal", type2=None, level=50,
            base_stats={"hp": 50, "atk": 50, "def": 50, "spa": 50, "spd": 50, "spe": 50},
            ivs={"hp": 0, "atk": 0, "def": 0, "spa": 0, "spd": 0, "spe": 0},
            evs={"hp": 0, "atk": 0, "def": 0, "spa": 0, "spd": 0, "spe": 0},
            nature="hardy",
            moves=[move],
        )
        assert bp.moves[0].current_pp == 20


# ---------------------------------------------------------------------------
# BattleEngine - turn resolution
# ---------------------------------------------------------------------------


class TestBattleEngineResolveTurn:
    """Tests for BattleEngine.resolve_turn()."""

    def test_no_events_if_not_both_submitted(self):
        state = _make_active_battle()
        events = BattleEngine.resolve_turn(state)
        assert events == []

    def test_attack_deals_damage(self):
        random.seed(42)
        state = _make_active_battle()
        assert state.team1 is not None and state.team2 is not None
        state.team1.action = BattleAction(action_type=BattleActionType.ATTACK, move_index=0, player_id="player1")
        state.team2.action = BattleAction(action_type=BattleActionType.ATTACK, move_index=0, player_id="player2")

        events = BattleEngine.resolve_turn(state)
        assert len(events) > 0
        assert state.turn_number == 1

        # At least one damage event should exist
        damage_events = [e for e in events if e.event_type == "damage"]
        assert len(damage_events) > 0

    def test_forfeit_ends_battle_player1(self):
        state = _make_active_battle()
        assert state.team1 is not None and state.team2 is not None
        state.team1.action = BattleAction(action_type=BattleActionType.FORFEIT, player_id="player1")
        state.team2.action = BattleAction(action_type=BattleActionType.ATTACK, move_index=0, player_id="player2")

        events = BattleEngine.resolve_turn(state)
        assert state.status == BattleStatus.FORFEIT
        assert state.winner_id == "player2"
        assert state.loser_id == "player1"
        forfeit_events = [e for e in events if e.event_type == "forfeit"]
        assert len(forfeit_events) == 1

    def test_forfeit_ends_battle_player2(self):
        state = _make_active_battle()
        assert state.team1 is not None and state.team2 is not None
        state.team1.action = BattleAction(action_type=BattleActionType.ATTACK, move_index=0, player_id="player1")
        state.team2.action = BattleAction(action_type=BattleActionType.FORFEIT, player_id="player2")

        events = BattleEngine.resolve_turn(state)
        assert state.status == BattleStatus.FORFEIT
        assert state.winner_id == "player1"
        assert state.loser_id == "player2"

    def test_switch_happens_before_attack(self):
        """Switches should resolve before attacks in the event list."""
        mon1a = _make_battle_pokemon(name="pokemon_a", spe=100)
        mon1b = _make_battle_pokemon(name="pokemon_b", spe=50)
        team1 = _make_team([mon1a, mon1b], player_id="player1", trainer_name="Ash")
        team2 = _make_team(
            [_make_battle_pokemon(name="enemy", spe=30)],
            player_id="player2",
            trainer_name="Gary",
        )
        state = _make_active_battle(team1, team2)
        assert state.team1 is not None and state.team2 is not None

        state.team1.action = BattleAction(action_type=BattleActionType.SWITCH, switch_to=1, player_id="player1")
        state.team2.action = BattleAction(action_type=BattleActionType.ATTACK, move_index=0, player_id="player2")

        events = BattleEngine.resolve_turn(state)
        event_types = [e.event_type for e in events]
        # Switch event should come before attack event
        if "switch" in event_types and "attack" in event_types:
            assert event_types.index("switch") < event_types.index("attack")

    def test_faster_pokemon_attacks_first(self):
        """Higher speed Pokemon should attack first."""
        random.seed(42)
        fast_mon = _make_battle_pokemon(name="fast", spe=200, hp=200)
        slow_mon = _make_battle_pokemon(name="slow", spe=10, hp=200)
        team1 = _make_team([fast_mon], player_id="player1", trainer_name="Fast")
        team2 = _make_team([slow_mon], player_id="player2", trainer_name="Slow")
        state = _make_active_battle(team1, team2)
        assert state.team1 is not None and state.team2 is not None

        state.team1.action = BattleAction(action_type=BattleActionType.ATTACK, move_index=0, player_id="player1")
        state.team2.action = BattleAction(action_type=BattleActionType.ATTACK, move_index=0, player_id="player2")

        events = BattleEngine.resolve_turn(state)
        attack_events = [e for e in events if e.event_type == "attack"]
        assert len(attack_events) == 2
        # First attack should be from the faster player
        assert attack_events[0].player_id == "player1"

    def test_faint_triggers_auto_switch(self):
        """When a Pokemon faints, the next alive one should be sent out."""
        weak_mon = _make_battle_pokemon(name="weak", hp=1, defense=1, spd=1, spe=10)
        backup_mon = _make_battle_pokemon(name="backup", hp=200, spe=10)
        strong_mon = _make_battle_pokemon(name="strong", atk=200, spa=200, spe=100)

        team1 = _make_team([strong_mon], player_id="player1", trainer_name="Strong")
        team2 = _make_team([weak_mon, backup_mon], player_id="player2", trainer_name="Weak")
        state = BattleState(
            challenger_id="player1", opponent_id="player2",
            format=BattleFormat.SINGLES_3V3, status=BattleStatus.ACTIVE,
            team1=team1, team2=team2,
        )
        assert state.team1 is not None and state.team2 is not None

        state.team1.action = BattleAction(action_type=BattleActionType.ATTACK, move_index=0, player_id="player1")
        state.team2.action = BattleAction(action_type=BattleActionType.ATTACK, move_index=0, player_id="player2")

        events = BattleEngine.resolve_turn(state)
        event_types = [e.event_type for e in events]
        assert "faint" in event_types

        # The defending team should have auto-switched to backup
        if state.team2.roster[0].is_fainted:
            assert state.team2.active_index == 1

    def test_battle_finishes_when_all_fainted(self):
        """Battle should finish when one side has no usable Pokemon."""
        random.seed(42)
        weak = _make_battle_pokemon(name="weak", hp=1, defense=1, spd=1, spe=1)
        strong = _make_battle_pokemon(name="strong", atk=200, spa=200, spe=200, hp=500)

        team1 = _make_team([strong], player_id="player1", trainer_name="Winner")
        team2 = _make_team([weak], player_id="player2", trainer_name="Loser")
        state = _make_active_battle(team1, team2)
        assert state.team1 is not None and state.team2 is not None

        state.team1.action = BattleAction(action_type=BattleActionType.ATTACK, move_index=0, player_id="player1")
        state.team2.action = BattleAction(action_type=BattleActionType.ATTACK, move_index=0, player_id="player2")

        events = BattleEngine.resolve_turn(state)
        assert state.status == BattleStatus.FINISHED
        assert state.winner_id == "player1"
        assert state.loser_id == "player2"

    def test_turn_log_records_events(self):
        random.seed(42)
        state = _make_active_battle()
        assert state.team1 is not None and state.team2 is not None
        state.team1.action = BattleAction(action_type=BattleActionType.ATTACK, move_index=0, player_id="player1")
        state.team2.action = BattleAction(action_type=BattleActionType.ATTACK, move_index=0, player_id="player2")
        BattleEngine.resolve_turn(state)
        assert len(state.turn_log) == 1
        assert len(state.turn_log[0]) > 0

    def test_actions_cleared_after_turn(self):
        random.seed(42)
        state = _make_active_battle()
        assert state.team1 is not None and state.team2 is not None
        state.team1.action = BattleAction(action_type=BattleActionType.ATTACK, move_index=0, player_id="player1")
        state.team2.action = BattleAction(action_type=BattleActionType.ATTACK, move_index=0, player_id="player2")
        BattleEngine.resolve_turn(state)
        assert state.team1.action is None
        assert state.team2.action is None

    def test_protect_blocks_attack(self):
        """Protect should prevent the defender from taking damage."""
        protect_move = Move(name="protect", type="normal", damage_class=DamageClass.STATUS, power=None, accuracy=None, pp=10)
        strong_attack = _make_move("hyper-beam", "normal", 150, 100, 5)

        protector = _make_battle_pokemon(name="protector", hp=100, spe=200, moves=[protect_move])
        attacker = _make_battle_pokemon(name="attacker", hp=100, atk=200, spe=50, moves=[strong_attack])

        team1 = _make_team([attacker], player_id="player1", trainer_name="Attacker")
        team2 = _make_team([protector], player_id="player2", trainer_name="Protector")
        state = _make_active_battle(team1, team2)
        assert state.team1 is not None and state.team2 is not None

        state.team1.action = BattleAction(action_type=BattleActionType.ATTACK, move_index=0, player_id="player1")
        state.team2.action = BattleAction(action_type=BattleActionType.ATTACK, move_index=0, player_id="player2")

        BattleEngine.resolve_turn(state)
        # Protector should have taken no damage because it used Protect
        assert protector.current_hp == 100


class TestBattleEngineStatusEffects:
    """Tests for status effect handling in battles."""

    def test_burn_end_of_turn_damage(self):
        """Burned Pokemon takes 1/16 max HP at end of turn."""
        mon1 = _make_battle_pokemon(name="mon1", hp=160, spe=100)
        mon2 = _make_battle_pokemon(name="mon2", hp=160, spe=50)
        mon2.status = StatusEffect.BURN

        team1 = _make_team([mon1], player_id="player1", trainer_name="P1")
        team2 = _make_team([mon2], player_id="player2", trainer_name="P2")
        state = _make_active_battle(team1, team2)
        assert state.team1 is not None and state.team2 is not None

        state.team1.action = BattleAction(action_type=BattleActionType.ATTACK, move_index=0, player_id="player1")
        state.team2.action = BattleAction(action_type=BattleActionType.ATTACK, move_index=0, player_id="player2")

        random.seed(42)
        BattleEngine.resolve_turn(state)

        # Burn should have dealt 160/16 = 10 damage at end of turn (plus any attack damage)
        status_events = [e for e in state.turn_log[0] if e.event_type == "status" and "burn" in e.message.lower()]
        assert len(status_events) >= 1

    def test_poison_end_of_turn_damage(self):
        """Poisoned Pokemon takes 1/8 max HP at end of turn."""
        mon = _make_battle_pokemon(name="poisoned", hp=80, spe=50)
        mon.status = StatusEffect.POISON

        team1 = _make_team([_make_battle_pokemon(spe=100)], player_id="player1", trainer_name="P1")
        team2 = _make_team([mon], player_id="player2", trainer_name="P2")
        state = _make_active_battle(team1, team2)
        assert state.team1 is not None and state.team2 is not None

        state.team1.action = BattleAction(action_type=BattleActionType.ATTACK, move_index=0, player_id="player1")
        state.team2.action = BattleAction(action_type=BattleActionType.ATTACK, move_index=0, player_id="player2")

        random.seed(42)
        BattleEngine.resolve_turn(state)

        status_events = [e for e in state.turn_log[0] if e.event_type == "status" and "poison" in e.message.lower()]
        assert len(status_events) >= 1

    def test_sleep_prevents_action(self):
        """Sleeping Pokemon should not attack."""
        mon = _make_battle_pokemon(name="sleepy", hp=200, spe=200, atk=200)
        mon.status = StatusEffect.SLEEP
        mon.status_turns = 3

        team1 = _make_team([mon], player_id="player1", trainer_name="Sleepy")
        team2 = _make_team([_make_battle_pokemon(name="enemy", hp=200, spe=50)], player_id="player2", trainer_name="Awake")
        state = _make_active_battle(team1, team2)
        assert state.team1 is not None and state.team2 is not None

        state.team1.action = BattleAction(action_type=BattleActionType.ATTACK, move_index=0, player_id="player1")
        state.team2.action = BattleAction(action_type=BattleActionType.ATTACK, move_index=0, player_id="player2")

        random.seed(42)
        BattleEngine.resolve_turn(state)

        sleep_events = [e for e in state.turn_log[0] if "asleep" in e.message.lower() or "woke" in e.message.lower()]
        assert len(sleep_events) >= 1

    def test_frozen_prevents_action(self):
        """Frozen Pokemon should not attack (unless it thaws)."""
        random.seed(100)  # Pick a seed that keeps it frozen
        mon = _make_battle_pokemon(name="icy", hp=200, spe=200)
        mon.status = StatusEffect.FREEZE

        team1 = _make_team([mon], player_id="player1", trainer_name="Icy")
        team2 = _make_team([_make_battle_pokemon(name="enemy", hp=200, spe=50)], player_id="player2", trainer_name="Warm")
        state = _make_active_battle(team1, team2)
        assert state.team1 is not None and state.team2 is not None

        state.team1.action = BattleAction(action_type=BattleActionType.ATTACK, move_index=0, player_id="player1")
        state.team2.action = BattleAction(action_type=BattleActionType.ATTACK, move_index=0, player_id="player2")

        BattleEngine.resolve_turn(state)

        # Either frozen or thawed event should appear
        ice_events = [e for e in state.turn_log[0] if "frozen" in e.message.lower() or "thawed" in e.message.lower()]
        assert len(ice_events) >= 1


class TestBattleEngineAttack:
    """Tests for attack-specific behavior."""

    def test_no_pp_uses_struggle(self):
        """Pokemon with 0 PP should use Struggle."""
        move = _make_move("volt-tackle", "electric", 120, 100, 1)
        move.current_pp = 0
        mon = _make_battle_pokemon(name="empty_pp", moves=[move], spe=100, hp=200)
        enemy = _make_battle_pokemon(name="target", hp=200, spe=50)

        team1 = _make_team([mon], player_id="player1", trainer_name="P1")
        team2 = _make_team([enemy], player_id="player2", trainer_name="P2")
        state = _make_active_battle(team1, team2)
        assert state.team1 is not None and state.team2 is not None

        state.team1.action = BattleAction(action_type=BattleActionType.ATTACK, move_index=0, player_id="player1")
        state.team2.action = BattleAction(action_type=BattleActionType.ATTACK, move_index=0, player_id="player2")

        random.seed(42)
        events = BattleEngine.resolve_turn(state)
        struggle_events = [e for e in events if "struggle" in e.message.lower()]
        assert len(struggle_events) >= 1

    def test_pp_deducted(self):
        """Using a move should deduct 1 PP."""
        move = _make_move("thunderbolt", "electric", 90, 100, 15)
        mon = _make_battle_pokemon(name="user", moves=[move], spe=100)

        team1 = _make_team([mon], player_id="player1", trainer_name="P1")
        team2 = _make_team([_make_battle_pokemon(spe=50)], player_id="player2", trainer_name="P2")
        state = _make_active_battle(team1, team2)
        assert state.team1 is not None and state.team2 is not None

        state.team1.action = BattleAction(action_type=BattleActionType.ATTACK, move_index=0, player_id="player1")
        state.team2.action = BattleAction(action_type=BattleActionType.ATTACK, move_index=0, player_id="player2")

        random.seed(42)
        BattleEngine.resolve_turn(state)
        assert move.current_pp == 14

    def test_immune_type_no_damage(self):
        """Ground move should not damage Flying type."""
        ground_move = _make_move("earthquake", "ground", 100, 100, 10)
        attacker = _make_battle_pokemon(name="ground_user", type1="ground", moves=[ground_move], spe=100)
        flier = _make_battle_pokemon(name="flier", type1="flying", hp=100, spe=50)

        team1 = _make_team([attacker], player_id="player1", trainer_name="P1")
        team2 = _make_team([flier], player_id="player2", trainer_name="P2")
        state = _make_active_battle(team1, team2)
        assert state.team1 is not None and state.team2 is not None

        state.team1.action = BattleAction(action_type=BattleActionType.ATTACK, move_index=0, player_id="player1")
        state.team2.action = BattleAction(action_type=BattleActionType.ATTACK, move_index=0, player_id="player2")

        random.seed(42)
        events = BattleEngine.resolve_turn(state)

        immune_events = [e for e in events if e.event_type == "immune"]
        assert len(immune_events) >= 1
        # Flier should still be at full HP (from the ground move at least)
        assert flier.current_hp > 0


# ---------------------------------------------------------------------------
# ELO rating
# ---------------------------------------------------------------------------


class TestEloCalculation:
    """Tests for ELO rating changes."""

    def test_equal_elo_symmetric(self):
        """Equal ELO players: winner gains, loser loses same absolute amount."""
        w, l = calculate_elo_change(1000, 1000)
        assert w > 0
        assert l < 0
        assert w == -l  # Symmetric for equal ratings

    def test_upset_gives_more_points(self):
        """Lower-rated beating higher-rated should gain more."""
        w_upset, _ = calculate_elo_change(800, 1200)
        w_normal, _ = calculate_elo_change(1200, 800)
        assert w_upset > w_normal

    def test_winner_delta_positive(self):
        w, _ = calculate_elo_change(1500, 1200)
        assert w > 0

    def test_loser_delta_negative(self):
        _, l = calculate_elo_change(1500, 1200)
        assert l < 0

    def test_k_factor_bounds(self):
        """Deltas should not exceed K-factor (32)."""
        w, l = calculate_elo_change(100, 2000)
        assert w <= 32
        assert abs(l) <= 32


# ---------------------------------------------------------------------------
# Multi-turn battle
# ---------------------------------------------------------------------------


class TestMultiTurnBattle:
    """Integration tests simulating multi-turn battles."""

    def test_three_turn_battle(self):
        """Run a 3-turn battle and verify state progression."""
        random.seed(42)
        mon1 = _make_battle_pokemon(name="tanky", hp=500, atk=50, spa=50, spe=100)
        mon2 = _make_battle_pokemon(name="also_tanky", hp=500, atk=50, spa=50, spe=50)

        team1 = _make_team([mon1], player_id="player1", trainer_name="P1")
        team2 = _make_team([mon2], player_id="player2", trainer_name="P2")
        state = _make_active_battle(team1, team2)
        assert state.team1 is not None and state.team2 is not None

        for turn in range(3):
            state.team1.action = BattleAction(action_type=BattleActionType.ATTACK, move_index=0, player_id="player1")
            state.team2.action = BattleAction(action_type=BattleActionType.ATTACK, move_index=0, player_id="player2")
            BattleEngine.resolve_turn(state)

        assert state.turn_number == 3
        assert len(state.turn_log) == 3
        # Both should have taken some damage
        assert mon1.current_hp < 500
        assert mon2.current_hp < 500

    def test_battle_to_completion(self):
        """Run a battle until it finishes."""
        random.seed(42)
        mon1 = _make_battle_pokemon(name="fighter1", hp=100, atk=100, spa=100, spe=100)
        mon2 = _make_battle_pokemon(name="fighter2", hp=100, atk=100, spa=100, spe=50)

        team1 = _make_team([mon1], player_id="player1", trainer_name="P1")
        team2 = _make_team([mon2], player_id="player2", trainer_name="P2")
        state = _make_active_battle(team1, team2)
        assert state.team1 is not None and state.team2 is not None

        max_turns = 50  # Safety limit
        for _ in range(max_turns):
            if state.status in (BattleStatus.FINISHED, BattleStatus.FORFEIT):
                break
            state.team1.action = BattleAction(action_type=BattleActionType.ATTACK, move_index=0, player_id="player1")
            state.team2.action = BattleAction(action_type=BattleActionType.ATTACK, move_index=0, player_id="player2")
            BattleEngine.resolve_turn(state)

        assert state.status == BattleStatus.FINISHED
        assert state.winner_id is not None
        assert state.loser_id is not None
        assert state.winner_id != state.loser_id


# ---------------------------------------------------------------------------
# Pokemon.to_battle_pokemon integration
# ---------------------------------------------------------------------------


class TestPokemonToBattlePokemon:
    """Tests for Pokemon.to_battle_pokemon() integration."""

    def test_creates_valid_battle_pokemon(self):
        from pokedo.core.pokemon import Pokemon

        p = Pokemon(
            id=1,
            pokedex_id=25,
            name="pikachu",
            type1="electric",
            level=50,
            base_stats={"hp": 35, "atk": 55, "def": 40, "spa": 50, "spd": 50, "spe": 90},
            ivs={"hp": 15, "atk": 15, "def": 15, "spa": 15, "spd": 15, "spe": 15},
            evs={"hp": 0, "atk": 0, "def": 0, "spa": 0, "spd": 0, "spe": 0},
            nature="adamant",
        )
        bp = p.to_battle_pokemon()
        assert isinstance(bp, BattlePokemon)
        assert bp.name == "pikachu"
        assert bp.current_hp == bp.max_hp
        assert len(bp.moves) > 0

    def test_moves_are_copied(self):
        """Moves should be copies, not references to the original."""
        from pokedo.core.pokemon import Pokemon

        p = Pokemon(
            id=1, pokedex_id=1, name="bulbasaur", type1="grass", type2="poison",
            level=30, nature="bold",
        )
        p.ensure_moves()
        bp = p.to_battle_pokemon()

        # Mutating battle pokemon moves should not affect original
        if bp.moves:
            bp.moves[0].current_pp = 0
            assert p.moves[0].current_pp != 0 or p.moves[0].pp == 0


# ---------------------------------------------------------------------------
# Trainer PvP fields
# ---------------------------------------------------------------------------


class TestTrainerPvP:
    """Tests for Trainer PvP-related fields and methods."""

    def test_default_pvp_stats(self):
        from pokedo.core.trainer import Trainer
        t = Trainer(name="Test")
        assert t.battle_wins == 0
        assert t.battle_losses == 0
        assert t.battle_draws == 0
        assert t.elo_rating == 1000
        assert t.pvp_rank == "Unranked"

    def test_battles_fought(self):
        from pokedo.core.trainer import Trainer
        t = Trainer(name="Test", battle_wins=5, battle_losses=3, battle_draws=2)
        assert t.battles_fought == 10

    def test_win_rate(self):
        from pokedo.core.trainer import Trainer
        t = Trainer(name="Test", battle_wins=7, battle_losses=3)
        assert t.win_rate == 70.0

    def test_win_rate_zero_battles(self):
        from pokedo.core.trainer import Trainer
        t = Trainer(name="Test")
        assert t.win_rate == 0.0

    def test_record_battle_win(self):
        from pokedo.core.trainer import Trainer
        t = Trainer(name="Test", elo_rating=1000)
        t.record_battle(won=True, elo_delta=16)
        assert t.battle_wins == 1
        assert t.elo_rating == 1016
        assert t.pvp_rank != ""

    def test_record_battle_loss(self):
        from pokedo.core.trainer import Trainer
        t = Trainer(name="Test", elo_rating=1000)
        t.record_battle(won=False, elo_delta=-16)
        assert t.battle_losses == 1
        assert t.elo_rating == 984

    def test_elo_floor_at_zero(self):
        from pokedo.core.trainer import Trainer
        t = Trainer(name="Test", elo_rating=5)
        t.record_battle(won=False, elo_delta=-100)
        assert t.elo_rating == 0

    def test_rank_thresholds(self):
        from pokedo.core.trainer import Trainer
        t = Trainer(name="Test")

        cases = [
            (1000, "Youngster"),
            (1099, "Youngster"),
            (1100, "Bug Catcher"),
            (1300, "Ace Trainer"),
            (1500, "Gym Leader"),
            (1700, "Elite Four"),
            (1900, "Champion"),
            (2100, "Pokemon Master"),
        ]
        for elo, expected_rank in cases:
            t.elo_rating = elo
            t.record_battle(won=True, elo_delta=0)
            assert t.pvp_rank == expected_rank, f"ELO {elo} should be {expected_rank}, got {t.pvp_rank}"


# ---------------------------------------------------------------------------
# Mutual KO / Draw
# ---------------------------------------------------------------------------


class TestMutualKODraw:
    """When both sides' last Pokemon faint on the same turn, it's a draw."""

    def test_mutual_ko_is_draw(self):
        """Both Pokemon knock each other out on the same turn -> draw."""
        random.seed(42)
        # Both use a heavy-recoil move so the attacker KOs the defender
        # but also faints from recoil. The second attacker is already fainted
        # because the first attack killed it, so both are out.
        recoil_move = Move(
            name="explosion", type="normal", damage_class=DamageClass.PHYSICAL,
            power=250, accuracy=100, pp=5, drain_percent=-100,
        )
        # Both have same speed so order is randomized, but either way
        # the first attacker KOs the defender, then faints from recoil.
        mon1 = _make_battle_pokemon(name="bomber1", hp=50, atk=200, spe=100, moves=[recoil_move])
        mon2 = _make_battle_pokemon(name="bomber2", hp=50, atk=200, spe=100, moves=[recoil_move])

        team1 = _make_team([mon1], player_id="player1", trainer_name="P1")
        team2 = _make_team([mon2], player_id="player2", trainer_name="P2")
        state = _make_active_battle(team1, team2)
        assert state.team1 is not None and state.team2 is not None

        state.team1.action = BattleAction(action_type=BattleActionType.ATTACK, move_index=0, player_id="player1")
        state.team2.action = BattleAction(action_type=BattleActionType.ATTACK, move_index=0, player_id="player2")

        events = BattleEngine.resolve_turn(state)
        assert state.status == BattleStatus.FINISHED
        # Both should be fainted
        assert mon1.is_fainted
        assert mon2.is_fainted
        # Draw: both winner_id and loser_id should be None
        assert state.winner_id is None
        assert state.loser_id is None
        draw_events = [e for e in events if "draw" in e.message.lower()]
        assert len(draw_events) >= 1


# ---------------------------------------------------------------------------
# Move priority ordering
# ---------------------------------------------------------------------------


class TestMovePriority:
    """Pokemon with priority moves should act before faster foes."""

    def test_quick_attack_outspeeds_normal_move(self):
        """Slower mon with Quick Attack (+1) should move before faster mon with tackle (0)."""
        random.seed(42)
        quick_atk = Move(
            name="quick-attack", type="normal", damage_class=DamageClass.PHYSICAL,
            power=40, accuracy=100, pp=30, priority=1,
        )
        normal_atk = _make_move("tackle", "normal", 40, 100, 35)

        slow_mon = _make_battle_pokemon(name="slow_priority", spe=10, hp=200, moves=[quick_atk])
        fast_mon = _make_battle_pokemon(name="fast_normal", spe=200, hp=200, moves=[normal_atk])

        team1 = _make_team([slow_mon], player_id="player1", trainer_name="Slow")
        team2 = _make_team([fast_mon], player_id="player2", trainer_name="Fast")
        state = _make_active_battle(team1, team2)
        assert state.team1 is not None and state.team2 is not None

        state.team1.action = BattleAction(action_type=BattleActionType.ATTACK, move_index=0, player_id="player1")
        state.team2.action = BattleAction(action_type=BattleActionType.ATTACK, move_index=0, player_id="player2")

        events = BattleEngine.resolve_turn(state)
        attack_events = [e for e in events if e.event_type == "attack"]
        assert len(attack_events) == 2
        # Slow mon with priority should attack first
        assert attack_events[0].player_id == "player1"

    def test_protect_goes_before_attacks(self):
        """Protect (+4 priority) should activate even against a faster attacker."""
        random.seed(42)
        protect_move = Move(
            name="protect", type="normal", damage_class=DamageClass.STATUS,
            power=None, accuracy=None, pp=10, priority=4,
        )
        hyper_beam = _make_move("hyper-beam", "normal", 150, 100, 5)

        protector = _make_battle_pokemon(name="slowpoke", spe=5, hp=100, moves=[protect_move])
        attacker = _make_battle_pokemon(name="speedster", spe=200, atk=200, hp=100, moves=[hyper_beam])

        team1 = _make_team([protector], player_id="player1", trainer_name="Tank")
        team2 = _make_team([attacker], player_id="player2", trainer_name="Nuke")
        state = _make_active_battle(team1, team2)
        assert state.team1 is not None and state.team2 is not None

        state.team1.action = BattleAction(action_type=BattleActionType.ATTACK, move_index=0, player_id="player1")
        state.team2.action = BattleAction(action_type=BattleActionType.ATTACK, move_index=0, player_id="player2")

        BattleEngine.resolve_turn(state)
        # Protector should have taken no damage
        assert protector.current_hp == 100


# ---------------------------------------------------------------------------
# Paralysis speed halving
# ---------------------------------------------------------------------------


class TestParalysisSpeed:
    """Paralyzed Pokemon's speed is halved for turn order."""

    def test_paralysis_reverses_speed_order(self):
        """A paralyzed fast mon (200 spe -> 100) should be outsped by a 150 spe mon."""
        # Use a seed where paralysis doesn't prevent the action (75% chance)
        random.seed(0)
        fast_paralyzed = _make_battle_pokemon(name="fast_para", spe=200, hp=200)
        fast_paralyzed.status = StatusEffect.PARALYSIS
        medium_speed = _make_battle_pokemon(name="medium", spe=150, hp=200)

        team1 = _make_team([fast_paralyzed], player_id="player1", trainer_name="Para")
        team2 = _make_team([medium_speed], player_id="player2", trainer_name="Normal")
        state = _make_active_battle(team1, team2)
        assert state.team1 is not None and state.team2 is not None

        state.team1.action = BattleAction(action_type=BattleActionType.ATTACK, move_index=0, player_id="player1")
        state.team2.action = BattleAction(action_type=BattleActionType.ATTACK, move_index=0, player_id="player2")

        events = BattleEngine.resolve_turn(state)
        attack_events = [e for e in events if e.event_type == "attack"]
        # Even if paralysis causes full-para and only 1 attack event fires,
        # if both attack, player2 should go first (150 > 200//2=100)
        if len(attack_events) == 2:
            assert attack_events[0].player_id == "player2"


# ---------------------------------------------------------------------------
# Accuracy miss
# ---------------------------------------------------------------------------


class TestAccuracyMiss:
    """Moves can miss based on their accuracy stat."""

    def test_low_accuracy_can_miss(self):
        """A move with 1% accuracy should almost always miss."""
        miss_count = 0
        for seed in range(20):
            random.seed(seed)
            bad_aim = _make_move("wild-shot", "normal", 100, 1, 10)  # 1% accuracy
            attacker = _make_battle_pokemon(name="misser", spe=100, hp=200, moves=[bad_aim])
            target = _make_battle_pokemon(name="dodger", spe=50, hp=200)

            team1 = _make_team([attacker], player_id="player1", trainer_name="P1")
            team2 = _make_team([target], player_id="player2", trainer_name="P2")
            state = _make_active_battle(team1, team2)
            assert state.team1 is not None and state.team2 is not None

            state.team1.action = BattleAction(action_type=BattleActionType.ATTACK, move_index=0, player_id="player1")
            state.team2.action = BattleAction(action_type=BattleActionType.ATTACK, move_index=0, player_id="player2")

            events = BattleEngine.resolve_turn(state)
            miss_events = [e for e in events if e.event_type == "miss"]
            if miss_events:
                miss_count += 1

        # With 1% accuracy over 20 trials, we should see mostly misses
        assert miss_count >= 15, f"Expected mostly misses with 1% accuracy, got {miss_count}/20"


# ---------------------------------------------------------------------------
# Burn halving physical attack
# ---------------------------------------------------------------------------


class TestBurnPhysicalHalved:
    """Burned Pokemon deals half damage with physical moves."""

    def test_burn_reduces_physical_damage(self):
        """Damaged dealt should be less when attacker is burned."""
        # Run the same attack scenario with and without burn
        damages = {}
        for label, burn in [("normal", False), ("burned", True)]:
            random.seed(42)
            physical_move = _make_move("body-slam", "normal", 85, 100, 15, DamageClass.PHYSICAL)
            attacker = _make_battle_pokemon(name="attacker", atk=150, spe=100, hp=200, moves=[physical_move])
            if burn:
                attacker.status = StatusEffect.BURN
            target = _make_battle_pokemon(name="target", hp=500, defense=80, spe=50)

            team1 = _make_team([attacker], player_id="player1", trainer_name="P1")
            team2 = _make_team([target], player_id="player2", trainer_name="P2")
            state = _make_active_battle(team1, team2)
            assert state.team1 is not None and state.team2 is not None

            state.team1.action = BattleAction(action_type=BattleActionType.ATTACK, move_index=0, player_id="player1")
            state.team2.action = BattleAction(action_type=BattleActionType.ATTACK, move_index=0, player_id="player2")
            BattleEngine.resolve_turn(state)

            damage_taken = 500 - target.current_hp
            # Subtract any burn status damage from target's HP loss
            # Burn damage is on the attacker, not the target, so damage_taken is clean
            damages[label] = damage_taken

        assert damages["burned"] < damages["normal"], (
            f"Burned attacker should deal less physical damage: burned={damages['burned']} vs normal={damages['normal']}"
        )


# ---------------------------------------------------------------------------
# Drain move healing
# ---------------------------------------------------------------------------


class TestDrainMove:
    """Positive drain_percent should heal the attacker."""

    def test_drain_heals_attacker(self):
        random.seed(42)
        drain_move = Move(
            name="giga-drain", type="grass", damage_class=DamageClass.SPECIAL,
            power=75, accuracy=100, pp=10, drain_percent=50,
        )
        attacker = _make_battle_pokemon(name="drainer", spa=150, spe=100, hp=200,
                                        type1="grass", moves=[drain_move])
        attacker.current_hp = 100  # Damaged
        target = _make_battle_pokemon(name="target", hp=500, spd=50, spe=50)

        team1 = _make_team([attacker], player_id="player1", trainer_name="P1")
        team2 = _make_team([target], player_id="player2", trainer_name="P2")
        state = _make_active_battle(team1, team2)
        assert state.team1 is not None and state.team2 is not None

        state.team1.action = BattleAction(action_type=BattleActionType.ATTACK, move_index=0, player_id="player1")
        state.team2.action = BattleAction(action_type=BattleActionType.ATTACK, move_index=0, player_id="player2")

        events = BattleEngine.resolve_turn(state)
        drain_events = [e for e in events if "drained" in e.message.lower()]
        assert len(drain_events) >= 1
        # Attacker should have more HP than before
        assert attacker.current_hp > 100


# ---------------------------------------------------------------------------
# Recoil damage (negative drain_percent)
# ---------------------------------------------------------------------------


class TestRecoilDamage:
    """Negative drain_percent should hurt the attacker (recoil)."""

    def test_struggle_deals_recoil(self):
        """Struggle (drain_percent=-25) should damage the attacker after hitting."""
        random.seed(42)
        # Give them a move with 0 PP so Struggle is forced
        empty_move = _make_move("fake-move", "normal", 50, 100, 1)
        empty_move.current_pp = 0
        attacker = _make_battle_pokemon(name="recoiler", atk=100, spe=100, hp=200, moves=[empty_move])
        target = _make_battle_pokemon(name="target", hp=500, spe=50)

        team1 = _make_team([attacker], player_id="player1", trainer_name="P1")
        team2 = _make_team([target], player_id="player2", trainer_name="P2")
        state = _make_active_battle(team1, team2)
        assert state.team1 is not None and state.team2 is not None

        state.team1.action = BattleAction(action_type=BattleActionType.ATTACK, move_index=0, player_id="player1")
        state.team2.action = BattleAction(action_type=BattleActionType.ATTACK, move_index=0, player_id="player2")

        events = BattleEngine.resolve_turn(state)
        recoil_events = [e for e in events if "recoil" in e.message.lower()]
        assert len(recoil_events) >= 1
        assert attacker.current_hp < 200

    def test_recoil_faint_triggers_event(self):
        """If recoil KOs the attacker, a faint event should fire."""
        random.seed(42)
        recoil_move = Move(
            name="brave-bird", type="flying", damage_class=DamageClass.PHYSICAL,
            power=120, accuracy=100, pp=15, drain_percent=-33,
        )
        attacker = _make_battle_pokemon(name="kamikaze", atk=200, spe=100, hp=10,
                                        type1="flying", moves=[recoil_move])
        target = _make_battle_pokemon(name="wall", hp=500, defense=50, spe=50)

        team1 = _make_team([attacker], player_id="player1", trainer_name="P1")
        team2 = _make_team([target], player_id="player2", trainer_name="P2")
        state = _make_active_battle(team1, team2)
        assert state.team1 is not None and state.team2 is not None

        state.team1.action = BattleAction(action_type=BattleActionType.ATTACK, move_index=0, player_id="player1")
        state.team2.action = BattleAction(action_type=BattleActionType.ATTACK, move_index=0, player_id="player2")

        events = BattleEngine.resolve_turn(state)
        faint_events = [e for e in events if e.event_type == "faint" and e.player_id == "player1"]
        assert len(faint_events) >= 1
        assert attacker.is_fainted


# ---------------------------------------------------------------------------
# Status moves: Rest, status infliction, already-afflicted
# ---------------------------------------------------------------------------


class TestStatusMoves:
    """Tests for _handle_status_move branches."""

    def test_rest_heals_and_sleeps(self):
        """Rest should fully heal HP and apply 2-turn Sleep."""
        rest_move = Move(
            name="rest", type="normal", damage_class=DamageClass.STATUS,
            power=None, accuracy=None, pp=10, priority=0,
        )
        user = _make_battle_pokemon(name="rester", hp=200, spe=100, moves=[rest_move])
        user.current_hp = 50  # Damaged
        enemy = _make_battle_pokemon(name="enemy", hp=200, spe=50)

        team1 = _make_team([user], player_id="player1", trainer_name="P1")
        team2 = _make_team([enemy], player_id="player2", trainer_name="P2")
        state = _make_active_battle(team1, team2)
        assert state.team1 is not None and state.team2 is not None

        state.team1.action = BattleAction(action_type=BattleActionType.ATTACK, move_index=0, player_id="player1")
        state.team2.action = BattleAction(action_type=BattleActionType.ATTACK, move_index=0, player_id="player2")

        random.seed(42)
        BattleEngine.resolve_turn(state)
        # Rest heals to full, but enemy attacks after (slower), so HP may be less than max.
        # Key check: HP should be higher than where we started (50), and status should be Sleep.
        assert user.current_hp > 50
        assert user.status == StatusEffect.SLEEP
        assert user.status_turns == 2
        # Verify the rest event was recorded
        rest_events = [e for e in state.turn_log[0] if "restored hp" in e.message.lower() or "went to sleep" in e.message.lower()]
        assert len(rest_events) >= 1

    def test_rest_at_full_hp_no_sleep(self):
        """Rest at full HP should produce 'HP is already full' and NOT apply Sleep."""
        rest_move = Move(
            name="rest", type="normal", damage_class=DamageClass.STATUS,
            power=None, accuracy=None, pp=10, priority=0,
        )
        user = _make_battle_pokemon(name="rester", hp=200, spe=200, moves=[rest_move])
        enemy = _make_battle_pokemon(name="enemy", hp=200, spe=50)

        team1 = _make_team([user], player_id="player1", trainer_name="P1")
        team2 = _make_team([enemy], player_id="player2", trainer_name="P2")
        state = _make_active_battle(team1, team2)
        assert state.team1 is not None and state.team2 is not None

        state.team1.action = BattleAction(action_type=BattleActionType.ATTACK, move_index=0, player_id="player1")
        state.team2.action = BattleAction(action_type=BattleActionType.ATTACK, move_index=0, player_id="player2")

        events = BattleEngine.resolve_turn(state)
        full_hp_events = [e for e in events if "already full" in e.message.lower()]
        assert len(full_hp_events) >= 1
        assert user.status == StatusEffect.NONE

    def test_status_move_inflicts_on_defender(self):
        """Thunder Wave should paralyze a healthy target."""
        random.seed(42)
        t_wave = Move(
            name="thunder-wave", type="electric", damage_class=DamageClass.STATUS,
            power=None, accuracy=90, pp=20,
            status_effect=StatusEffect.PARALYSIS,
        )
        user = _make_battle_pokemon(name="paralyzer", spe=100, hp=200, moves=[t_wave])
        target = _make_battle_pokemon(name="victim", spe=50, hp=200)

        team1 = _make_team([user], player_id="player1", trainer_name="P1")
        team2 = _make_team([target], player_id="player2", trainer_name="P2")
        state = _make_active_battle(team1, team2)
        assert state.team1 is not None and state.team2 is not None

        state.team1.action = BattleAction(action_type=BattleActionType.ATTACK, move_index=0, player_id="player1")
        state.team2.action = BattleAction(action_type=BattleActionType.ATTACK, move_index=0, player_id="player2")

        BattleEngine.resolve_turn(state)
        assert target.status == StatusEffect.PARALYSIS

    def test_status_move_on_already_afflicted(self):
        """Status move against an already-statused target should fail."""
        random.seed(42)
        t_wave = Move(
            name="thunder-wave", type="electric", damage_class=DamageClass.STATUS,
            power=None, accuracy=90, pp=20,
            status_effect=StatusEffect.PARALYSIS,
        )
        user = _make_battle_pokemon(name="paralyzer", spe=100, hp=200, moves=[t_wave])
        target = _make_battle_pokemon(name="victim", spe=50, hp=200)
        target.status = StatusEffect.BURN  # Already afflicted

        team1 = _make_team([user], player_id="player1", trainer_name="P1")
        team2 = _make_team([target], player_id="player2", trainer_name="P2")
        state = _make_active_battle(team1, team2)
        assert state.team1 is not None and state.team2 is not None

        state.team1.action = BattleAction(action_type=BattleActionType.ATTACK, move_index=0, player_id="player1")
        state.team2.action = BattleAction(action_type=BattleActionType.ATTACK, move_index=0, player_id="player2")

        events = BattleEngine.resolve_turn(state)
        afflicted_events = [e for e in events if "already afflicted" in e.message.lower()]
        assert len(afflicted_events) >= 1
        # Status should still be burn, not paralysis
        assert target.status == StatusEffect.BURN

    def test_healing_status_move(self):
        """A status move with healing_percent > 0 should restore HP."""
        heal_move = Move(
            name="recover", type="normal", damage_class=DamageClass.STATUS,
            power=None, accuracy=None, pp=10, healing_percent=50,
        )
        user = _make_battle_pokemon(name="healer", hp=200, spe=200, moves=[heal_move])
        user.current_hp = 50
        enemy = _make_battle_pokemon(name="enemy", hp=200, spe=50)

        team1 = _make_team([user], player_id="player1", trainer_name="P1")
        team2 = _make_team([enemy], player_id="player2", trainer_name="P2")
        state = _make_active_battle(team1, team2)
        assert state.team1 is not None and state.team2 is not None

        state.team1.action = BattleAction(action_type=BattleActionType.ATTACK, move_index=0, player_id="player1")
        state.team2.action = BattleAction(action_type=BattleActionType.ATTACK, move_index=0, player_id="player2")

        events = BattleEngine.resolve_turn(state)
        recover_events = [e for e in events if "recovered" in e.message.lower()]
        assert len(recover_events) >= 1
        # Should have healed 50% of 200 = 100 HP (from 50 to 150, minus any enemy damage)
        assert user.current_hp > 50

    def test_generic_status_move_no_effect(self):
        """A status move with no special handling should produce a 'no additional effect' message."""
        generic = Move(
            name="splash", type="normal", damage_class=DamageClass.STATUS,
            power=None, accuracy=None, pp=40,
        )
        user = _make_battle_pokemon(name="user", spe=100, hp=200, moves=[generic])
        enemy = _make_battle_pokemon(name="enemy", spe=50, hp=200)

        team1 = _make_team([user], player_id="player1", trainer_name="P1")
        team2 = _make_team([enemy], player_id="player2", trainer_name="P2")
        state = _make_active_battle(team1, team2)
        assert state.team1 is not None and state.team2 is not None

        state.team1.action = BattleAction(action_type=BattleActionType.ATTACK, move_index=0, player_id="player1")
        state.team2.action = BattleAction(action_type=BattleActionType.ATTACK, move_index=0, player_id="player2")

        events = BattleEngine.resolve_turn(state)
        no_effect_events = [e for e in events if "no additional effect" in e.message.lower()]
        assert len(no_effect_events) >= 1


# ---------------------------------------------------------------------------
# Badly poisoned escalating damage
# ---------------------------------------------------------------------------


class TestBadlyPoisoned:
    """Badly poisoned damage should escalate each turn."""

    def test_badly_poisoned_escalates(self):
        """Each turn, badly poisoned damage should increase."""
        mon1 = _make_battle_pokemon(name="tanky1", hp=1000, spe=100)
        mon2 = _make_battle_pokemon(name="tanky2", hp=1000, spe=50)
        mon2.status = StatusEffect.BADLY_POISONED
        mon2.status_turns = 0

        team1 = _make_team([mon1], player_id="player1", trainer_name="P1")
        team2 = _make_team([mon2], player_id="player2", trainer_name="P2")
        state = _make_active_battle(team1, team2)
        assert state.team1 is not None and state.team2 is not None

        turn_damages = []
        for _ in range(3):
            random.seed(42)
            hp_before_status = mon2.current_hp
            state.team1.action = BattleAction(action_type=BattleActionType.ATTACK, move_index=0, player_id="player1")
            state.team2.action = BattleAction(action_type=BattleActionType.ATTACK, move_index=0, player_id="player2")
            events = BattleEngine.resolve_turn(state)
            if state.status != BattleStatus.ACTIVE:
                break

            # Find the badly poisoned status event
            poison_events = [e for e in events if "badly hurt by poison" in e.message.lower()]
            if poison_events:
                turn_damages.append(poison_events[0].damage)

        # Should have escalating damage (each turn's poison damage > previous)
        assert len(turn_damages) >= 2, f"Expected at least 2 poison events, got {len(turn_damages)}"
        for i in range(1, len(turn_damages)):
            assert turn_damages[i] > turn_damages[i - 1], (
                f"Badly poisoned damage should escalate: turn {i}={turn_damages[i-1]}, turn {i+1}={turn_damages[i]}"
            )


# ---------------------------------------------------------------------------
# Secondary status effect application
# ---------------------------------------------------------------------------


class TestSecondaryStatusEffect:
    """Damaging moves with effect_chance can inflict status."""

    def test_secondary_effect_can_apply(self):
        """A move with 100% effect_chance should always inflict its status."""
        burn_move = Move(
            name="scald", type="water", damage_class=DamageClass.SPECIAL,
            power=80, accuracy=100, pp=15,
            status_effect=StatusEffect.BURN, effect_chance=100,
        )
        attacker = _make_battle_pokemon(name="scalder", spa=100, spe=100, hp=200,
                                        type1="water", moves=[burn_move])
        target = _make_battle_pokemon(name="victim", hp=500, spe=50)

        team1 = _make_team([attacker], player_id="player1", trainer_name="P1")
        team2 = _make_team([target], player_id="player2", trainer_name="P2")
        state = _make_active_battle(team1, team2)
        assert state.team1 is not None and state.team2 is not None

        random.seed(42)
        state.team1.action = BattleAction(action_type=BattleActionType.ATTACK, move_index=0, player_id="player1")
        state.team2.action = BattleAction(action_type=BattleActionType.ATTACK, move_index=0, player_id="player2")

        events = BattleEngine.resolve_turn(state)
        burn_events = [e for e in events if "burn" in e.message.lower() and e.event_type == "status"]
        assert len(burn_events) >= 1
        assert target.status == StatusEffect.BURN


# ---------------------------------------------------------------------------
# Protect flag reset + multi-turn protect
# ---------------------------------------------------------------------------


class TestProtectFlagReset:
    """Protect should not persist across turns."""

    def test_protect_flag_clears_after_turn(self):
        """After using Protect, is_protected should be False at end of turn."""
        protect_move = Move(
            name="protect", type="normal", damage_class=DamageClass.STATUS,
            power=None, accuracy=None, pp=10, priority=4,
        )
        attack_move = _make_move("tackle", "normal", 40, 100, 35)

        protector = _make_battle_pokemon(name="protector", spe=200, hp=100, moves=[protect_move])
        attacker = _make_battle_pokemon(name="attacker", spe=50, hp=100, atk=100, moves=[attack_move])

        team1 = _make_team([protector], player_id="player1", trainer_name="P1")
        team2 = _make_team([attacker], player_id="player2", trainer_name="P2")
        state = _make_active_battle(team1, team2)
        assert state.team1 is not None and state.team2 is not None

        state.team1.action = BattleAction(action_type=BattleActionType.ATTACK, move_index=0, player_id="player1")
        state.team2.action = BattleAction(action_type=BattleActionType.ATTACK, move_index=0, player_id="player2")

        BattleEngine.resolve_turn(state)
        # After end-of-turn processing, is_protected should be reset
        assert protector.is_protected is False


# ---------------------------------------------------------------------------
# End-of-turn status faint + auto-switch
# ---------------------------------------------------------------------------


class TestStatusFaint:
    """Pokemon fainting from end-of-turn status damage should trigger auto-switch."""

    def test_burn_faint_triggers_auto_switch(self):
        """If burn damage KOs a Pokemon with a backup, auto-switch should happen."""
        # Give burn victim 1 HP so burn damage (max_hp//16 = at least 1) is lethal
        burned = _make_battle_pokemon(name="burned", hp=16, spe=50)
        burned.current_hp = 1
        burned.status = StatusEffect.BURN
        backup = _make_battle_pokemon(name="backup", hp=200, spe=50)
        healthy = _make_battle_pokemon(name="healthy", hp=200, spe=100)

        team1 = _make_team([healthy], player_id="player1", trainer_name="P1")
        team2 = _make_team([burned, backup], player_id="player2", trainer_name="P2")
        state = BattleState(
            challenger_id="player1", opponent_id="player2",
            format=BattleFormat.SINGLES_3V3, status=BattleStatus.ACTIVE,
            team1=team1, team2=team2,
        )
        assert state.team1 is not None and state.team2 is not None

        random.seed(42)
        state.team1.action = BattleAction(action_type=BattleActionType.ATTACK, move_index=0, player_id="player1")
        state.team2.action = BattleAction(action_type=BattleActionType.ATTACK, move_index=0, player_id="player2")

        events = BattleEngine.resolve_turn(state)
        faint_events = [e for e in events if e.event_type == "faint" and e.player_id == "player2"]
        # Burned mon should have fainted (from either attack or burn or both)
        assert burned.is_fainted
        assert len(faint_events) >= 1
        # If burned fainted from status, backup should be active
        assert state.team2.active_index == 1


# ---------------------------------------------------------------------------
# create_battle_pokemon edge cases
# ---------------------------------------------------------------------------


class TestCreateBattlePokemonEdgeCases:
    """Edge cases for the create_battle_pokemon factory."""

    def test_no_moves_generates_defaults(self):
        """When moves=None, default moveset should be generated based on types."""
        bp = create_battle_pokemon(
            pokemon_id=1, pokedex_id=25, name="pikachu", nickname=None,
            type1="electric", type2=None, level=50,
            base_stats={"hp": 35, "atk": 55, "def": 40, "spa": 50, "spd": 50, "spe": 90},
            ivs={"hp": 0, "atk": 0, "def": 0, "spa": 0, "spd": 0, "spe": 0},
            evs={"hp": 0, "atk": 0, "def": 0, "spa": 0, "spd": 0, "spe": 0},
            nature="hardy",
            moves=None,
        )
        assert len(bp.moves) >= 1
        assert len(bp.moves) <= 4
        # All moves should have full PP
        for m in bp.moves:
            assert m.current_pp == m.pp

    def test_nickname_preserved(self):
        """Nickname should be preserved in the battle snapshot."""
        bp = create_battle_pokemon(
            pokemon_id=1, pokedex_id=25, name="pikachu", nickname="Sparky",
            type1="electric", type2=None, level=50,
            base_stats={"hp": 35, "atk": 55, "def": 40, "spa": 50, "spd": 50, "spe": 90},
            ivs={"hp": 0, "atk": 0, "def": 0, "spa": 0, "spd": 0, "spe": 0},
            evs={"hp": 0, "atk": 0, "def": 0, "spa": 0, "spd": 0, "spe": 0},
            nature="hardy",
        )
        assert bp.nickname == "Sparky"
        assert bp.display_name == "Sparky"

    def test_hp_stat_formula(self):
        """HP uses a different formula: (2*base + iv + ev//4) * level/100 + level + 10."""
        bp = create_battle_pokemon(
            pokemon_id=1, pokedex_id=1, name="test", nickname=None,
            type1="normal", type2=None, level=50,
            base_stats={"hp": 100, "atk": 50, "def": 50, "spa": 50, "spd": 50, "spe": 50},
            ivs={"hp": 31, "atk": 0, "def": 0, "spa": 0, "spd": 0, "spe": 0},
            evs={"hp": 252, "atk": 0, "def": 0, "spa": 0, "spd": 0, "spe": 0},
            nature="hardy",
        )
        # HP = int((2*100 + 31 + 252//4) * 50/100) + 50 + 10
        # = int((200 + 31 + 63) * 0.5) + 60
        # = int(294 * 0.5) + 60
        # = 147 + 60 = 207
        assert bp.max_hp == 207
        assert bp.current_hp == 207


# ---------------------------------------------------------------------------
# BattleState edge cases
# ---------------------------------------------------------------------------


class TestBattleStateEdgeCases:
    """Additional edge cases for BattleState."""

    def test_get_opponent_team_unknown_player(self):
        """get_opponent_team with unknown player_id should return None."""
        state = _make_active_battle()
        assert state.get_opponent_team("nobody") is None

    def test_both_forfeit_same_turn(self):
        """If both players forfeit, the first one (player1) should be processed."""
        state = _make_active_battle()
        assert state.team1 is not None and state.team2 is not None

        state.team1.action = BattleAction(action_type=BattleActionType.FORFEIT, player_id="player1")
        state.team2.action = BattleAction(action_type=BattleActionType.FORFEIT, player_id="player2")

        events = BattleEngine.resolve_turn(state)
        assert state.status == BattleStatus.FORFEIT
        # First forfeit (team1) is processed; team2 wins
        assert state.winner_id == "player2"
        assert state.loser_id == "player1"
        forfeit_events = [e for e in events if e.event_type == "forfeit"]
        assert len(forfeit_events) == 1

    def test_move_index_out_of_bounds_defaults_to_zero(self):
        """If move_index is beyond the movelist, it should default to index 0."""
        random.seed(42)
        mon = _make_battle_pokemon(name="user", spe=100, hp=200)
        enemy = _make_battle_pokemon(name="target", spe=50, hp=200)

        team1 = _make_team([mon], player_id="player1", trainer_name="P1")
        team2 = _make_team([enemy], player_id="player2", trainer_name="P2")
        state = _make_active_battle(team1, team2)
        assert state.team1 is not None and state.team2 is not None

        # Submit action with move_index=99 (way out of bounds)
        state.team1.action = BattleAction(action_type=BattleActionType.ATTACK, move_index=99, player_id="player1")
        state.team2.action = BattleAction(action_type=BattleActionType.ATTACK, move_index=0, player_id="player2")

        # Should not crash -- falls back to move index 0
        events = BattleEngine.resolve_turn(state)
        attack_events = [e for e in events if e.event_type == "attack"]
        assert len(attack_events) >= 1

    def test_speed_tie_randomization(self):
        """Two Pokemon with exactly the same speed should randomly alternate who goes first."""
        first_attackers = set()
        for seed in range(20):
            random.seed(seed)
            mon1 = _make_battle_pokemon(name="twin_a", spe=100, hp=500)
            mon2 = _make_battle_pokemon(name="twin_b", spe=100, hp=500)

            team1 = _make_team([mon1], player_id="player1", trainer_name="P1")
            team2 = _make_team([mon2], player_id="player2", trainer_name="P2")
            state = _make_active_battle(team1, team2)
            assert state.team1 is not None and state.team2 is not None

            state.team1.action = BattleAction(action_type=BattleActionType.ATTACK, move_index=0, player_id="player1")
            state.team2.action = BattleAction(action_type=BattleActionType.ATTACK, move_index=0, player_id="player2")

            events = BattleEngine.resolve_turn(state)
            attack_events = [e for e in events if e.event_type == "attack"]
            if len(attack_events) >= 1:
                first_attackers.add(attack_events[0].player_id)

        # Over 20 seeds, both players should have gone first at least once
        assert len(first_attackers) == 2, (
            f"Speed tie should produce both outcomes over 20 seeds, got only {first_attackers}"
        )

    def test_paralysis_full_para_skips_turn(self):
        """25% chance a paralyzed Pokemon can't move at all."""
        skip_count = 0
        for seed in range(40):
            random.seed(seed)
            mon = _make_battle_pokemon(name="paralyzed", spe=100, hp=500)
            mon.status = StatusEffect.PARALYSIS
            enemy = _make_battle_pokemon(name="enemy", spe=50, hp=500)

            team1 = _make_team([mon], player_id="player1", trainer_name="P1")
            team2 = _make_team([enemy], player_id="player2", trainer_name="P2")
            state = _make_active_battle(team1, team2)
            assert state.team1 is not None and state.team2 is not None

            state.team1.action = BattleAction(action_type=BattleActionType.ATTACK, move_index=0, player_id="player1")
            state.team2.action = BattleAction(action_type=BattleActionType.ATTACK, move_index=0, player_id="player2")

            events = BattleEngine.resolve_turn(state)
            cant_move = [e for e in events if "can't move" in e.message.lower()]
            if cant_move:
                skip_count += 1

        # With 25% chance over 40 trials, we should see some skips (expected ~10)
        assert skip_count >= 3, f"Expected some full-para skips, got {skip_count}/40"
        assert skip_count <= 25, f"Too many full-para skips: {skip_count}/40"

    def test_sleep_wakes_up(self):
        """A sleeping Pokemon with status_turns=1 should wake up and attack."""
        random.seed(42)
        mon = _make_battle_pokemon(name="sleepy", spe=100, hp=200, atk=100)
        mon.status = StatusEffect.SLEEP
        mon.status_turns = 1  # Will wake up this turn
        enemy = _make_battle_pokemon(name="enemy", spe=50, hp=200)

        team1 = _make_team([mon], player_id="player1", trainer_name="P1")
        team2 = _make_team([enemy], player_id="player2", trainer_name="P2")
        state = _make_active_battle(team1, team2)
        assert state.team1 is not None and state.team2 is not None

        state.team1.action = BattleAction(action_type=BattleActionType.ATTACK, move_index=0, player_id="player1")
        state.team2.action = BattleAction(action_type=BattleActionType.ATTACK, move_index=0, player_id="player2")

        events = BattleEngine.resolve_turn(state)
        woke_events = [e for e in events if "woke up" in e.message.lower()]
        assert len(woke_events) >= 1
        assert mon.status == StatusEffect.NONE
