"""Wellbeing tracking models."""

from datetime import datetime, date
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class MoodLevel(int, Enum):
    """Mood levels from 1-5."""
    VERY_LOW = 1
    LOW = 2
    NEUTRAL = 3
    GOOD = 4
    GREAT = 5


class ExerciseType(str, Enum):
    """Types of exercise that map to Pokemon types."""
    CARDIO = "cardio"           # Fire
    STRENGTH = "strength"       # Fighting
    YOGA = "yoga"               # Psychic
    SWIMMING = "swimming"       # Water
    CYCLING = "cycling"         # Electric
    WALKING = "walking"         # Normal
    RUNNING = "running"         # Fire
    SPORTS = "sports"           # Fighting
    HIKING = "hiking"           # Rock, Ground
    DANCING = "dancing"         # Fairy
    OTHER = "other"             # Normal


class MoodEntry(BaseModel):
    """A mood check-in entry."""

    id: Optional[int] = None
    date: date = Field(default_factory=date.today)
    timestamp: datetime = Field(default_factory=datetime.now)
    mood: MoodLevel
    note: Optional[str] = None
    energy_level: Optional[int] = None  # 1-5

    def get_pokemon_happiness_modifier(self) -> int:
        """Get happiness modifier for Pokemon based on mood."""
        modifiers = {
            MoodLevel.VERY_LOW: -2,
            MoodLevel.LOW: -1,
            MoodLevel.NEUTRAL: 0,
            MoodLevel.GOOD: 1,
            MoodLevel.GREAT: 2
        }
        return modifiers[self.mood]


class ExerciseEntry(BaseModel):
    """An exercise log entry."""

    id: Optional[int] = None
    date: date = Field(default_factory=date.today)
    timestamp: datetime = Field(default_factory=datetime.now)
    exercise_type: ExerciseType
    duration_minutes: int
    intensity: int = 3  # 1-5
    note: Optional[str] = None

    def get_type_affinity(self) -> list[str]:
        """Get Pokemon types with affinity for this exercise."""
        affinities = {
            ExerciseType.CARDIO: ["fire", "flying"],
            ExerciseType.STRENGTH: ["fighting", "rock"],
            ExerciseType.YOGA: ["psychic", "fairy"],
            ExerciseType.SWIMMING: ["water", "ice"],
            ExerciseType.CYCLING: ["electric", "steel"],
            ExerciseType.WALKING: ["normal", "grass"],
            ExerciseType.RUNNING: ["fire", "fighting"],
            ExerciseType.SPORTS: ["fighting", "normal"],
            ExerciseType.HIKING: ["rock", "ground"],
            ExerciseType.DANCING: ["fairy", "normal"],
            ExerciseType.OTHER: ["normal"],
        }
        return affinities[self.exercise_type]

    @property
    def xp_bonus(self) -> int:
        """Calculate bonus XP from exercise."""
        base = self.duration_minutes // 10 * 5
        intensity_multiplier = 0.5 + (self.intensity * 0.25)
        return int(base * intensity_multiplier)


class SleepEntry(BaseModel):
    """A sleep log entry."""

    id: Optional[int] = None
    date: date = Field(default_factory=date.today)
    hours: float
    quality: int = 3  # 1-5
    note: Optional[str] = None

    def get_catch_rate_modifier(self) -> float:
        """Get catch rate modifier based on sleep."""
        if self.hours < 5:
            return 0.8  # -20% catch rate
        elif self.hours < 7:
            return 0.9  # -10% catch rate
        elif self.hours <= 9:
            return 1.1  # +10% catch rate
        else:
            return 1.0  # Normal


class HydrationEntry(BaseModel):
    """A hydration log entry."""

    id: Optional[int] = None
    date: date = Field(default_factory=date.today)
    glasses: int  # 8oz glasses
    note: Optional[str] = None

    @property
    def is_goal_met(self) -> bool:
        """Check if daily hydration goal (8 glasses) is met."""
        return self.glasses >= 8

    def get_water_type_bonus(self) -> float:
        """Get bonus for water-type Pokemon encounters."""
        if self.glasses >= 8:
            return 1.5  # 50% more likely to encounter water types
        elif self.glasses >= 6:
            return 1.25
        return 1.0


class MeditationEntry(BaseModel):
    """A meditation log entry."""

    id: Optional[int] = None
    date: date = Field(default_factory=date.today)
    timestamp: datetime = Field(default_factory=datetime.now)
    minutes: int
    note: Optional[str] = None

    def get_psychic_type_bonus(self) -> float:
        """Get bonus for psychic/fairy Pokemon encounters."""
        if self.minutes >= 20:
            return 1.5
        elif self.minutes >= 10:
            return 1.25
        return 1.0


class JournalEntry(BaseModel):
    """A gratitude journal entry."""

    id: Optional[int] = None
    date: date = Field(default_factory=date.today)
    timestamp: datetime = Field(default_factory=datetime.now)
    content: str
    gratitude_items: list[str] = Field(default_factory=list)

    def get_friendship_bonus(self) -> int:
        """Get friendship bonus for Pokemon based on journaling."""
        base = 1
        if len(self.gratitude_items) >= 3:
            base += 2
        if len(self.content) >= 100:
            base += 1
        return base


class DailyWellbeing(BaseModel):
    """Aggregated wellbeing data for a day."""

    date: date = Field(default_factory=date.today)
    mood: Optional[MoodEntry] = None
    exercises: list[ExerciseEntry] = Field(default_factory=list)
    sleep: Optional[SleepEntry] = None
    hydration: Optional[HydrationEntry] = None
    meditation: Optional[MeditationEntry] = None
    journal: Optional[JournalEntry] = None

    @property
    def is_complete(self) -> bool:
        """Check if all wellbeing metrics are logged."""
        return all([
            self.mood is not None,
            self.sleep is not None,
            self.hydration is not None,
        ])

    @property
    def completion_score(self) -> float:
        """Calculate completion percentage."""
        total = 6  # mood, exercise, sleep, hydration, meditation, journal
        completed = sum([
            self.mood is not None,
            len(self.exercises) > 0,
            self.sleep is not None,
            self.hydration is not None,
            self.meditation is not None,
            self.journal is not None,
        ])
        return (completed / total) * 100
