"""Async turn-based battle state machine.

Handles the full lifecycle of a PvP battle:
    challenge -> accept -> select teams -> take turns -> resolve -> finish

All game logic is authoritative -- the server runs this code to resolve
turns so neither client can cheat.
"""

from __future__ import annotations

import random
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from pokedo.core.moves import (
    DamageClass,
    Move,
    StatusEffect,
    calculate_damage,
    generate_default_moveset,
    get_nature_multiplier,
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class BattleStatus(str, Enum):
    """Lifecycle status of a battle."""

    PENDING = "pending"  # Challenge sent, waiting for accept
    TEAM_SELECT = "team_select"  # Both players selecting teams
    ACTIVE = "active"  # Battle in progress
    FINISHED = "finished"  # Battle complete
    CANCELLED = "cancelled"  # Declined or timed out
    FORFEIT = "forfeit"  # One player forfeited


class BattleActionType(str, Enum):
    """Types of actions a player can take each turn."""

    ATTACK = "attack"
    SWITCH = "switch"
    FORFEIT = "forfeit"


class BattleFormat(str, Enum):
    """Battle format rules."""

    SINGLES_3V3 = "singles_3v3"
    SINGLES_6V6 = "singles_6v6"
    SINGLES_1V1 = "singles_1v1"


# ---------------------------------------------------------------------------
# Supporting models
# ---------------------------------------------------------------------------

class BattlePokemon(BaseModel):
    """A Pokemon prepared for battle with runtime HP and move PP tracking.

    This is a snapshot -- changes here do NOT propagate back to the
    player's permanent Pokemon data.
    """

    # Identity
    pokemon_id: int  # DB id of the source Pokemon
    pokedex_id: int
    name: str
    nickname: str | None = None

    # Types
    type1: str
    type2: str | None = None

    # Calculated stats (frozen at battle start)
    max_hp: int
    current_hp: int
    atk: int
    defense: int  # 'def' is a Python keyword
    spa: int
    spd: int
    spe: int

    # Level and nature
    level: int = 50
    nature: str = "hardy"

    # Moves (up to 4)
    moves: list[Move] = Field(default_factory=list)

    # Status
    status: StatusEffect = StatusEffect.NONE
    status_turns: int = 0  # Turns remaining for sleep, etc.
    is_fainted: bool = False

    # Flags for turn resolution
    is_protected: bool = False  # Used Protect this turn
    confusion_turns: int = 0

    @property
    def display_name(self) -> str:
        return self.nickname or self.name.capitalize()

    @property
    def hp_percent(self) -> float:
        if self.max_hp == 0:
            return 0.0
        return (self.current_hp / self.max_hp) * 100

    @property
    def types(self) -> list[str]:
        t = [self.type1]
        if self.type2:
            t.append(self.type2)
        return t

    def take_damage(self, amount: int) -> int:
        """Apply damage, return actual amount dealt. Clamps to 0."""
        actual = min(amount, self.current_hp)
        self.current_hp -= actual
        if self.current_hp <= 0:
            self.current_hp = 0
            self.is_fainted = True
        return actual

    def heal(self, amount: int) -> int:
        """Heal HP, return actual amount healed. Clamps to max_hp."""
        if self.is_fainted:
            return 0
        actual = min(amount, self.max_hp - self.current_hp)
        self.current_hp += actual
        return actual


class BattleAction(BaseModel):
    """An action submitted by a player for one turn."""

    action_type: BattleActionType
    move_index: int | None = None  # Index into active Pokemon's moves (0-3)
    switch_to: int | None = None  # Index into the player's team roster
    player_id: str = ""


class TurnEvent(BaseModel):
    """A single event that occurred during turn resolution.

    The client uses these to animate/display the battle.
    """

    event_type: str  # "attack", "damage", "faint", "switch", "status", "miss", "immune", "info"
    player_id: str = ""
    pokemon_name: str = ""
    target_name: str = ""
    move_name: str = ""
    damage: int = 0
    effectiveness: float = 1.0
    critical: bool = False
    message: str = ""


class BattleTeam(BaseModel):
    """One player's side in a battle."""

    player_id: str
    trainer_name: str = ""
    roster: list[BattlePokemon] = Field(default_factory=list)
    active_index: int = 0  # Which Pokemon is currently out
    action: BattleAction | None = None  # Submitted action for current turn

    @property
    def active_pokemon(self) -> BattlePokemon | None:
        if 0 <= self.active_index < len(self.roster):
            return self.roster[self.active_index]
        return None

    @property
    def has_usable_pokemon(self) -> bool:
        return any(not p.is_fainted for p in self.roster)

    @property
    def alive_count(self) -> int:
        return sum(1 for p in self.roster if not p.is_fainted)

    def next_alive_index(self) -> int | None:
        """Return the index of the next non-fainted Pokemon, or None."""
        for i, p in enumerate(self.roster):
            if i != self.active_index and not p.is_fainted:
                return i
        return None


# ---------------------------------------------------------------------------
# Main battle state
# ---------------------------------------------------------------------------

class BattleState(BaseModel):
    """The complete state of a battle between two players.

    This object is persisted (as JSON) between turns so it can be
    loaded, advanced, and saved by the server.
    """

    # Identity
    battle_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Battle config
    format: BattleFormat = BattleFormat.SINGLES_3V3
    status: BattleStatus = BattleStatus.PENDING

    # Players
    challenger_id: str  # Server user ID / username
    opponent_id: str
    team1: BattleTeam | None = None  # Challenger
    team2: BattleTeam | None = None  # Opponent

    # Turn tracking
    turn_number: int = 0
    turn_log: list[list[TurnEvent]] = Field(default_factory=list)  # Events per turn

    # Result
    winner_id: str | None = None
    loser_id: str | None = None

    # ELO changes (set after resolution)
    winner_elo_delta: int = 0
    loser_elo_delta: int = 0

    def get_team(self, player_id: str) -> BattleTeam | None:
        """Get a player's team by their ID."""
        if self.team1 and self.team1.player_id == player_id:
            return self.team1
        if self.team2 and self.team2.player_id == player_id:
            return self.team2
        return None

    def get_opponent_team(self, player_id: str) -> BattleTeam | None:
        """Get the opposing team."""
        if self.team1 and self.team1.player_id == player_id:
            return self.team2
        if self.team2 and self.team2.player_id == player_id:
            return self.team1
        return None

    def both_actions_submitted(self) -> bool:
        """Check if both players have submitted their actions for this turn."""
        if not self.team1 or not self.team2:
            return False
        return self.team1.action is not None and self.team2.action is not None


# ---------------------------------------------------------------------------
# Battle Pokemon factory
# ---------------------------------------------------------------------------

def create_battle_pokemon(
    pokemon_id: int,
    pokedex_id: int,
    name: str,
    nickname: str | None,
    type1: str,
    type2: str | None,
    level: int,
    base_stats: dict[str, int],
    ivs: dict[str, int],
    evs: dict[str, int],
    nature: str,
    moves: list[Move] | None = None,
) -> BattlePokemon:
    """Create a BattlePokemon snapshot from a Pokemon's permanent data.

    Calculates all stats and freezes them for the duration of the battle.
    If no moves are provided, generates a default moveset.
    """

    def calc_stat(stat_name: str) -> int:
        base = base_stats.get(stat_name, 50)
        iv = ivs.get(stat_name, 0)
        ev = evs.get(stat_name, 0)
        nature_mult = get_nature_multiplier(nature, stat_name)
        if stat_name == "hp":
            return int((2 * base + iv + ev // 4) * level / 100) + level + 10
        else:
            return int(((2 * base + iv + ev // 4) * level / 100 + 5) * nature_mult)

    hp = calc_stat("hp")

    battle_moves = moves if moves else generate_default_moveset(type1, type2, level)
    # Reset PP for all moves
    for m in battle_moves:
        m.current_pp = m.pp

    return BattlePokemon(
        pokemon_id=pokemon_id,
        pokedex_id=pokedex_id,
        name=name,
        nickname=nickname,
        type1=type1,
        type2=type2,
        max_hp=hp,
        current_hp=hp,
        atk=calc_stat("atk"),
        defense=calc_stat("def"),
        spa=calc_stat("spa"),
        spd=calc_stat("spd"),
        spe=calc_stat("spe"),
        level=level,
        nature=nature,
        moves=battle_moves,
    )


# ---------------------------------------------------------------------------
# Turn resolution engine
# ---------------------------------------------------------------------------

class BattleEngine:
    """Resolves one turn of a battle.

    Stateless -- takes a BattleState, mutates it, and returns the events
    for that turn.
    """

    @staticmethod
    def resolve_turn(state: BattleState) -> list[TurnEvent]:
        """Resolve a single turn where both players have submitted actions.

        Mutation: updates state in-place (HP, status, active Pokemon, etc.).
        Returns the list of events for this turn.
        """
        if not state.both_actions_submitted():
            return []

        events: list[TurnEvent] = []
        team1 = state.team1
        team2 = state.team2
        assert team1 is not None, "team1 must be set before resolving"
        assert team2 is not None, "team2 must be set before resolving"
        action1 = team1.action
        action2 = team2.action
        assert action1 is not None, "action1 must be set before resolving"
        assert action2 is not None, "action2 must be set before resolving"

        state.turn_number += 1

        # Handle forfeits first
        if action1.action_type == BattleActionType.FORFEIT:
            state.status = BattleStatus.FORFEIT
            state.winner_id = team2.player_id
            state.loser_id = team1.player_id
            events.append(TurnEvent(
                event_type="forfeit",
                player_id=team1.player_id,
                message=f"{team1.trainer_name} forfeited the battle!",
            ))
            team1.action = None
            team2.action = None
            return events

        if action2.action_type == BattleActionType.FORFEIT:
            state.status = BattleStatus.FORFEIT
            state.winner_id = team1.player_id
            state.loser_id = team2.player_id
            events.append(TurnEvent(
                event_type="forfeit",
                player_id=team2.player_id,
                message=f"{team2.trainer_name} forfeited the battle!",
            ))
            team1.action = None
            team2.action = None
            return events

        # Process switches first (switches always happen before attacks)
        for team, action in [(team1, action1), (team2, action2)]:
            if action.action_type == BattleActionType.SWITCH:
                old_name = team.active_pokemon.display_name if team.active_pokemon else "?"
                team.active_index = action.switch_to or 0
                new_name = team.active_pokemon.display_name if team.active_pokemon else "?"
                events.append(TurnEvent(
                    event_type="switch",
                    player_id=team.player_id,
                    pokemon_name=new_name,
                    message=f"{team.trainer_name} switched {old_name} for {new_name}!",
                ))

        # Determine attack order by speed (higher goes first)
        attackers: list[tuple[BattleTeam, BattleAction, BattleTeam]] = []
        if action1.action_type == BattleActionType.ATTACK:
            attackers.append((team1, action1, team2))
        if action2.action_type == BattleActionType.ATTACK:
            attackers.append((team2, action2, team1))

        if len(attackers) == 2:
            # Compare move priority first, then speed (halved if paralyzed)
            def _effective_speed(mon: BattlePokemon) -> int:
                """Return speed, halved when paralyzed (Gen V+)."""
                spd = mon.spe
                if mon.status == StatusEffect.PARALYSIS:
                    spd = spd // 2
                return spd

            def sort_key(entry: tuple[BattleTeam, BattleAction, BattleTeam]) -> tuple[int, int]:
                team, action, _ = entry
                pokemon = team.active_pokemon
                move_priority = 0
                if action.move_index is not None and pokemon and action.move_index < len(pokemon.moves):
                    move_priority = pokemon.moves[action.move_index].priority
                speed = _effective_speed(pokemon) if pokemon else 0
                return (move_priority, speed)

            attackers.sort(key=sort_key, reverse=True)

            # Speed tie -- random
            t1, a1, _ = attackers[0]
            t2, a2, _ = attackers[1]
            p1 = t1.active_pokemon
            p2 = t2.active_pokemon
            if p1 and p2:
                pri1 = 0
                pri2 = 0
                if a1.move_index is not None and a1.move_index < len(p1.moves):
                    pri1 = p1.moves[a1.move_index].priority
                if a2.move_index is not None and a2.move_index < len(p2.moves):
                    pri2 = p2.moves[a2.move_index].priority
                if pri1 == pri2 and _effective_speed(p1) == _effective_speed(p2):
                    random.shuffle(attackers)

        # Execute attacks in order
        for atk_team, atk_action, def_team in attackers:
            atk_mon = atk_team.active_pokemon
            def_mon = def_team.active_pokemon

            if not atk_mon or atk_mon.is_fainted:
                continue
            if not def_mon or def_mon.is_fainted:
                continue

            # Check if defender is protected
            if def_mon.is_protected:
                events.append(TurnEvent(
                    event_type="info",
                    player_id=def_team.player_id,
                    pokemon_name=def_mon.display_name,
                    message=f"{def_mon.display_name} protected itself!",
                ))
                continue

            events.extend(BattleEngine._execute_attack(atk_team, atk_action, def_team))

            # Check if attacker fainted (recoil / Struggle)
            if atk_mon.is_fainted:
                events.append(TurnEvent(
                    event_type="faint",
                    player_id=atk_team.player_id,
                    pokemon_name=atk_mon.display_name,
                    message=f"{atk_mon.display_name} fainted!",
                ))
                next_idx = atk_team.next_alive_index()
                if next_idx is not None:
                    atk_team.active_index = next_idx
                    new_mon = atk_team.active_pokemon
                    events.append(TurnEvent(
                        event_type="switch",
                        player_id=atk_team.player_id,
                        pokemon_name=new_mon.display_name if new_mon else "?",
                        message=f"{atk_team.trainer_name} sent out {new_mon.display_name if new_mon else '?'}!",
                    ))

            # Check if defender fainted
            if def_mon.is_fainted:
                events.append(TurnEvent(
                    event_type="faint",
                    player_id=def_team.player_id,
                    pokemon_name=def_mon.display_name,
                    message=f"{def_mon.display_name} fainted!",
                ))
                # Auto-switch to next alive Pokemon
                next_idx = def_team.next_alive_index()
                if next_idx is not None:
                    def_team.active_index = next_idx
                    new_mon = def_team.active_pokemon
                    events.append(TurnEvent(
                        event_type="switch",
                        player_id=def_team.player_id,
                        pokemon_name=new_mon.display_name if new_mon else "?",
                        message=f"{def_team.trainer_name} sent out {new_mon.display_name if new_mon else '?'}!",
                    ))

        # Apply end-of-turn status damage
        for team in [team1, team2]:
            mon = team.active_pokemon
            if mon and not mon.is_fainted:
                status_events = BattleEngine._apply_status_damage(team)
                events.extend(status_events)
                if mon.is_fainted:
                    events.append(TurnEvent(
                        event_type="faint",
                        player_id=team.player_id,
                        pokemon_name=mon.display_name,
                        message=f"{mon.display_name} fainted from {mon.status.value}!",
                    ))
                    next_idx = team.next_alive_index()
                    if next_idx is not None:
                        team.active_index = next_idx
                        new_mon = team.active_pokemon
                        events.append(TurnEvent(
                            event_type="switch",
                            player_id=team.player_id,
                            pokemon_name=new_mon.display_name if new_mon else "?",
                            message=f"{team.trainer_name} sent out {new_mon.display_name if new_mon else '?'}!",
                        ))

        # Check win condition
        t1_out = not team1.has_usable_pokemon
        t2_out = not team2.has_usable_pokemon
        if t1_out and t2_out:
            # Mutual KO -- draw
            state.status = BattleStatus.FINISHED
            state.winner_id = None
            state.loser_id = None
            events.append(TurnEvent(
                event_type="info",
                message="Both sides are out of usable Pokemon -- it's a draw!",
            ))
        elif t1_out:
            state.status = BattleStatus.FINISHED
            state.winner_id = team2.player_id
            state.loser_id = team1.player_id
            events.append(TurnEvent(
                event_type="info",
                message=f"{team2.trainer_name} wins the battle!",
            ))
        elif t2_out:
            state.status = BattleStatus.FINISHED
            state.winner_id = team1.player_id
            state.loser_id = team2.player_id
            events.append(TurnEvent(
                event_type="info",
                message=f"{team1.trainer_name} wins the battle!",
            ))

        # Clear actions for next turn
        team1.action = None
        team2.action = None

        # Save turn events
        state.turn_log.append(events)
        state.updated_at = datetime.now(timezone.utc)

        return events

    @staticmethod
    def _execute_attack(
        atk_team: BattleTeam,
        action: BattleAction,
        def_team: BattleTeam,
    ) -> list[TurnEvent]:
        """Execute a single attack action. Returns events."""
        events: list[TurnEvent] = []
        atk_mon = atk_team.active_pokemon
        def_mon = def_team.active_pokemon

        if not atk_mon or not def_mon:
            return events

        # Check status preventing action
        if atk_mon.status == StatusEffect.SLEEP:
            atk_mon.status_turns -= 1
            if atk_mon.status_turns <= 0:
                atk_mon.status = StatusEffect.NONE
                events.append(TurnEvent(
                    event_type="status",
                    player_id=atk_team.player_id,
                    pokemon_name=atk_mon.display_name,
                    message=f"{atk_mon.display_name} woke up!",
                ))
            else:
                events.append(TurnEvent(
                    event_type="status",
                    player_id=atk_team.player_id,
                    pokemon_name=atk_mon.display_name,
                    message=f"{atk_mon.display_name} is fast asleep!",
                ))
                return events

        if atk_mon.status == StatusEffect.FREEZE:
            # 20% chance to thaw each turn
            if random.random() < 0.2:
                atk_mon.status = StatusEffect.NONE
                events.append(TurnEvent(
                    event_type="status",
                    player_id=atk_team.player_id,
                    pokemon_name=atk_mon.display_name,
                    message=f"{atk_mon.display_name} thawed out!",
                ))
            else:
                events.append(TurnEvent(
                    event_type="status",
                    player_id=atk_team.player_id,
                    pokemon_name=atk_mon.display_name,
                    message=f"{atk_mon.display_name} is frozen solid!",
                ))
                return events

        if atk_mon.status == StatusEffect.PARALYSIS:
            # 25% chance to be fully paralyzed
            if random.random() < 0.25:
                events.append(TurnEvent(
                    event_type="status",
                    player_id=atk_team.player_id,
                    pokemon_name=atk_mon.display_name,
                    message=f"{atk_mon.display_name} is paralyzed and can't move!",
                ))
                return events

        # Get the move
        move_idx = action.move_index or 0
        if move_idx >= len(atk_mon.moves):
            move_idx = 0
        move = atk_mon.moves[move_idx]

        # Check PP
        if move.current_pp is not None and move.current_pp <= 0:
            events.append(TurnEvent(
                event_type="info",
                player_id=atk_team.player_id,
                pokemon_name=atk_mon.display_name,
                message=f"{atk_mon.display_name} has no PP left for {move.display_name}! It used Struggle!",
            ))
            # Struggle: 50 power, typeless (neutral vs everything), 25% recoil
            move = Move(
                name="struggle", type="typeless",
                damage_class=DamageClass.PHYSICAL, power=50,
                accuracy=100, pp=999, drain_percent=-25,
            )

        # Deduct PP
        if move.current_pp is not None:
            move.current_pp -= 1

        events.append(TurnEvent(
            event_type="attack",
            player_id=atk_team.player_id,
            pokemon_name=atk_mon.display_name,
            target_name=def_mon.display_name,
            move_name=move.display_name,
        ))

        # Status moves (simplified handling)
        if move.damage_class == DamageClass.STATUS:
            events.extend(BattleEngine._handle_status_move(atk_team, move, def_team))
            return events

        # Accuracy check
        if move.accuracy is not None:
            if random.randint(1, 100) > move.accuracy:
                events.append(TurnEvent(
                    event_type="miss",
                    player_id=atk_team.player_id,
                    pokemon_name=atk_mon.display_name,
                    message=f"{atk_mon.display_name}'s attack missed!",
                ))
                return events

        # Determine attack/defense stats
        if move.damage_class == DamageClass.PHYSICAL:
            atk_stat = atk_mon.atk
            def_stat = def_mon.defense
            # Burn halves physical attack
            if atk_mon.status == StatusEffect.BURN:
                atk_stat = atk_stat // 2
        else:
            atk_stat = atk_mon.spa
            def_stat = def_mon.spd

        # Calculate damage
        damage, effectiveness, was_crit = calculate_damage(
            attacker_level=atk_mon.level,
            move=move,
            attack_stat=atk_stat,
            defense_stat=max(1, def_stat),
            attacker_types=atk_mon.types,
            defender_type1=def_mon.type1,
            defender_type2=def_mon.type2,
            critical=False,
        )

        # Apply damage
        if effectiveness == 0:
            events.append(TurnEvent(
                event_type="immune",
                player_id=def_team.player_id,
                pokemon_name=def_mon.display_name,
                message=f"It doesn't affect {def_mon.display_name}...",
                effectiveness=0.0,
            ))
            return events

        actual_damage = def_mon.take_damage(damage)

        eff_msg = ""
        if effectiveness > 1.0:
            eff_msg = "It's super effective!"
        elif effectiveness < 1.0:
            eff_msg = "It's not very effective..."

        crit_msg = " A critical hit!" if was_crit else ""

        events.append(TurnEvent(
            event_type="damage",
            player_id=def_team.player_id,
            pokemon_name=def_mon.display_name,
            damage=actual_damage,
            effectiveness=effectiveness,
            critical=was_crit,
            message=f"{def_mon.display_name} took {actual_damage} damage!{crit_msg} {eff_msg}".strip(),
        ))

        # Drain / recoil
        if move.drain_percent != 0:
            drain_amount = int(actual_damage * abs(move.drain_percent) / 100)
            if move.drain_percent > 0:
                healed = atk_mon.heal(drain_amount)
                if healed > 0:
                    events.append(TurnEvent(
                        event_type="info",
                        player_id=atk_team.player_id,
                        pokemon_name=atk_mon.display_name,
                        message=f"{atk_mon.display_name} drained {healed} HP!",
                    ))
            else:
                recoil = atk_mon.take_damage(drain_amount)
                if recoil > 0:
                    events.append(TurnEvent(
                        event_type="info",
                        player_id=atk_team.player_id,
                        pokemon_name=atk_mon.display_name,
                        message=f"{atk_mon.display_name} took {recoil} recoil damage!",
                    ))

        # Secondary status effect
        if move.status_effect != StatusEffect.NONE and move.effect_chance:
            if random.randint(1, 100) <= move.effect_chance and def_mon.status == StatusEffect.NONE:
                def_mon.status = move.status_effect
                if move.status_effect == StatusEffect.SLEEP:
                    def_mon.status_turns = random.randint(1, 3)
                events.append(TurnEvent(
                    event_type="status",
                    player_id=def_team.player_id,
                    pokemon_name=def_mon.display_name,
                    message=f"{def_mon.display_name} was afflicted with {move.status_effect.value}!",
                ))

        return events

    @staticmethod
    def _handle_status_move(
        atk_team: BattleTeam,
        move: Move,
        def_team: BattleTeam,
    ) -> list[TurnEvent]:
        """Handle non-damaging status moves (simplified)."""
        events: list[TurnEvent] = []
        atk_mon = atk_team.active_pokemon
        def_mon = def_team.active_pokemon
        if not atk_mon or not def_mon:
            return events

        name = move.name.lower()

        if name == "protect":
            atk_mon.is_protected = True
            events.append(TurnEvent(
                event_type="status",
                player_id=atk_team.player_id,
                pokemon_name=atk_mon.display_name,
                message=f"{atk_mon.display_name} protected itself!",
            ))
        elif name == "rest":
            if atk_mon.current_hp < atk_mon.max_hp:
                atk_mon.current_hp = atk_mon.max_hp
                atk_mon.status = StatusEffect.SLEEP
                atk_mon.status_turns = 2
                events.append(TurnEvent(
                    event_type="status",
                    player_id=atk_team.player_id,
                    pokemon_name=atk_mon.display_name,
                    message=f"{atk_mon.display_name} went to sleep and restored HP!",
                ))
            else:
                events.append(TurnEvent(
                    event_type="info",
                    player_id=atk_team.player_id,
                    pokemon_name=atk_mon.display_name,
                    message=f"{atk_mon.display_name}'s HP is already full!",
                ))
        elif move.healing_percent > 0:
            heal_amount = int(atk_mon.max_hp * move.healing_percent / 100)
            healed = atk_mon.heal(heal_amount)
            events.append(TurnEvent(
                event_type="info",
                player_id=atk_team.player_id,
                pokemon_name=atk_mon.display_name,
                message=f"{atk_mon.display_name} recovered {healed} HP!",
            ))
        elif move.status_effect != StatusEffect.NONE:
            if def_mon.status == StatusEffect.NONE:
                # Accuracy check
                if move.accuracy is not None and random.randint(1, 100) > move.accuracy:
                    events.append(TurnEvent(
                        event_type="miss",
                        player_id=atk_team.player_id,
                        pokemon_name=atk_mon.display_name,
                        message=f"{atk_mon.display_name}'s attack missed!",
                    ))
                    return events
                def_mon.status = move.status_effect
                if move.status_effect == StatusEffect.SLEEP:
                    def_mon.status_turns = random.randint(1, 3)
                _STATUS_VERB = {
                    "burn": "burned",
                    "freeze": "frozen",
                    "paralysis": "paralyzed",
                    "poison": "poisoned",
                    "badly_poisoned": "badly poisoned",
                    "sleep": "put to sleep",
                }
                verb = _STATUS_VERB.get(move.status_effect.value, "afflicted")
                events.append(TurnEvent(
                    event_type="status",
                    player_id=def_team.player_id,
                    pokemon_name=def_mon.display_name,
                    message=f"{def_mon.display_name} was {verb}!",
                ))
            else:
                events.append(TurnEvent(
                    event_type="info",
                    player_id=def_team.player_id,
                    pokemon_name=def_mon.display_name,
                    message=f"But {def_mon.display_name} is already afflicted...",
                ))
        else:
            events.append(TurnEvent(
                event_type="info",
                player_id=atk_team.player_id,
                pokemon_name=atk_mon.display_name,
                message=f"{atk_mon.display_name} used {move.display_name}!  (No additional effect.)",
            ))

        return events

    @staticmethod
    def _apply_status_damage(team: BattleTeam) -> list[TurnEvent]:
        """Apply end-of-turn status damage (burn, poison)."""
        events: list[TurnEvent] = []
        mon = team.active_pokemon
        if not mon or mon.is_fainted:
            return events

        if mon.status == StatusEffect.BURN:
            dmg = max(1, mon.max_hp // 16)
            mon.take_damage(dmg)
            events.append(TurnEvent(
                event_type="status",
                player_id=team.player_id,
                pokemon_name=mon.display_name,
                damage=dmg,
                message=f"{mon.display_name} was hurt by its burn! (-{dmg} HP)",
            ))

        elif mon.status == StatusEffect.POISON:
            dmg = max(1, mon.max_hp // 8)
            mon.take_damage(dmg)
            events.append(TurnEvent(
                event_type="status",
                player_id=team.player_id,
                pokemon_name=mon.display_name,
                damage=dmg,
                message=f"{mon.display_name} was hurt by poison! (-{dmg} HP)",
            ))

        elif mon.status == StatusEffect.BADLY_POISONED:
            mon.status_turns += 1
            dmg = max(1, mon.max_hp * mon.status_turns // 16)
            mon.take_damage(dmg)
            events.append(TurnEvent(
                event_type="status",
                player_id=team.player_id,
                pokemon_name=mon.display_name,
                damage=dmg,
                message=f"{mon.display_name} was badly hurt by poison! (-{dmg} HP)",
            ))

        # Reset protect flag at end of turn
        mon.is_protected = False

        return events


# ---------------------------------------------------------------------------
# ELO rating helpers
# ---------------------------------------------------------------------------

DEFAULT_ELO = 1000
K_FACTOR = 32


def calculate_elo_change(winner_elo: int, loser_elo: int) -> tuple[int, int]:
    """Calculate ELO rating changes after a battle.

    Returns (winner_delta, loser_delta) where winner_delta > 0 and loser_delta < 0.
    Uses a K-factor of 32.
    """
    expected_winner = 1.0 / (1.0 + 10 ** ((loser_elo - winner_elo) / 400))
    expected_loser = 1.0 - expected_winner

    winner_delta = round(K_FACTOR * (1 - expected_winner))
    loser_delta = round(K_FACTOR * (0 - expected_loser))

    return winner_delta, loser_delta


def compute_rank(elo: int) -> str:
    """Derive a PvP rank label from an ELO rating.

    Shared by the client-side Trainer model and the server.
    """
    if elo < 1100:
        return "Youngster"
    if elo < 1300:
        return "Bug Catcher"
    if elo < 1500:
        return "Ace Trainer"
    if elo < 1700:
        return "Gym Leader"
    if elo < 1900:
        return "Elite Four"
    if elo < 2100:
        return "Champion"
    return "Pokemon Master"
