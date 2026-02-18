# PokeDo Multiplayer -- PvP Battles & Leaderboard

## Overview

PokeDo multiplayer adds async turn-based Pokemon battles between trainers and a
global ELO-based leaderboard. All multiplayer logic runs through a self-hosted
FastAPI server backed by PostgreSQL.

**Key design principles:**

- **Async / turn-based** -- players submit actions independently; the server
  resolves each turn once both players have acted.
- **Server-authoritative** -- damage, status effects, and win conditions are
  calculated server-side. Clients send intents, not results.
- **Snapshot-based teams** -- when a battle starts, each player's Pokemon are
  snapshotted (stats, moves, nature). Local roster changes don't affect in-flight
  battles.
- **ELO rating system** -- K-factor 32, starting at 1000. Ranks are derived from
  ELO thresholds.

---

## Architecture

```
CLI (Typer/Rich)                     TUI (Textual)
    |                                     |
    | REST / JSON                         |
    v                                     v
FastAPI Server (pokedo/server.py, lifespan ctx manager)
    |
    |--- ServerUser, BattleRecord (SQLModel / Postgres)
    |--- BattleEngine  (pokedo/core/battle.py)
    |--- Moves & Types (pokedo/core/moves.py)
```

### Components

| Module                               | Purpose                                           |
|--------------------------------------|---------------------------------------------------|
| `pokedo/core/moves.py`               | 18-type chart, Move model, damage formula, natures |
| `pokedo/core/battle.py`              | Battle state machine, turn resolution, ELO calc    |
| `pokedo/core/pokemon.py`             | `nature`, `moves`, `to_battle_pokemon()` conversion|
| `pokedo/core/trainer.py`             | PvP stats (wins/losses/draws, ELO, rank)           |
| `pokedo/data/server_models.py`       | Postgres models (ServerUser, BattleRecord)         |
| `pokedo/data/pokeapi.py`             | Move fetching from PokeAPI                         |
| `pokedo/server.py`                   | Full REST API (auth, battles, leaderboard, sync)   |
| `pokedo/cli/commands/battle.py`      | CLI battle commands                                |
| `pokedo/cli/commands/leaderboard.py` | CLI leaderboard commands                           |

---

## Setup

### 1. Start PostgreSQL

```bash
docker-compose up -d db
```

### 2. Start the PokeDo server

```bash
# Option A: Direct
uvicorn pokedo.server:app --host 0.0.0.0 --port 8000

# Option B: Docker Compose (includes both DB and server)
docker-compose up -d
```

### 3. Set environment variables (optional)

| Variable             | Default                                                   | Description              |
|----------------------|-----------------------------------------------------------|--------------------------|
| `POKEDO_DATABASE_URL` | `postgresql://pokedo:pokedopass@localhost:5432/pokedo`    | Postgres connection URL  |
| `POKEDO_SECRET_KEY`   | `your-secret-key-keep-it-secret`                         | JWT signing secret       |
| `POKEDO_SERVER_URL`   | `http://localhost:8000`                                  | Server URL for CLI client|

### 4. Register an account

```bash
pokedo battle register -u myname -p mypassword
```

---

## Battle Flow

### 1. Challenge

```bash
pokedo battle challenge opponent_name -u myname -p mypass
# Returns a Battle ID
```

### 2. Accept

```bash
pokedo battle accept <battle-id> -u opponent -p theirpass
```

### 3. Submit Teams

Both players submit their team. The server picks the first N Pokemon based on
the battle format (1 for singles_1v1, 3 for singles_3v3, 6 for singles_6v6).

```bash
pokedo battle team <battle-id> -u myname -p mypass
```

The battle becomes **active** once both teams are submitted.

### 4. Take Turns

```bash
# Attack with move index 0-3
pokedo battle move <battle-id> -m 0 -u myname -p mypass

# Switch to team slot 1
pokedo battle switch <battle-id> 1 -u myname -p mypass

# Forfeit
pokedo battle forfeit <battle-id> -u myname -p mypass
```

The server holds each action until both players have submitted. Then it resolves
the turn and returns events (damage, faints, switches, status effects).

### 5. Check Status

```bash
pokedo battle status <battle-id> -u myname -p mypass
```

Shows your team, opponent team (censored HP/moves), turn events, and winner.

