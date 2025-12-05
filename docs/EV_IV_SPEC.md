# EV / IV Spec (Pokedo Expansion) - Minimal Reference

**Status:** Partially Implemented (Core Models & Helpers done; DB persistence pending)

Overview:

- EVs (Effort Values): Track training per-stat. Max 510 total, 252 per stat.
- IVs (Individual Values): 0-31 per stat, set at capture.

Task -> Stat affinity [Implemented]:

- work -> spa (Special Attack)
- exercise -> atk (Attack)
- learning -> spd (Special Defense)
- health -> hp (HP)
- personal -> def (Defense)
- creative -> spe (Speed)

Task difficulty -> EV yield (base) [Implemented]:

- easy: 1
- medium: 2
- hard: 4
- epic: 8

Rules:

- On task completion, active Pokémon receives EVs = task_difficulty.
- Cap enforcement: per-stat cap and total cap.
- Vitamins (consumables) add fixed EVs but cannot exceed caps.
- IVs assigned at capture randomly in [0,31]; breeding can inherit.

Implementation notes:

- [x] `evs` and `ivs` fields in `Pokemon` model (dict[str, int]).
- [x] Helper functions: `add_evs(stat, amount)`, `remaining_evs`, `assign_ivs()`.
- [ ] Database persistence (SQLite schema update).

## Examples

**Scenario 1: Balanced Training**
- Task: "Write Report" (Category: Work -> Sp. Atk, Difficulty: Medium -> 2 EVs)
- Active Pokemon: Pikachu (Current Sp. Atk EVs: 0)
- **Result:** Pikachu gains +2 Sp. Atk EVs. Total Sp. Atk: 2.

**Scenario 2: Hitting the Cap**
- Task: "Marathon" (Category: Exercise -> Attack, Difficulty: Epic -> 8 EVs)
- Active Pokemon: Machamp (Current Attack EVs: 250, Total EVs: 508)
- **Result:**
  - Per-stat cap (252): Can add 2.
  - Total cap (510): Can add 2.
  - Machamp gains +2 Attack EVs. (6 wasted).
