"""Pokemon model and related logic."""

import random
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from pokedo.core.moves import Move, PokemonNature, generate_default_moveset, random_nature

if TYPE_CHECKING:
    from pokedo.core.battle import BattlePokemon


class PokemonRarity(str, Enum):
    """Rarity tiers for Pokemon."""

    COMMON = "common"
    UNCOMMON = "uncommon"
    RARE = "rare"
    EPIC = "epic"
    LEGENDARY = "legendary"
    MYTHICAL = "mythical"


class Pokemon(BaseModel):
    """A Pokemon instance owned by the player."""

    id: int | None = None  # Database ID
    pokedex_id: int  # National Pokedex number
    name: str
    nickname: str | None = None

    # Types
    type1: str
    type2: str | None = None

    # Stats
    level: int = 1
    xp: int = 0
    happiness: int = 50  # 0-255
    evs: dict[str, int] = Field(
        default_factory=lambda: {"hp": 0, "atk": 0, "def": 0, "spa": 0, "spd": 0, "spe": 0}
    )
    ivs: dict[str, int] = Field(
        default_factory=lambda: {"hp": 0, "atk": 0, "def": 0, "spa": 0, "spd": 0, "spe": 0}
    )
    base_stats: dict[str, int] = Field(
        default_factory=lambda: {"hp": 50, "atk": 50, "def": 50, "spa": 50, "spd": 50, "spe": 50}
    )

    # Catch info
    caught_at: datetime = Field(default_factory=datetime.now)
    is_shiny: bool = False
    catch_location: str | None = None  # Task category that triggered catch

    # Status
    is_active: bool = False  # In active team
    is_favorite: bool = False

    # Evolution
    can_evolve: bool = False
    evolution_id: int | None = None  # Pokedex ID of evolution
    evolution_level: int | None = None
    evolution_method: str | None = None  # "level", "item", "trade", "friendship"

    # Nature and moves (multiplayer / battle support)
    nature: str = "hardy"  # PokemonNature value; defaults to neutral
    moves: list[Move] = Field(default_factory=list)  # Up to 4 moves

    # Sprites (cached paths)
    sprite_url: str | None = None
    sprite_path: str | None = None

    @property
    def display_name(self) -> str:
        """Get display name (nickname or species name)."""
        return self.nickname or self.name.capitalize()

    @property
    def types_display(self) -> str:
        """Get formatted type display."""
        if self.type2:
            return f"{self.type1.capitalize()}/{self.type2.capitalize()}"
        return self.type1.capitalize()

    @property
    def remaining_evs(self) -> int:
        """Calculate remaining EV points (max 510 total)."""
        return 510 - sum(self.evs.values())

    def calculate_stat(self, stat_name: str) -> int:
        """Calculate actual stat value using the Pokemon formula.

        HP: ((2 * base + iv + ev/4) * level / 100) + level + 10
        Other: ((2 * base + iv + ev/4) * level / 100) + 5
        """
        base = self.base_stats.get(stat_name, 50)
        iv = self.ivs.get(stat_name, 0)
        ev = self.evs.get(stat_name, 0)

        if stat_name == "hp":
            return int((2 * base + iv + ev // 4) * self.level / 100) + self.level + 10
        else:
            return int((2 * base + iv + ev // 4) * self.level / 100) + 5

    @property
    def stats(self) -> dict[str, int]:
        """Get all calculated stats."""
        return {stat: self.calculate_stat(stat) for stat in ["hp", "atk", "def", "spa", "spd", "spe"]}

    def add_evs(self, stat: str, amount: int) -> int:
        """
        Add EVs to a stat, respecting caps.
        Returns the actual amount added.
        """
        if stat not in self.evs:
            return 0

        # Check global cap (510)
        amount = min(amount, self.remaining_evs)
        if amount <= 0:
            return 0

        # Check per-stat cap (252)
        current_val = self.evs[stat]
        space_in_stat = 252 - current_val
        amount = min(amount, space_in_stat)

        if amount > 0:
            self.evs[stat] += amount
            return amount
        return 0

    def assign_ivs(self) -> None:
        """Randomize IVs (0-31) for all stats."""
        # Only assign if they look uninitialized (all 0)
        # Use a flag or just overwrite? Spec says "at capture".
        # We'll overwrite to ensure randomness when called.
        for stat in self.ivs:
            self.ivs[stat] = random.randint(0, 31)

    def gain_xp(self, amount: int) -> bool:
        """Add XP to Pokemon, returns True if leveled up."""
        self.xp += amount
        new_level = self._calculate_level()
        if new_level > self.level:
            self.level = new_level
            self._check_evolution()
            return True
        return False

    def _calculate_level(self) -> int:
        """Calculate level from XP."""
        level = 1
        xp_needed = 0
        while level < 100:
            # Pokémon use a different XP curve than trainers (level * 50 vs. level * 100 in helpers.py)
            # to allow for faster Pokémon leveling and better pacing. This is an intentional design choice.
            xp_for_next = level * 50
            if self.xp < xp_needed + xp_for_next:
                break
            xp_needed += xp_for_next
            level += 1
        return level

    def _check_evolution(self) -> None:
        """Check if Pokemon can evolve based on level."""
        if self.evolution_id and self.evolution_level:
            if self.level >= self.evolution_level:
                self.can_evolve = True

    def increase_happiness(self, amount: int = 1) -> None:
        """Increase happiness, capped at 255."""
        self.happiness = min(255, self.happiness + amount)

    def decrease_happiness(self, amount: int = 1) -> None:
        """Decrease happiness, minimum 0."""
        self.happiness = max(0, self.happiness - amount)

    def ensure_nature(self) -> None:
        """Assign a random nature if one is not yet set.

        Only assigns if the nature is the default empty/unset value.
        'hardy' is a valid nature and is NOT overwritten.
        Called at catch time so existing Pokemon retain their nature.
        """
        if not self.nature:
            self.nature = random_nature().value

    def ensure_moves(self) -> None:
        """Generate a default moveset if none is assigned."""
        if not self.moves:
            self.moves = generate_default_moveset(self.type1, self.type2, self.level)

    def to_battle_pokemon(self) -> "BattlePokemon":
        """Create a BattlePokemon snapshot for use in PvP."""
        from pokedo.core.battle import create_battle_pokemon

        self.ensure_nature()
        self.ensure_moves()
        return create_battle_pokemon(
            pokemon_id=self.id or 0,
            pokedex_id=self.pokedex_id,
            name=self.name,
            nickname=self.nickname,
            type1=self.type1,
            type2=self.type2,
            level=self.level,
            base_stats=self.base_stats,
            ivs=self.ivs,
            evs=self.evs,
            nature=self.nature,
            moves=[m.model_copy(deep=True) for m in self.moves],  # Deep copy so battle doesn't mutate permanent moves
        )


class PokedexEntry(BaseModel):
    """A Pokedex entry for tracking caught Pokemon."""

    pokedex_id: int
    name: str
    type1: str
    type2: str | None = None

    # Base stats for the species
    base_stats: dict[str, int] = Field(
        default_factory=lambda: {"hp": 50, "atk": 50, "def": 50, "spa": 50, "spd": 50, "spe": 50}
    )

    # Catch tracking
    is_seen: bool = False
    is_caught: bool = False
    times_caught: int = 0
    first_caught_at: datetime | None = None

    # Shiny tracking
    shiny_caught: bool = False

    # Sprite URL for display
    sprite_url: str | None = None

    # Rarity classification
    rarity: PokemonRarity = PokemonRarity.COMMON

    # Evolution info
    evolves_from: int | None = None
    evolves_to: list[int] = Field(default_factory=list)


class PokemonTeam(BaseModel):
    """The player's active Pokemon team."""

    pokemon: list[Pokemon] = Field(default_factory=list, max_length=6)

    @property
    def size(self) -> int:
        """Current team size."""
        return len(self.pokemon)

    @property
    def is_full(self) -> bool:
        """Check if team is full."""
        return len(self.pokemon) >= 6

    def add(self, pokemon: Pokemon) -> bool:
        """Add Pokemon to team if not full."""
        if self.is_full:
            return False
        pokemon.is_active = True
        self.pokemon.append(pokemon)
        return True

    def remove(self, pokemon_id: int) -> Pokemon | None:
        """Remove Pokemon from team by ID."""
        for i, p in enumerate(self.pokemon):
            if p.id == pokemon_id:
                removed = self.pokemon.pop(i)
                removed.is_active = False
                return removed
        return None
