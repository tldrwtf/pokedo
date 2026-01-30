# EV / IV Spec (Pokedo Expansion) - Reference

**Status:** Implemented

## Overview

- **EVs (Effort Values):** Track training per-stat. Max 510 total, 252 per stat.
- **IVs (Individual Values):** 0-31 per stat, set at capture.
- **Base Stats:** Species-specific stats fetched from PokeAPI.

## Stat Calculation Formula

Pokemon stats are calculated using the official Pokemon formula:

```
HP = ((2 * base + iv + ev/4) * level / 100) + level + 10
Other Stats = ((2 * base + iv + ev/4) * level / 100) + 5
```

Where:
- `base` = Species base stat from PokeAPI
- `iv` = Individual Value (0-31, randomized at capture)
- `ev` = Effort Value (0-252 per stat, 510 total max)
- `level` = Pokemon level (1-100)

## Task to Stat Affinity

| Task Category | Stat | Abbreviation |
|---------------|------|--------------|
| Work | Special Attack | spa |
| Exercise | Attack | atk |
| Learning | Special Defense | spd |
| Health | HP | hp |
| Personal | Defense | def |
| Creative | Speed | spe |

## Task Difficulty to EV Yield

| Difficulty | EVs Gained |
|------------|------------|
| Easy | 1 |
| Medium | 2 |
| Hard | 4 |
| Epic | 8 |

## Rules

- On task completion, the lead Pokemon in the active team receives EVs based on task category and difficulty.
- Cap enforcement: per-stat cap (252) and total cap (510) are both enforced.
- IVs are assigned at capture randomly in [0,31] range.
- EVs and IVs are displayed in the `pokemon info` command.

## Implementation Details

### Pokemon Model (pokedo/core/pokemon.py)
- [x] `evs` field: dict[str, int] - EV values per stat
- [x] `ivs` field: dict[str, int] - IV values per stat
- [x] `base_stats` field: dict[str, int] - Species base stats
- [x] `add_evs(stat, amount)` - Add EVs with cap enforcement
- [x] `remaining_evs` property - Remaining EV points (510 - total)
- [x] `assign_ivs()` - Randomize IVs at capture
- [x] `calculate_stat(stat_name)` - Calculate actual stat value
- [x] `stats` property - Get all calculated stats

### PokedexEntry Model (pokedo/core/pokemon.py)
- [x] `base_stats` field: dict[str, int] - Species base stats

### Database (pokedo/data/database.py)
- [x] `pokemon.evs` TEXT column (JSON)
- [x] `pokemon.ivs` TEXT column (JSON)
- [x] `pokemon.base_stats` TEXT column (JSON)
- [x] `pokedex.base_stats` TEXT column (JSON)

### PokeAPI Client (pokedo/data/pokeapi.py)
- [x] Extract base stats from API response
- [x] `_extract_base_stats()` helper method
- [x] Base stats populated on Pokemon creation

### CLI Display (pokedo/cli/ui/displays.py)
- [x] Stats table in detailed Pokemon view
- [x] Shows calculated stat, EVs, and IVs per stat
- [x] Shows total EVs used

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

**Scenario 3: Viewing Stats**
```
pokedo pokemon info 1
```
Output shows:
```
Stats
 HP:  95  (  0 EV / 24 IV)
Atk:  55  (  0 EV / 18 IV)
Def:  40  (  0 EV / 31 IV)
SpA:  65  (252 EV / 15 IV)
SpD:  50  (  0 EV / 22 IV)
Spe:  90  (  0 EV / 28 IV)

Total EVs: 252/510
```
