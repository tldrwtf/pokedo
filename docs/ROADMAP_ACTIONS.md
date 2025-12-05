# Actionable Roadmap (first sprint)

1. EV/IV core

- [x] Add `stat_affinity` to `pokedo/core/task.py`
- [x] Add `evs` and `ivs` JSON fields to `pokedo/core/pokemon.py`
- [x] Implement `add_evs()` helpers + unit tests

2. Trainer Classes

- [x] Add `TrainerClass` enum and model
- [x] Add CLI commands to choose class

3. Sync API skeleton

- [x] Add FastAPI `pokedo/server.py` and Docker compose
- [x] Add tests for `/sync` endpoint (and auth)

4. Developer ergonomics

- [x] Add `docs/GETTING_STARTED.md`
- [x] Add examples in `tools/` and small integration tests

Suggested next issues (small, PR-sized):

- [x] `docs/EV_IV_SPEC.md` improvements and examples
- [x] `tools/cli_example.py` convert to use repo's models
- [x] Add `DATABASE_URL` env handling in `pokedo/data/database.py`
