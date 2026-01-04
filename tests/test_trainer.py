"""Tests for Trainer model and related logic."""

from datetime import date, timedelta

from pokedo.core.trainer import AVAILABLE_BADGES, Streak, Trainer


class TestStreak:
    """Tests for Streak model."""

    def test_create_new_streak(self):
        """Create a new streak."""
        streak = Streak(streak_type="daily")
        assert streak.current_count == 0
        assert streak.best_count == 0
        assert streak.last_activity_date is None

    def test_first_activity(self):
        """First activity starts streak at 1."""
        streak = Streak(streak_type="daily")
        result = streak.update(date.today())
        assert result is True
        assert streak.current_count == 1
        assert streak.last_activity_date == date.today()
        assert streak.best_count == 1

    def test_consecutive_day_increases_streak(self):
        """Activity on consecutive day increases streak."""
        streak = Streak(streak_type="daily")
        yesterday = date.today() - timedelta(days=1)
        streak.update(yesterday)
        assert streak.current_count == 1

        result = streak.update(date.today())
        assert result is True
        assert streak.current_count == 2

    def test_same_day_no_change(self):
        """Activity on same day doesn't change streak."""
        streak = Streak(streak_type="daily")
        streak.update(date.today())
        initial_count = streak.current_count

        result = streak.update(date.today())
        assert result is True
        assert streak.current_count == initial_count

    def test_missed_day_resets_streak(self):
        """Missing a day resets streak to 1."""
        streak = Streak(streak_type="daily")
        two_days_ago = date.today() - timedelta(days=2)
        streak.update(two_days_ago)
        streak.current_count = 5  # Simulate built-up streak

        result = streak.update(date.today())
        assert result is False
        assert streak.current_count == 1

    def test_best_count_updated(self):
        """Best count is updated when current exceeds it."""
        streak = Streak(streak_type="daily")
        streak.current_count = 5
        streak.best_count = 5
        streak.last_activity_date = date.today() - timedelta(days=1)

        streak.update(date.today())
        assert streak.best_count == 6

    def test_best_count_preserved(self):
        """Best count is preserved when streak resets."""
        streak = Streak(streak_type="daily")
        streak.current_count = 10
        streak.best_count = 10
        streak.last_activity_date = date.today() - timedelta(days=5)

        streak.update(date.today())
        assert streak.current_count == 1
        assert streak.best_count == 10  # Preserved


class TestTrainerBadge:
    """Tests for TrainerBadge model."""

    def test_create_badge(self, sample_badge):
        """Create a badge."""
        assert sample_badge.id == "starter"
        assert sample_badge.name == "Starter"
        assert sample_badge.is_earned is False

    def test_available_badges_defined(self):
        """AVAILABLE_BADGES has expected badges."""
        badge_ids = [b.id for b in AVAILABLE_BADGES]
        assert "starter" in badge_ids
        assert "first_catch" in badge_ids
        assert "collector" in badge_ids
        assert "dedicated" in badge_ids


class TestTrainerCreation:
    """Tests for Trainer creation."""

    def test_create_minimal_trainer(self):
        """Create trainer with minimal info."""
        trainer = Trainer()
        assert trainer.name == "Trainer"
        assert trainer.total_xp == 0
        assert trainer.tasks_completed == 0
        assert trainer.pokemon_caught == 0

    def test_create_named_trainer(self, new_trainer):
        """Create trainer with name."""
        assert new_trainer.name == "Test Trainer"

    def test_default_streaks(self, new_trainer):
        """Trainer has default streaks."""
        assert new_trainer.daily_streak is not None
        assert new_trainer.wellbeing_streak is not None
        assert new_trainer.daily_streak.streak_type == "daily"
        assert new_trainer.wellbeing_streak.streak_type == "wellbeing"

    def test_default_inventory(self, new_trainer):
        """Trainer has empty inventory."""
        assert new_trainer.inventory == {}

    def test_default_badges(self, new_trainer):
        """Trainer has no badges initially."""
        assert new_trainer.badges == []


class TestTrainerLevel:
    """Tests for Trainer level calculation."""

    def test_level_1_at_zero_xp(self, new_trainer):
        """Trainer is level 1 with 0 XP."""
        assert new_trainer.level == 1

    def test_level_increases_with_xp(self):
        """Level increases with XP."""
        trainer = Trainer(total_xp=100)
        assert trainer.level == 2

        trainer = Trainer(total_xp=300)
        assert trainer.level == 3

    def test_experienced_trainer_level(self, experienced_trainer):
        """Experienced trainer has higher level."""
        # 5000 XP should be around level 9-10
        assert experienced_trainer.level > 5


