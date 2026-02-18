"""Move model, type effectiveness chart, and damage calculation."""

import random
from enum import Enum

from pydantic import BaseModel, Field


class PokemonType(str, Enum):
    """All 18 Pokemon types."""

    NORMAL = "normal"
    FIRE = "fire"
    WATER = "water"
    ELECTRIC = "electric"
    GRASS = "grass"
    ICE = "ice"
    FIGHTING = "fighting"
    POISON = "poison"
    GROUND = "ground"
    FLYING = "flying"
    PSYCHIC = "psychic"
    BUG = "bug"
    ROCK = "rock"
    GHOST = "ghost"
    DRAGON = "dragon"
    DARK = "dark"
    STEEL = "steel"
    FAIRY = "fairy"


class DamageClass(str, Enum):
    """Move damage classification."""

    PHYSICAL = "physical"
    SPECIAL = "special"
    STATUS = "status"


class StatusEffect(str, Enum):
    """Battle status conditions."""

    NONE = "none"
    BURN = "burn"
    FREEZE = "freeze"
    PARALYSIS = "paralysis"
    POISON = "poison"
    BADLY_POISONED = "badly_poisoned"
    SLEEP = "sleep"


class PokemonNature(str, Enum):
    """All 25 Pokemon natures. 5 are neutral (no stat modification)."""

    HARDY = "hardy"
    LONELY = "lonely"
    BRAVE = "brave"
    ADAMANT = "adamant"
    NAUGHTY = "naughty"
    BOLD = "bold"
    DOCILE = "docile"
    RELAXED = "relaxed"
    IMPISH = "impish"
    LAX = "lax"
    TIMID = "timid"
    HASTY = "hasty"
    SERIOUS = "serious"
    JOLLY = "jolly"
    NAIVE = "naive"
    MODEST = "modest"
    MILD = "mild"
    QUIET = "quiet"
    BASHFUL = "bashful"
    RASH = "rash"
    CALM = "calm"
    GENTLE = "gentle"
    SASSY = "sassy"
    CAREFUL = "careful"
    QUIRKY = "quirky"


# Nature stat modifiers: nature_name -> (boosted_stat, lowered_stat)
# Neutral natures have None for both
NATURE_MODIFIERS: dict[str, tuple[str | None, str | None]] = {
    "hardy": (None, None),
    "lonely": ("atk", "def"),
    "brave": ("atk", "spe"),
    "adamant": ("atk", "spa"),
    "naughty": ("atk", "spd"),
    "bold": ("def", "atk"),
    "docile": (None, None),
    "relaxed": ("def", "spe"),
    "impish": ("def", "spa"),
    "lax": ("def", "spd"),
    "timid": ("spe", "atk"),
    "hasty": ("spe", "def"),
    "serious": (None, None),
    "jolly": ("spe", "spa"),
    "naive": ("spe", "spd"),
    "modest": ("spa", "atk"),
    "mild": ("spa", "def"),
    "quiet": ("spa", "spe"),
    "bashful": (None, None),
    "rash": ("spa", "spd"),
    "calm": ("spd", "atk"),
    "gentle": ("spd", "def"),
    "sassy": ("spd", "spe"),
    "careful": ("spd", "spa"),
    "quirky": (None, None),
}


def get_nature_multiplier(nature: str, stat: str) -> float:
    """Return the nature multiplier for a given stat (1.0, 1.1, or 0.9)."""
    mods = NATURE_MODIFIERS.get(nature, (None, None))
    boosted, lowered = mods
    if stat == boosted:
        return 1.1
    if stat == lowered:
        return 0.9
    return 1.0


def random_nature() -> PokemonNature:
    """Pick a random nature."""
    return random.choice(list(PokemonNature))


# ---------------------------------------------------------------------------
# Type effectiveness chart
# ---------------------------------------------------------------------------
# Encoded as: TYPE_CHART[attacking_type][defending_type] = multiplier
# 2.0 = super effective, 0.5 = not very effective, 0.0 = immune, 1.0 = normal
# ---------------------------------------------------------------------------

_ALL_TYPES = [t.value for t in PokemonType]

# Start with all 1.0, then override
TYPE_CHART: dict[str, dict[str, float]] = {a: {d: 1.0 for d in _ALL_TYPES} for a in _ALL_TYPES}

