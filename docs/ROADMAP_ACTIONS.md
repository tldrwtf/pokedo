# Actionable Roadmap

## Sprint 1: Foundation (Completed)

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

Extra items:

- [x] `docs/EV_IV_SPEC.md` improvements and examples
- [x] `tools/cli_example.py` convert to use repo's models
- [x] Add `DATABASE_URL` env handling in `pokedo/data/database.py`

## Sprint 2: Multiplayer (Completed)

1. Battle engine

- [x] `pokedo/core/moves.py` -- Move model, 18-type chart, Gen V+ damage formula, 25 natures
- [x] `pokedo/core/battle.py` -- BattleState machine, BattleEngine.resolve_turn(), ELO calc
- [x] `pokedo/core/pokemon.py` -- `to_battle_pokemon()` conversion, nature/moves fields
- [x] `pokedo/core/trainer.py` -- PvP stats (battle_wins/losses/draws, elo_rating, pvp_rank)

2. Server infrastructure

- [x] `pokedo/data/server_models.py` -- ServerUser, BattleRecord (SQLModel/Postgres)
- [x] `pokedo/server.py` -- Full REST API (auth, battles, leaderboard, sync)
- [x] FastAPI lifespan context manager (replaced deprecated `on_event`)
- [x] PostgreSQL + Docker Compose support

3. Battle API endpoints

- [x] POST `/battles/challenge` -- send challenge
- [x] POST `/battles/{id}/accept` and `/battles/{id}/decline`
- [x] POST `/battles/{id}/team` -- submit team (snapshot-based)
- [x] POST `/battles/{id}/action` -- submit move/switch/forfeit
- [x] GET `/battles/{id}` -- censored battle state
- [x] GET `/battles/{id}/history` -- turn event log
- [x] GET `/battles/history/me` -- completed battle history

4. Leaderboard

- [x] GET `/leaderboard` -- global rankings (sortable by ELO, wins, losses)
- [x] GET `/leaderboard/{username}` -- individual stats
- [x] ELO-based rank system (Youngster through Pokemon Master)

5. CLI commands

- [x] `pokedo/cli/commands/battle.py` -- challenge, accept, team, move, switch, forfeit, status, history
- [x] `pokedo/cli/commands/leaderboard.py` -- show, me

6. Documentation

- [x] `docs/MULTIPLAYER.md` -- full multiplayer guide

7. Test suite

- [x] `tests/test_moves.py` -- 51 tests (type chart, damage, movesets, natures)
- [x] `tests/test_battle.py` -- 91 tests (state machine, turn resolution, edge cases)
- [x] `tests/test_server.py` -- 61 tests (auth, battles, leaderboard, validation)
- [x] Battle fixtures in `tests/conftest.py`
- [x] All 556 tests passing

## Suggested Next Items

- [ ] WebSocket-based real-time battles with timers
- [ ] Doubles (2v2) battle format
- [ ] Hold items and in-battle item use
- [ ] Pokemon abilities affecting battle mechanics
- [ ] Tournament bracket mode
- [ ] Battle spectating
- [ ] Full bidirectional sync (pull from server)