### 6. View History

```bash
pokedo battle history -u myname -p mypass -n 20
```

---

## Leaderboard

```bash
# Global leaderboard (sorted by ELO by default)
pokedo leaderboard show

# Sort by wins
pokedo leaderboard show --sort battle_wins

# Your own profile
pokedo leaderboard me -u myname
```

### Rank Thresholds

| ELO Range   | Rank           |
|-------------|----------------|
| < 1100      | Youngster      |
| 1100-1299   | Bug Catcher    |
| 1300-1499   | Ace Trainer    |
| 1500-1699   | Gym Leader     |
| 1700-1899   | Elite Four     |
| 1900-2099   | Champion       |
| >= 2100     | Pokemon Master |

---

## Battle Formats

| Format        | Team Size | Description                     |
|---------------|----------:|----------------------------------|
| `singles_1v1` |         1 | Single Pokemon duel              |
| `singles_3v3` |         3 | Pick 3, one active at a time     |
| `singles_6v6` |         6 | Full team, one active at a time  |

---

## Damage Formula

Uses the Generation V+ damage formula:

```
damage = ((2 * level / 5 + 2) * power * (atk / def) / 50 + 2)
         * STAB * type_effectiveness * critical * random(0.85-1.0)
```

- **STAB**: 1.5x if the move type matches the user's type
- **Critical**: 1.5x (6.25% base chance)
- **Type effectiveness**: 0x, 0.25x, 0.5x, 1x, 2x, 4x (dual types multiply)

---

## API Endpoints

### Authentication

| Method | Endpoint     | Description          |
|--------|-------------|----------------------|
| POST   | `/register` | Create account       |
| POST   | `/token`    | Login (returns JWT)  |

### Battles

| Method | Endpoint                    | Description                        |
|--------|-----------------------------|------------------------------------|
| POST   | `/battles/challenge`        | Send a challenge                   |
| GET    | `/battles/pending`          | List pending/active battles        |
| POST   | `/battles/{id}/accept`      | Accept challenge                   |
| POST   | `/battles/{id}/decline`     | Decline challenge                  |
| POST   | `/battles/{id}/team`        | Submit team                        |
| POST   | `/battles/{id}/action`      | Submit turn action                 |
| GET    | `/battles/{id}`             | Get battle state (censored)        |
| GET    | `/battles/{id}/history`     | Turn event log                     |
| GET    | `/battles/history/me`       | Completed battle history           |

### Leaderboard

| Method | Endpoint                    | Description                        |
|--------|-----------------------------|------------------------------------|
| GET    | `/leaderboard`              | Global rankings                    |
| GET    | `/leaderboard/{username}`   | Individual player stats            |

---

## Type Effectiveness Chart

The full 18-type effectiveness matrix is implemented in `pokedo/core/moves.py`.
Supports all standard type matchups from the main series games (Normal, Fire,
Water, Electric, Grass, Ice, Fighting, Poison, Ground, Flying, Psychic, Bug,
Rock, Ghost, Dragon, Dark, Steel, Fairy).

---

## Natures

25 natures are supported, each modifying two stats by +10% / -10% (or neutral).
Natures are assigned randomly when a Pokemon is caught and affect battle stat
calculations. See `NATURE_MODIFIERS` in `pokedo/core/moves.py`.

---

## Future Considerations

- **Real-time mode**: WebSocket-based battles with timers
- **Doubles**: 2v2 battle format
- **Items**: Hold items and in-battle item use
- **Abilities**: Pokemon abilities affecting battle mechanics
- **Tournaments**: Bracket-based tournament mode
- **Spectating**: Watch ongoing battles in real-time
- **Battle replays**: Save and share completed battles

---

## Testing

The multiplayer system has comprehensive test coverage:

| Test File | Tests | Scope |
|-----------|------:|-------|
| `tests/test_moves.py` | 51 | Type chart, damage calc, movesets, natures |
| `tests/test_battle.py` | 91 | State machine, turn resolution, edge cases |
| `tests/test_server.py` | 61 | Auth, battles, leaderboard, validation |

Run them with:

```bash
# All multiplayer tests
pytest tests/test_moves.py tests/test_battle.py tests/test_server.py -v

# Full suite (556 tests)
pytest
```
