"""Reward and encounter system for PokeDo."""

import random
from datetime import date

from pokedo.core.pokemon import Pokemon, PokemonRarity
from pokedo.core.task import Task
from pokedo.core.trainer import Trainer
from pokedo.data.pokeapi import (
    LEGENDARY_IDS,
    MYTHICAL_IDS,
    PARADOX_IDS,
    PSEUDO_LEGENDARY_IDS,
    STARTER_FINAL_IDS,
    ULTRA_BEAST_IDS,
    create_pokemon_sync,
)
from pokedo.utils.config import config
from pokedo.utils.helpers import weighted_random_choice


def _generate_pokemon_pools() -> dict[PokemonRarity, list[int]]:
    """Generate Pokemon pools by rarity for all generations."""
    max_id = config.max_pokemon_id

    # Start with all Pokemon IDs
    all_ids = set(range(1, max_id + 1))

    # Remove special categories
    special = LEGENDARY_IDS | MYTHICAL_IDS | PSEUDO_LEGENDARY_IDS | STARTER_FINAL_IDS | ULTRA_BEAST_IDS | PARADOX_IDS

    # Regular Pokemon (not in special categories)
    regular = all_ids - special

    # Classify regular Pokemon by estimated rarity
    # Using generation-based heuristics + position in evolutionary lines
    common = []
    uncommon = []
    rare = []

    for pid in regular:
        # Determine generation
        gen = None
        for g, (start, end) in config.generation_ranges.items():
            if start <= pid <= end:
                gen = g
                break

        if gen is None:
            common.append(pid)
            continue

        # Heuristic: Pokemon ending in certain patterns tend to be evolved/rarer
        # This is approximate - real rarity would come from API data
        gen_start, _gen_end = config.generation_ranges[gen]
        position_in_gen = pid - gen_start

        # Common Pokemon tend to be early route Pokemon
        # Using modular arithmetic as rough heuristic
        if position_in_gen % 10 < 4:
            common.append(pid)
        elif position_in_gen % 10 < 7:
            uncommon.append(pid)
        else:
            rare.append(pid)

    return {
        PokemonRarity.COMMON: common,
        PokemonRarity.UNCOMMON: uncommon,
        PokemonRarity.RARE: rare + list(PARADOX_IDS),
        PokemonRarity.EPIC: list(PSEUDO_LEGENDARY_IDS | STARTER_FINAL_IDS | ULTRA_BEAST_IDS),
        PokemonRarity.LEGENDARY: list(LEGENDARY_IDS),
        PokemonRarity.MYTHICAL: list(MYTHICAL_IDS),
    }


# Generate pools on module load
POKEMON_BY_RARITY = _generate_pokemon_pools()


class EncounterResult:
    """Result of a Pokemon encounter."""

    def __init__(
        self,
        encountered: bool,
        caught: bool,
        pokemon: Pokemon | None = None,
        is_shiny: bool = False,
        xp_earned: int = 0,
        level_up: bool = False,
        new_level: int = 0,
        streak_continued: bool = True,
        streak_count: int = 0,
        badges_earned: list | None = None,
        items_earned: dict | None = None
    ):
        self.encountered = encountered
        self.caught = caught
        self.pokemon = pokemon
        self.is_shiny = is_shiny
        self.xp_earned = xp_earned
        self.level_up = level_up
        self.new_level = new_level
        self.streak_continued = streak_continued
        self.streak_count = streak_count
        self.badges_earned = badges_earned or []
        self.items_earned = items_earned or {}


