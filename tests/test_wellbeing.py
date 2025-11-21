"""Tests for Wellbeing models."""

from datetime import date

from pokedo.core.wellbeing import (
    DailyWellbeing,
    ExerciseEntry,
    ExerciseType,
    HydrationEntry,
    JournalEntry,
    MeditationEntry,
    MoodEntry,
    MoodLevel,
    SleepEntry,
)


class TestMoodLevel:
    """Tests for MoodLevel enum."""

    def test_mood_levels_exist(self):
        """Verify all mood levels exist."""
        assert MoodLevel.VERY_LOW.value == 1
        assert MoodLevel.LOW.value == 2
        assert MoodLevel.NEUTRAL.value == 3
        assert MoodLevel.GOOD.value == 4
        assert MoodLevel.GREAT.value == 5


class TestExerciseType:
    """Tests for ExerciseType enum."""

    def test_exercise_types_exist(self):
        """Verify exercise types exist."""
        expected = [
            "cardio",
            "strength",
            "yoga",
            "swimming",
            "cycling",
            "walking",
            "running",
            "sports",
            "hiking",
            "dancing",
            "other",
        ]
        actual = [e.value for e in ExerciseType]
        assert sorted(actual) == sorted(expected)


class TestMoodEntry:
    """Tests for MoodEntry model."""

    def test_create_mood_entry(self, good_mood):
        """Create mood entry."""
        assert good_mood.mood == MoodLevel.GOOD
        assert good_mood.energy_level == 4
        assert good_mood.note == "Feeling productive"

    def test_default_date(self):
        """Mood entry defaults to today."""
        entry = MoodEntry(mood=MoodLevel.NEUTRAL)
        assert entry.date == date.today()

    def test_happiness_modifier_great(self):
        """Great mood gives +2 happiness modifier."""
        entry = MoodEntry(mood=MoodLevel.GREAT)
        assert entry.get_pokemon_happiness_modifier() == 2

    def test_happiness_modifier_good(self, good_mood):
        """Good mood gives +1 happiness modifier."""
        assert good_mood.get_pokemon_happiness_modifier() == 1

    def test_happiness_modifier_neutral(self):
        """Neutral mood gives 0 happiness modifier."""
        entry = MoodEntry(mood=MoodLevel.NEUTRAL)
        assert entry.get_pokemon_happiness_modifier() == 0

    def test_happiness_modifier_low(self, low_mood):
        """Low mood gives -1 happiness modifier."""
        assert low_mood.get_pokemon_happiness_modifier() == -1

    def test_happiness_modifier_very_low(self):
        """Very low mood gives -2 happiness modifier."""
        entry = MoodEntry(mood=MoodLevel.VERY_LOW)
        assert entry.get_pokemon_happiness_modifier() == -2


class TestExerciseEntry:
    """Tests for ExerciseEntry model."""

    def test_create_exercise_entry(self, cardio_exercise):
        """Create exercise entry."""
        assert cardio_exercise.exercise_type == ExerciseType.CARDIO
        assert cardio_exercise.duration_minutes == 30
        assert cardio_exercise.intensity == 4

    def test_default_intensity(self):
        """Default intensity is 3."""
        entry = ExerciseEntry(
            exercise_type=ExerciseType.WALKING,
            duration_minutes=20,
        )
        assert entry.intensity == 3

    def test_cardio_type_affinity(self, cardio_exercise):
        """Cardio has fire/flying affinity."""
        types = cardio_exercise.get_type_affinity()
        assert "fire" in types
        assert "flying" in types

    def test_yoga_type_affinity(self, yoga_exercise):
        """Yoga has psychic/fairy affinity."""
        types = yoga_exercise.get_type_affinity()
        assert "psychic" in types
        assert "fairy" in types

    def test_swimming_type_affinity(self):
        """Swimming has water/ice affinity."""
        entry = ExerciseEntry(exercise_type=ExerciseType.SWIMMING, duration_minutes=30)
        types = entry.get_type_affinity()
        assert "water" in types
        assert "ice" in types

    def test_xp_bonus_short_exercise(self):
        """Short exercise gives small XP bonus."""
        entry = ExerciseEntry(
            exercise_type=ExerciseType.WALKING,
            duration_minutes=10,
            intensity=3,
        )
        # 10 min / 10 * 5 = 5 base, * (0.5 + 3*0.25) = 5 * 1.25 = 6
        assert entry.xp_bonus == 6

    def test_xp_bonus_long_high_intensity(self, cardio_exercise):
        """Long high intensity exercise gives larger bonus."""
        # 30 min / 10 * 5 = 15 base, intensity 4: * (0.5 + 4*0.25) = 15 * 1.5 = 22
        assert cardio_exercise.xp_bonus == 22


