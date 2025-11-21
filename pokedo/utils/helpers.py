"""Helper utilities for PokeDo."""

import random
from datetime import datetime, date


def get_today() -> date:
    """Get today's date."""
    return date.today()


def get_now() -> datetime:
    """Get current datetime."""
    return datetime.now()


def weighted_random_choice(weights: dict) -> str:
    """Select a random key based on weights.

    Args:
        weights: Dict of {choice: weight} where weights sum to 1.0

    Returns:
        Selected choice key.
    """
    choices = list(weights.keys())
    probabilities = list(weights.values())
    return random.choices(choices, weights=probabilities, k=1)[0]


def calculate_level(xp: int) -> int:
    """Calculate level from XP using Pokemon-style curve.

    Uses a simplified experience curve where each level requires
    progressively more XP.
    """
    level = 1
    xp_required = 0
    while True:
        xp_for_next = level * 100  # Simple formula: level * 100 XP per level
        if xp < xp_required + xp_for_next:
            break
        xp_required += xp_for_next
        level += 1
        if level >= 100:
            break
    return level


def xp_for_level(level: int) -> int:
    """Calculate total XP required to reach a level."""
    total = 0
    for lvl in range(1, level):
        total += lvl * 100
    return total


def xp_to_next_level(current_xp: int) -> tuple[int, int]:
    """Calculate XP progress to next level.

    Returns:
        Tuple of (current_xp_in_level, xp_needed_for_level)
    """
    level = calculate_level(current_xp)
    xp_at_level_start = xp_for_level(level)
    xp_needed = level * 100
    xp_in_level = current_xp - xp_at_level_start
    return xp_in_level, xp_needed


def format_date(d: date) -> str:
    """Format date for display."""
    return d.strftime("%Y-%m-%d")


def format_datetime(dt: datetime) -> str:
    """Format datetime for display."""
    return dt.strftime("%Y-%m-%d %H:%M")


def days_between(d1: date, d2: date) -> int:
    """Calculate days between two dates."""
    return abs((d2 - d1).days)
