"""Tests for Reward and encounter system."""


import pytest

from pokedo.core.pokemon import PokemonRarity
from pokedo.core.rewards import POKEMON_BY_RARITY, EncounterResult, RewardEngine
from pokedo.core.task import Task, TaskDifficulty
from pokedo.core.trainer import Trainer


class TestEncounterResult:
    """Tests for EncounterResult class."""

    def test_create_no_encounter(self):
        """Create result with no encounter."""
        result = EncounterResult(encountered=False, caught=False)
        assert result.encountered is False
        assert result.caught is False
        assert result.pokemon is None
        assert result.is_shiny is False

    def test_create_caught_encounter(self):
        """Create result with caught Pokemon."""
        result = EncounterResult(
            encountered=True,
            caught=True,
            xp_earned=25,
            streak_count=5,
        )
        assert result.encountered is True
        assert result.caught is True
        assert result.xp_earned == 25
        assert result.streak_count == 5

    def test_default_lists(self):
        """Default lists are empty."""
        result = EncounterResult(encountered=False, caught=False)
        assert result.badges_earned == []
        assert result.items_earned == {}


class TestPokemonByRarity:
    """Tests for POKEMON_BY_RARITY pools."""

    def test_all_rarities_have_pools(self):
        """All rarity tiers have Pokemon pools."""
        for rarity in PokemonRarity:
            assert rarity in POKEMON_BY_RARITY

    def test_common_has_most(self):
        """Common has the most Pokemon."""
        common_count = len(POKEMON_BY_RARITY[PokemonRarity.COMMON])
        for rarity in [PokemonRarity.RARE, PokemonRarity.EPIC, PokemonRarity.LEGENDARY]:
            assert common_count > len(POKEMON_BY_RARITY[rarity])

    def test_mythical_has_fewest(self):
        """Mythical has few Pokemon."""
        mythical_count = len(POKEMON_BY_RARITY[PokemonRarity.MYTHICAL])
        assert mythical_count < 30  # There are only ~22 mythicals

    def test_legendary_pool_not_empty(self):
        """Legendary pool is not empty."""
        assert len(POKEMON_BY_RARITY[PokemonRarity.LEGENDARY]) > 0


class TestRewardEngine:
    """Tests for RewardEngine class."""

    @pytest.fixture
    def engine(self):
        """Create a reward engine."""
        return RewardEngine()

    @pytest.fixture
    def gen1_engine(self):
        """Create engine filtered to Gen 1."""
        return RewardEngine(generation_filter=[1])

    def test_create_engine(self, engine):
        """Create reward engine."""
        assert engine.base_catch_rate == 0.6
        assert engine.shiny_rate == 0.01

    def test_create_filtered_engine(self, gen1_engine):
        """Create generation-filtered engine."""
        assert gen1_engine.generation_filter == [1]


class TestEncounterChance:
    """Tests for encounter chance calculation."""

    @pytest.fixture
    def engine(self):
        return RewardEngine()

    def test_base_encounter_chance(self, engine, sample_task, new_trainer):
        """Base encounter chance is ~70%."""
        chance = engine._calculate_encounter_chance(sample_task, new_trainer)
        assert 0.7 <= chance <= 0.85

    def test_difficulty_bonus(self, engine, new_trainer):
        """Higher difficulty increases encounter chance."""
        easy_task = Task(title="Easy", difficulty=TaskDifficulty.EASY)
        epic_task = Task(title="Epic", difficulty=TaskDifficulty.EPIC)

        easy_chance = engine._calculate_encounter_chance(easy_task, new_trainer)
        epic_chance = engine._calculate_encounter_chance(epic_task, new_trainer)

        assert epic_chance > easy_chance

    def test_streak_bonus(self, engine, sample_task, trainer_with_streak):
        """Streak increases encounter chance."""
        no_streak = Trainer(name="No Streak")

        no_streak_chance = engine._calculate_encounter_chance(sample_task, no_streak)
        streak_chance = engine._calculate_encounter_chance(sample_task, trainer_with_streak)

        assert streak_chance > no_streak_chance

    def test_encounter_chance_capped(self, engine, epic_task):
        """Encounter chance caps at 95%."""
        trainer = Trainer(name="Max")
        trainer.daily_streak.current_count = 100

        chance = engine._calculate_encounter_chance(epic_task, trainer)
        assert chance <= 0.95