class TestSleepEntry:
    """Tests for SleepEntry model."""

    def test_create_sleep_entry(self, good_sleep):
        """Create sleep entry."""
        assert good_sleep.hours == 8.0
        assert good_sleep.quality == 4

    def test_default_quality(self):
        """Default quality is 3."""
        entry = SleepEntry(hours=7)
        assert entry.quality == 3

    def test_catch_modifier_little_sleep(self, poor_sleep):
        """Little sleep reduces catch rate."""
        modifier = poor_sleep.get_catch_rate_modifier()
        assert modifier == 0.8  # -20%

    def test_catch_modifier_moderate_sleep(self):
        """Moderate sleep slightly reduces catch rate."""
        entry = SleepEntry(hours=6)
        modifier = entry.get_catch_rate_modifier()
        assert modifier == 0.9  # -10%

    def test_catch_modifier_good_sleep(self, good_sleep):
        """Good sleep increases catch rate."""
        modifier = good_sleep.get_catch_rate_modifier()
        assert modifier == 1.1  # +10%

    def test_catch_modifier_too_much_sleep(self):
        """Too much sleep is normal catch rate."""
        entry = SleepEntry(hours=10)
        modifier = entry.get_catch_rate_modifier()
        assert modifier == 1.0


class TestHydrationEntry:
    """Tests for HydrationEntry model."""

    def test_create_hydration_entry(self, full_hydration):
        """Create hydration entry."""
        assert full_hydration.glasses == 8

    def test_goal_met(self, full_hydration):
        """Goal met at 8+ glasses."""
        assert full_hydration.is_goal_met is True

    def test_goal_not_met(self, partial_hydration):
        """Goal not met under 8 glasses."""
        assert partial_hydration.is_goal_met is False

    def test_water_type_bonus_full(self, full_hydration):
        """Full hydration gives 1.5x water type bonus."""
        bonus = full_hydration.get_water_type_bonus()
        assert bonus == 1.5

    def test_water_type_bonus_partial(self, partial_hydration):
        """Partial hydration (5 glasses) gives no bonus."""
        bonus = partial_hydration.get_water_type_bonus()
        assert bonus == 1.0

    def test_water_type_bonus_medium(self):
        """Medium hydration (6-7 glasses) gives 1.25x bonus."""
        entry = HydrationEntry(glasses=6)
        bonus = entry.get_water_type_bonus()
        assert bonus == 1.25


class TestMeditationEntry:
    """Tests for MeditationEntry model."""

    def test_create_meditation_entry(self, long_meditation):
        """Create meditation entry."""
        assert long_meditation.minutes == 20

    def test_psychic_bonus_long(self, long_meditation):
        """Long meditation gives 1.5x psychic bonus."""
        bonus = long_meditation.get_psychic_type_bonus()
        assert bonus == 1.5

    def test_psychic_bonus_medium(self):
        """Medium meditation gives 1.25x bonus."""
        entry = MeditationEntry(minutes=15)
        bonus = entry.get_psychic_type_bonus()
        assert bonus == 1.25

    def test_psychic_bonus_short(self, short_meditation):
        """Short meditation gives no bonus."""
        bonus = short_meditation.get_psychic_type_bonus()
        assert bonus == 1.0


class TestJournalEntry:
    """Tests for JournalEntry model."""

    def test_create_journal_entry(self, gratitude_journal):
        """Create journal entry."""
        assert "productive" in gratitude_journal.content
        assert len(gratitude_journal.gratitude_items) == 3

    def test_friendship_bonus_full(self):
        """Full journal gives high friendship bonus."""
        # 3+ gratitude items + 100+ chars = 1 + 2 + 1 = 4
        entry = JournalEntry(
            content="Today was an absolutely wonderful and productive day. I managed to accomplish all of my goals and feel great about my progress!",
            gratitude_items=["health", "family", "progress"],
        )
        bonus = entry.get_friendship_bonus()
        assert bonus == 4

    def test_friendship_bonus_minimal(self):
        """Minimal journal gives low bonus."""
        entry = JournalEntry(content="Short")
        bonus = entry.get_friendship_bonus()
        assert bonus == 1

    def test_friendship_bonus_gratitude_only(self):
        """Gratitude items add bonus."""
        entry = JournalEntry(
            content="Short",
            gratitude_items=["a", "b", "c"],
        )
        bonus = entry.get_friendship_bonus()
        assert bonus == 3  # 1 base + 2 for gratitude


class TestDailyWellbeing:
    """Tests for DailyWellbeing model."""

    def test_create_empty(self):
        """Create empty daily wellbeing."""
        daily = DailyWellbeing()
        assert daily.date == date.today()
        assert daily.mood is None
        assert daily.exercises == []
        assert daily.is_complete is False

    def test_complete_wellbeing(self, complete_daily_wellbeing):
        """Complete wellbeing is marked complete."""
        assert complete_daily_wellbeing.is_complete is True

    def test_partial_wellbeing_not_complete(self, partial_daily_wellbeing):
        """Partial wellbeing is not complete."""
        assert partial_daily_wellbeing.is_complete is False

    def test_completion_score_full(self, complete_daily_wellbeing):
        """Full completion is 100%."""
        score = complete_daily_wellbeing.completion_score
        assert score == 100.0

    def test_completion_score_empty(self):
        """Empty completion is 0%."""
        daily = DailyWellbeing()
        assert daily.completion_score == 0.0

    def test_completion_score_partial(self, partial_daily_wellbeing):
        """Partial completion shows percentage."""
        # mood + sleep = 2/6 = 33.33%
        score = partial_daily_wellbeing.completion_score
        assert 30 < score < 40