# fmt: off
_SUPER_EFFECTIVE: list[tuple[str, str]] = [
    # Normal - none super effective
    # Fire
    ("fire", "grass"), ("fire", "ice"), ("fire", "bug"), ("fire", "steel"),
    # Water
    ("water", "fire"), ("water", "ground"), ("water", "rock"),
    # Electric
    ("electric", "water"), ("electric", "flying"),
    # Grass
    ("grass", "water"), ("grass", "ground"), ("grass", "rock"),
    # Ice
    ("ice", "grass"), ("ice", "ground"), ("ice", "flying"), ("ice", "dragon"),
    # Fighting
    ("fighting", "normal"), ("fighting", "ice"), ("fighting", "rock"),
    ("fighting", "dark"), ("fighting", "steel"),
    # Poison
    ("poison", "grass"), ("poison", "fairy"),
    # Ground
    ("ground", "fire"), ("ground", "electric"), ("ground", "poison"),
    ("ground", "rock"), ("ground", "steel"),
    # Flying
    ("flying", "grass"), ("flying", "fighting"), ("flying", "bug"),
    # Psychic
    ("psychic", "fighting"), ("psychic", "poison"),
    # Bug
    ("bug", "grass"), ("bug", "psychic"), ("bug", "dark"),
    # Rock
    ("rock", "fire"), ("rock", "ice"), ("rock", "flying"), ("rock", "bug"),
    # Ghost
    ("ghost", "psychic"), ("ghost", "ghost"),
    # Dragon
    ("dragon", "dragon"),
    # Dark
    ("dark", "psychic"), ("dark", "ghost"),
    # Steel
    ("steel", "ice"), ("steel", "rock"), ("steel", "fairy"),
    # Fairy
    ("fairy", "fighting"), ("fairy", "dragon"), ("fairy", "dark"),
]

_NOT_VERY_EFFECTIVE: list[tuple[str, str]] = [
    # Normal
    ("normal", "rock"), ("normal", "steel"),
    # Fire
    ("fire", "fire"), ("fire", "water"), ("fire", "rock"), ("fire", "dragon"),
    # Water
    ("water", "water"), ("water", "grass"), ("water", "dragon"),
    # Electric
    ("electric", "electric"), ("electric", "grass"), ("electric", "dragon"),
    # Grass
    ("grass", "fire"), ("grass", "grass"), ("grass", "poison"),
    ("grass", "flying"), ("grass", "bug"), ("grass", "dragon"), ("grass", "steel"),
    # Ice
    ("ice", "fire"), ("ice", "water"), ("ice", "ice"), ("ice", "steel"),
    # Fighting
    ("fighting", "poison"), ("fighting", "flying"), ("fighting", "psychic"),
    ("fighting", "bug"), ("fighting", "fairy"),
    # Poison
    ("poison", "poison"), ("poison", "ground"), ("poison", "rock"), ("poison", "ghost"),
    # Ground
    ("ground", "grass"), ("ground", "bug"),
    # Flying
    ("flying", "electric"), ("flying", "rock"), ("flying", "steel"),
    # Psychic
    ("psychic", "psychic"), ("psychic", "steel"),
    # Bug
    ("bug", "fire"), ("bug", "fighting"), ("bug", "poison"),
    ("bug", "flying"), ("bug", "ghost"), ("bug", "steel"), ("bug", "fairy"),
    # Rock
    ("rock", "fighting"), ("rock", "ground"), ("rock", "steel"),
    # Ghost
    ("ghost", "dark"),
    # Dragon
    ("dragon", "steel"),
    # Dark
    ("dark", "fighting"), ("dark", "dark"), ("dark", "fairy"),
    # Steel
    ("steel", "fire"), ("steel", "water"), ("steel", "electric"), ("steel", "steel"),
    # Fairy
    ("fairy", "fire"), ("fairy", "poison"), ("fairy", "steel"),
]

_IMMUNE: list[tuple[str, str]] = [
    ("normal", "ghost"),
    ("electric", "ground"),
    ("fighting", "ghost"),
    ("poison", "steel"),
    ("ground", "flying"),
    ("psychic", "dark"),
    ("ghost", "normal"),
    ("dragon", "fairy"),
]
# fmt: on

for atk, dfn in _SUPER_EFFECTIVE:
    TYPE_CHART[atk][dfn] = 2.0
for atk, dfn in _NOT_VERY_EFFECTIVE:
    TYPE_CHART[atk][dfn] = 0.5
for atk, dfn in _IMMUNE:
    TYPE_CHART[atk][dfn] = 0.0


