# Troubleshooting Guide

Common issues and their fixes while working on PokeDo.

## Environment Setup

### Missing Dependencies

- **Symptom:** `ModuleNotFoundError` when running the CLI or tests.
- **Fix:** Ensure the virtual environment is active and run `pip install -e ".[dev]"`.

### Database Permission Errors

- **Symptom:** `sqlite3.OperationalError: unable to open database file`.
- **Fix:** Delete `~/.pokedo/pokedo.db` and rerun `pokedo init`. Confirm you have write access to the directory.

## CLI Issues

### Typer Option Errors

- **Symptom:** `No such option` or `OptionInfo` type errors when calling shortcuts.
- **Fix:** Use the namespaced command (`pokedo pokemon pokedex`) when you need advanced options. Shortcuts are guarded wrappers and may have fewer flags.

### Pokedex Empty After Init

- **Symptom:** `pokedo pokedex` shows empty data even after initializing.
- **Fix:** Run `pokedo init --quick` again; ensure the PokeAPI requests succeeded and check for networking issues.

## TUI Issues

### Textual `_task` Name Collision

- **Symptom:** Exiting the task screen raises `TypeError: cannot use 'pokedo.core.task.Task' as a dict key (unhashable type: 'Task')`.
- **Cause:** A widget/screen attribute named `self._task` was used for a domain `Task` object. In Textual, `_task` is an internal async lifecycle field and must remain an `asyncio.Task`.
- **Fix:** Rename app state attributes to explicit names such as `self._detail_task`, `self._editing_task`, `self._completed_task`, or `self._selected_task`. Do not use `self._task` in Textual components for domain data.

## Testing Problems

### Pytest Missing

- **Symptom:** `No module named pytest`.
- **Fix:** Install dev dependencies (`pip install -e ".[dev]"`) and rerun tests.

### Database Tests Interfering with Local Data

- **Symptom:** Tests modify your real `~/.pokedo` database.
- **Fix:** Use the `isolated_db` fixture from `tests/conftest.py` and avoid importing the global `db` outside fixtures in tests.

### Server Tests Failing with Postgres Errors

- **Symptom:** `test_server.py` tries to connect to PostgreSQL and fails.
- **Fix:** Server tests use in-memory SQLite with `StaticPool`. If you see Postgres connection errors, ensure you are not overriding `POKEDO_DATABASE_URL` in your environment. The test fixtures handle database setup automatically.

## Server / Multiplayer Issues

### Cannot Connect to Server

- **Symptom:** `ConnectionRefusedError` when running battle commands.
- **Fix:** Make sure the server is running (`uvicorn pokedo.server:app --port 8000` or `docker-compose up -d`). Check that `POKEDO_SERVER_URL` is set correctly if not using the default `http://localhost:8000`.

### PostgreSQL Connection Refused

- **Symptom:** Server fails to start with `Connection refused` to port 5432.
- **Fix:** Start the database with `docker-compose up -d db` and wait a few seconds for it to initialize. Verify `POKEDO_DATABASE_URL` matches your Docker setup (default: `postgresql://pokedo:pokedopass@localhost:5432/pokedo`).

### JWT Token Expired

- **Symptom:** `401 Unauthorized` when making authenticated requests.
- **Fix:** Re-authenticate via `POST /token` to get a fresh access token. The default expiry is 30 minutes.

### Battle Stuck in Pending State

- **Symptom:** Battle was challenged but never moved to active.
- **Fix:** The opponent must accept (`POST /battles/{id}/accept`), then both players must submit teams (`POST /battles/{id}/team`). The battle only becomes active once both teams are submitted.

## Pydantic Model Errors

### FieldInfo clashes

- **Symptom:** `PydanticUserError: Error when building FieldInfo from annotated attribute`.
- **Fix:** Ensure datetime/date fields use module-qualified names (`import datetime as dt`) or callable factories (e.g., `Field(default_factory=dt.date.today)`). Clear `__pycache__` if errors persist.

## Logging and Debugging Tips

- Set `POKEDO_DEBUG=1` (if implemented) or instrument CLI commands with temporary prints to trace logic.
- Clear caches in `~/.pokedo/cache` if sprite downloads or API responses look stale.

## Getting Support

- Re-read `docs/CONTRIBUTING.md` for setup steps.
- See `docs/MULTIPLAYER.md` for battle system details.
- Check open issues in the repository for similar problems.
- When filing a new issue, include OS, Python version, and exact command output.
