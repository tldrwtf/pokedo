"""Shared fixtures for PokeDo tests."""

import importlib
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pokedo.core.pokemon import PokedexEntry, Pokemon, PokemonRarity, PokemonTeam
from pokedo.core.task import RecurrenceType, Task, TaskCategory, TaskDifficulty, TaskPriority
from pokedo.core.trainer import Streak, Trainer, TrainerBadge
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
from pokedo.data.database import Database
from pokedo.utils import config as config_module


# Task fixtures
@pytest.fixture
def sample_task():
    """Create a basic sample task."""
    return Task(
        id=1,
        title="Test Task",
        description="A test task description",
        category=TaskCategory.WORK,
        difficulty=TaskDifficulty.MEDIUM,
        priority=TaskPriority.MEDIUM,
    )


@pytest.fixture
def easy_task():
    """Create an easy task."""
    return Task(
        id=2,
        title="Easy Task",
        category=TaskCategory.PERSONAL,
        difficulty=TaskDifficulty.EASY,
    )


@pytest.fixture
def hard_task():
    """Create a hard task."""
    return Task(
        id=3,
        title="Hard Task",
        category=TaskCategory.EXERCISE,
        difficulty=TaskDifficulty.HARD,
    )


@pytest.fixture
def epic_task():
    """Create an epic task."""
    return Task(
        id=4,
        title="Epic Task",
        category=TaskCategory.LEARNING,
        difficulty=TaskDifficulty.EPIC,
    )


@pytest.fixture
def overdue_task():
    """Create an overdue task."""
    return Task(
        id=5,
        title="Overdue Task",
        due_date=date.today() - timedelta(days=1),
        is_completed=False,
    )


@pytest.fixture
def completed_task():
    """Create a completed task."""
    return Task(
        id=6,
        title="Completed Task",
        is_completed=True,
        completed_at=datetime.now(),
    )


@pytest.fixture
def recurring_task():
    """Create a recurring daily task."""
    return Task(
        id=7,
        title="Daily Task",
        recurrence=RecurrenceType.DAILY,
    )


# Pokemon fixtures
@pytest.fixture
def sample_pokemon():
    """Create a sample Pokemon."""
    return Pokemon(
        id=1,
        pokedex_id=25,
        name="pikachu",
        type1="electric",
        level=5,
        xp=100,
        happiness=70,
    )


@pytest.fixture
def shiny_pokemon():
    """Create a shiny Pokemon."""
    return Pokemon(
        id=2,
        pokedex_id=6,
        name="charizard",
        type1="fire",
        type2="flying",
        level=36,
        is_shiny=True,
    )


@pytest.fixture
def evolvable_pokemon():
    """Create a Pokemon ready to evolve."""
    return Pokemon(
        id=3,
        pokedex_id=4,
        name="charmander",
        type1="fire",
        level=16,
        can_evolve=True,
        evolution_id=5,
        evolution_level=16,
    )


@pytest.fixture
def sample_pokedex_entry():
    """Create a sample Pokedex entry."""
    return PokedexEntry(
        pokedex_id=25,
        name="pikachu",
        type1="electric",
        is_seen=True,
        is_caught=True,
        times_caught=3,
        rarity=PokemonRarity.COMMON,
    )


@pytest.fixture
def legendary_pokedex_entry():
    """Create a legendary Pokedex entry."""
    return PokedexEntry(
        pokedex_id=150,
        name="mewtwo",
        type1="psychic",
        rarity=PokemonRarity.LEGENDARY,
    )


@pytest.fixture
def empty_team():
    """Create an empty Pokemon team."""
    return PokemonTeam()


@pytest.fixture
def partial_team(sample_pokemon):
    """Create a team with one Pokemon."""
    team = PokemonTeam()
    team.add(sample_pokemon)
    return team


@pytest.fixture
def full_team():
    """Create a full team of 6 Pokemon."""
    team = PokemonTeam()
    for i in range(6):
        pokemon = Pokemon(
            id=i + 1,
            pokedex_id=i + 1,
            name=f"pokemon_{i + 1}",
            type1="normal",
        )
        team.add(pokemon)
    return team


# Trainer fixtures
@pytest.fixture
def new_trainer():
    """Create a new trainer with no progress."""
    return Trainer(name="Test Trainer")


@pytest.fixture
def experienced_trainer():
    """Create an experienced trainer."""
    return Trainer(
        id=1,
        name="Experienced Trainer",
        total_xp=5000,
        tasks_completed=50,
        pokemon_caught=30,
        pokedex_seen=50,
        pokedex_caught=30,
    )