def get_type_effectiveness(move_type: str, defender_type1: str, defender_type2: str | None) -> float:
    """Calculate combined type effectiveness multiplier.

    Takes into account both defender types. Results can be:
    0x, 0.25x, 0.5x, 1x, 2x, or 4x.
    """
    move_t = move_type.lower()
    mult = TYPE_CHART.get(move_t, {}).get(defender_type1.lower(), 1.0)
    if defender_type2:
        mult *= TYPE_CHART.get(move_t, {}).get(defender_type2.lower(), 1.0)
    return mult


# ---------------------------------------------------------------------------
# Move model
# ---------------------------------------------------------------------------

class Move(BaseModel):
    """A Pokemon move."""

    id: int | None = None  # PokeAPI move ID
    name: str
    display_name: str = ""  # Human-friendly (computed from name if blank)
    type: str  # Pokemon type (e.g. "fire")
    damage_class: DamageClass = DamageClass.PHYSICAL
    power: int | None = None  # None for status moves
    accuracy: int | None = None  # None means always hits
    pp: int = 20  # Power points (uses per battle)
    current_pp: int | None = None  # Tracked during battle; reset between battles
    priority: int = 0  # Move priority bracket (-7 to +5)

    # Effect metadata
    effect_text: str = ""
    effect_chance: int | None = None  # % chance of secondary effect
    status_effect: StatusEffect = StatusEffect.NONE
    stat_changes: dict[str, int] = Field(default_factory=dict)  # e.g. {"atk": -1}
    drain_percent: int = 0  # Positive = drain, negative = recoil
    healing_percent: int = 0  # % of max HP healed
    flinch_chance: int = 0  # % chance to flinch

    def model_post_init(self, __context) -> None:
        """Set display_name from name if not provided."""
        if not self.display_name:
            self.display_name = self.name.replace("-", " ").title()
        if self.current_pp is None:
            self.current_pp = self.pp


# ---------------------------------------------------------------------------
# Damage calculation (Gen V+ formula)
# ---------------------------------------------------------------------------

def calculate_damage(
    attacker_level: int,
    move: Move,
    attack_stat: int,
    defense_stat: int,
    attacker_types: list[str],
    defender_type1: str,
    defender_type2: str | None = None,
    critical: bool = False,
    weather_modifier: float = 1.0,
) -> tuple[int, float, bool]:
    """Calculate damage using the official Gen V+ Pokemon damage formula.

    Returns (damage, effectiveness_multiplier, was_critical).

    Formula:
        base = (((2 * level / 5 + 2) * power * A / D) / 50) + 2
        damage = base * modifier

    Modifier = STAB * type_effectiveness * critical * random(0.85..1.0) * weather
    """
    if move.power is None or move.power == 0:
        return 0, 1.0, False

    # Determine if critical hit (1/16 base chance unless forced)
    is_crit = critical or (random.randint(1, 16) == 1)

    # Base damage
    base = (((2 * attacker_level / 5 + 2) * move.power * attack_stat / defense_stat) / 50) + 2

    # STAB (Same-Type Attack Bonus)
    stab = 1.5 if move.type.lower() in [t.lower() for t in attacker_types] else 1.0

    # Type effectiveness
    effectiveness = get_type_effectiveness(move.type, defender_type1, defender_type2)

    # Critical hit multiplier
    crit_mult = 1.5 if is_crit else 1.0

    # Random factor
    rand_factor = random.uniform(0.85, 1.0)

    # Combine all modifiers
    modifier = stab * effectiveness * crit_mult * rand_factor * weather_modifier

    damage = max(1, int(base * modifier)) if effectiveness > 0 else 0

    return damage, effectiveness, is_crit


# ---------------------------------------------------------------------------
# Default moveset generation
# ---------------------------------------------------------------------------
# When we do not have PokeAPI move data for a Pokemon (or as a fallback),
# we generate a sensible default moveset based on types and level.
# ---------------------------------------------------------------------------

