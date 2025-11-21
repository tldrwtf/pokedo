"""SQLite database operations for PokeDo."""

import sqlite3
import json
from datetime import datetime, date
from pathlib import Path
from typing import Optional
from contextlib import contextmanager

from pokedo.utils.config import config
from pokedo.core.task import Task, TaskCategory, TaskDifficulty, TaskPriority, RecurrenceType
from pokedo.core.pokemon import Pokemon, PokedexEntry, PokemonRarity
from pokedo.core.trainer import Trainer, Streak, TrainerBadge
from pokedo.core.wellbeing import (
    MoodEntry, ExerciseEntry, SleepEntry, HydrationEntry,
    MeditationEntry, JournalEntry, MoodLevel, ExerciseType
)


class Database:
    """SQLite database manager."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or config.db_path
        config.ensure_dirs()
        self._init_db()

    @contextmanager
    def _get_connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self) -> None:
        """Initialize database schema."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Tasks table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT,
                    category TEXT DEFAULT 'personal',
                    difficulty TEXT DEFAULT 'medium',
                    priority TEXT DEFAULT 'medium',
                    created_at TEXT NOT NULL,
                    due_date TEXT,
                    completed_at TEXT,
                    is_completed INTEGER DEFAULT 0,
                    is_archived INTEGER DEFAULT 0,
                    recurrence TEXT DEFAULT 'none',
                    parent_task_id INTEGER,
                    tags TEXT DEFAULT '[]',
                    FOREIGN KEY (parent_task_id) REFERENCES tasks(id)
                )
            """)

            # Pokemon table (owned Pokemon)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pokemon (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pokedex_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    nickname TEXT,
                    type1 TEXT NOT NULL,
                    type2 TEXT,
                    level INTEGER DEFAULT 1,
                    xp INTEGER DEFAULT 0,
                    happiness INTEGER DEFAULT 50,
                    caught_at TEXT NOT NULL,
                    is_shiny INTEGER DEFAULT 0,
                    catch_location TEXT,
                    is_active INTEGER DEFAULT 0,
                    is_favorite INTEGER DEFAULT 0,
                    can_evolve INTEGER DEFAULT 0,
                    evolution_id INTEGER,
                    evolution_level INTEGER,
                    evolution_method TEXT,
                    sprite_url TEXT,
                    sprite_path TEXT
                )
            """)

            # Pokedex table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pokedex (
                    pokedex_id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    type1 TEXT NOT NULL,
                    type2 TEXT,
                    is_seen INTEGER DEFAULT 0,
                    is_caught INTEGER DEFAULT 0,
                    times_caught INTEGER DEFAULT 0,
                    first_caught_at TEXT,
                    shiny_caught INTEGER DEFAULT 0,
                    sprite_url TEXT,
                    rarity TEXT DEFAULT 'common',
                    evolves_from INTEGER,
                    evolves_to TEXT DEFAULT '[]'
                )
            """)

            # Trainer table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trainer (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT DEFAULT 'Trainer',
                    created_at TEXT NOT NULL,
                    total_xp INTEGER DEFAULT 0,
                    tasks_completed INTEGER DEFAULT 0,
                    tasks_completed_today INTEGER DEFAULT 0,
                    pokemon_caught INTEGER DEFAULT 0,
                    pokemon_released INTEGER DEFAULT 0,
                    evolutions_triggered INTEGER DEFAULT 0,
                    pokedex_seen INTEGER DEFAULT 0,
                    pokedex_caught INTEGER DEFAULT 0,
                    daily_streak_count INTEGER DEFAULT 0,
                    daily_streak_best INTEGER DEFAULT 0,
                    daily_streak_last_date TEXT,
                    wellbeing_streak_count INTEGER DEFAULT 0,
                    wellbeing_streak_best INTEGER DEFAULT 0,
                    wellbeing_streak_last_date TEXT,
                    badges TEXT DEFAULT '[]',
                    inventory TEXT DEFAULT '{}',
                    favorite_pokemon_id INTEGER,
                    last_active_date TEXT
                )
            """)

            # Wellbeing tables
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS mood_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    mood INTEGER NOT NULL,
                    note TEXT,
                    energy_level INTEGER
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS exercise_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    exercise_type TEXT NOT NULL,
                    duration_minutes INTEGER NOT NULL,
                    intensity INTEGER DEFAULT 3,
                    note TEXT
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sleep_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    hours REAL NOT NULL,
                    quality INTEGER DEFAULT 3,
                    note TEXT
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS hydration_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    glasses INTEGER NOT NULL,
                    note TEXT
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS meditation_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    minutes INTEGER NOT NULL,
                    note TEXT
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS journal_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    content TEXT NOT NULL,
                    gratitude_items TEXT DEFAULT '[]'
                )
            """)

    # Task operations
    def create_task(self, task: Task) -> Task:
        """Create a new task."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO tasks (title, description, category, difficulty, priority,
                    created_at, due_date, completed_at, is_completed, is_archived,
                    recurrence, parent_task_id, tags)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                task.title, task.description, task.category.value, task.difficulty.value,
                task.priority.value, task.created_at.isoformat(),
                task.due_date.isoformat() if task.due_date else None,
                task.completed_at.isoformat() if task.completed_at else None,
                int(task.is_completed), int(task.is_archived),
                task.recurrence.value, task.parent_task_id, json.dumps(task.tags)
            ))
            task.id = cursor.lastrowid
            return task

    def get_task(self, task_id: int) -> Optional[Task]:
        """Get a task by ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
            row = cursor.fetchone()
            if row:
                return self._row_to_task(row)
            return None

    def get_tasks(self, include_completed: bool = False, include_archived: bool = False) -> list[Task]:
        """Get all tasks with optional filters."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM tasks WHERE 1=1"
            if not include_completed:
                query += " AND is_completed = 0"
            if not include_archived:
                query += " AND is_archived = 0"
            query += " ORDER BY due_date ASC, priority DESC"
            cursor.execute(query)
            return [self._row_to_task(row) for row in cursor.fetchall()]

    def get_tasks_for_date(self, target_date: date) -> list[Task]:
        """Get tasks due on a specific date."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM tasks
                WHERE due_date = ? AND is_archived = 0
                ORDER BY priority DESC
            """, (target_date.isoformat(),))
            return [self._row_to_task(row) for row in cursor.fetchall()]

    def update_task(self, task: Task) -> None:
        """Update an existing task."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE tasks SET
                    title = ?, description = ?, category = ?, difficulty = ?,
                    priority = ?, due_date = ?, completed_at = ?, is_completed = ?,
                    is_archived = ?, recurrence = ?, parent_task_id = ?, tags = ?
                WHERE id = ?
            """, (
                task.title, task.description, task.category.value, task.difficulty.value,
                task.priority.value,
                task.due_date.isoformat() if task.due_date else None,
                task.completed_at.isoformat() if task.completed_at else None,
                int(task.is_completed), int(task.is_archived),
                task.recurrence.value, task.parent_task_id, json.dumps(task.tags),
                task.id
            ))

    def delete_task(self, task_id: int) -> None:
        """Delete a task."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))

    def _row_to_task(self, row: sqlite3.Row) -> Task:
        """Convert database row to Task model."""
        return Task(
            id=row["id"],
            title=row["title"],
            description=row["description"],
            category=TaskCategory(row["category"]),
            difficulty=TaskDifficulty(row["difficulty"]),
            priority=TaskPriority(row["priority"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            due_date=date.fromisoformat(row["due_date"]) if row["due_date"] else None,
            completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
            is_completed=bool(row["is_completed"]),
            is_archived=bool(row["is_archived"]),
            recurrence=RecurrenceType(row["recurrence"]),
            parent_task_id=row["parent_task_id"],
            tags=json.loads(row["tags"])
        )

    # Pokemon operations
    def save_pokemon(self, pokemon: Pokemon) -> Pokemon:
        """Save a caught Pokemon."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if pokemon.id:
                cursor.execute("""
                    UPDATE pokemon SET
                        nickname = ?, level = ?, xp = ?, happiness = ?,
                        is_active = ?, is_favorite = ?, can_evolve = ?
                    WHERE id = ?
                """, (
                    pokemon.nickname, pokemon.level, pokemon.xp, pokemon.happiness,
                    int(pokemon.is_active), int(pokemon.is_favorite),
                    int(pokemon.can_evolve), pokemon.id
                ))
            else:
                cursor.execute("""
                    INSERT INTO pokemon (pokedex_id, name, nickname, type1, type2,
                        level, xp, happiness, caught_at, is_shiny, catch_location,
                        is_active, is_favorite, can_evolve, evolution_id,
                        evolution_level, evolution_method, sprite_url, sprite_path)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    pokemon.pokedex_id, pokemon.name, pokemon.nickname,
                    pokemon.type1, pokemon.type2, pokemon.level, pokemon.xp,
                    pokemon.happiness, pokemon.caught_at.isoformat(),
                    int(pokemon.is_shiny), pokemon.catch_location,
                    int(pokemon.is_active), int(pokemon.is_favorite),
                    int(pokemon.can_evolve), pokemon.evolution_id,
                    pokemon.evolution_level, pokemon.evolution_method,
                    pokemon.sprite_url, pokemon.sprite_path
                ))
                pokemon.id = cursor.lastrowid
            return pokemon

    def get_pokemon(self, pokemon_id: int) -> Optional[Pokemon]:
        """Get a Pokemon by ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM pokemon WHERE id = ?", (pokemon_id,))
            row = cursor.fetchone()
            if row:
                return self._row_to_pokemon(row)
            return None

    def get_all_pokemon(self) -> list[Pokemon]:
        """Get all owned Pokemon."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM pokemon ORDER BY caught_at DESC")
            return [self._row_to_pokemon(row) for row in cursor.fetchall()]

    def get_active_team(self) -> list[Pokemon]:
        """Get Pokemon in active team."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM pokemon WHERE is_active = 1 LIMIT 6")
            return [self._row_to_pokemon(row) for row in cursor.fetchall()]

    def delete_pokemon(self, pokemon_id: int) -> None:
        """Release a Pokemon."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM pokemon WHERE id = ?", (pokemon_id,))

    def _row_to_pokemon(self, row: sqlite3.Row) -> Pokemon:
        """Convert database row to Pokemon model."""
        return Pokemon(
            id=row["id"],
            pokedex_id=row["pokedex_id"],
            name=row["name"],
            nickname=row["nickname"],
            type1=row["type1"],
            type2=row["type2"],
            level=row["level"],
            xp=row["xp"],
            happiness=row["happiness"],
            caught_at=datetime.fromisoformat(row["caught_at"]),
            is_shiny=bool(row["is_shiny"]),
            catch_location=row["catch_location"],
            is_active=bool(row["is_active"]),
            is_favorite=bool(row["is_favorite"]),
            can_evolve=bool(row["can_evolve"]),
            evolution_id=row["evolution_id"],
            evolution_level=row["evolution_level"],
            evolution_method=row["evolution_method"],
            sprite_url=row["sprite_url"],
            sprite_path=row["sprite_path"]
        )

    # Pokedex operations
    def save_pokedex_entry(self, entry: PokedexEntry) -> None:
        """Save or update a Pokedex entry."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO pokedex (pokedex_id, name, type1, type2,
                    is_seen, is_caught, times_caught, first_caught_at, shiny_caught,
                    sprite_url, rarity, evolves_from, evolves_to)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entry.pokedex_id, entry.name, entry.type1, entry.type2,
                int(entry.is_seen), int(entry.is_caught), entry.times_caught,
                entry.first_caught_at.isoformat() if entry.first_caught_at else None,
                int(entry.shiny_caught), entry.sprite_url, entry.rarity.value,
                entry.evolves_from, json.dumps(entry.evolves_to)
            ))

    def get_pokedex_entry(self, pokedex_id: int) -> Optional[PokedexEntry]:
        """Get a Pokedex entry."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM pokedex WHERE pokedex_id = ?", (pokedex_id,))
            row = cursor.fetchone()
            if row:
                return self._row_to_pokedex_entry(row)
            return None

    def get_pokedex(self) -> list[PokedexEntry]:
        """Get all Pokedex entries."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM pokedex ORDER BY pokedex_id")
            return [self._row_to_pokedex_entry(row) for row in cursor.fetchall()]

    def _row_to_pokedex_entry(self, row: sqlite3.Row) -> PokedexEntry:
        """Convert database row to PokedexEntry model."""
        return PokedexEntry(
            pokedex_id=row["pokedex_id"],
            name=row["name"],
            type1=row["type1"],
            type2=row["type2"],
            is_seen=bool(row["is_seen"]),
            is_caught=bool(row["is_caught"]),
            times_caught=row["times_caught"],
            first_caught_at=datetime.fromisoformat(row["first_caught_at"]) if row["first_caught_at"] else None,
            shiny_caught=bool(row["shiny_caught"]),
            sprite_url=row["sprite_url"],
            rarity=PokemonRarity(row["rarity"]),
            evolves_from=row["evolves_from"],
            evolves_to=json.loads(row["evolves_to"])
        )

    # Trainer operations
    def get_or_create_trainer(self, name: str = "Trainer") -> Trainer:
        """Get existing trainer or create new one."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM trainer LIMIT 1")
            row = cursor.fetchone()
            if row:
                return self._row_to_trainer(row)

            # Create new trainer
            trainer = Trainer(name=name)
            cursor.execute("""
                INSERT INTO trainer (name, created_at, total_xp, tasks_completed,
                    pokemon_caught, badges, inventory)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                trainer.name, trainer.created_at.isoformat(), trainer.total_xp,
                trainer.tasks_completed, trainer.pokemon_caught,
                json.dumps([]), json.dumps({})
            ))
            trainer.id = cursor.lastrowid
            return trainer

    def save_trainer(self, trainer: Trainer) -> None:
        """Save trainer data."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            badges_data = [
                {"id": b.id, "earned_at": b.earned_at.isoformat() if b.earned_at else None}
                for b in trainer.badges if b.is_earned
            ]
            cursor.execute("""
                UPDATE trainer SET
                    name = ?, total_xp = ?, tasks_completed = ?, tasks_completed_today = ?,
                    pokemon_caught = ?, pokemon_released = ?, evolutions_triggered = ?,
                    pokedex_seen = ?, pokedex_caught = ?,
                    daily_streak_count = ?, daily_streak_best = ?, daily_streak_last_date = ?,
                    wellbeing_streak_count = ?, wellbeing_streak_best = ?, wellbeing_streak_last_date = ?,
                    badges = ?, inventory = ?, favorite_pokemon_id = ?, last_active_date = ?
                WHERE id = ?
            """, (
                trainer.name, trainer.total_xp, trainer.tasks_completed,
                trainer.tasks_completed_today, trainer.pokemon_caught,
                trainer.pokemon_released, trainer.evolutions_triggered,
                trainer.pokedex_seen, trainer.pokedex_caught,
                trainer.daily_streak.current_count, trainer.daily_streak.best_count,
                trainer.daily_streak.last_activity_date.isoformat() if trainer.daily_streak.last_activity_date else None,
                trainer.wellbeing_streak.current_count, trainer.wellbeing_streak.best_count,
                trainer.wellbeing_streak.last_activity_date.isoformat() if trainer.wellbeing_streak.last_activity_date else None,
                json.dumps(badges_data), json.dumps(trainer.inventory),
                trainer.favorite_pokemon_id,
                trainer.last_active_date.isoformat() if trainer.last_active_date else None,
                trainer.id
            ))

    def _row_to_trainer(self, row: sqlite3.Row) -> Trainer:
        """Convert database row to Trainer model."""
        daily_streak = Streak(
            streak_type="daily",
            current_count=row["daily_streak_count"],
            best_count=row["daily_streak_best"],
            last_activity_date=date.fromisoformat(row["daily_streak_last_date"]) if row["daily_streak_last_date"] else None
        )
        wellbeing_streak = Streak(
            streak_type="wellbeing",
            current_count=row["wellbeing_streak_count"] or 0,
            best_count=row["wellbeing_streak_best"] or 0,
            last_activity_date=date.fromisoformat(row["wellbeing_streak_last_date"]) if row["wellbeing_streak_last_date"] else None
        )

        return Trainer(
            id=row["id"],
            name=row["name"],
            created_at=datetime.fromisoformat(row["created_at"]),
            total_xp=row["total_xp"],
            tasks_completed=row["tasks_completed"],
            tasks_completed_today=row["tasks_completed_today"] or 0,
            pokemon_caught=row["pokemon_caught"],
            pokemon_released=row["pokemon_released"] or 0,
            evolutions_triggered=row["evolutions_triggered"] or 0,
            pokedex_seen=row["pokedex_seen"] or 0,
            pokedex_caught=row["pokedex_caught"] or 0,
            daily_streak=daily_streak,
            wellbeing_streak=wellbeing_streak,
            badges=[],
            inventory=json.loads(row["inventory"]) if row["inventory"] else {},
            favorite_pokemon_id=row["favorite_pokemon_id"],
            last_active_date=date.fromisoformat(row["last_active_date"]) if row["last_active_date"] else None
        )

    # Wellbeing operations
    def save_mood(self, entry: MoodEntry) -> MoodEntry:
        """Save a mood entry."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO mood_entries (date, timestamp, mood, note, energy_level)
                VALUES (?, ?, ?, ?, ?)
            """, (
                entry.date.isoformat(), entry.timestamp.isoformat(),
                entry.mood.value, entry.note, entry.energy_level
            ))
            entry.id = cursor.lastrowid
            return entry

    def save_exercise(self, entry: ExerciseEntry) -> ExerciseEntry:
        """Save an exercise entry."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO exercise_entries (date, timestamp, exercise_type,
                    duration_minutes, intensity, note)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                entry.date.isoformat(), entry.timestamp.isoformat(),
                entry.exercise_type.value, entry.duration_minutes,
                entry.intensity, entry.note
            ))
            entry.id = cursor.lastrowid
            return entry

    def save_sleep(self, entry: SleepEntry) -> SleepEntry:
        """Save a sleep entry."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO sleep_entries (date, hours, quality, note)
                VALUES (?, ?, ?, ?)
            """, (entry.date.isoformat(), entry.hours, entry.quality, entry.note))
            entry.id = cursor.lastrowid
            return entry

    def save_hydration(self, entry: HydrationEntry) -> HydrationEntry:
        """Save a hydration entry."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO hydration_entries (date, glasses, note)
                VALUES (?, ?, ?)
            """, (entry.date.isoformat(), entry.glasses, entry.note))
            entry.id = cursor.lastrowid
            return entry

    def save_meditation(self, entry: MeditationEntry) -> MeditationEntry:
        """Save a meditation entry."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO meditation_entries (date, timestamp, minutes, note)
                VALUES (?, ?, ?, ?)
            """, (
                entry.date.isoformat(), entry.timestamp.isoformat(),
                entry.minutes, entry.note
            ))
            entry.id = cursor.lastrowid
            return entry

    def save_journal(self, entry: JournalEntry) -> JournalEntry:
        """Save a journal entry."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO journal_entries (date, timestamp, content, gratitude_items)
                VALUES (?, ?, ?, ?)
            """, (
                entry.date.isoformat(), entry.timestamp.isoformat(),
                entry.content, json.dumps(entry.gratitude_items)
            ))
            entry.id = cursor.lastrowid
            return entry

    def get_mood_for_date(self, target_date: date) -> Optional[MoodEntry]:
        """Get mood entry for a date."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM mood_entries WHERE date = ? ORDER BY timestamp DESC LIMIT 1
            """, (target_date.isoformat(),))
            row = cursor.fetchone()
            if row:
                return MoodEntry(
                    id=row["id"],
                    date=date.fromisoformat(row["date"]),
                    timestamp=datetime.fromisoformat(row["timestamp"]),
                    mood=MoodLevel(row["mood"]),
                    note=row["note"],
                    energy_level=row["energy_level"]
                )
            return None

    def get_exercises_for_date(self, target_date: date) -> list[ExerciseEntry]:
        """Get exercise entries for a date."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM exercise_entries WHERE date = ?
            """, (target_date.isoformat(),))
            return [
                ExerciseEntry(
                    id=row["id"],
                    date=date.fromisoformat(row["date"]),
                    timestamp=datetime.fromisoformat(row["timestamp"]),
                    exercise_type=ExerciseType(row["exercise_type"]),
                    duration_minutes=row["duration_minutes"],
                    intensity=row["intensity"],
                    note=row["note"]
                )
                for row in cursor.fetchall()
            ]


# Global database instance
db = Database()
