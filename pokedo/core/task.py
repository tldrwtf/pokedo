"""Task model and related logic."""

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, Field


class TaskCategory(str, Enum):
    """Categories for tasks that map to Pokemon types."""
    WORK = "work"           # Steel, Electric
    EXERCISE = "exercise"   # Fighting, Fire
    LEARNING = "learning"   # Psychic, Ghost
    PERSONAL = "personal"   # Normal, Fairy
    HEALTH = "health"       # Grass, Water
    CREATIVE = "creative"   # Fairy, Dragon


class TaskDifficulty(str, Enum):
    """Task difficulty levels affecting rewards."""
    EASY = "easy"       # Common Pokemon, 10 XP
    MEDIUM = "medium"   # Uncommon Pokemon, 25 XP
    HARD = "hard"       # Rare Pokemon, 50 XP
    EPIC = "epic"       # Legendary Pokemon, 100 XP


class TaskPriority(str, Enum):
    """Task priority levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class RecurrenceType(str, Enum):
    """Types of task recurrence."""
    NONE = "none"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class Task(BaseModel):
    """A task/todo item."""

    id: int | None = None
    title: str
    description: str | None = None
    category: TaskCategory = TaskCategory.PERSONAL
    difficulty: TaskDifficulty = TaskDifficulty.MEDIUM
    priority: TaskPriority = TaskPriority.MEDIUM

    # Dates
    created_at: datetime = Field(default_factory=datetime.now)
    due_date: date | None = None
    completed_at: datetime | None = None

    # Status
    is_completed: bool = False
    is_archived: bool = False

    # Recurrence
    recurrence: RecurrenceType = RecurrenceType.NONE
    parent_task_id: int | None = None  # For subtasks

    # Tags for flexible categorization
    tags: list[str] = Field(default_factory=list)

    @property
    def is_overdue(self) -> bool:
        """Check if task is overdue."""
        if self.due_date and not self.is_completed:
            return date.today() > self.due_date
        return False

    @property
    def xp_reward(self) -> int:
        """Calculate XP reward for completing this task."""
        from pokedo.utils.config import config
        rewards = {
            TaskDifficulty.EASY: config.task_xp_easy,
            TaskDifficulty.MEDIUM: config.task_xp_medium,
            TaskDifficulty.HARD: config.task_xp_hard,
            TaskDifficulty.EPIC: config.task_xp_epic,
        }
        return rewards[self.difficulty]

    def get_pokemon_rarity_weights(self) -> dict[str, float]:
        """Get Pokemon rarity weights based on difficulty."""
        weights = {
            TaskDifficulty.EASY: {
                "common": 0.70,
                "uncommon": 0.25,
                "rare": 0.05,
                "epic": 0.00,
                "legendary": 0.00
            },
            TaskDifficulty.MEDIUM: {
                "common": 0.50,
                "uncommon": 0.35,
                "rare": 0.12,
                "epic": 0.03,
                "legendary": 0.00
            },
            TaskDifficulty.HARD: {
                "common": 0.30,
                "uncommon": 0.35,
                "rare": 0.25,
                "epic": 0.09,
                "legendary": 0.01
            },
            TaskDifficulty.EPIC: {
                "common": 0.10,
                "uncommon": 0.25,
                "rare": 0.35,
                "epic": 0.25,
                "legendary": 0.05
            }
        }
        return weights[self.difficulty]

    def get_type_affinity(self) -> list[str]:
        """Get Pokemon types with affinity for this task category."""
        affinities = {
            TaskCategory.WORK: ["steel", "electric", "normal"],
            TaskCategory.EXERCISE: ["fighting", "fire", "rock"],
            TaskCategory.LEARNING: ["psychic", "ghost", "dark"],
            TaskCategory.PERSONAL: ["normal", "fairy", "flying"],
            TaskCategory.HEALTH: ["grass", "water", "poison"],
            TaskCategory.CREATIVE: ["fairy", "dragon", "ice"],
        }
        return affinities[self.category]