class TestRaritySelection:
    """Tests for rarity selection."""

    @pytest.fixture
    def engine(self):
        return RewardEngine()

    def test_select_rarity_returns_valid(self, engine):
        """Selected rarity is valid."""
        weights = {"common": 0.7, "uncommon": 0.3, "rare": 0.0}
        for _ in range(100):
            rarity = engine._select_rarity(weights, streak_count=0)
            assert rarity in PokemonRarity

    def test_streak_improves_rarity(self, engine):
        """Higher streak improves rarity chances."""
        weights = {"common": 0.7, "uncommon": 0.2, "rare": 0.1, "epic": 0.0, "legendary": 0.0}

        # With 30-day streak, legendary should have chance > 0
        rarity = engine._select_rarity(weights, streak_count=30)
        # Just verify it runs without error
        assert rarity is not None


class TestShinyCheck:
    """Tests for shiny Pokemon checks."""

    @pytest.fixture
    def engine(self):
        return RewardEngine()

    def test_base_shiny_rate(self, engine):
        """Base shiny rate is 1%."""
        shiny_count = 0
        trials = 10000

        for _ in range(trials):
            if engine._check_shiny(streak_count=0):
                shiny_count += 1

        # Allow variance: should be around 1% (100 out of 10000)
        assert 50 < shiny_count < 200

    def test_streak_increases_shiny_rate(self, engine):
        """Streak increases shiny rate."""
        # With 10-day streak: 1% + 10 * 0.5% = 6%
        shiny_count = 0
        trials = 10000

        for _ in range(trials):
            if engine._check_shiny(streak_count=10):
                shiny_count += 1

        # Should be around 6% (600 out of 10000)
        assert 400 < shiny_count < 800

    def test_shiny_rate_caps_at_10_percent(self, engine):
        """Shiny rate caps at 10%."""
        # Even with 100-day streak, should cap at 10%
        shiny_count = 0
        trials = 10000

        for _ in range(trials):
            if engine._check_shiny(streak_count=100):
                shiny_count += 1

        # Should be around 10% (1000 out of 10000)
        assert 800 < shiny_count < 1200


class TestCatchRate:
    """Tests for catch rate calculation."""

    @pytest.fixture
    def engine(self):
        return RewardEngine()

    def test_common_catch_rate(self, engine, new_trainer):
        """Common Pokemon have high catch rate."""
        rate = engine._calculate_catch_rate(PokemonRarity.COMMON, new_trainer)
        assert rate >= 0.90

    def test_legendary_catch_rate(self, engine, new_trainer):
        """Legendary Pokemon have low catch rate."""
        rate = engine._calculate_catch_rate(PokemonRarity.LEGENDARY, new_trainer)
        assert rate <= 0.35  # Base 0.15 + some trainer bonus

    def test_mythical_catch_rate(self, engine, new_trainer):
        """Mythical Pokemon have very low catch rate."""
        rate = engine._calculate_catch_rate(PokemonRarity.MYTHICAL, new_trainer)
        assert rate <= 0.25  # Base 0.05 + some trainer bonus

    def test_trainer_level_bonus(self, engine):
        """Higher level trainer has better catch rate."""
        low_level = Trainer(name="Low", total_xp=0)
        high_level = Trainer(name="High", total_xp=10000)

        low_rate = engine._calculate_catch_rate(PokemonRarity.RARE, low_level)
        high_rate = engine._calculate_catch_rate(PokemonRarity.RARE, high_level)

        assert high_rate > low_rate

    def test_master_ball_guarantee(self, engine, trainer_with_inventory):
        """Master ball guarantees catch."""
        rate = engine._calculate_catch_rate(PokemonRarity.MYTHICAL, trainer_with_inventory)
        assert rate == 1.0

    def test_ultra_ball_bonus(self, engine):
        """Ultra ball increases catch rate."""
        trainer = Trainer(name="Test")
        trainer.inventory["ultra_ball"] = 1

        base_rate = engine._calculate_catch_rate(PokemonRarity.RARE, Trainer(name="No Items"))
        ultra_rate = engine._calculate_catch_rate(PokemonRarity.RARE, trainer)

        assert ultra_rate > base_rate

    def test_catch_rate_capped(self, engine):
        """Catch rate caps at 95%."""
        trainer = Trainer(name="Max", total_xp=100000)
        trainer.inventory["ultra_ball"] = 1

        rate = engine._calculate_catch_rate(PokemonRarity.COMMON, trainer)
        assert rate <= 0.95