@pytest.fixture
def trainer_with_streak():
    """Create a trainer with an active streak."""
    trainer = Trainer(name="Streak Trainer")
    trainer.daily_streak.current_count = 7
    trainer.daily_streak.best_count = 10
    trainer.daily_streak.last_activity_date = date.today()
    return trainer


@pytest.fixture
def trainer_with_inventory():
    """Create a trainer with items."""
    trainer = Trainer(name="Inventory Trainer")
    trainer.inventory = {
        "pokeball": 10,
        "great_ball": 5,
        "ultra_ball": 2,
        "master_ball": 1,
    }
    return trainer


@pytest.fixture
def sample_streak():
    """Create a sample streak."""
    return Streak(
        streak_type="daily",
        current_count=5,
        best_count=10,
        last_activity_date=date.today(),
    )


@pytest.fixture
def sample_badge():
    """Create a sample badge."""
    return TrainerBadge(
        id="starter",
        name="Starter",
        description="Complete your first task",
        icon="[ST]",
        requirement_type="tasks",
        requirement_count=1,
    )


# Wellbeing fixtures
@pytest.fixture
def good_mood():
    """Create a good mood entry."""
    return MoodEntry(
        mood=MoodLevel.GOOD,
        note="Feeling productive",
        energy_level=4,
    )


@pytest.fixture
def low_mood():
    """Create a low mood entry."""
    return MoodEntry(
        mood=MoodLevel.LOW,
        note="Tired today",
        energy_level=2,
    )


@pytest.fixture
def cardio_exercise():
    """Create a cardio exercise entry."""
    return ExerciseEntry(
        exercise_type=ExerciseType.CARDIO,
        duration_minutes=30,
        intensity=4,
    )


@pytest.fixture
def yoga_exercise():
    """Create a yoga exercise entry."""
    return ExerciseEntry(
        exercise_type=ExerciseType.YOGA,
        duration_minutes=45,
        intensity=3,
    )


@pytest.fixture
def good_sleep():
    """Create a good sleep entry."""
    return SleepEntry(
        hours=8.0,
        quality=4,
    )


@pytest.fixture
def poor_sleep():
    """Create a poor sleep entry."""
    return SleepEntry(
        hours=4.5,
        quality=2,
    )


@pytest.fixture
def full_hydration():
    """Create an entry meeting hydration goal."""
    return HydrationEntry(glasses=8)


@pytest.fixture
def partial_hydration():
    """Create a partial hydration entry."""
    return HydrationEntry(glasses=5)


@pytest.fixture
def long_meditation():
    """Create a long meditation entry."""
    return MeditationEntry(minutes=20)


@pytest.fixture
def short_meditation():
    """Create a short meditation entry."""
    return MeditationEntry(minutes=5)


@pytest.fixture
def gratitude_journal():
    """Create a gratitude journal entry."""
    return JournalEntry(
        content="Today was a productive day. I accomplished my goals.",
        gratitude_items=["health", "family", "progress"],
    )


@pytest.fixture
def complete_daily_wellbeing(
    good_mood, cardio_exercise, good_sleep, full_hydration, long_meditation, gratitude_journal
):
    """Create a complete daily wellbeing record."""
    return DailyWellbeing(
        mood=good_mood,
        exercises=[cardio_exercise],
        sleep=good_sleep,
        hydration=full_hydration,
        meditation=long_meditation,
        journal=gratitude_journal,
    )


@pytest.fixture
def partial_daily_wellbeing(good_mood, good_sleep):
    """Create a partial daily wellbeing record."""
    return DailyWellbeing(
        mood=good_mood,
        sleep=good_sleep,
    )


# Utility fixtures
@pytest.fixture
def temp_data_dir():
    """Create a temporary data directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def cli_runner() -> CliRunner:
    """Provide a Typer CLI runner for command tests."""
    return CliRunner()


@pytest.fixture
def isolated_db(tmp_path, monkeypatch) -> Database:
    """Provide a database instance isolated to a temporary directory."""
    data_dir = tmp_path / "data"
    cache_dir = data_dir / "cache"
    sprites_dir = cache_dir / "sprites"
    db_path = data_dir / "pokedo.db"

    for attr, value in (
        ("data_dir", data_dir),
        ("cache_dir", cache_dir),
        ("sprites_dir", sprites_dir),
        ("db_path", db_path),
    ):
        monkeypatch.setattr(config_module.config, attr, value)

    test_db = Database(db_path=db_path)

    modules_to_patch = [
        "pokedo.data.database",
        "pokedo.cli.commands.pokemon",
        "pokedo.cli.commands.tasks",
        "pokedo.cli.commands.stats",
        "pokedo.cli.commands.wellbeing",
    ]
    for module_name in modules_to_patch:
        module = importlib.import_module(module_name)
        monkeypatch.setattr(module, "db", test_db)

    return test_db
