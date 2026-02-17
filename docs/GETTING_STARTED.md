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

To test the synchronization features, you can run the local FastAPI development server.

```bash
uvicorn pokedo.server:app --reload --port 8000
```

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

## Running Tests

Run the full test suite to ensure everything is working correctly.

```bash
pytest
```

## Notes

- The application uses a local-first SQLite database by default (`~/.pokedo/pokedo.db`).
- If you are working on the Sync client, remember to initialize the sync table: `python -m pokedo.data.sync init`.
- For Textual development, avoid using `self._task` for domain models in widgets/screens/modals. `_task` is reserved by Textual internals; use explicit names like `self._selected_task` or `self._editing_task`.
