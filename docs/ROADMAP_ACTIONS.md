# Actionable Roadmap (first sprint)

1. EV/IV core

- [x] Add `stat_affinity` to `pokedo/core/task.py`
- [x] Add `evs` and `ivs` JSON fields to `pokedo/core/pokemon.py`
- [x] Implement `add_evs()` helpers + unit tests

2. Trainer Classes

- Add `TrainerClass` enum and model
- Add CLI commands to choose class

3. Sync API skeleton

- Add FastAPI `pokedo/server.py` and Docker compose
- Add tests for `/sync` endpoint

4. Developer ergonomics

- Add `docs/GETTING_STARTED.md`
- Add examples in `tools/` and small integration tests

Suggested next issues (small, PR-sized):

- `docs/EV_IV_SPEC.md` improvements and examples
- `tools/cli_example.py` convert to use repo's models
- Add `DATABASE_URL` env handling in `pokedo/data/database.py`