class RewardEngine:
    """Engine for calculating rewards and triggering encounters."""

    def __init__(self, generation_filter: list[int] | None = None):
        """Initialize reward engine.

        Args:
            generation_filter: Optional list of generation numbers to include.
                            If None, all generations are included.
        """
        self.base_catch_rate = config.base_catch_rate
        self.shiny_rate = config.shiny_rate
        self.streak_shiny_bonus = config.streak_shiny_bonus
        self.generation_filter = generation_filter
        self._filtered_pools = None

    def _get_filtered_pools(self) -> dict[PokemonRarity, list[int]]:
        """Get Pokemon pools filtered by generation."""
        if self._filtered_pools is not None:
            return self._filtered_pools

        if self.generation_filter is None:
            return POKEMON_BY_RARITY

        # Filter pools by generation
        filtered = {}
        for rarity, pokemon_ids in POKEMON_BY_RARITY.items():
            filtered_ids = []
            for pid in pokemon_ids:
                for gen in self.generation_filter:
                    if gen in config.generation_ranges:
                        start, end = config.generation_ranges[gen]
                        if start <= pid <= end:
                            filtered_ids.append(pid)
                            break
            filtered[rarity] = filtered_ids if filtered_ids else POKEMON_BY_RARITY[rarity]

        self._filtered_pools = filtered
        return filtered

    def process_task_completion(
        self,
        task: Task,
        trainer: Trainer,
        type_affinity_bonus: list[str] | None = None
    ) -> EncounterResult:
        """Process task completion and generate rewards."""
        result = EncounterResult(encountered=False, caught=False)

        # Award XP
        result.xp_earned = task.xp_reward
        new_level = trainer.add_xp(result.xp_earned)
        if new_level:
            result.level_up = True
            result.new_level = new_level

        # Update streak
        today = date.today()
        streak_continued, streak_count = trainer.update_streak(today)
        result.streak_continued = streak_continued
        result.streak_count = streak_count

        # Check for streak rewards
        result.items_earned = self._check_streak_rewards(streak_count)

        # Determine if encounter happens
        encounter_chance = self._calculate_encounter_chance(task, trainer)
        if random.random() < encounter_chance:
            result.encountered = True

            # Determine rarity
            rarity_weights = task.get_pokemon_rarity_weights()
            rarity = self._select_rarity(rarity_weights, streak_count)

            # Check for shiny
            result.is_shiny = self._check_shiny(streak_count)

            # Select Pokemon
            pokemon_id = self._select_pokemon(
                rarity,
                task.get_type_affinity(),
                type_affinity_bonus
            )

            # Create Pokemon instance
            pokemon = create_pokemon_sync(
                pokemon_id,
                is_shiny=result.is_shiny,
                catch_location=task.category.value
            )

            if pokemon:
                # Attempt catch
                catch_rate = self._calculate_catch_rate(rarity, trainer)
                if random.random() < catch_rate:
                    result.caught = True
                    result.pokemon = pokemon
                else:
                    # Pokemon escaped but still return it for display
                    result.pokemon = pokemon

        # Update trainer stats
        trainer.tasks_completed += 1
        trainer.last_active_date = today

        return result

    def _calculate_encounter_chance(self, task: Task, trainer: Trainer) -> float:
        """Calculate chance of encountering a Pokemon."""
        base_chance = 0.7  # 70% base encounter rate

        # Difficulty bonus
        difficulty_bonus = {
            "easy": 0.0,
            "medium": 0.05,
            "hard": 0.10,
            "epic": 0.15
        }
        base_chance += difficulty_bonus.get(task.difficulty.value, 0)

        # Streak bonus (up to 10% bonus)
        streak_bonus = min(trainer.daily_streak.current_count * 0.01, 0.10)
        base_chance += streak_bonus

        return min(base_chance, 0.95)  # Cap at 95%

    def _select_rarity(self, weights: dict[str, float], streak_count: int) -> PokemonRarity:
        """Select rarity based on weights and streak."""
        # Adjust weights based on streak
        adjusted = weights.copy()

        # Streak bonuses for higher rarities
        if streak_count >= 7:
            adjusted["rare"] = adjusted.get("rare", 0) + 0.05
            adjusted["common"] = max(0, adjusted.get("common", 0) - 0.05)

        if streak_count >= 14:
            adjusted["epic"] = adjusted.get("epic", 0) + 0.03
            adjusted["rare"] = adjusted.get("rare", 0) + 0.02

        if streak_count >= 30:
            adjusted["legendary"] = adjusted.get("legendary", 0) + 0.02
            adjusted["epic"] = adjusted.get("epic", 0) + 0.03

        if streak_count >= 50:
            adjusted["mythical"] = adjusted.get("mythical", 0) + 0.01
            adjusted["legendary"] = adjusted.get("legendary", 0) + 0.02

        # Normalize weights
        total = sum(adjusted.values())
        if total > 0:
            adjusted = {k: v / total for k, v in adjusted.items()}

        selected = weighted_random_choice(adjusted)
        return PokemonRarity(selected)

    def _select_pokemon(
        self,
        rarity: PokemonRarity,
        type_affinity: list[str],
        bonus_types: list[str] | None = None
    ) -> int:
        """Select a Pokemon ID based on rarity and type affinity."""
        pools = self._get_filtered_pools()
        available = pools.get(rarity, pools[PokemonRarity.COMMON])

        if not available:
            # Fallback to common if rarity pool is empty
            available = pools[PokemonRarity.COMMON]

        return random.choice(available)

    def _check_shiny(self, streak_count: int) -> bool:
        """Check if Pokemon should be shiny."""
        shiny_chance = self.shiny_rate + (streak_count * self.streak_shiny_bonus)
        # Cap at 10% max shiny chance
        shiny_chance = min(shiny_chance, 0.10)
        return random.random() < shiny_chance

    def _calculate_catch_rate(self, rarity: PokemonRarity, trainer: Trainer) -> float:
        """Calculate catch rate based on rarity and trainer level."""
        base_rates = {
            PokemonRarity.COMMON: 0.90,
            PokemonRarity.UNCOMMON: 0.75,
            PokemonRarity.RARE: 0.50,
            PokemonRarity.EPIC: 0.30,
            PokemonRarity.LEGENDARY: 0.15,
            PokemonRarity.MYTHICAL: 0.05
        }

        base = base_rates.get(rarity, 0.5)

        # Trainer level bonus (up to 20%)
        level_bonus = min(trainer.level * 0.02, 0.20)

        # Inventory items could modify this
        if "master_ball" in trainer.inventory and trainer.inventory["master_ball"] > 0:
            return 1.0  # Guaranteed catch
        if "ultra_ball" in trainer.inventory and trainer.inventory["ultra_ball"] > 0:
            base += 0.20
        elif "great_ball" in trainer.inventory and trainer.inventory["great_ball"] > 0:
            base += 0.10

        return min(base + level_bonus, 0.95)

    def _check_streak_rewards(self, streak_count: int) -> dict[str, int]:
        """Check if streak milestones award items."""
        rewards = {}

        if streak_count == 3:
            rewards["great_ball"] = 3
        elif streak_count == 7:
            rewards["evolution_stone"] = 1
        elif streak_count == 14:
            rewards["ultra_ball"] = 5
        elif streak_count == 21:
            rewards["rare_candy"] = 3
        elif streak_count == 30:
            rewards["master_ball"] = 1
        elif streak_count == 50:
            rewards["legendary_ticket"] = 1
        elif streak_count == 100:
            rewards["mythical_ticket"] = 1

        # Bonus items at every 10-day milestone
        if streak_count > 0 and streak_count % 10 == 0:
            rewards["great_ball"] = rewards.get("great_ball", 0) + 5
            rewards["rare_candy"] = rewards.get("rare_candy", 0) + 1

        return rewards

    def trigger_guaranteed_encounter(
        self,
        rarity: PokemonRarity,
        trainer: Trainer,
        is_shiny: bool = False
    ) -> Pokemon | None:
        """Trigger a guaranteed Pokemon encounter of specific rarity."""
        pools = self._get_filtered_pools()
        pool = pools.get(rarity, pools[PokemonRarity.COMMON])
        if not pool:
            pool = pools[PokemonRarity.COMMON]
        pokemon_id = random.choice(pool)
        return create_pokemon_sync(pokemon_id, is_shiny=is_shiny)

    def get_pokemon_count_by_rarity(self) -> dict[str, int]:
        """Get count of Pokemon available in each rarity tier."""
        pools = self._get_filtered_pools()
        return {rarity.value: len(ids) for rarity, ids in pools.items()}


# Global reward engine instance (all generations)
reward_engine = RewardEngine()
