# Getting Started (Developer)

## Prerequisites

- Python 3.10+
- pip (Python package manager)
- Docker (Optional, for future PostgreSQL support)

## Installation

**Windows (cmd.exe):**

```cmd
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
```

**Linux/macOS:**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Running the CLI

1.  **Initialize the Database:**
    This downloads the initial Pokemon data cache.

    ```bash
    pokedo init --name "Dev" --quick
    ```

2.  **Basic Commands:**

    ```bash
    pokedo task add "Finish report" --category work --difficulty medium
    pokedo task list
    pokedo pokemon box
    ```

## Running the TUI

Launch the interactive Textual interface:

```bash
pokedo tui
```

Use `t` to open task management and `Escape` to return to the dashboard.

## Running the Server

To test the multiplayer battle system and synchronization features, start the
FastAPI server backed by PostgreSQL.

### Option A: Docker Compose (recommended)

```bash
# Start both PostgreSQL and the PokeDo server
docker-compose up -d
```

### Option B: Manual

```bash
# 1. Start a PostgreSQL instance (ensure POKEDO_DATABASE_URL is set)
# 2. Run the server
uvicorn pokedo.server:app --reload --port 8000
```

(Ensure you have installed development dependencies: `pip install -e ".[dev]"`)

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `POKEDO_DATABASE_URL` | `postgresql://pokedo:pokedopass@localhost:5432/pokedo` | Postgres connection URL |
| `POKEDO_SECRET_KEY` | `your-secret-key-keep-it-secret` | JWT signing secret |
| `POKEDO_SERVER_URL` | `http://localhost:8000` | Server URL for CLI client |

## Testing Authentication

You can use `curl` to test the registration and login flow.

**1. Register a user:**

```bash
curl -X POST http://localhost:8000/register \
  -H "Content-Type: application/json" \
  -d "{\"username\": \"me\", \"password\": \"secret\"}"
```

**2. Login to get a token:**

```bash
curl -X POST http://localhost:8000/token \
  -F "username=me" \
  -F "password=secret"
```

## Testing Battles

With the server running and two users registered:

```bash
# Challenge another player
pokedo battle challenge opponent_name -u me -p secret

# Accept the challenge (as the opponent)
pokedo battle accept <battle-id> -u opponent_name -p theirpass

# Submit teams
pokedo battle team <battle-id> -u me -p secret

# Make moves
pokedo battle move <battle-id> -m 0 -u me -p secret

# Check status
pokedo battle status <battle-id> -u me -p secret
```

## Running Tests

Run the full test suite to ensure everything is working correctly.

```bash
# All 556 tests
pytest

# Just multiplayer tests
pytest tests/test_moves.py tests/test_battle.py tests/test_server.py -v

# With short traceback
pytest --tb=short
```

## Notes

- The application uses a local-first SQLite database by default (`~/.pokedo/pokedo.db`).
- The multiplayer server uses PostgreSQL for shared state (battles, leaderboard).
- Server tests use in-memory SQLite (`StaticPool`) so no Postgres instance is needed to run tests.
- If you are working on the Sync client, remember to initialize the sync table: `python -m pokedo.data.sync init`.
- For Textual development, avoid using `self._task` for domain models in widgets/screens/modals. `_task` is reserved by Textual internals; use explicit names like `self._selected_task` or `self._editing_task`.
