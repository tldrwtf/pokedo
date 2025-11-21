"""Tests for PokeDo."""
import datetime as dt
from typing import Optional

from pydantic import BaseModel, Field

class SleepEntry(BaseModel):
    """A sleep log entry."""

    id: Optional[int] = None
    date: dt.date = Field(default_factory=dt.date.today)
    timestamp: dt.datetime = Field(default_factory=dt.datetime.now)
    hours: float
    quality: Optional[int] = None  # 1-5 scale

    def get_recovery_bonus(self) -> float:
        """Get recovery bonus for Pokemon based on sleep."""
        if self.hours >= 8:
            return 1.5
        elif self.hours >= 6:
            return 1.25
        return 1.0
class HydrationEntry(BaseModel):
    """A hydration log entry."""

    id: Optional[int] = None
    date: dt.date = Field(default_factory=dt.date.today)
    timestamp: dt.datetime = Field(default_factory=dt.datetime.now)
    glasses: int  # 8oz glasses

    def is_goal_met(self) -> bool:
        """Check if daily hydration goal (8 glasses) is met."""
        return self.glasses >= 8
class MeditationEntry(BaseModel):   
    """A meditation log entry."""

    id: Optional[int] = None
    date: dt.date = Field(default_factory=dt.date.today)
    timestamp: dt.datetime = Field(default_factory=dt.datetime.now)
    minutes: int

    def get_focus_bonus(self) -> float:
        """Get focus bonus for Pokemon encounters."""
        if self.minutes >= 20:
            return 1.5
        elif self.minutes >= 10:
            return 1.25
        return 1.0 
class MoodEntry(BaseModel):
    """A mood log entry."""

    id: Optional[int] = None
    date: dt.date = Field(default_factory=dt.date.today)
    timestamp: dt.datetime = Field(default_factory=dt.datetime.now)
    mood_level: int  # 1-10 scale

    def get_happiness_bonus(self) -> float:
        """Get happiness bonus for Pokemon encounters."""
        if self.mood_level >= 8:
            return 1.5
        elif self.mood_level >= 5:
            return 1.25
        return 1.0
    print(MoodEntry(mood_level=7)) 
    