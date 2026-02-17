# PokeDo

A Pokemon-themed CLI task manager and wellbeing tracker. Complete tasks to catch Pokemon, build your collection, and track your mental and physical wellbeing.

**Version:** 0.3.2 | **License:** MIT | **Python:** 3.10+ 

![CI](https://github.com/tldrwtf/pokedo/actions/workflows/ci.yml/badge.svg?branch=main) ![Version](https://badgen.net/github/release/tldrwtf/pokedo/stable)

## Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Usage](#usage)
- [Server Usage (Optional)](#server-usage-optional)
- [How It Works](#how-it-works)
- [Data Storage](#data-storage)
- [Development](#development)
- [Troubleshooting](#troubleshooting)
- [FAQ](#faq)
- [Credits](#credits)

## Features

### Task Management

- Create tasks with categories (work, exercise, learning, personal, health, creative)
- Set difficulty levels (easy, medium, hard, epic) that affect XP and Pokemon rarity
- Recurring tasks (daily, weekly, monthly)
- Task priorities and due dates

### Pokemon System

- Catch Pokemon by completing tasks
- **All 1025 Pokemon** from Gen 1 (Kanto) through Gen 9 (Paldea)
- Pokemon rarity based on task difficulty
- Pokemon **EVs (Effort Values) and IVs (Individual Values)** for stat training with calculated stats display
- Shiny Pokemon (rare variants with boosted rates from streaks)
- Legendary, Mythical, Pseudo-Legendary, and Ultra Beast encounters
- Paradox Pokemon from Scarlet/Violet
- Pokedex tracking with generation filtering
- Active team of 6 Pokemon
- Pokemon evolution based on level
- Nickname your Pokemon

### Wellbeing Tracking

- Mood logging (1-5 scale)
- Exercise tracking with type detection
- Sleep logging with catch rate modifiers
- Hydration tracking (Water-type bonuses)
- Meditation logging (Psychic/Fairy bonuses)
- Gratitude journaling (friendship bonuses)

### Progression

- Trainer levels and XP
- **Trainer Classes** to specialize your journey (e.g., Ace Trainer, Hiker, Scientist). Choose your class via `pokedo stats set-class`.
- Daily streaks with milestone rewards
- Achievement badges
- Inventory system (Pokeballs, evolution items)

### Terminal User Interface (TUI)

- Interactive dashboard with trainer profile, team, and task summaries
- Full task management with tabbed filtering (Active/Due Today/All/Archived)
- Add, edit, complete, and delete tasks with keyboard shortcuts
- Task completion triggers Pokemon encounters with visual feedback
- Profile switching support

## Installation

### Requirements

- Python 3.10 or higher
- pip (Python package manager)
- Internet connection (for initial Pokemon data download)

### Install from Source

```bash
# Clone the repository
git clone https://github.com/tldrwtf/pokedo.git
cd pokedo

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install PokeDo
pip install -e .
```

## Quick Start

```bash
# 1. Initialize (downloads Pokemon data)
pokedo init --name "YourName" --quick  # Quick start with Gen 1 only

# 2. Add your first task
pokedo task add "Complete a task" --difficulty easy

# 3. Complete the task and catch a Pokemon!
pokedo task complete 1

# 4. View your dashboard
pokedo
```

## Usage

You can use `pd` as a shorthand for `pokedo` once installed.

### Initialize

```bash
# Full initialization (all 1025 Pokemon, takes a few minutes first time)
pokedo init --name "Ash"

# Speed up full initialization with parallel requests
pokedo init --name "Ash" --concurrency 20

# Quick start with Gen 1 only (151 Pokemon)
pokedo init --name "Ash" --quick

# Initialize specific generation
pokedo init --name "Ash" --gen 9  # Paldea only
```

### Tasks

```bash
# Add a task
pokedo task add "Complete project report" --category work --difficulty hard --due tomorrow

# List tasks
pokedo task list
pokedo task list --today
pokedo task list --category work

# Complete a task (triggers Pokemon encounter!)
pokedo task complete 1

# Edit/delete tasks
pokedo task edit 1 --priority urgent
pokedo task delete 1
```

### Pokemon

```bash
# View your team
pokedo team
pokedo pokemon team

# View all Pokemon
pokedo pokemon box

# View Pokedex
pokedo pokedex
pokedo pokemon pokedex --caught
pokedo pokemon pokedex --gen 3  # Filter by generation

# Manage team
pokedo pokemon set-active 5
pokedo pokemon remove-active 5

# Evolve Pokemon
pokedo pokemon evolve 3

# Nickname
pokedo pokemon nickname 1 "Sparky"

# Release
pokedo pokemon release 10
```

### Wellbeing

```bash
# Quick commands
pokedo mood 4 --note "Feeling productive"
pokedo exercise cardio --duration 30 --intensity 4
pokedo sleep 7.5 --quality 4
pokedo water --glasses 8
pokedo meditate 15

# Full commands
pokedo wellbeing mood 5
pokedo wellbeing exercise running --duration 45
pokedo wellbeing today
```

### Stats & Profile

```bash
# Dashboard
pokedo
pokedo daily

# Profiles
pokedo init --name "Misty"
pokedo profile set-default Misty

# Profile
pokedo profile
pokedo stats profile
pokedo profile set-default <name-or-id>

# Streaks
pokedo streaks

# Badges
pokedo badges

# Inventory
pokedo stats inventory

# History
pokedo stats history --days 14
```

### TUI (Terminal User Interface)

Launch the interactive terminal UI for a full-featured graphical experience.

```bash
pokedo tui
```

**Dashboard Keybindings:**

| Key | Action |
|-----|--------|
| `q` | Quit the TUI |
| `r` | Refresh dashboard |
| `p` | Switch profiles |
| `t` | Open task management |

**Task Management Screen** (press `t` from dashboard):

The task screen provides full CRUD operations with tabbed filtering:

- **Active** - Pending tasks (not completed, not archived)
- **Due Today** - Tasks due on the current date
- **All** - All non-archived tasks
- **Archived** - Archived tasks

| Key | Action |
|-----|--------|
| `a` | Add new task |
| `c` | Complete selected task (triggers Pokemon encounter) |
| `e` | Edit selected task |
| `d` | Delete selected task (with confirmation) |
| `r` | Refresh task lists |
| `Escape` | Return to dashboard |

Completing a task in the TUI triggers the full encounter flow with XP rewards, streak updates, and Pokemon catching, just like the CLI.

### Server Usage (Optional)

PokeDo is developing a FastAPI server to enable cloud synchronization and multi-user features. This system uses `requests` for client-side pushing and `bcrypt` for secure authentication.

1.  **Run the Server:**

    ```bash
    uvicorn pokedo.server:app --reload --port 8000
    ```

    (Ensure you have installed development dependencies: `pip install -e ".[dev]"`)

2.  **Register a User:**

    ```bash
    curl -X POST http://localhost:8000/register -H "Content-Type: application/json" -d "{\"username\": \"testuser\", \"password\": \"testpassword\"}"
    ```

3.  **Login and Get an Access Token:**

    ```bash
    curl -X POST http://localhost:8000/token -F "username=testuser" -F "password=testpassword"
    ```

    This will return a JSON object containing your `access_token`.

4.  **Access Protected Endpoints (e.g., /users/me or /sync):**
    Replace `<YOUR_ACCESS_TOKEN>` with the token received from the login step.
    ```bash
    curl -X GET http://localhost:8000/users/me -H "Authorization: Bearer <YOUR_ACCESS_TOKEN>"
    ```

## How It Works

### Catching Pokemon

When you complete a task, there's a chance to encounter a Pokemon:

- **Encounter Rate**: ~70% base, increases with difficulty and streaks
- **Rarity**: Determined by task difficulty
  - Easy: Mostly common Pokemon
  - Medium: Common + Uncommon
  - Hard: Higher rare/epic chances
  - Epic: Best legendary chances
- **Catch Rate**: Based on Pokemon rarity and trainer level

### Rarity Tiers

- **Common** (60%): Early-route Pokemon from all generations
- **Uncommon** (25%): Mid-evolution Pokemon, starters
- **Rare** (10%): Final evolutions, Paradox Pokemon
- **Epic** (4%): Final starter evolutions, Pseudo-Legendaries (Dragonite, Tyranitar, Salamence, Metagross, Garchomp, etc.), Ultra Beasts
- **Legendary** (1%): Articuno, Zapdos, Moltres, Mewtwo, Lugia, Ho-Oh, Weather Trio, Creation Trio, Tao Trio, and more
- **Mythical**: Mew, Celebi, Jirachi, Arceus, and more (special encounters only)

### Generation Support

- **Gen 1 (Kanto)**: #001-151
- **Gen 2 (Johto)**: #152-251
- **Gen 3 (Hoenn)**: #252-386
- **Gen 4 (Sinnoh)**: #387-493
- **Gen 5 (Unova)**: #494-649
- **Gen 6 (Kalos)**: #650-721
- **Gen 7 (Alola)**: #722-809
- **Gen 8 (Galar)**: #810-905
- **Gen 9 (Paldea)**: #906-1025

### Shiny Pokemon

- Base rate: 1/100
- Streak bonus: +0.5% per day of streak
- Perfect week: Boosted shiny chance

### Streak Rewards

- 3 days: Great Balls (better catch rate)
- 7 days: Evolution Stone
- 14 days: Ultra Balls
- 30 days: Master Ball
- 100 days: Legendary Ticket

### Wellbeing Bonuses

- **Good mood**: Pokemon happiness boost
- **Exercise**: Type-specific encounter bonuses
- **Good sleep**: Catch rate boost
- **Hydration goal**: Water-type bonus
- **Meditation**: Psychic/Fairy bonus
- **Journaling**: Friendship evolution bonus

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
- **Hydration goal (8 glasses)**: Water-type bonus
- **Meditation**: Psychic/Fairy bonus
- **Exercise**: Fighting-type bonus

---

## Recent Fixes & Behavior Notes

- **EV/IV persistence**: Pokemon now persist their EV/IV dictionaries, so every completion permanently boosts the lead Pokémon’s stats (see `pokedo/data/database.py` and `pokedo/core/pokemon.py`).
- **Affinity-aware encounters**: The reward engine filters rarity pools by task/wellbeing affinities, backfills missing type data (`_ensure_pokedex_entry_types`), and consumes the best available ball (master/ultra/great) for each attempt (`pokedo/core/rewards.py`).
- **Pokedex tracking parity**: Every catch or evolution increments `pokedex_seen`/`pokedex_caught` (with first-caught timestamps and shiny flags), keeping trainer completion metrics in sync (`pokedo/cli/commands/tasks.py`, `pokedo/cli/commands/pokemon.py`).
- **Priority ordering & streak sync**: Task listings now sort using explicit numeric weights, and streak best counters update immediately on first-day or resumed streaks (`pokedo/data/database.py`, `pokedo/core/trainer.py`).

### EV/IV System

This system provides RPG mechanics for training your Pokemon's stats:

- **IVs (Individual Values):** Represents a Pokemon's innate potential (0-31 per stat), assigned randomly at capture.
- **EVs (Effort Values):** Training points gained by completing tasks (max 510 total, 252 per stat).

**Task Categories influence which stats are trained:**

| Task Category | Stat Trained    |
| ------------- | --------------- |
| Work          | Special Attack  |
| Exercise      | Attack          |
| Learning      | Special Defense |
| Health        | HP              |
| Personal      | Defense         |
| Creative      | Speed           |

**Task Difficulty determines the EV yield:**

| Difficulty | EV Yield |
| ---------- | -------- |
|------------|----------|
| Easy       | 1 EV     |
| Medium     | 2 EVs    |
| Hard       | 4 EVs    |
| Epic       | 8 EVs    |

## Data Storage

All data is stored locally in `~/.pokedo/`:

- `pokedo.db`: SQLite database
- `cache/`: Cached PokeAPI data
- `cache/sprites/`: Downloaded Pokemon sprites

## Development

The project includes a FastAPI server (`pokedo/server.py`) for future cloud synchronization and currently provides **user authentication (registration/login with JWT)**.

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run tests with coverage
pytest --cov=pokedo

# Run specific test file
pytest tests/test_tasks.py
```

For more development information, see:

- [Architecture Documentation](docs/ARCHITECTURE.md) - System design and code structure
- [Contributing Guide](docs/CONTRIBUTING.md) - How to contribute to PokeDo
- [API Reference](docs/API.md) - Internal API documentation

---

## Troubleshooting

### Common Issues

**"Command not found: pokedo"**

- Ensure you installed with `pip install -e .`
- Check that your virtual environment is activated
- Try running with `python -m pokedo` instead

**"Database error" on first run**

- Run `pokedo init --name "YourName"` to initialize the database
- Check write permissions in your home directory

**`TypeError: cannot use 'pokedo.core.task.Task' as a dict key (unhashable type: 'Task')` in TUI**

- Cause: a Textual widget/screen used `self._task` for a domain `Task`, which conflicts with Textual's internal `Widget._task` asyncio lifecycle field.
- Fixed in current code by renaming state fields to domain-specific names like `_detail_task`, `_editing_task`, and `_completed_task`.
- For future TUI changes, do not store app models in `self._task`; always use explicit names such as `_selected_task` or `_editing_task`.

**Slow initialization**

- Full initialization downloads data for 1025 Pokemon
- Use `--quick` flag for Gen 1 only (151 Pokemon)
- Use `--gen N` to initialize a specific generation
- Use `--concurrency N` to increase parallel PokeAPI requests

**Pokemon sprites not displaying**

- Sprites require terminal with image support (iTerm2, Kitty, etc.)
- Text fallback is used in unsupported terminals
- Check `~/.pokedo/cache/sprites/` for cached images

**API rate limiting**

- PokeAPI is free and has generous limits
- Data is cached locally after first fetch
- Clear cache: delete `~/.pokedo/cache/` folder

### Reset Data

```bash
# Remove all PokeDo data (start fresh)
rm -rf ~/.pokedo

# Reinitialize
pokedo init --name "YourName"
```

---

## FAQ

**Q: Can I play offline?**
A: Yes, after initial setup. All Pokemon data is cached locally.

**Q: How do I backup my progress?**
A: Copy the `~/.pokedo/` directory. The `pokedo.db` file contains all your data.

**Q: What happens if I miss a day?**
A: Your daily streak resets to 0, but your best streak is preserved.

**Q: Can I catch legendary Pokemon?**
A: Yes! Epic and hard tasks have small chances to encounter legendaries. Mythical Pokemon require special tickets earned from long streaks.

**Q: How does shiny hunting work?**
A: Base shiny rate is 1%. Each day of your streak adds 0.5% (up to 10% max).

**Q: Can I have multiple profiles?**
A: Yes. Each trainer profile is stored in the same local database. The CLI uses the default profile, and the TUI lets you switch profiles (press `p`) and set a new default.

**Q: Does wellbeing tracking affect gameplay?**
A: Yes! Good sleep improves catch rates, hydration goals boost Water-type encounters, and meditation increases Psychic/Fairy encounters.

**Q: How do I evolve Pokemon?**
A: Level up your Pokemon by completing tasks. When evolution requirements are met, use `pokedo pokemon evolve <id>`.

**Q: What is the difference between CLI and TUI?**
A: The CLI (Command Line Interface) uses typed commands like `pokedo task add`. The TUI (Terminal User Interface) launched with `pokedo tui` provides an interactive graphical experience with keyboard navigation, tabbed views, and real-time updates.

---

## Project Structure

```
pokedo/
├── cli/           # Command-line interface
├── core/          # Business logic and models
├── data/          # Database and API clients
├── tui/           # Terminal user interface (Textual)
│   ├── app.py         # Main TUI application
│   ├── screens/       # Screen classes (tasks, etc.)
│   ├── widgets/       # Reusable UI components
│   └── styles/        # Textual CSS styling
└── utils/         # Configuration and helpers
```

See [ARCHITECTURE.md](docs/ARCHITECTURE.md) for detailed documentation.

---

## Credits

- Pokemon data from [PokeAPI](https://pokeapi.co/)
- CLI built with [Typer](https://typer.tiangolo.com/) and [Rich](https://rich.readthedocs.io/)
- TUI built with [Textual](https://textual.textualize.io/)
- Inspired by the Pokemon franchise by Nintendo/Game Freak

---

## License

MIT License - see LICENSE file for details.
