# PokeDo

A Pokemon-themed CLI task manager and wellbeing tracker. Complete tasks to catch Pokemon, build your collection, and track your mental and physical wellbeing.

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
- Daily streaks with milestone rewards
- Achievement badges
- Inventory system (Pokeballs, evolution items)

## Installation

```bash
cd pokedo
pip install -e .
```

## Usage

### Initialize
```bash
# Full initialization (all 1025 Pokemon - takes a few minutes first time)
pokedo init --name "Ash"

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

# Profile
pokedo profile
pokedo stats profile

# Streaks
pokedo streaks

# Badges
pokedo badges

# Inventory
pokedo stats inventory

# History
pokedo stats history --days 14
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

## Data Storage

All data is stored locally in `~/.pokedo/`:
- `pokedo.db`: SQLite database
- `cache/`: Cached PokeAPI data
- `cache/sprites/`: Downloaded Pokemon sprites

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest
```

## Credits

- Pokemon data from [PokeAPI](https://pokeapi.co/)
- Built with [Typer](https://typer.tiangolo.com/) and [Rich](https://rich.readthedocs.io/)