class TestTrainerXPProgress:
    """Tests for Trainer XP progress tracking."""

    def test_xp_progress_at_start(self, new_trainer):
        """XP progress at level 1."""
        current, needed = new_trainer.xp_progress
        assert current == 0
        assert needed == 100  # Level 1 needs 100 XP

    def test_xp_progress_mid_level(self):
        """XP progress mid-level."""
        trainer = Trainer(total_xp=50)
        current, needed = trainer.xp_progress
        assert current == 50
        assert needed == 100


class TestTrainerAddXP:
    """Tests for Trainer.add_xp method."""

    def test_add_xp_no_level_up(self, new_trainer):
        """Adding XP without level up."""
        result = new_trainer.add_xp(50)
        assert result == 0  # No level up
        assert new_trainer.total_xp == 50

    def test_add_xp_with_level_up(self, new_trainer):
        """Adding XP with level up."""
        result = new_trainer.add_xp(100)
        assert result == 2  # Leveled up to 2
        assert new_trainer.total_xp == 100

    def test_multiple_level_ups(self):
        """Adding large XP causes multiple level ups."""
        trainer = Trainer()
        result = trainer.add_xp(300)  # Should be level 3
        assert result == 3


class TestTrainerInventory:
    """Tests for Trainer inventory management."""

    def test_add_new_item(self, new_trainer):
        """Add new item to inventory."""
        new_trainer.add_item("pokeball", 10)
        assert new_trainer.inventory["pokeball"] == 10

    def test_add_existing_item(self, trainer_with_inventory):
        """Add to existing item count."""
        initial = trainer_with_inventory.inventory["pokeball"]
        trainer_with_inventory.add_item("pokeball", 5)
        assert trainer_with_inventory.inventory["pokeball"] == initial + 5

    def test_use_item_success(self, trainer_with_inventory):
        """Use item successfully."""
        initial = trainer_with_inventory.inventory["pokeball"]
        result = trainer_with_inventory.use_item("pokeball")
        assert result is True
        assert trainer_with_inventory.inventory["pokeball"] == initial - 1

    def test_use_item_removes_empty(self, trainer_with_inventory):
        """Using last item removes it from inventory."""
        trainer_with_inventory.inventory["test_item"] = 1
        trainer_with_inventory.use_item("test_item")
        assert "test_item" not in trainer_with_inventory.inventory

    def test_use_item_not_in_inventory(self, new_trainer):
        """Cannot use item not in inventory."""
        result = new_trainer.use_item("nonexistent")
        assert result is False

    def test_use_item_zero_count(self, trainer_with_inventory):
        """Cannot use item with zero count."""
        trainer_with_inventory.inventory["empty_item"] = 0
        result = trainer_with_inventory.use_item("empty_item")
        assert result is False


class TestTrainerStreak:
    """Tests for Trainer streak management."""

    def test_update_streak(self, new_trainer):
        """Update daily streak."""
        continued, count = new_trainer.update_streak(date.today())
        assert continued is True
        assert count == 1

    def test_streak_continues(self, trainer_with_streak):
        """Continuing streak increments count."""
        # Streak was updated today already
        continued, count = trainer_with_streak.update_streak(date.today())
        assert continued is True
        assert count == 7  # No change on same day

    def test_streak_broken(self):
        """Breaking streak resets count."""
        trainer = Trainer(name="Test")
        trainer.daily_streak.current_count = 5
        trainer.daily_streak.last_activity_date = date.today() - timedelta(days=3)

        continued, count = trainer.update_streak(date.today())
        assert continued is False
        assert count == 1


class TestTrainerPokedexCompletion:
    """Tests for Trainer Pokedex completion."""

    def test_zero_completion(self, new_trainer):
        """New trainer has 0% completion."""
        assert new_trainer.pokedex_completion == 0.0

    def test_partial_completion(self, experienced_trainer):
        """Experienced trainer has partial completion."""
        # 30 caught out of 1025 = ~2.9%
        completion = experienced_trainer.pokedex_completion
        assert completion > 0
        assert completion < 100