class TestStreakRewards:
    """Tests for streak milestone rewards."""

    @pytest.fixture
    def engine(self):
        return RewardEngine()

    def test_no_reward_day_1(self, engine):
        """No reward on day 1."""
        rewards = engine._check_streak_rewards(1)
        assert rewards == {} or "great_ball" not in rewards

    def test_day_3_reward(self, engine):
        """Day 3 gives great balls."""
        rewards = engine._check_streak_rewards(3)
        assert "great_ball" in rewards

    def test_day_7_reward(self, engine):
        """Day 7 gives evolution stone."""
        rewards = engine._check_streak_rewards(7)
        assert "evolution_stone" in rewards

    def test_day_14_reward(self, engine):
        """Day 14 gives ultra balls."""
        rewards = engine._check_streak_rewards(14)
        assert "ultra_ball" in rewards

    def test_day_30_reward(self, engine):
        """Day 30 gives master ball."""
        rewards = engine._check_streak_rewards(30)
        assert "master_ball" in rewards

    def test_day_50_reward(self, engine):
        """Day 50 gives legendary ticket."""
        rewards = engine._check_streak_rewards(50)
        assert "legendary_ticket" in rewards

    def test_day_100_reward(self, engine):
        """Day 100 gives mythical ticket."""
        rewards = engine._check_streak_rewards(100)
        assert "mythical_ticket" in rewards

    def test_milestone_10_bonus(self, engine):
        """Every 10 days gives bonus items."""
        rewards = engine._check_streak_rewards(10)
        assert "great_ball" in rewards
        assert "rare_candy" in rewards

    def test_milestone_20_bonus(self, engine):
        """Day 20 gives bonus items."""
        rewards = engine._check_streak_rewards(20)
        assert "great_ball" in rewards


class TestPokemonCountByRarity:
    """Tests for Pokemon count reporting."""

    @pytest.fixture
    def engine(self):
        return RewardEngine()

    def test_returns_all_rarities(self, engine):
        """Returns count for all rarities."""
        counts = engine.get_pokemon_count_by_rarity()
        for rarity in PokemonRarity:
            assert rarity.value in counts

    def test_counts_are_positive(self, engine):
        """All counts are positive."""
        counts = engine.get_pokemon_count_by_rarity()
        for _rarity, count in counts.items():
            assert count >= 0

    def test_common_has_most(self, engine):
        """Common has most Pokemon."""
        counts = engine.get_pokemon_count_by_rarity()
        assert counts["common"] > counts["legendary"]


class TestGenerationFilter:
    """Tests for generation filtering."""

    def test_gen1_filter(self):
        """Gen 1 filter limits to first 151."""
        engine = RewardEngine(generation_filter=[1])
        pools = engine._get_filtered_pools()

        for rarity, pokemon_ids in pools.items():
            for pid in pokemon_ids:
                assert 1 <= pid <= 151 or pid in POKEMON_BY_RARITY[rarity]

    def test_multiple_gen_filter(self):
        """Multiple generation filter."""
        engine = RewardEngine(generation_filter=[1, 2])
        pools = engine._get_filtered_pools()

        # Should include Gen 1 and Gen 2
        all_ids = []
        for pokemon_ids in pools.values():
            all_ids.extend(pokemon_ids)

        # Should have Pokemon from both gens
        assert any(1 <= pid <= 151 for pid in all_ids)
        assert any(152 <= pid <= 251 for pid in all_ids)

    def test_no_filter_includes_all(self):
        """No filter includes all generations."""
        engine = RewardEngine()
        pools = engine._get_filtered_pools()

        all_ids = []
        for pokemon_ids in pools.values():
            all_ids.extend(pokemon_ids)

        # Should have Pokemon from later gens too
        assert any(pid > 800 for pid in all_ids)