# A curated pool of default moves per type.  Each tuple is:
# (name, type, damage_class, power, accuracy, pp)
DEFAULT_MOVES_BY_TYPE: dict[str, list[tuple[str, str, str, int | None, int | None, int]]] = {
    "normal": [
        ("tackle", "normal", "physical", 40, 100, 35),
        ("quick-attack", "normal", "physical", 40, 100, 30),
        ("slam", "normal", "physical", 80, 75, 20),
        ("hyper-beam", "normal", "special", 150, 90, 5),
        ("body-slam", "normal", "physical", 85, 100, 15),
    ],
    "fire": [
        ("ember", "fire", "special", 40, 100, 25),
        ("fire-spin", "fire", "special", 35, 85, 15),
        ("flamethrower", "fire", "special", 90, 100, 15),
        ("fire-blast", "fire", "special", 110, 85, 5),
        ("fire-punch", "fire", "physical", 75, 100, 15),
    ],
    "water": [
        ("water-gun", "water", "special", 40, 100, 25),
        ("bubble-beam", "water", "special", 65, 100, 20),
        ("surf", "water", "special", 90, 100, 15),
        ("hydro-pump", "water", "special", 110, 80, 5),
        ("waterfall", "water", "physical", 80, 100, 15),
    ],
    "electric": [
        ("thunder-shock", "electric", "special", 40, 100, 30),
        ("spark", "electric", "physical", 65, 100, 20),
        ("thunderbolt", "electric", "special", 90, 100, 15),
        ("thunder", "electric", "special", 110, 70, 10),
        ("volt-tackle", "electric", "physical", 120, 100, 15),
    ],
    "grass": [
        ("vine-whip", "grass", "physical", 45, 100, 25),
        ("razor-leaf", "grass", "physical", 55, 95, 25),
        ("solar-beam", "grass", "special", 120, 100, 10),
        ("energy-ball", "grass", "special", 90, 100, 10),
        ("seed-bomb", "grass", "physical", 80, 100, 15),
    ],
    "ice": [
        ("powder-snow", "ice", "special", 40, 100, 25),
        ("ice-shard", "ice", "physical", 40, 100, 30),
        ("ice-beam", "ice", "special", 90, 100, 10),
        ("blizzard", "ice", "special", 110, 70, 5),
        ("ice-punch", "ice", "physical", 75, 100, 15),
    ],
    "fighting": [
        ("karate-chop", "fighting", "physical", 50, 100, 25),
        ("low-kick", "fighting", "physical", 60, 100, 20),
        ("brick-break", "fighting", "physical", 75, 100, 15),
        ("close-combat", "fighting", "physical", 120, 100, 5),
        ("aura-sphere", "fighting", "special", 80, None, 20),
    ],
    "poison": [
        ("poison-sting", "poison", "physical", 15, 100, 35),
        ("sludge", "poison", "special", 65, 100, 20),
        ("sludge-bomb", "poison", "special", 90, 100, 10),
        ("poison-jab", "poison", "physical", 80, 100, 20),
        ("gunk-shot", "poison", "physical", 120, 80, 5),
    ],
    "ground": [
        ("mud-slap", "ground", "special", 20, 100, 10),
        ("mud-shot", "ground", "special", 55, 95, 15),
        ("dig", "ground", "physical", 80, 100, 10),
        ("earthquake", "ground", "physical", 100, 100, 10),
        ("earth-power", "ground", "special", 90, 100, 10),
    ],
    "flying": [
        ("gust", "flying", "special", 40, 100, 35),
        ("wing-attack", "flying", "physical", 60, 100, 35),
        ("aerial-ace", "flying", "physical", 60, None, 20),
        ("air-slash", "flying", "special", 75, 95, 15),
        ("brave-bird", "flying", "physical", 120, 100, 15),
    ],
    "psychic": [
        ("confusion", "psychic", "special", 50, 100, 25),
        ("psybeam", "psychic", "special", 65, 100, 20),
        ("psychic", "psychic", "special", 90, 100, 10),
        ("psyshock", "psychic", "special", 80, 100, 10),
        ("zen-headbutt", "psychic", "physical", 80, 90, 15),
    ],
    "bug": [
        ("bug-bite", "bug", "physical", 60, 100, 20),
        ("fury-cutter", "bug", "physical", 40, 95, 20),
        ("x-scissor", "bug", "physical", 80, 100, 15),
        ("bug-buzz", "bug", "special", 90, 100, 10),
        ("signal-beam", "bug", "special", 75, 100, 15),
    ],
    "rock": [
        ("rock-throw", "rock", "physical", 50, 90, 15),
        ("rock-slide", "rock", "physical", 75, 90, 10),
        ("stone-edge", "rock", "physical", 100, 80, 5),
        ("power-gem", "rock", "special", 80, 100, 20),
        ("rock-blast", "rock", "physical", 25, 90, 10),
    ],
    "ghost": [
        ("lick", "ghost", "physical", 30, 100, 30),
        ("shadow-ball", "ghost", "special", 80, 100, 15),
        ("shadow-claw", "ghost", "physical", 70, 100, 15),
        ("phantom-force", "ghost", "physical", 90, 100, 10),
        ("hex", "ghost", "special", 65, 100, 10),
    ],
    "dragon": [
        ("dragon-rage", "dragon", "special", 40, 100, 10),
        ("dragon-breath", "dragon", "special", 60, 100, 20),
        ("dragon-claw", "dragon", "physical", 80, 100, 15),
        ("dragon-pulse", "dragon", "special", 85, 100, 10),
        ("outrage", "dragon", "physical", 120, 100, 10),
    ],
    "dark": [
        ("bite", "dark", "physical", 60, 100, 25),
        ("feint-attack", "dark", "physical", 60, None, 20),
        ("crunch", "dark", "physical", 80, 100, 15),
        ("dark-pulse", "dark", "special", 80, 100, 15),
        ("night-slash", "dark", "physical", 70, 100, 15),
    ],
    "steel": [
        ("metal-claw", "steel", "physical", 50, 95, 35),
        ("iron-tail", "steel", "physical", 100, 75, 15),
        ("flash-cannon", "steel", "special", 80, 100, 10),
        ("iron-head", "steel", "physical", 80, 100, 15),
        ("meteor-mash", "steel", "physical", 90, 90, 10),
    ],
    "fairy": [
        ("fairy-wind", "fairy", "special", 40, 100, 30),
        ("draining-kiss", "fairy", "special", 50, 100, 10),
        ("dazzling-gleam", "fairy", "special", 80, 100, 10),
        ("moonblast", "fairy", "special", 95, 100, 15),
        ("play-rough", "fairy", "physical", 90, 90, 10),
    ],
}

