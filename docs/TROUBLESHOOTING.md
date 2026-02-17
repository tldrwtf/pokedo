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

## Pydantic Model Errors

### FieldInfo clashes

- **Symptom:** `PydanticUserError: Error when building FieldInfo from annotated attribute`.
- **Fix:** Ensure datetime/date fields use module-qualified names (`import datetime as dt`) or callable factories (e.g., `Field(default_factory=dt.date.today)`). Clear `__pycache__` if errors persist.

## Logging and Debugging Tips

- Set `POKEDO_DEBUG=1` (if implemented) or instrument CLI commands with temporary prints to trace logic.
- Clear caches in `~/.pokedo/cache` if sprite downloads or API responses look stale.

## Getting Support

- Re-read `docs/CONTRIBUTING.md` for setup steps.
- Check open issues in the repository for similar problems.
- When filing a new issue, include OS, Python version, and exact command output.
