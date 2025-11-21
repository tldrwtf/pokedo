"""Tests for helper utilities."""

from datetime import date, datetime, timedelta

from pokedo.utils.helpers import (
    calculate_level,
    days_between,
    format_date,
    format_datetime,
    get_now,
    get_today,
    weighted_random_choice,
    xp_for_level,
    xp_to_next_level,
)


class TestGetToday:
    """Tests for get_today function."""

    def test_returns_today(self):
        """Returns today's date."""
        result = get_today()
        assert result == date.today()

    def test_returns_date_type(self):
        """Returns date type."""
        result = get_today()
        assert isinstance(result, date)


class TestGetNow:
    """Tests for get_now function."""

    def test_returns_now(self):
        """Returns current datetime."""
        before = datetime.now()
        result = get_now()
        after = datetime.now()
        assert before <= result <= after

    def test_returns_datetime_type(self):
        """Returns datetime type."""
        result = get_now()
        assert isinstance(result, datetime)


class TestWeightedRandomChoice:
    """Tests for weighted_random_choice function."""

    def test_single_option(self):
        """Single option always selected."""
        weights = {"only": 1.0}
        result = weighted_random_choice(weights)
        assert result == "only"

    def test_guaranteed_option(self):
        """Option with weight 1.0 always selected."""
        weights = {"winner": 1.0, "loser": 0.0}
        # Run multiple times to be sure
        for _ in range(10):
            result = weighted_random_choice(weights)
            assert result == "winner"

    def test_returns_valid_choice(self):
        """Returns one of the valid choices."""
        weights = {"a": 0.5, "b": 0.3, "c": 0.2}
        for _ in range(100):
            result = weighted_random_choice(weights)
            assert result in weights.keys()

    def test_distribution_approximately_correct(self):
        """Distribution roughly matches weights."""
        weights = {"a": 0.7, "b": 0.3}
        results = {"a": 0, "b": 0}
        trials = 1000

        for _ in range(trials):
            result = weighted_random_choice(weights)
            results[result] += 1

        # Allow 10% variance
        assert results["a"] > trials * 0.6
        assert results["a"] < trials * 0.8
        assert results["b"] > trials * 0.2
        assert results["b"] < trials * 0.4


class TestCalculateLevel:
    """Tests for calculate_level function."""

    def test_level_1_at_zero_xp(self):
        """Level 1 at 0 XP."""
        assert calculate_level(0) == 1

    def test_level_1_at_99_xp(self):
        """Still level 1 at 99 XP."""
        assert calculate_level(99) == 1

    def test_level_2_at_100_xp(self):
        """Level 2 at 100 XP."""
        assert calculate_level(100) == 2

    def test_level_3_at_300_xp(self):
        """Level 3 at 300 XP (100 + 200)."""
        assert calculate_level(300) == 3

    def test_higher_levels(self):
        """Higher levels require progressively more XP."""
        # Level 4 needs 100 + 200 + 300 = 600
        assert calculate_level(600) == 4
        # Level 5 needs 600 + 400 = 1000
        assert calculate_level(1000) == 5

    def test_max_level_100(self):
        """Level caps at 100."""
        result = calculate_level(999999999)
        assert result == 100


class TestXPForLevel:
    """Tests for xp_for_level function."""

    def test_xp_for_level_1(self):
        """Level 1 requires 0 XP."""
        assert xp_for_level(1) == 0

    def test_xp_for_level_2(self):
        """Level 2 requires 100 XP."""
        assert xp_for_level(2) == 100

    def test_xp_for_level_3(self):
        """Level 3 requires 300 XP."""
        assert xp_for_level(3) == 300

    def test_xp_for_level_5(self):
        """Level 5 requires 1000 XP."""
        # 100 + 200 + 300 + 400 = 1000
        assert xp_for_level(5) == 1000


class TestXPToNextLevel:
    """Tests for xp_to_next_level function."""

    def test_at_level_start(self):
        """At level start, current is 0."""
        current, needed = xp_to_next_level(0)
        assert current == 0
        assert needed == 100

    def test_mid_level(self):
        """Mid-level progress."""
        current, needed = xp_to_next_level(50)
        assert current == 50
        assert needed == 100

    def test_at_level_boundary(self):
        """At level boundary."""
        current, needed = xp_to_next_level(100)
        # At level 2, need 200 for next level
        assert current == 0
        assert needed == 200

    def test_higher_level(self):
        """Progress at higher level."""
        # Level 3 starts at 300 XP, needs 300 for level 4
        current, needed = xp_to_next_level(350)
        assert current == 50
        assert needed == 300


class TestFormatDate:
    """Tests for format_date function."""

    def test_format_date(self):
        """Formats date correctly."""
        d = date(2024, 1, 15)
        assert format_date(d) == "2024-01-15"

    def test_format_today(self):
        """Formats today's date."""
        today = date.today()
        result = format_date(today)
        assert today.strftime("%Y-%m-%d") == result


class TestFormatDatetime:
    """Tests for format_datetime function."""

    def test_format_datetime(self):
        """Formats datetime correctly."""
        dt = datetime(2024, 1, 15, 14, 30)
        assert format_datetime(dt) == "2024-01-15 14:30"

    def test_format_with_seconds(self):
        """Seconds are not included."""
        dt = datetime(2024, 1, 15, 14, 30, 45)
        assert format_datetime(dt) == "2024-01-15 14:30"


class TestDaysBetween:
    """Tests for days_between function."""

    def test_same_day(self):
        """Same day is 0 days."""
        d = date.today()
        assert days_between(d, d) == 0

    def test_one_day_apart(self):
        """One day apart."""
        d1 = date.today()
        d2 = d1 + timedelta(days=1)
        assert days_between(d1, d2) == 1

    def test_order_doesnt_matter(self):
        """Order of dates doesn't matter."""
        d1 = date(2024, 1, 1)
        d2 = date(2024, 1, 10)
        assert days_between(d1, d2) == 9
        assert days_between(d2, d1) == 9

    def test_long_period(self):
        """Longer period."""
        d1 = date(2024, 1, 1)
        d2 = date(2024, 12, 31)
        assert days_between(d1, d2) == 365  # 2024 is leap year
