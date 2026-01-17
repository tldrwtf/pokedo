"""Tests for per-profile data scoping."""

from pokedo.core.pokemon import Pokemon
from pokedo.core.task import Task
from pokedo.core.wellbeing import MoodEntry, MoodLevel


def test_tasks_scoped_by_profile(isolated_db):
    """Tasks should be isolated per trainer profile."""
    trainer_a = isolated_db.create_trainer("Alpha")
    trainer_b = isolated_db.create_trainer("Beta")

    isolated_db.set_active_trainer_id(trainer_a.id)
    task_a = isolated_db.create_task(Task(title="A task"))

    isolated_db.set_active_trainer_id(trainer_b.id)
    task_b = isolated_db.create_task(Task(title="B task"))

    tasks_a = isolated_db.get_tasks(trainer_id=trainer_a.id)
    tasks_b = isolated_db.get_tasks(trainer_id=trainer_b.id)

    assert [t.id for t in tasks_a] == [task_a.id]
    assert [t.id for t in tasks_b] == [task_b.id]
    assert isolated_db.get_task(task_a.id, trainer_id=trainer_b.id) is None
    assert isolated_db.get_task(task_b.id, trainer_id=trainer_a.id) is None


def test_pokemon_scoped_by_profile(isolated_db):
    """Pokemon collections should be isolated per trainer profile."""
    trainer_a = isolated_db.create_trainer("Alpha")
    trainer_b = isolated_db.create_trainer("Beta")

    isolated_db.set_active_trainer_id(trainer_a.id)
    pokemon_a = isolated_db.save_pokemon(
        Pokemon(pokedex_id=25, name="pikachu", type1="electric")
    )

    isolated_db.set_active_trainer_id(trainer_b.id)
    pokemon_b = isolated_db.save_pokemon(
        Pokemon(pokedex_id=4, name="charmander", type1="fire")
    )

    list_a = isolated_db.get_all_pokemon(trainer_id=trainer_a.id)
    list_b = isolated_db.get_all_pokemon(trainer_id=trainer_b.id)

    assert [p.id for p in list_a] == [pokemon_a.id]
    assert [p.id for p in list_b] == [pokemon_b.id]
    assert isolated_db.get_pokemon(pokemon_a.id, trainer_id=trainer_b.id) is None
    assert isolated_db.get_pokemon(pokemon_b.id, trainer_id=trainer_a.id) is None


def test_wellbeing_scoped_by_profile(isolated_db):
    """Wellbeing entries should be isolated per trainer profile."""
    trainer_a = isolated_db.create_trainer("Alpha")
    trainer_b = isolated_db.create_trainer("Beta")

    isolated_db.set_active_trainer_id(trainer_a.id)
    entry = isolated_db.save_mood(MoodEntry(mood=MoodLevel.GOOD, note="Good day"))

    isolated_db.set_active_trainer_id(trainer_b.id)
    mood_b = isolated_db.get_mood_for_date(entry.date, trainer_id=trainer_b.id)
    mood_a = isolated_db.get_mood_for_date(entry.date, trainer_id=trainer_a.id)

    assert mood_b is None
    assert mood_a is not None
    assert mood_a.note == "Good day"
