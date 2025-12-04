# EV / IV Spec (Pokedo Expansion) — Minimal Reference

Overview:

- EVs (Effort Values): Track training per-stat. Max 510 total, 252 per stat.
- IVs (Individual Values): 0-31 per stat, set at capture.

Task -> Stat affinity:

- work -> spa
- exercise -> atk
- learning -> spd
- health -> hp
- chores -> def
- creative -> spe

Task difficulty -> EV yield (base):

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

- Store `evs` and `ivs` as JSON mapping stat string -> int for portability.
- Use integers for EV units (not derived stat points).
- Provide helper functions: `add_evs(pokemon, stat, amount)`, `remaining_evs(pokemon)`, `assign_ivs(pokemon)`.
