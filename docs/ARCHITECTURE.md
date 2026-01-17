# PokeDo Architecture

## Table of Contents

- [Overview](#overview)
- [Project Structure](#project-structure)
- [Layered Architecture](#layered-architecture)
- [Core Components](#core-components)
- [Data Flow](#data-flow)
- [Database Schema](#database-schema)
- [External Integrations](#external-integrations)
- [Game Mechanics](#game-mechanics)
- [Configuration](#configuration)

---

## Overview

PokeDo is a gamified task manager that combines productivity tracking with Pokemon collection mechanics. The application follows a layered architecture pattern with clear separation between:

- **Presentation Layer** (CLI/TUI) - User interface and command handling
- **Business Logic Layer** (Core) - Domain models and game mechanics
- **Data Access Layer** (Data) - Database operations and API clients
- **Synchronization Layer** (Sync) - Client-side change queuing and server communication

**Technology Stack:**
- Python 3.10+
- Typer (CLI framework)
- Textual (TUI framework)
- Rich (Terminal UI)
- Pydantic (Data validation)
- SQLite (Local storage)
- FastAPI (Server)
- Bcrypt (Direct password hashing)
- httpx (Async HTTP client for PokeAPI)
- requests (Sync HTTP client for Server Sync)

---

## Project Structure

```
pokedo/
├── __init__.py           # Package init with version
├── __main__.py           # Entry point for `python -m pokedo`
├── cli/                  # Presentation Layer
│   ├── app.py            # Main Typer application
│   └── ...
├── tui/                  # TUI Layer (Textual)
│   ├── app.py            # Textual dashboard app
├── core/                 # Business Logic Layer
│   ├── auth.py           # Authentication logic (Bcrypt/JWT)
│   ├── task.py           # Task model and enums
│   ├── trainer.py        # Trainer model and progression
│   ├── pokemon.py        # Pokemon and Pokedex models
│   ├── rewards.py        # Encounter and reward system
│   └── wellbeing.py      # Wellbeing tracking models
├── data/                 # Data Access Layer
│   ├── database.py       # SQLite operations
│   ├── pokeapi.py        # PokeAPI client
│   └── sync.py           # NEW: Sync client and change queue
├── server.py             # FastAPI server entry point
└── utils/                # Utilities
    ├── config.py         # Configuration management
    └── helpers.py        # Helper functions
```

---

## Layered Architecture

### Presentation Layer (`cli/`, `tui/`)

The CLI layer handles all user interaction through the Typer framework.

**`app.py`** - Main application entry point
- Initializes the Typer app with sub-command groups
- Registers command modules (task, pokemon, wellbeing, stats)
- Provides shortcut commands for common operations
- Handles the default dashboard display

**`commands/`** - Command implementations
- Each module corresponds to a feature domain
- Commands validate input and delegate to core/data layers
- Return formatted output using Rich components

**`ui/`** - Display components
- `displays.py`: Tables, panels, progress bars, ASCII art
- `menus.py`: Interactive selection menus

**TUI Layer (`tui/`)**
- `app.py`: Textual-based dashboard for trainer, tasks, and team summaries
- Uses the same data access layer (`data/`) for read-only views

### Server Layer (`server.py`)

Handles centralized operations and synchronization.

**`server.py`** - FastAPI Application
- User registration and authentication endpoints (`/register`, `/token`)
- Protected synchronization endpoint (`/sync`)
- In-memory user store (prototype)

### Business Logic Layer (`core/`)

The core layer contains domain models and game logic.

**`auth.py`** - Authentication
- Password hashing (Direct Bcrypt usage)
- JWT Token generation and verification

**`task.py`** - Task Management
```python
class TaskCategory(Enum):
    WORK, EXERCISE, LEARNING, PERSONAL, HEALTH, CREATIVE

class TaskDifficulty(Enum):
    EASY, MEDIUM, HARD, EPIC

class Task(BaseModel):
    # Properties: is_overdue, xp_reward, stat_affinity, ev_yield
```

**`pokemon.py`** - Pokemon System
```python
class PokemonRarity(Enum):
    COMMON, UNCOMMON, RARE, EPIC, LEGENDARY, MYTHICAL

class Pokemon(BaseModel):
    # Evolution tracking, XP system, happiness
    # EV/IV stats (new)
```

**`trainer.py`** - Player Progression
```python
class Trainer(BaseModel):
    # Level calculation, XP management
    # Streak tracking, badge system
    # Inventory management
```

**`rewards.py`** - Reward System
```python
class RewardSystem:
    # Encounter probability calculation
    # Catch rate computation
    # Shiny rate with streak bonuses
    # Streak milestone rewards
```

**`wellbeing.py`** - Wellbeing Tracking
```python
class MoodEntry, ExerciseEntry, SleepEntry,
      HydrationEntry, MeditationEntry, JournalEntry

class DailyWellbeing:
    # Aggregate daily wellbeing data
    # Type affinity bonuses
```

### Data Access Layer (`data/`)

**`database.py`** - SQLite Operations
- CRUD operations for all models
- Connection management
- Schema initialization
- Query builders
- EV/IV columns (`pokemon.evs`, `pokemon.ivs`) store serialized stat distributions so training progress survives restarts without an extra join table.

**`pokeapi.py`** - External API Client
- Async HTTP client using `httpx`
- Response caching (JSON files)
- Sprite downloading
- Evolution chain parsing

**`sync.py`** - Synchronization Client
- Local change queue management (SQLModel `Change` entity)
- Sync push operations using `requests`

---

## Synchronization Layer

This layer enables local-first data handling with cloud synchronization.

**Concept:**
- **Local-First:** All user actions (Task Create, Pokemon Catch) are committed to the local SQLite database immediately.
- **Change Queue:** Simultaneously, a record of the action is written to a `change` table in the local DB.
- **Push Sync:** A background process (or manual command) reads unsynced changes from the `change` table and pushes them to the server via HTTP POST.

**Change Entity:**
```python
class Change(SQLModel):
    id: str (UUID)
    entity_id: str
    entity_type: str (e.g., "task", "pokemon")
    action: str (CREATE, UPDATE, DELETE)
    payload: JSON
    timestamp: datetime
    synced: bool
```

**Sync Process:**
1.  `queue_change()`: Called by CRUD functions in `database.py` whenever data modifies.
2.  `push_changes()`: Reads unsynced records, sends to `POST /sync`.
3.  On 200 OK, marks records as `synced=True`.

---

## Data Flow

### Task Completion Flow

```
User Input -> CLI Command -> Validate Input -> Database Update -> Queue Change
                                                    |
                                                    v
Display Result <- UI Components <- Reward System <- Calculate Rewards
                                         |
                                         v
                                   Pokemon Encounter
                                         |
                                         v
                                   Catch Attempt
                                         |
                                         v
                                   Update Database -> Queue Change
```

### Pokemon Encounter Flow

```
1. Task completed
2. Calculate encounter probability
   - Base rate (70%)
   - Difficulty bonus (+5-15%)
   - Streak bonus (+1%/day, max 10%)
3. If encounter:
   a. Determine rarity (weighted by difficulty)
   b. Select Pokemon from rarity pool
   c. Check shiny status (1% + streak bonus)
   d. Calculate catch rate
   e. Apply ball modifiers
   f. Determine success/failure
4. Update database (trainer stats, Pokemon, Pokedex)
5. Display result
```

---

## Database Schema

### Entity Relationship Diagram

```
┌─────────────┐       ┌─────────────┐
│   trainer   │       │   tasks     │
├─────────────┤       ├─────────────┤
│ id (PK)     │       │ id (PK)     │
│             │       │ trainer_id  │
│ name        │       │ title       │
│ total_xp    │       │ category    │
│ badges      │       │ difficulty  │
│ inventory   │       │ due_date    │
│ streaks     │       │ completed   │
└─────────────┘       └─────────────┘

┌─────────────┐       ┌─────────────┐
│   pokemon   │──────→│   pokedex   │
├─────────────┤       ├─────────────┤
│ id (PK)     │       │ pokedex_id  │
│ trainer_id  │       │ trainer_id  │
│ pokedex_id  │       │ name        │
│ nickname    │       │ type1/type2 │
│ level       │       │ rarity      │
│ is_shiny    │       │ is_caught   │
│ is_active   │       │ times_caught│
└─────────────┘       └─────────────┘

┌──────────────────┐  ┌──────────────────┐
│  mood_entries    │  │ exercise_entries │
├──────────────────┤  ├──────────────────┤
│ id, trainer_id   │  │ id, trainer_id   │
│ date, mood       │  │ date, type       │
│ note, energy     │  │ duration, note   │
└──────────────────┘  └──────────────────┘

┌──────────────────┐  ┌──────────────────┐
│  sleep_entries   │  │hydration_entries │
├──────────────────┤  ├──────────────────┤
│ id, trainer_id   │  │ id, trainer_id   │
│ date, hours      │  │ date, glasses    │
│ quality, note    │  │ note             │
└──────────────────┘  └──────────────────┘

┌──────────────────┐  ┌──────────────────┐
│meditation_entries│  │ journal_entries  │
├──────────────────┤  ├──────────────────┤
│ id, trainer_id   │  │ id, trainer_id   │
│ date, minutes    │  │ date, content    │
│ note             │  │ gratitude_items  │
└──────────────────┘  └──────────────────┘
```

### Table Definitions

**tasks**
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Auto-increment ID |
| trainer_id | INTEGER FK | Owning trainer profile |
| title | TEXT | Task title |
| description | TEXT | Optional description |
| category | TEXT | work/exercise/learning/personal/health/creative |
| difficulty | TEXT | easy/medium/hard/epic |
| priority | TEXT | low/medium/high/urgent |
| created_at | TIMESTAMP | Creation time |
| due_date | DATE | Optional due date |
| completed_at | TIMESTAMP | Completion time |
| is_completed | BOOLEAN | Completion status |
| is_archived | BOOLEAN | Archive status |
| recurrence | TEXT | daily/weekly/monthly/none |
| parent_task_id | INTEGER FK | Parent for recurring tasks |
| tags | TEXT | JSON array of tags |

**pokemon**
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Auto-increment ID |
| trainer_id | INTEGER FK | Owning trainer profile |
| pokedex_id | INTEGER | National Pokedex number |
| name | TEXT | Species name |
| nickname | TEXT | User-assigned nickname |
| type1, type2 | TEXT | Pokemon types |
| level | INTEGER | Current level (1-100) |
| xp | INTEGER | Experience points |
| happiness | INTEGER | Happiness value |
| caught_at | TIMESTAMP | Catch time |
| is_shiny | BOOLEAN | Shiny variant |
| catch_location | TEXT | Where caught (task category) |
| is_active | BOOLEAN | In active team |
| is_favorite | BOOLEAN | Marked as favorite |
| can_evolve | BOOLEAN | Evolution available |
| evolution_id | INTEGER | Evolution target ID |
| evolution_level | INTEGER | Level required to evolve |
| sprite_url | TEXT | Remote sprite URL |
| sprite_path | TEXT | Local cached sprite path |

**pokedex**
| Column | Type | Description |
|--------|------|-------------|
| trainer_id | INTEGER PK | Owning trainer profile |
| pokedex_id | INTEGER PK | National Pokedex number |
| name | TEXT | Species name |
| type1, type2 | TEXT | Pokemon types |
| is_seen | BOOLEAN | Encountered |
| is_caught | BOOLEAN | Successfully caught |
| times_caught | INTEGER | Total catch count |
| first_caught_at | TIMESTAMP | First catch time |
| shiny_caught | BOOLEAN | Shiny variant caught |
| sprite_url | TEXT | Sprite URL |
| rarity | TEXT | Rarity tier |
| evolves_from | INTEGER | Pre-evolution ID |
| evolves_to | TEXT | JSON array of evolution IDs |

**trainer**
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Trainer profile ID |
| name | TEXT | Trainer name |
| created_at | TIMESTAMP | Profile creation time |
| total_xp | INTEGER | Accumulated XP |
| tasks_completed | INTEGER | Total tasks done |
| pokemon_caught | INTEGER | Total Pokemon caught |
| pokemon_released | INTEGER | Total released |
| evolutions_triggered | INTEGER | Total evolutions |
| pokedex_seen | INTEGER | Unique species seen |
| pokedex_caught | INTEGER | Unique species caught |
| daily_streak_count | INTEGER | Current task streak |
| daily_streak_best | INTEGER | Best task streak |
| daily_streak_last_date | DATE | Last task completion |
| wellbeing_streak_count | INTEGER | Current wellbeing streak |
| wellbeing_streak_best | INTEGER | Best wellbeing streak |
| wellbeing_streak_last_date | DATE | Last wellbeing log |
| badges | TEXT | JSON array of badges |
| inventory | TEXT | JSON object of items |
| favorite_pokemon_id | INTEGER | Favorite Pokemon |
| last_active_date | DATE | Last activity |

---

## External Integrations

### PokeAPI Integration

**Base URL:** `https://pokeapi.co/api/v2`

**Endpoints Used:**
- `GET /pokemon/{id}` - Pokemon data (stats, types, sprites)
- `GET /pokemon-species/{id}` - Species data (evolution chain URL)
- `GET /evolution-chain/{id}` - Evolution requirements

**Caching Strategy:**
- API responses cached as JSON in `~/.pokedo/cache/`
- Sprites downloaded to `~/.pokedo/cache/sprites/`
- Cache never expires (Pokemon data is static)
- Initial population during `pokedo init`

**Rate Limiting:**
- No explicit rate limiting (PokeAPI is generous)
- Async batch requests during initialization
- Cached data used for all subsequent requests

---

## Game Mechanics

### XP and Leveling

**Task XP Rewards:**
| Difficulty | XP |
|------------|-----|
| Easy | 10 |
| Medium | 25 |
| Hard | 50 |
| Epic | 100 |

**Trainer Level Formula:**
```python
level = 1
while total_xp >= level * 100:
    total_xp -= level * 100
    level += 1
```

**Pokemon Level:**
- Gain XP when tasks completed
- Level up affects evolution eligibility
- Max level: 100

### Rarity System

**Rarity Weights by Difficulty:**
| Rarity | Easy | Medium | Hard | Epic |
|--------|------|--------|------|------|
| Common | 70% | 50% | 30% | 15% |
| Uncommon | 25% | 35% | 35% | 25% |
| Rare | 4% | 10% | 20% | 25% |
| Epic | 1% | 4% | 12% | 25% |
| Legendary | 0% | 1% | 3% | 10% |

**Pokemon Rarity Classification:**
- **Legendary:** Hardcoded list (Articuno, Zapdos, Mewtwo, Lugia, etc.)
- **Mythical:** Hardcoded list (Mew, Celebi, Jirachi, Arceus, etc.)
- **Epic:** Pseudo-legendaries, Ultra Beasts, final starters
- **Rare:** Final evolutions, Paradox Pokemon
- **Uncommon:** Mid-evolutions, uncommon spawns
- **Common:** Everything else

### Catch Rate Formula

```python
base_rate = {
    'common': 0.90,
    'uncommon': 0.75,
    'rare': 0.50,
    'epic': 0.30,
    'legendary': 0.15,
    'mythical': 0.05
}

# Modifiers
trainer_bonus = min(trainer_level * 0.02, 0.20)  # Max +20%
ball_bonus = {'pokeball': 0, 'great': 0.10, 'ultra': 0.20, 'master': 1.0}
sleep_bonus = get_sleep_modifier()  # +10% or -20%

final_rate = min(base_rate + trainer_bonus + ball_bonus + sleep_bonus, 1.0)
```

### Shiny Rate Formula

```python
base_shiny_rate = 0.01  # 1%
streak_bonus = streak_days * 0.005  # +0.5% per day
max_shiny_rate = 0.10  # 10% cap

shiny_rate = min(base_shiny_rate + streak_bonus, max_shiny_rate)
```

### Type Affinities

Task categories influence Pokemon type encounter probabilities:

| Category | Boosted Types |
|----------|---------------|
| Work | Steel, Electric, Normal |
| Exercise | Fighting, Fire, Rock |
| Learning | Psychic, Ghost, Dark |
| Personal | Normal, Fairy, Flying |
| Health | Grass, Water, Poison |
| Creative | Fairy, Dragon, Ice |

Wellbeing actions also affect type encounters:
- Hydration goal (8 glasses) -> Water-type bonus
- Meditation -> Psychic/Fairy bonus
- Exercise -> Fighting-type bonus

---

### EV/IV Persistence & Affinity Backfill

- **EV/IV persistence**: `pokemon.evs`/`pokemon.ivs` are saved as JSON blobs in the database, so the stat training that occurs every time a task completes is recorded once and carried over every time the Pokemon is loaded. This supports the standard 510/252 caps and keeps spreads deterministic across sessions (`pokedo/core/pokemon.py`, `pokedo/data/database.py`).
- **Affinity backfill**: `_ensure_pokedex_entry_types` fetches missing Pokedex entries from the API before affinity filtering, enabling tasks and wellbeing logs to bias rarity pools even for unseen species. The reward engine caches the resulting entry so type-based filtering (`type_affinities` + wellbeing bonuses) reliably narrows the candidate pool (`pokedo/core/rewards.py`).


## Configuration

### Default Paths

```python
DATA_DIR = Path.home() / ".pokedo"
DB_PATH = DATA_DIR / "pokedo.db"
CACHE_DIR = DATA_DIR / "cache"
SPRITES_DIR = CACHE_DIR / "sprites"
```

### Game Constants

```python
# XP Values
TASK_XP = {'easy': 10, 'medium': 25, 'hard': 50, 'epic': 100}

# Encounter Rates
BASE_ENCOUNTER_RATE = 0.70
DIFFICULTY_BONUS = {'easy': 0.05, 'medium': 0.10, 'hard': 0.12, 'epic': 0.15}
STREAK_BONUS_PER_DAY = 0.01
MAX_STREAK_BONUS = 0.10

# Catch Rates
BASE_CATCH_RATE = 0.60
SHINY_RATE = 0.01
STREAK_SHINY_BONUS = 0.005

# Generation Ranges
GENERATION_RANGES = {
    1: (1, 151),    # Kanto
    2: (152, 251),  # Johto
    3: (252, 386),  # Hoenn
    4: (387, 493),  # Sinnoh
    5: (494, 649),  # Unova
    6: (650, 721),  # Kalos
    7: (722, 809),  # Alola
    8: (810, 905),  # Galar
    9: (906, 1025)  # Paldea
}
```

### Streak Milestones

```python
STREAK_REWARDS = {
    3: {'item': 'great_ball', 'quantity': 5},
    7: {'item': 'evolution_stone', 'quantity': 1},
    14: {'item': 'ultra_ball', 'quantity': 5},
    21: {'item': 'rare_candy', 'quantity': 3},
    30: {'item': 'master_ball', 'quantity': 1},
    50: {'item': 'legendary_ticket', 'quantity': 1},
    100: {'item': 'mythical_ticket', 'quantity': 1}
}
```

---

## Design Decisions

### Why SQLite?

- No external database server required
- Portable (single file)
- Sufficient for single-user application
- Good Python support

### Why Typer + Rich?

- Typer provides automatic CLI argument parsing
- Rich enables beautiful terminal output
- Both are well-maintained and documented
- Compatible with each other

### Why PokeAPI?

- Free and open Pokemon data
- Complete coverage (all 1025 Pokemon)
- Includes sprites and evolution data
- No authentication required

### Why Local Caching?

- Reduces API calls
- Faster subsequent loads
- Offline functionality (after initial setup)
- Pokemon data is static

### Why Pydantic?

- Type validation at runtime
- JSON serialization built-in
- Clear model definitions
- IDE autocompletion support

---

## Future Considerations

### Potential Enhancements

- **Multiplayer:** Battle/trade with other trainers
- **Cloud Sync:** Backup data to cloud storage
- **Mobile App:** Companion mobile interface
- **Plugin System:** Custom game mechanics
- **Notifications:** Task reminders and streak alerts

### Scalability Notes

- Local database supports multiple trainer profiles via `trainer_id` scoping
- Cloud sync would need per-user separation and conflict resolution
- API client is already async-ready
- Cache strategy would need revision for cloud deployment