# Status moves available to all Pokemon at higher levels
UNIVERSAL_STATUS_MOVES: list[tuple[str, str, str, int | None, int | None, int]] = [
    ("protect", "normal", "status", None, None, 10),
    ("rest", "psychic", "status", None, None, 10),
    ("substitute", "normal", "status", None, None, 10),
]

# Moves that have non-zero priority. Looked up by name in _move_from_tuple.
_MOVE_PRIORITY: dict[str, int] = {
    "protect": 4,
    "quick-attack": 1,
    "ice-shard": 1,
}


def _move_from_tuple(data: tuple[str, str, str, int | None, int | None, int]) -> Move:
    """Create a Move from a default-pool tuple."""
    name, mtype, dclass, power, accuracy, pp = data
    return Move(
        name=name,
        type=mtype,
        damage_class=DamageClass(dclass),
        power=power,
        accuracy=accuracy,
        pp=pp,
        priority=_MOVE_PRIORITY.get(name, 0),
    )


def generate_default_moveset(
    type1: str,
    type2: str | None,
    level: int,
) -> list[Move]:
    """Generate a sensible moveset (up to 4 moves) based on types and level.

    Low-level Pokemon get weaker moves; high-level Pokemon get stronger ones.
    Prioritises STAB moves from the Pokemon's own types.
    """
    pool: list[Move] = []

    # Gather type-matched moves
    t1 = type1.lower()
    t2 = type2.lower() if type2 else None

    for mt in DEFAULT_MOVES_BY_TYPE.get(t1, []):
        pool.append(_move_from_tuple(mt))
    if t2 and t2 != t1:
        for mt in DEFAULT_MOVES_BY_TYPE.get(t2, []):
            pool.append(_move_from_tuple(mt))

    # All Pokemon have access to a basic Normal move (coverage)
    if t1 != "normal" and (t2 is None or t2 != "normal"):
        for mt in DEFAULT_MOVES_BY_TYPE["normal"][:2]:
            pool.append(_move_from_tuple(mt))

    # Filter by level -- stronger moves unlock at higher levels
    def power_cap(lv: int) -> int:
        if lv < 10:
            return 50
        if lv < 20:
            return 65
        if lv < 35:
            return 85
        if lv < 50:
            return 100
        return 999  # No cap

    cap = power_cap(level)
    eligible = [m for m in pool if m.power is None or m.power <= cap]

    if not eligible:
        eligible = pool[:2] if pool else [_move_from_tuple(("struggle", "normal", "physical", 50, 100, 999))]

    # Sort by power descending (status moves sink to bottom) then pick top 4
    eligible.sort(key=lambda m: m.power or 0, reverse=True)

    # Take at most 4, preferring type diversity
    selected: list[Move] = []
    types_used: set[str] = set()
    for m in eligible:
        if len(selected) >= 4:
            break
        # Prefer type diversity (but accept duplicates if needed)
        if m.type not in types_used or len(selected) < 2:
            selected.append(m)
            types_used.add(m.type)

    # Fill remaining slots from whatever is left
    for m in eligible:
        if len(selected) >= 4:
            break
        if m not in selected:
            selected.append(m)

    return selected[:4]
