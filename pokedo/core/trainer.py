"""Trainer (player) profile model."""

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, Field

from pokedo.utils.helpers import calculate_level, xp_to_next_level


class TrainerClass(str, Enum):
    """Trainer archetype classes."""

    ACE_TRAINER = "ace_trainer"
    HIKER = "hiker"
    SCIENTIST = "scientist"
    BLACK_BELT = "black_belt"
    PSYCHIC = "psychic"
    SWIMMER = "swimmer"
    BREEDER = "breeder"
    COORDINATOR = "coordinator"


class TrainerBadge(BaseModel):
    """An achievement badge."""

    id: str
    name: str
    description: str
    icon: str  # ASCII/emoji representation
    earned_at: datetime | None = None
    is_earned: bool = False

    # Requirements
    requirement_type: str  # "tasks", "pokemon", "streak", "wellbeing"
    requirement_count: int


class Streak(BaseModel):
    """Streak tracking for various activities."""

    streak_type: str  # "daily", "category", "wellbeing"
    category: str | None = None  # For category-specific streaks
    current_count: int = 0
    best_count: int = 0
    last_activity_date: date | None = None

    def update(self, activity_date: date) -> bool:
        """Update streak, returns True if streak continued."""
        if self.last_activity_date is None:
            self.current_count = 1
            self.last_activity_date = activity_date
            return True

        days_diff = (activity_date - self.last_activity_date).days

        if days_diff == 0:
            # Same day, no change
            return True
        elif days_diff == 1:
            # Consecutive day, increase streak
            self.current_count += 1
            self.last_activity_date = activity_date
            if self.current_count > self.best_count:
                self.best_count = self.current_count
            return True
        else:
            # Streak broken
            self.current_count = 1
            self.last_activity_date = activity_date
            return False


class Trainer(BaseModel):
    """The player's trainer profile."""

    id: int | None = None
    name: str = "Trainer"
    trainer_class: TrainerClass = TrainerClass.ACE_TRAINER
    created_at: datetime = Field(default_factory=datetime.now)

    # Experience and level
    total_xp: int = 0

    # Statistics
    tasks_completed: int = 0
    tasks_completed_today: int = 0
    pokemon_caught: int = 0
    pokemon_released: int = 0
    evolutions_triggered: int = 0

    # Pokedex progress
    pokedex_seen: int = 0
    pokedex_caught: int = 0

    # Streaks
    daily_streak: Streak = Field(default_factory=lambda: Streak(streak_type="daily"))
    wellbeing_streak: Streak = Field(default_factory=lambda: Streak(streak_type="wellbeing"))

    # Badges earned
    badges: list[TrainerBadge] = Field(default_factory=list)

    # Inventory (evolution items, etc.)
    inventory: dict[str, int] = Field(default_factory=dict)

    # Settings
    favorite_pokemon_id: int | None = None
    last_active_date: date | None = None

    @property
    def level(self) -> int:
        """Calculate trainer level from XP."""
        return calculate_level(self.total_xp)

    @property
    def xp_progress(self) -> tuple[int, int]:
        """Get XP progress to next level."""
        return xp_to_next_level(self.total_xp)

    @property
    def pokedex_completion(self) -> float:
        """Calculate Pokedex completion percentage."""
        from pokedo.utils.config import config

        if config.max_pokemon_id == 0:
            return 0.0
        return (self.pokedex_caught / config.max_pokemon_id) * 100

    def add_xp(self, amount: int) -> int:
        """Add XP and return new level if leveled up."""
        old_level = self.level
        self.total_xp += amount
        new_level = self.level
        if new_level > old_level:
            return new_level
        return 0

    def add_item(self, item: str, count: int = 1) -> None:
        """Add item to inventory."""
        if item in self.inventory:
            self.inventory[item] += count
        else:
            self.inventory[item] = count

    def use_item(self, item: str) -> bool:
        """Use item from inventory, returns True if successful."""
        if item in self.inventory and self.inventory[item] > 0:
            self.inventory[item] -= 1
            if self.inventory[item] == 0:
                del self.inventory[item]
            return True
        return False

    def update_streak(self, activity_date: date) -> tuple[bool, int]:
        """Update daily streak, returns (streak_continued, current_count)."""
        continued = self.daily_streak.update(activity_date)
        return continued, self.daily_streak.current_count


# Predefined badges
AVAILABLE_BADGES = [
    TrainerBadge(
        id="early_bird",
        name="Early Bird",
        description="Complete 10 tasks before 9 AM",
        icon="[EB]",
        requirement_type="tasks",
        requirement_count=10,
    ),
    TrainerBadge(
        id="night_owl",
        name="Night Owl",
        description="Complete 10 tasks after 9 PM",
        icon="[NO]",
        requirement_type="tasks",
        requirement_count=10,
    ),
    TrainerBadge(
        id="gym_leader",
        name="Gym Leader",
        description="Log 50 exercise sessions",
        icon="[GL]",
        requirement_type="wellbeing",
        requirement_count=50,
    ),
    TrainerBadge(
        id="professor",
        name="Professor",
        description="Complete 100 learning tasks",
        icon="[PR]",
        requirement_type="tasks",
        requirement_count=100,
    ),
    TrainerBadge(
        id="champion",
        name="Champion",
        description="Catch 50% of the Pokedex",
        icon="[CH]",
        requirement_type="pokemon",
        requirement_count=50,
    ),
    TrainerBadge(
        id="collector",
        name="Collector",
        description="Catch 100 Pokemon",
        icon="[CO]",
        requirement_type="pokemon",
        requirement_count=100,
    ),
    TrainerBadge(
        id="dedicated",
        name="Dedicated",
        description="Maintain a 30-day streak",
        icon="[DE]",
        requirement_type="streak",
        requirement_count=30,
    ),
    TrainerBadge(
        id="centurion",
        name="Centurion",
        description="Maintain a 100-day streak",
        icon="[CE]",
        requirement_type="streak",
        requirement_count=100,
    ),
    TrainerBadge(
        id="starter",
        name="Starter",
        description="Complete your first task",
        icon="[ST]",
        requirement_type="tasks",
        requirement_count=1,
    ),
    TrainerBadge(
        id="first_catch",
        name="First Catch",
        description="Catch your first Pokemon",
        icon="[FC]",
        requirement_type="pokemon",
        requirement_count=1,
    ),
]
