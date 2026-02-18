# PokeDo API Reference

## Table of Contents

- [Core Models](#core-models)
- [Database Operations](#database-operations)
- [PokeAPI Client](#pokeapi-client)
- [Reward System](#reward-system)
- [Configuration](#configuration)
- [UI Components](#ui-components)

---

## Core Models

### Task (`pokedo/core/task.py`)

#### Enums

```python
class TaskCategory(str, Enum):
    """Categories for organizing tasks."""
    WORK = "work"
    EXERCISE = "exercise"
    LEARNING = "learning"
    PERSONAL = "personal"
    HEALTH = "health"
    CREATIVE = "creative"

class TaskDifficulty(str, Enum):
    """Difficulty levels affecting XP rewards."""
    EASY = "easy"      # 10 XP
    MEDIUM = "medium"  # 25 XP
    HARD = "hard"      # 50 XP
    EPIC = "epic"      # 100 XP

class TaskPriority(str, Enum):
    """Task priority levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"

class RecurrenceType(str, Enum):
    """Recurrence patterns for tasks."""
    NONE = "none"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
```

#### Task Model

```python
class Task(BaseModel):
    """Represents a task in the system."""

    id: int | None = None
    title: str
    description: str | None = None
    category: TaskCategory = TaskCategory.PERSONAL
    difficulty: TaskDifficulty = TaskDifficulty.MEDIUM
    priority: TaskPriority = TaskPriority.MEDIUM
    created_at: datetime = Field(default_factory=datetime.now)
    due_date: date | None = None
    completed_at: datetime | None = None
    is_completed: bool = False
    is_archived: bool = False
    recurrence: RecurrenceType = RecurrenceType.NONE
    parent_task_id: int | None = None
    tags: list[str] = Field(default_factory=list)

    @property
    def is_overdue(self) -> bool:
        """Check if task is past due date."""

    @property
    def xp_reward(self) -> int:
        """Get XP reward based on difficulty."""

    def get_pokemon_rarity_weights(self) -> dict[str, float]:
        """Get rarity weights for Pokemon encounters."""

    def get_type_affinity(self) -> list[str]:
        """Get boosted Pokemon types for this category."""

    @property
    def stat_affinity(self) -> str:
        """Get the stat affinity for this task category."""

    @property
    def ev_yield(self) -> int:
        """Get EV yield based on task difficulty."""

---

### Pokemon (`pokedo/core/pokemon.py`)

#### Enums

```python
class PokemonRarity(str, Enum):
    """Rarity tiers for Pokemon."""
    COMMON = "common"        # 90% catch rate
    UNCOMMON = "uncommon"    # 75% catch rate
    RARE = "rare"            # 50% catch rate
    EPIC = "epic"            # 30% catch rate
    LEGENDARY = "legendary"  # 15% catch rate
    MYTHICAL = "mythical"    # 5% catch rate
```

#### Pokemon Model

```python
class Pokemon(BaseModel):
    """Represents a caught Pokemon."""

    id: int | None = None
    pokedex_id: int
    name: str
    nickname: str | None = None
    type1: str
    type2: str | None = None
    level: int = 1
    xp: int = 0
    happiness: int = 50
    evs: dict[str, int] = Field(default_factory=dict)
    ivs: dict[str, int] = Field(default_factory=dict)
    caught_at: datetime = Field(default_factory=datetime.now)
    is_shiny: bool = False
    catch_location: str | None = None
    is_active: bool = False
    is_favorite: bool = False
    can_evolve: bool = False
    evolution_id: int | None = None
    evolution_level: int | None = None
    sprite_url: str | None = None
    sprite_path: str | None = None

    @property
    def display_name(self) -> str:
        """Get display name (nickname or species name)."""

    @property
    def remaining_evs(self) -> int:
        """Calculate remaining EV points (max 510 total)."""

    def add_evs(self, stat: str, amount: int) -> int:
        """
        Add EVs to a stat, respecting caps (252 per stat, 510 total).
        Returns actual amount added.
        """

    def assign_ivs(self) -> None:
        """Randomize IVs (0-31) for all stats."""

    @property
    def xp_to_next_level(self) -> int:
        """Get XP needed for next level."""

    def add_xp(self, amount: int) -> bool:
        """Add XP and return True if leveled up."""

    def can_evolve_now(self) -> bool:
        """Check if evolution requirements are met."""
```

#### PokedexEntry Model

```python
class PokedexEntry(BaseModel):
    """Represents a Pokedex entry."""

    pokedex_id: int
    name: str
    type1: str
    type2: str | None = None
    is_seen: bool = False
    is_caught: bool = False
    times_caught: int = 0
    first_caught_at: datetime | None = None
    shiny_caught: bool = False
    sprite_url: str | None = None
    rarity: PokemonRarity = PokemonRarity.COMMON
    evolves_from: int | None = None
    evolves_to: list[int] = Field(default_factory=list)
```

#### PokemonTeam Model

```python
class PokemonTeam(BaseModel):
    """Manages the active team of 6 Pokemon."""

    members: list[Pokemon] = Field(default_factory=list, max_length=6)

    def add(self, pokemon: Pokemon) -> bool:
        """Add Pokemon to team. Returns False if full."""

    def remove(self, pokemon_id: int) -> bool:
        """Remove Pokemon from team."""

    def is_full(self) -> bool:
        """Check if team has 6 members."""

    def get_member(self, pokemon_id: int) -> Pokemon | None:
        """Get team member by ID."""
```

---

### Move (`pokedo/core/moves.py`)

```python
class Move(BaseModel):
    """Represents a Pokemon battle move."""

    name: str
    type: str                     # fire, water, electric, ...
    power: int                    # 0 for status moves
    accuracy: int                 # 1-100
    pp: int                       # Power Points (uses)
    category: str                 # "physical", "special", or "status"
    priority: int = 0             # Higher goes first (+4 Protect, +1 Quick Attack)
    drain_percent: int = 0        # Positive = heal, negative = recoil
    recoil_percent: int = 0       # Percentage of damage dealt taken as recoil
    status_effect: str | None = None       # burn, poison, paralysis, sleep, freeze, badly_poisoned
    secondary_effect_chance: int = 0       # % chance of secondary status application
    secondary_status: str | None = None    # Status applied as secondary effect
    heals_user: bool = False               # e.g. Recover, Rest
    is_protect: bool = False               # Protect-like moves
```

**Key functions:**

```python
TYPE_CHART: dict[str, dict[str, float]]
    # 18x18 effectiveness matrix (Normal through Fairy)

NATURE_MODIFIERS: dict[str, dict[str, float]]
    # 25 natures with +10%/-10% stat modifications

def calculate_damage(
    attacker: BattlePokemon,
    defender: BattlePokemon,
    move: Move,
    *,
    critical: bool = False,
    random_factor: float = 1.0,
    weather_modifier: float = 1.0,
) -> int:
    """Gen V+ damage formula with STAB, type chart, crits, burn halving."""

def generate_default_moveset(pokemon: Pokemon | BattlePokemon, level: int) -> list[Move]:
    """Generate a level-appropriate moveset (up to 4 moves) from the type pool."""
```

---

### Battle (`pokedo/core/battle.py`)

```python
class BattleFormat(str, Enum):
    SINGLES_1V1 = "singles_1v1"   # 1 Pokemon each
    SINGLES_3V3 = "singles_3v3"   # 3 Pokemon, one active
    SINGLES_6V6 = "singles_6v6"   # 6 Pokemon, one active

class BattleStatus(str, Enum):
    PENDING = "pending"
    TEAM_SUBMISSION = "team_submission"
    ACTIVE = "active"
    FINISHED = "finished"

class BattleActionType(str, Enum):
    MOVE = "move"
    SWITCH = "switch"
    FORFEIT = "forfeit"

class BattlePokemon(BaseModel):
    """Snapshot of a Pokemon for battle (stats, moves, HP, status)."""
    name: str
    nickname: str | None
    types: list[str]
    level: int
    max_hp: int
    current_hp: int
    stats: dict[str, int]    # atk, def, spa, spd, spe
    moves: list[Move]
    status: str | None       # burn, poison, paralysis, sleep, freeze, badly_poisoned
    status_turns: int = 0
    is_protected: bool = False

class BattleTeam(BaseModel):
    """A player's battle team."""
    pokemon: list[BattlePokemon]
    active_index: int = 0

class BattleState(BaseModel):
    """Full battle state machine."""
    format: BattleFormat
    player1_id: str
    player2_id: str
    team1: BattleTeam | None
    team2: BattleTeam | None
    status: BattleStatus
    turn: int
    winner_id: str | None
    pending_actions: dict[str, dict]
    turn_history: list[list[dict]]
    is_draw: bool = False

class BattleEngine:
    @staticmethod
    def resolve_turn(state: BattleState) -> list[TurnEvent]:
        """Resolve one turn: forfeits -> switches -> attacks (priority) -> end-of-turn."""

def calculate_elo_change(winner_elo: int, loser_elo: int, k: int = 32) -> tuple[int, int]:
    """Compute ELO deltas for winner and loser."""

def compute_rank(elo: int) -> str:
    """Map ELO rating to rank name (Youngster through Pokemon Master)."""
```

---

### Trainer (`pokedo/core/trainer.py`)

#### TrainerBadge Model

```python
class TrainerBadge(BaseModel):
    """Represents an achievement badge."""

    id: str
    name: str
    description: str
    icon: str
    earned_at: datetime | None = None
    requirement: str
```

**Available Badges:**
| ID | Name | Requirement |
|----|------|-------------|
| `starter` | Pokemon Trainer | Initialize PokeDo |
| `first_catch` | First Catch | Catch first Pokemon |
| `collector_10` | Collector | Catch 10 Pokemon |
| `collector_50` | Super Collector | Catch 50 Pokemon |
| `collector_100` | Master Collector | Catch 100 Pokemon |
| `pokedex_25` | Pokedex Starter | Register 25 species |
| `pokedex_100` | Pokedex Pro | Register 100 species |
| `pokedex_complete` | Pokedex Master | Complete Pokedex |
| `shiny_hunter` | Shiny Hunter | Catch a shiny Pokemon |
| `streak_7` | Dedicated | 7-day streak |
| `streak_30` | Committed | 30-day streak |
| `streak_100` | Legendary Dedication | 100-day streak |
| `legendary_catch` | Legend Tamer | Catch a legendary |
| `mythical_catch` | Myth Seeker | Catch a mythical |

#### Streak Model

```python
class Streak(BaseModel):
    """Tracks daily streaks."""

    count: int = 0
    best: int = 0
    last_date: date | None = None

    def check_and_update(self, current_date: date) -> tuple[bool, int]:
        """
        Update streak for current date.
        Returns (streak_maintained, days_since_last).
        """

    def reset(self) -> None:
        """Reset streak to zero."""
```

#### Trainer Model

```python
class Trainer(BaseModel):
    """Represents the player's profile."""

    id: int | None = None
    name: str = "Trainer"
    trainer_class: TrainerClass = TrainerClass.ACE_TRAINER
    created_at: datetime = Field(default_factory=datetime.now)
    total_xp: int = 0
    tasks_completed: int = 0
    tasks_completed_today: int = 0
    pokemon_caught: int = 0
    pokemon_released: int = 0
    evolutions_triggered: int = 0
    pokedex_seen: int = 0
    pokedex_caught: int = 0
    daily_streak: Streak = Field(default_factory=lambda: Streak(streak_type="daily"))
    wellbeing_streak: Streak = Field(default_factory=lambda: Streak(streak_type="wellbeing"))

    # PvP / multiplayer stats
    battle_wins: int = 0
    battle_losses: int = 0
    battle_draws: int = 0
    elo_rating: int = 1000      # Starting ELO
    pvp_rank: str = "Unranked"  # Derived from ELO via compute_rank()

    badges: list[TrainerBadge] = Field(default_factory=list)
    inventory: dict[str, int] = Field(default_factory=dict)
    favorite_pokemon_id: int | None = None
    last_active_date: date | None = None

    @property
    def level(self) -> int:
        """Calculate trainer level from XP."""

    @property
    def xp_progress(self) -> tuple[int, int]:
        """Get XP progress to next level (current, needed)."""

    def add_xp(self, amount: int) -> int:
        """Add XP and return new level if leveled up, else 0."""

    def add_item(self, item: str, count: int = 1) -> None:
        """Add item to inventory."""

    def use_item(self, item: str) -> bool:
        """Use item from inventory. Returns False if not available."""

    # --- PvP helpers ---

    @property
    def battles_fought(self) -> int:
        """Total battles completed (wins + losses + draws)."""

    @property
    def win_rate(self) -> float:
        """Win percentage (0-100)."""

    def record_battle(self, won: bool, elo_delta: int) -> None:
        """Record a battle result, adjust ELO, and recompute rank."""
```

---

### Wellbeing (`pokedo/core/wellbeing.py`)

#### Entry Models

```python
class MoodEntry(BaseModel):
    """Daily mood log entry."""
    id: int | None = None
    date: date = Field(default_factory=date.today)
    timestamp: datetime = Field(default_factory=datetime.now)
    mood: int = Field(..., ge=1, le=5)  # 1-5 scale
    note: str | None = None
    energy_level: int | None = Field(None, ge=1, le=5)

class ExerciseEntry(BaseModel):
    """Exercise log entry."""
    id: int | None = None
    date: date = Field(default_factory=date.today)
    timestamp: datetime = Field(default_factory=datetime.now)
    exercise_type: str  # cardio, strength, yoga, etc.
    duration_minutes: int = Field(..., gt=0)
    intensity: int | None = Field(None, ge=1, le=5)
    note: str | None = None

class SleepEntry(BaseModel):
    """Sleep log entry."""
    id: int | None = None
    date: date = Field(default_factory=date.today)
    hours: float = Field(..., gt=0, le=24)
    quality: int | None = Field(None, ge=1, le=5)
    note: str | None = None

class HydrationEntry(BaseModel):
    """Daily hydration tracking."""
    id: int | None = None
    date: date = Field(default_factory=date.today)
    glasses: int = Field(default=1, ge=1)
    note: str | None = None

class MeditationEntry(BaseModel):
    """Meditation log entry."""
    id: int | None = None
    date: date = Field(default_factory=date.today)
    timestamp: datetime = Field(default_factory=datetime.now)
    minutes: int = Field(..., gt=0)
    note: str | None = None

class JournalEntry(BaseModel):
    """Gratitude journal entry."""
    id: int | None = None
    date: date = Field(default_factory=date.today)
    timestamp: datetime = Field(default_factory=datetime.now)
    content: str
    gratitude_items: list[str] = Field(default_factory=list)
```

#### DailyWellbeing Model

```python
class DailyWellbeing(BaseModel):
    """Aggregated daily wellbeing data."""

    date: date
    mood_entries: list[MoodEntry] = Field(default_factory=list)
    exercise_entries: list[ExerciseEntry] = Field(default_factory=list)
    sleep_entry: SleepEntry | None = None
    hydration_entry: HydrationEntry | None = None
    meditation_entries: list[MeditationEntry] = Field(default_factory=list)
    journal_entries: list[JournalEntry] = Field(default_factory=list)

    @property
    def average_mood(self) -> float | None:
        """Calculate average mood for the day."""

    @property
    def total_exercise_minutes(self) -> int:
        """Sum of all exercise duration."""

    @property
    def total_meditation_minutes(self) -> int:
        """Sum of all meditation duration."""

    @property
    def hydration_goal_met(self) -> bool:
        """Check if 8 glasses reached."""

    def get_type_bonuses(self) -> dict[str, float]:
        """Get Pokemon type encounter bonuses."""

    def get_catch_rate_modifier(self) -> float:
        """Get catch rate modifier from sleep."""
```

---

## Database Operations

### Database Class (`pokedo/data/database.py`)

```python
class Database:
    """SQLite database operations."""

    def __init__(self, db_path: Path | None = None):
        """Initialize database connection."""

    def close(self) -> None:
        """Close database connection."""

    # === Schema ===

    def initialize_schema(self) -> None:
        """Create all tables if they don't exist."""

    # === Task Operations ===

    def insert_task(self, task: Task) -> int:
        """Insert task and return ID."""

    def get_task(self, task_id: int) -> Task | None:
        """Get task by ID."""

    def get_tasks(
        self,
        completed: bool | None = None,
        category: TaskCategory | None = None,
        due_before: date | None = None,
        due_after: date | None = None,
        archived: bool = False,
    ) -> list[Task]:
        """Get tasks with optional filters."""

    def update_task(self, task: Task) -> bool:
        """Update existing task."""

    def delete_task(self, task_id: int) -> bool:
        """Delete task by ID."""

    def complete_task(self, task_id: int) -> Task | None:
        """Mark task as completed and return updated task."""

    # === Pokemon Operations ===

    def insert_pokemon(self, pokemon: Pokemon) -> int:
        """Insert caught Pokemon and return ID."""

    def get_pokemon(self, pokemon_id: int) -> Pokemon | None:
        """Get Pokemon by ID."""

    def get_all_pokemon(
        self,
        is_active: bool | None = None,
        is_favorite: bool | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[Pokemon]:
        """Get all caught Pokemon with filters."""

    def get_active_team(self) -> list[Pokemon]:
        """Get active team members."""

    def update_pokemon(self, pokemon: Pokemon) -> bool:
        """Update Pokemon data."""

    def set_pokemon_active(self, pokemon_id: int, active: bool) -> bool:
        """Set Pokemon active status."""

    def release_pokemon(self, pokemon_id: int) -> bool:
        """Release Pokemon (delete from collection)."""

    # === Pokedex Operations ===

    def get_pokedex_entry(self, pokedex_id: int) -> PokedexEntry | None:
        """Get Pokedex entry by national dex number."""

    def get_pokedex(
        self,
        caught_only: bool = False,
        generation: int | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[PokedexEntry]:
        """Get Pokedex entries with filters."""

    def update_pokedex_entry(self, entry: PokedexEntry) -> bool:
        """Update Pokedex entry."""

    def mark_pokemon_seen(self, pokedex_id: int) -> None:
        """Mark Pokemon as seen in Pokedex."""

    def mark_pokemon_caught(self, pokedex_id: int, is_shiny: bool = False) -> None:
        """Mark Pokemon as caught in Pokedex."""

    def populate_pokedex(self, entries: list[PokedexEntry]) -> None:
        """Bulk insert Pokedex entries."""

    # === Trainer Operations ===

    def get_trainer(self) -> Trainer | None:
        """Get trainer profile."""

    def create_trainer(self, name: str) -> Trainer:
        """Create new trainer profile."""

    def update_trainer(self, trainer: Trainer) -> bool:
        """Update trainer profile."""

    # === Wellbeing Operations ===

    def insert_mood_entry(self, entry: MoodEntry) -> int:
        """Insert mood entry."""

    def insert_exercise_entry(self, entry: ExerciseEntry) -> int:
        """Insert exercise entry."""

    def insert_sleep_entry(self, entry: SleepEntry) -> int:
        """Insert sleep entry."""

    def insert_hydration_entry(self, entry: HydrationEntry) -> int:
        """Insert or update hydration entry."""

    def add_hydration(self, glasses: int = 1) -> HydrationEntry:
        """Add glasses to today's hydration."""

    def insert_meditation_entry(self, entry: MeditationEntry) -> int:
        """Insert meditation entry."""

    def insert_journal_entry(self, entry: JournalEntry) -> int:
        """Insert journal entry."""

    def get_daily_wellbeing(self, target_date: date | None = None) -> DailyWellbeing:
        """Get aggregated wellbeing for a date."""

    def get_wellbeing_history(self, days: int = 7) -> list[DailyWellbeing]:
        """Get wellbeing history for past N days."""
```

---

## PokeAPI Client

### PokeAPIClient Class (`pokedo/data/pokeapi.py`)

```python
class PokeAPIClient:
    """Async client for PokeAPI."""

    def __init__(self, cache_dir: Path | None = None):
        """Initialize client with optional cache directory."""

    async def close(self) -> None:
        """Close HTTP client."""

    # === Pokemon Data ===

    async def get_pokemon(self, pokemon_id: int) -> dict:
        """
        Get Pokemon data by ID.

        Returns:
            {
                'id': int,
                'name': str,
                'types': [{'type': {'name': str}}],
                'sprites': {'front_default': str, 'front_shiny': str},
                'stats': [...],
                'height': int,
                'weight': int
            }
        """

    async def get_pokemon_species(self, pokemon_id: int) -> dict:
        """
        Get Pokemon species data.

        Returns:
            {
                'id': int,
                'name': str,
                'evolution_chain': {'url': str},
                'is_legendary': bool,
                'is_mythical': bool,
                'generation': {'name': str}
            }
        """

    async def get_evolution_chain(self, chain_id: int) -> dict:
        """Get evolution chain data."""

    # === Batch Operations ===

    async def fetch_all_pokemon(
        self,
        start_id: int = 1,
        end_id: int = 1025,
        callback: Callable[[int, int], None] | None = None,
    ) -> list[PokedexEntry]:
        """
        Fetch all Pokemon data in batch.

        Args:
            start_id: Starting Pokedex number
            end_id: Ending Pokedex number
            callback: Progress callback (current, total)

        Returns:
            List of PokedexEntry objects
        """

    # === Sprites ===

    async def download_sprite(
        self,
        pokemon_id: int,
        shiny: bool = False,
    ) -> Path | None:
        """
        Download and cache Pokemon sprite.

        Returns:
            Path to cached sprite file
        """

    # === Rarity Classification ===

    def get_rarity(self, pokemon_id: int, species_data: dict) -> PokemonRarity:
        """
        Determine Pokemon rarity tier.

        Classification priority:
        1. Mythical (hardcoded list)
        2. Legendary (hardcoded list)
        3. Epic (pseudo-legendaries, ultra beasts, final starters)
        4. Rare (final evolutions, paradox Pokemon)
        5. Uncommon (mid-evolutions)
        6. Common (everything else)
        """

    # === Caching ===

    def get_cached_data(self, cache_key: str) -> dict | None:
        """Get cached API response."""

    def cache_data(self, cache_key: str, data: dict) -> None:
        """Cache API response."""

    def clear_cache(self) -> None:
        """Clear all cached data."""
```

### Special Pokemon Lists

```python
# Legendary Pokemon IDs
LEGENDARY_IDS = {
    # Gen 1
    144, 145, 146, 150,
    # Gen 2
    243, 244, 245, 249, 250,
    # Gen 3
    377, 378, 379, 380, 381, 382, 383, 384,
    # ... continues for all generations
}

# Mythical Pokemon IDs
MYTHICAL_IDS = {
    151,  # Mew
    251,  # Celebi
    385, 386,  # Jirachi, Deoxys
    # ... continues
}

# Pseudo-Legendary IDs (600 base stat total)
PSEUDO_LEGENDARY_IDS = {
    149,  # Dragonite
    248,  # Tyranitar
    373,  # Salamence
    376,  # Metagross
    445,  # Garchomp
    635,  # Hydreigon
    706,  # Goodra
    784,  # Kommo-o
    887,  # Dragapult
    998,  # Baxcalibur
}

# Ultra Beast IDs
ULTRA_BEAST_IDS = {
    793, 794, 795, 796, 797, 798, 799, 803, 804, 805, 806
}

# Paradox Pokemon IDs
PARADOX_IDS = {
    984, 985, 986, 987, 988, 989, 990, 991, 992, 993, 994, 995, 1005, 1006, 1007, 1008, 1009, 1010
}
```

---

## Reward System

### RewardSystem Class (`pokedo/core/rewards.py`)

```python
class RewardSystem:
    """Handles encounters, catches, and rewards."""

    def __init__(self, db: Database, pokeapi: PokeAPIClient):
        """Initialize with database and API client."""

    # === Encounter System ===

    def calculate_encounter_chance(
        self,
        task: Task,
        trainer: Trainer,
    ) -> float:
        """
        Calculate Pokemon encounter probability.

        Formula:
            base_rate (0.70)
            + difficulty_bonus (0.05-0.15)
            + streak_bonus (0.01 * days, max 0.10)
        """

    def roll_encounter(self, task: Task, trainer: Trainer) -> bool:
        """Roll for Pokemon encounter."""

    def select_pokemon(
        self,
        task: Task,
        wellbeing: DailyWellbeing | None = None,
    ) -> tuple[PokedexEntry, bool]:
        """
        Select Pokemon for encounter.

        Returns:
            (PokedexEntry, is_shiny)
        """

    # === Catch System ===

    def calculate_catch_rate(
        self,
        pokemon: PokedexEntry,
        trainer: Trainer,
        ball_type: str = "pokeball",
        wellbeing: DailyWellbeing | None = None,
    ) -> float:
        """
        Calculate catch success probability.

        Base rates by rarity:
            common: 0.90
            uncommon: 0.75
            rare: 0.50
            epic: 0.30
            legendary: 0.15
            mythical: 0.05

        Modifiers:
            + trainer_level * 0.02 (max 0.20)
            + ball_bonus (great: 0.10, ultra: 0.20, master: 1.00)
            + sleep_modifier (-0.20 to +0.10)
        """

    def attempt_catch(
        self,
        pokemon: PokedexEntry,
        trainer: Trainer,
        ball_type: str = "pokeball",
        wellbeing: DailyWellbeing | None = None,
    ) -> bool:
        """Attempt to catch Pokemon."""

    # === Shiny System ===

    def calculate_shiny_rate(self, trainer: Trainer) -> float:
        """
        Calculate shiny probability.

        Formula:
            base_rate (0.01)
            + streak_bonus (0.005 * streak_days)
            max: 0.10
        """

    def roll_shiny(self, trainer: Trainer) -> bool:
        """Roll for shiny variant."""

    # === Streak Rewards ===

    def get_streak_reward(self, streak_count: int) -> dict | None:
        """
        Get reward for streak milestone.

        Milestones:
            3 days: {'item': 'great_ball', 'quantity': 5}
            7 days: {'item': 'evolution_stone', 'quantity': 1}
            14 days: {'item': 'ultra_ball', 'quantity': 5}
            21 days: {'item': 'rare_candy', 'quantity': 3}
            30 days: {'item': 'master_ball', 'quantity': 1}
            50 days: {'item': 'legendary_ticket', 'quantity': 1}
            100 days: {'item': 'mythical_ticket', 'quantity': 1}
        """

    def check_and_award_badges(self, trainer: Trainer) -> list[TrainerBadge]:
        """Check badge conditions and award new badges."""

    # === XP System ===

    def award_task_completion(
        self,
        task: Task,
        trainer: Trainer,
    ) -> dict:
        """
        Process task completion rewards.

        Returns:
            {
                'xp_earned': int,
                'leveled_up': bool,
                'new_level': int | None,
                'encounter': bool,
                'pokemon': Pokemon | None,
                'caught': bool,
                'streak_reward': dict | None,
                'badges_earned': list[TrainerBadge]
            }
        """

---

## Server API

### Authentication (`pokedo/core/auth.py`)

```python
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash."""

def get_password_hash(password: str) -> str:
    """Hash a password."""

def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Create a JWT access token."""
```

### Endpoints (`pokedo/server.py`)

The server uses the FastAPI `lifespan` context manager (not the deprecated `@app.on_event`).

#### Authentication

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| POST | `/register` | Register a new user | No |
| POST | `/token` | Login (returns JWT) | No |
| GET | `/health` | Health check | No |
| GET | `/users/me` | Current user profile | Yes |

#### Sync

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| POST | `/sync` | Push local changes to server | Yes |

#### Battles

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| POST | `/battles/challenge` | Send a battle challenge | Yes |
| GET | `/battles/pending` | List pending/active battles | Yes |
| POST | `/battles/{id}/accept` | Accept a challenge | Yes |
| POST | `/battles/{id}/decline` | Decline a challenge | Yes |
| POST | `/battles/{id}/team` | Submit team for a battle | Yes |
| POST | `/battles/{id}/action` | Submit turn action (move/switch/forfeit) | Yes |
| GET | `/battles/{id}` | Get battle state (censored for opponent) | Yes |
| GET | `/battles/{id}/history` | Turn event log | Yes |
| GET | `/battles/history/me` | Completed battle history | Yes |

#### Leaderboard

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/leaderboard` | Global rankings (sortable) | No |
| GET | `/leaderboard/{username}` | Individual player stats | No |

#### Server Models

```python
class ServerUser(SQLModel, table=True):
    """Postgres-backed user account."""
    id: str          # UUID
    username: str    # Unique
    hashed_password: str
    elo_rating: int = 1000
    battle_wins: int = 0
    battle_losses: int = 0
    battle_draws: int = 0
    rank: str = "Youngster"
    disabled: bool = False
    created_at: datetime

class BattleRecord(SQLModel, table=True):
    """Persisted battle state."""
    id: str              # UUID
    challenger_id: str   # FK to ServerUser
    opponent_id: str     # FK to ServerUser
    format: str          # singles_1v1, singles_3v3, singles_6v6
    status: str          # pending, team_submission, active, finished
    winner_id: str | None
    state_json: str      # Serialized BattleState
    turn_history_json: str  # Serialized list of turn events
    created_at: datetime
    updated_at: datetime

class LeaderboardEntry(BaseModel):
    """Response model for leaderboard queries."""
    username: str
    elo_rating: int
    battle_wins: int
    battle_losses: int
    battle_draws: int
    rank: str
    win_rate: float

class Token(BaseModel):
    access_token: str
    token_type: str
```

---

## Configuration

### Config Class (`pokedo/utils/config.py`)

```python
class Config:
    """Application configuration."""

    # Paths
    data_dir: Path = Path.home() / ".pokedo"
    db_path: Path = data_dir / "pokedo.db"
    cache_dir: Path = data_dir / "cache"
    sprites_dir: Path = cache_dir / "sprites"

    # API
    pokeapi_base_url: str = "https://pokeapi.co/api/v2"
    max_pokemon_id: int = 1025

    # Generation ranges
    generation_ranges: dict[int, tuple[int, int]] = {
        1: (1, 151),
        2: (152, 251),
        3: (252, 386),
        4: (387, 493),
        5: (494, 649),
        6: (650, 721),
        7: (722, 809),
        8: (810, 905),
        9: (906, 1025),
    }

    # Game mechanics
    base_encounter_rate: float = 0.70
    base_catch_rate: float = 0.60
    shiny_rate: float = 0.01
    streak_shiny_bonus: float = 0.005
    max_shiny_rate: float = 0.10

    # XP values
    task_xp: dict[str, int] = {
        "easy": 10,
        "medium": 25,
        "hard": 50,
        "epic": 100,
    }

    # Catch rate modifiers
    catch_rate_by_rarity: dict[str, float] = {
        "common": 0.90,
        "uncommon": 0.75,
        "rare": 0.50,
        "epic": 0.30,
        "legendary": 0.15,
        "mythical": 0.05,
    }

    ball_bonuses: dict[str, float] = {
        "pokeball": 0.00,
        "great_ball": 0.10,
        "ultra_ball": 0.20,
        "master_ball": 1.00,
    }

    @classmethod
    def ensure_directories(cls) -> None:
        """Create data directories if they don't exist."""

    @classmethod
    def get_generation(cls, pokedex_id: int) -> int | None:
        """Get generation number for a Pokemon ID."""
```

---

## UI Components

### Display Functions (`pokedo/cli/ui/displays.py`)

```python
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress

console = Console()

def display_task_table(tasks: list[Task]) -> None:
    """Display tasks in a formatted table."""

def display_pokemon_card(pokemon: Pokemon) -> None:
    """Display Pokemon info as a card."""

def display_team(team: list[Pokemon]) -> None:
    """Display active team."""

def display_pokedex_grid(
    entries: list[PokedexEntry],
    columns: int = 5,
) -> None:
    """Display Pokedex entries in a grid."""

def display_trainer_profile(trainer: Trainer) -> None:
    """Display trainer profile panel."""

def display_streak_info(trainer: Trainer) -> None:
    """Display streak information."""

def display_badge_collection(badges: list[TrainerBadge]) -> None:
    """Display earned badges."""

def display_encounter(
    pokemon: PokedexEntry,
    is_shiny: bool,
    caught: bool,
) -> None:
    """Display encounter animation and result."""

def display_level_up(
    old_level: int,
    new_level: int,
) -> None:
    """Display level up celebration."""

def display_dashboard(
    trainer: Trainer,
    today_tasks: list[Task],
    wellbeing: DailyWellbeing,
) -> None:
    """Display main dashboard."""

def create_progress_bar(
    current: int,
    total: int,
    label: str = "",
) -> str:
    """Create ASCII progress bar."""
```

### Menu Functions (`pokedo/cli/ui/menus.py`)

```python
def select_pokemon(
    pokemon_list: list[Pokemon],
    prompt: str = "Select Pokemon",
) -> Pokemon | None:
    """Interactive Pokemon selection menu."""

def select_ball(
    inventory: dict[str, int],
) -> str | None:
    """Interactive ball selection menu."""

def confirm_action(
    message: str,
    default: bool = False,
) -> bool:
    """Confirmation prompt."""

def select_category() -> TaskCategory:
    """Interactive category selection."""

def select_difficulty() -> TaskDifficulty:
    """Interactive difficulty selection."""
```

---

## Error Handling

### Common Exceptions

```python
class PokeDoError(Exception):
    """Base exception for PokeDo."""

class DatabaseError(PokeDoError):
    """Database operation failed."""

class APIError(PokeDoError):
    """PokeAPI request failed."""

class ValidationError(PokeDoError):
    """Input validation failed."""

class NotFoundError(PokeDoError):
    """Resource not found."""
```

### CLI Error Handling Pattern

```python
@app.command()
def example_command(task_id: int) -> None:
    try:
        task = db.get_task(task_id)
        if not task:
            console.print(f"[red]Task {task_id} not found[/red]")
            raise typer.Exit(1)
        # ... process task
    except DatabaseError as e:
        console.print(f"[red]Database error:[/red] {e}")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error:[/red] {e}")
        raise typer.Exit(1)
```
