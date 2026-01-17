"""SQLite database operations for PokeDo."""

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path

from pokedo.core.pokemon import PokedexEntry, Pokemon, PokemonRarity
from pokedo.core.task import RecurrenceType, Task, TaskCategory, TaskDifficulty, TaskPriority
from pokedo.core.trainer import Streak, Trainer, TrainerClass
from pokedo.core.wellbeing import (
    ExerciseEntry,
    ExerciseType,
    HydrationEntry,
    JournalEntry,
    MeditationEntry,
    MoodEntry,
    MoodLevel,
    SleepEntry,
)
from pokedo.utils.config import config


class Database:
    """SQLite database manager."""

    def __init__(self, db_path: Path | None = None):
        if db_path is None:
            env_url = os.getenv("POKEDO_DATABASE_URL")
            if env_url and env_url.startswith("sqlite:///"):
                db_path = Path(env_url.replace("sqlite:///", ""))

        self._active_trainer_id: int | None = None
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
                    trainer_id INTEGER NOT NULL,
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
                    FOREIGN KEY (parent_task_id) REFERENCES tasks(id),
                    FOREIGN KEY (trainer_id) REFERENCES trainer(id)
                )
            """)

            # Pokemon table (owned Pokemon)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pokemon (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trainer_id INTEGER NOT NULL,
                    pokedex_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    nickname TEXT,
                    type1 TEXT NOT NULL,
                    type2 TEXT,
                    level INTEGER DEFAULT 1,
                    xp INTEGER DEFAULT 0,
                    happiness INTEGER DEFAULT 50,
                    evs TEXT DEFAULT '{}',
                    ivs TEXT DEFAULT '{}',
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
                    sprite_path TEXT,
                    FOREIGN KEY (trainer_id) REFERENCES trainer(id)
                )
            """)

            # Pokedex table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pokedex (
                    trainer_id INTEGER NOT NULL,
                    pokedex_id INTEGER NOT NULL,
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
                    evolves_to TEXT DEFAULT '[]',
                    PRIMARY KEY (trainer_id, pokedex_id),
                    FOREIGN KEY (trainer_id) REFERENCES trainer(id)
                )
            """)

            # Trainer table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trainer (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT DEFAULT 'Trainer',
                    trainer_class TEXT DEFAULT 'ace_trainer',
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

            # App settings (key/value)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS app_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)

            # Migration: Add trainer_class if missing
            try:
                cursor.execute(
                    "ALTER TABLE trainer ADD COLUMN trainer_class TEXT DEFAULT 'ace_trainer'"
                )
            except sqlite3.OperationalError:
                pass  # Column likely exists

            # Migration: Add EV/IV columns if missing on existing pokemon table
            for column in ("evs", "ivs"):
                try:
                    cursor.execute(f"ALTER TABLE pokemon ADD COLUMN {column} TEXT DEFAULT '{{}}'")
                except sqlite3.OperationalError:
                    pass  # Column likely exists

            # Migration: Add trainer_id columns and backfill existing rows
            default_trainer_id = self._ensure_default_trainer_id_for_migration(cursor)
            for table_name in (
                "tasks",
                "pokemon",
                "mood_entries",
                "exercise_entries",
                "sleep_entries",
                "hydration_entries",
                "meditation_entries",
                "journal_entries",
            ):
                self._ensure_trainer_id_column(cursor, table_name, default_trainer_id)

            # Migration: Make pokedex per-trainer
            self._migrate_pokedex_table(cursor, default_trainer_id)

            # Wellbeing tables
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS mood_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trainer_id INTEGER NOT NULL,
                    date TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    mood INTEGER NOT NULL,
                    note TEXT,
                    energy_level INTEGER,
                    FOREIGN KEY (trainer_id) REFERENCES trainer(id)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS exercise_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trainer_id INTEGER NOT NULL,
                    date TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    exercise_type TEXT NOT NULL,
                    duration_minutes INTEGER NOT NULL,
                    intensity INTEGER DEFAULT 3,
                    note TEXT,
                    FOREIGN KEY (trainer_id) REFERENCES trainer(id)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sleep_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trainer_id INTEGER NOT NULL,
                    date TEXT NOT NULL,
                    hours REAL NOT NULL,
                    quality INTEGER DEFAULT 3,
                    note TEXT,
                    FOREIGN KEY (trainer_id) REFERENCES trainer(id)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS hydration_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trainer_id INTEGER NOT NULL,
                    date TEXT NOT NULL,
                    glasses INTEGER NOT NULL,
                    note TEXT,
                    FOREIGN KEY (trainer_id) REFERENCES trainer(id)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS meditation_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trainer_id INTEGER NOT NULL,
                    date TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    minutes INTEGER NOT NULL,
                    note TEXT,
                    FOREIGN KEY (trainer_id) REFERENCES trainer(id)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS journal_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trainer_id INTEGER NOT NULL,
                    date TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    content TEXT NOT NULL,
                    gratitude_items TEXT DEFAULT '[]',
                    FOREIGN KEY (trainer_id) REFERENCES trainer(id)
                )
            """)

    def _ensure_trainer_id_column(
        self, cursor: sqlite3.Cursor, table_name: str, default_trainer_id: int | None
    ) -> None:
        """Ensure a trainer_id column exists and backfill existing rows."""
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table_name,),
        )
        if cursor.fetchone() is None:
            return
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = {row["name"] for row in cursor.fetchall()}
        if "trainer_id" not in columns:
            cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN trainer_id INTEGER")
        if default_trainer_id is not None:
            cursor.execute(
                f"UPDATE {table_name} SET trainer_id = ? WHERE trainer_id IS NULL",
                (default_trainer_id,),
            )

    def _ensure_default_trainer_id_for_migration(self, cursor: sqlite3.Cursor) -> int | None:
        """Ensure a default trainer ID exists for data migrations."""
        cursor.execute(
            "SELECT value FROM app_settings WHERE key = ?",
            ("default_trainer_id",),
        )
        row = cursor.fetchone()
        if row and row["value"]:
            try:
                return int(row["value"])
            except ValueError:
                pass

        cursor.execute("SELECT id FROM trainer ORDER BY id LIMIT 1")
        row = cursor.fetchone()
        if row:
            default_id = row["id"]
        else:
            trainer = self._create_trainer(cursor, "Trainer")
            default_id = trainer.id

        if default_id is None:
            return None

        cursor.execute(
            """
            INSERT INTO app_settings (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
            ("default_trainer_id", str(default_id)),
        )
        return default_id

    def _migrate_pokedex_table(
        self, cursor: sqlite3.Cursor, default_trainer_id: int | None
    ) -> None:
        """Migrate legacy pokedex table to per-trainer schema."""
        cursor.execute("PRAGMA table_info(pokedex)")
        columns = {row["name"] for row in cursor.fetchall()}
        if "trainer_id" in columns:
            return
        if default_trainer_id is None:
            default_trainer_id = self._ensure_default_trainer_id_for_migration(cursor)

        cursor.execute("ALTER TABLE pokedex RENAME TO pokedex_legacy")
        cursor.execute("""
            CREATE TABLE pokedex (
                trainer_id INTEGER NOT NULL,
                pokedex_id INTEGER NOT NULL,
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
                evolves_to TEXT DEFAULT '[]',
                PRIMARY KEY (trainer_id, pokedex_id),
                FOREIGN KEY (trainer_id) REFERENCES trainer(id)
            )
        """)
        if default_trainer_id is not None:
            cursor.execute(
                """
                INSERT INTO pokedex (
                    trainer_id, pokedex_id, name, type1, type2, is_seen, is_caught,
                    times_caught, first_caught_at, shiny_caught, sprite_url, rarity,
                    evolves_from, evolves_to
                )
                SELECT ?, pokedex_id, name, type1, type2, is_seen, is_caught,
                    times_caught, first_caught_at, shiny_caught, sprite_url, rarity,
                    evolves_from, evolves_to
                FROM pokedex_legacy
            """,
                (default_trainer_id,),
            )
        cursor.execute("DROP TABLE pokedex_legacy")

    def set_active_trainer_id(self, trainer_id: int | None) -> None:
        """Set the active trainer ID for this database session."""
        self._active_trainer_id = trainer_id

    def _resolve_trainer_id(
        self, trainer_id: int | None, ensure: bool = False
    ) -> int | None:
        """Resolve trainer ID using explicit, active, or default settings."""
        if trainer_id is not None:
            self._active_trainer_id = trainer_id
            return trainer_id
        if self._active_trainer_id is not None:
            return self._active_trainer_id

        default_id = self.get_default_trainer_id()
        if default_id is not None:
            self._active_trainer_id = default_id
            return default_id

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM trainer ORDER BY id LIMIT 1")
            row = cursor.fetchone()
            if row:
                self._active_trainer_id = row["id"]
                return self._active_trainer_id

        if ensure:
            trainer = self.get_or_create_trainer()
            return trainer.id

        return None

    # Task operations
    def create_task(self, task: Task, trainer_id: int | None = None) -> Task:
        """Create a new task."""
        resolved_trainer_id = self._resolve_trainer_id(trainer_id, ensure=True)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO tasks (trainer_id, title, description, category, difficulty, priority,
                    created_at, due_date, completed_at, is_completed, is_archived,
                    recurrence, parent_task_id, tags)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    resolved_trainer_id,
                    task.title,
                    task.description,
                    task.category.value,
                    task.difficulty.value,
                    task.priority.value,
                    task.created_at.isoformat(),
                    task.due_date.isoformat() if task.due_date else None,
                    task.completed_at.isoformat() if task.completed_at else None,
                    int(task.is_completed),
                    int(task.is_archived),
                    task.recurrence.value,
                    task.parent_task_id,
                    json.dumps(task.tags),
                ),
            )
            task.id = cursor.lastrowid
            return task

    def get_task(self, task_id: int, trainer_id: int | None = None) -> Task | None:
        """Get a task by ID."""
        resolved_trainer_id = self._resolve_trainer_id(trainer_id)
        if resolved_trainer_id is None:
            return None
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM tasks WHERE id = ? AND trainer_id = ?",
                (task_id, resolved_trainer_id),
            )
            row = cursor.fetchone()
            if row:
                return self._row_to_task(row)
            return None

    def get_tasks(
        self,
        include_completed: bool = False,
        include_archived: bool = False,
        trainer_id: int | None = None,
    ) -> list[Task]:
        """Get all tasks with optional filters."""
        resolved_trainer_id = self._resolve_trainer_id(trainer_id)
        if resolved_trainer_id is None:
            return []
        with self._get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM tasks WHERE trainer_id = ?"
            params: list = [resolved_trainer_id]
            if not include_completed:
                query += " AND is_completed = 0"
            if not include_archived:
                query += " AND is_archived = 0"
            query += """
                ORDER BY
                    due_date ASC,
                    CASE priority
                        WHEN 'urgent' THEN 4
                        WHEN 'high' THEN 3
                        WHEN 'medium' THEN 2
                        WHEN 'low' THEN 1
                        ELSE 0
                    END DESC
            """
            cursor.execute(query, params)
            return [self._row_to_task(row) for row in cursor.fetchall()]

    def get_tasks_for_date(
        self, target_date: date, trainer_id: int | None = None
    ) -> list[Task]:
        """Get tasks due on a specific date."""
        resolved_trainer_id = self._resolve_trainer_id(trainer_id)
        if resolved_trainer_id is None:
            return []
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM tasks
                WHERE due_date = ? AND is_archived = 0 AND trainer_id = ?
                ORDER BY
                    CASE priority
                        WHEN 'urgent' THEN 4
                        WHEN 'high' THEN 3
                        WHEN 'medium' THEN 2
                        WHEN 'low' THEN 1
                        ELSE 0
                    END DESC
            """,
                (target_date.isoformat(), resolved_trainer_id),
            )
            return [self._row_to_task(row) for row in cursor.fetchall()]

    def update_task(self, task: Task, trainer_id: int | None = None) -> None:
        """Update an existing task."""
        resolved_trainer_id = self._resolve_trainer_id(trainer_id)
        if resolved_trainer_id is None:
            return
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE tasks SET
                    title = ?, description = ?, category = ?, difficulty = ?,
                    priority = ?, due_date = ?, completed_at = ?, is_completed = ?,
                    is_archived = ?, recurrence = ?, parent_task_id = ?, tags = ?
                WHERE id = ? AND trainer_id = ?
            """,
                (
                    task.title,
                    task.description,
                    task.category.value,
                    task.difficulty.value,
                    task.priority.value,
                    task.due_date.isoformat() if task.due_date else None,
                    task.completed_at.isoformat() if task.completed_at else None,
                    int(task.is_completed),
                    int(task.is_archived),
                    task.recurrence.value,
                    task.parent_task_id,
                    json.dumps(task.tags),
                    task.id,
                    resolved_trainer_id,
                ),
            )

    def delete_task(self, task_id: int, trainer_id: int | None = None) -> None:
        """Delete a task."""
        resolved_trainer_id = self._resolve_trainer_id(trainer_id)
        if resolved_trainer_id is None:
            return
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM tasks WHERE id = ? AND trainer_id = ?",
                (task_id, resolved_trainer_id),
            )

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
            completed_at=(
                datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None
            ),
            is_completed=bool(row["is_completed"]),
            is_archived=bool(row["is_archived"]),
            recurrence=RecurrenceType(row["recurrence"]),
            parent_task_id=row["parent_task_id"],
            tags=json.loads(row["tags"]),
        )

    # Pokemon operations
    def save_pokemon(self, pokemon: Pokemon, trainer_id: int | None = None) -> Pokemon:
        """Save a caught Pokemon."""
        resolved_trainer_id = self._resolve_trainer_id(trainer_id, ensure=True)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if pokemon.id:
                cursor.execute(
                    """
                    UPDATE pokemon SET
                        nickname = ?, level = ?, xp = ?, happiness = ?, evs = ?, ivs = ?,
                        is_active = ?, is_favorite = ?, can_evolve = ?
                    WHERE id = ? AND trainer_id = ?
                """,
                    (
                        pokemon.nickname,
                        pokemon.level,
                        pokemon.xp,
                        pokemon.happiness,
                        json.dumps(pokemon.evs),
                        json.dumps(pokemon.ivs),
                        int(pokemon.is_active),
                        int(pokemon.is_favorite),
                        int(pokemon.can_evolve),
                        pokemon.id,
                        resolved_trainer_id,
                    ),
                )
            else:
                cursor.execute(
                    """
                    INSERT INTO pokemon (trainer_id, pokedex_id, name, nickname, type1, type2,
                        level, xp, happiness, evs, ivs, caught_at, is_shiny, catch_location,
                        is_active, is_favorite, can_evolve, evolution_id,
                        evolution_level, evolution_method, sprite_url, sprite_path)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        resolved_trainer_id,
                        pokemon.pokedex_id,
                        pokemon.name,
                        pokemon.nickname,
                        pokemon.type1,
                        pokemon.type2,
                        pokemon.level,
                        pokemon.xp,
                        pokemon.happiness,
                        json.dumps(pokemon.evs),
                        json.dumps(pokemon.ivs),
                        pokemon.caught_at.isoformat(),
                        int(pokemon.is_shiny),
                        pokemon.catch_location,
                        int(pokemon.is_active),
                        int(pokemon.is_favorite),
                        int(pokemon.can_evolve),
                        pokemon.evolution_id,
                        pokemon.evolution_level,
                        pokemon.evolution_method,
                        pokemon.sprite_url,
                        pokemon.sprite_path,
                    ),
                )
                pokemon.id = cursor.lastrowid
            return pokemon

    def get_pokemon(self, pokemon_id: int, trainer_id: int | None = None) -> Pokemon | None:
        """Get a Pokemon by ID."""
        resolved_trainer_id = self._resolve_trainer_id(trainer_id)
        if resolved_trainer_id is None:
            return None
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM pokemon WHERE id = ? AND trainer_id = ?",
                (pokemon_id, resolved_trainer_id),
            )
            row = cursor.fetchone()
            if row:
                return self._row_to_pokemon(row)
            return None

    def get_all_pokemon(self, trainer_id: int | None = None) -> list[Pokemon]:
        """Get all owned Pokemon."""
        resolved_trainer_id = self._resolve_trainer_id(trainer_id)
        if resolved_trainer_id is None:
            return []
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM pokemon WHERE trainer_id = ? ORDER BY caught_at DESC",
                (resolved_trainer_id,),
            )
            return [self._row_to_pokemon(row) for row in cursor.fetchall()]

    def get_active_team(self, trainer_id: int | None = None) -> list[Pokemon]:
        """Get Pokemon in active team."""
        resolved_trainer_id = self._resolve_trainer_id(trainer_id)
        if resolved_trainer_id is None:
            return []
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM pokemon WHERE trainer_id = ? AND is_active = 1 LIMIT 6",
                (resolved_trainer_id,),
            )
            return [self._row_to_pokemon(row) for row in cursor.fetchall()]

    def delete_pokemon(self, pokemon_id: int, trainer_id: int | None = None) -> None:
        """Release a Pokemon."""
        resolved_trainer_id = self._resolve_trainer_id(trainer_id)
        if resolved_trainer_id is None:
            return
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM pokemon WHERE id = ? AND trainer_id = ?",
                (pokemon_id, resolved_trainer_id),
            )

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
            evs=(
                json.loads(row["evs"])
                if "evs" in row.keys() and row["evs"]
                else {"hp": 0, "atk": 0, "def": 0, "spa": 0, "spd": 0, "spe": 0}
            ),
            ivs=(
                json.loads(row["ivs"])
                if "ivs" in row.keys() and row["ivs"]
                else {"hp": 0, "atk": 0, "def": 0, "spa": 0, "spd": 0, "spe": 0}
            ),
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
            sprite_path=row["sprite_path"],
        )

    # Pokedex operations
    def save_pokedex_entry(self, entry: PokedexEntry, trainer_id: int | None = None) -> None:
        """Save or update a Pokedex entry."""
        resolved_trainer_id = self._resolve_trainer_id(trainer_id, ensure=True)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO pokedex (
                    trainer_id, pokedex_id, name, type1, type2,
                    is_seen, is_caught, times_caught, first_caught_at, shiny_caught,
                    sprite_url, rarity, evolves_from, evolves_to)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    resolved_trainer_id,
                    entry.pokedex_id,
                    entry.name,
                    entry.type1,
                    entry.type2,
                    int(entry.is_seen),
                    int(entry.is_caught),
                    entry.times_caught,
                    entry.first_caught_at.isoformat() if entry.first_caught_at else None,
                    int(entry.shiny_caught),
                    entry.sprite_url,
                    entry.rarity.value,
                    entry.evolves_from,
                    json.dumps(entry.evolves_to),
                ),
            )

    def get_pokedex_entry(
        self, pokedex_id: int, trainer_id: int | None = None
    ) -> PokedexEntry | None:
        """Get a Pokedex entry."""
        resolved_trainer_id = self._resolve_trainer_id(trainer_id)
        if resolved_trainer_id is None:
            return None
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM pokedex WHERE trainer_id = ? AND pokedex_id = ?",
                (resolved_trainer_id, pokedex_id),
            )
            row = cursor.fetchone()
            if row:
                return self._row_to_pokedex_entry(row)
            return None

    def get_pokedex(self, trainer_id: int | None = None) -> list[PokedexEntry]:
        """Get all Pokedex entries."""
        resolved_trainer_id = self._resolve_trainer_id(trainer_id)
        if resolved_trainer_id is None:
            return []
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM pokedex WHERE trainer_id = ? ORDER BY pokedex_id",
                (resolved_trainer_id,),
            )
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
            first_caught_at=(
                datetime.fromisoformat(row["first_caught_at"]) if row["first_caught_at"] else None
            ),
            shiny_caught=bool(row["shiny_caught"]),
            sprite_url=row["sprite_url"],
            rarity=PokemonRarity(row["rarity"]),
            evolves_from=row["evolves_from"],
            evolves_to=json.loads(row["evolves_to"]),
        )

    # Trainer operations
    def get_or_create_trainer(self, name: str = "Trainer") -> Trainer:
        """Get existing trainer or create new one."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT value FROM app_settings WHERE key = ?",
                ("default_trainer_id",),
            )
            row = cursor.fetchone()
            if row and row["value"]:
                try:
                    default_id = int(row["value"])
                except ValueError:
                    default_id = None
                if default_id is not None:
                    cursor.execute("SELECT * FROM trainer WHERE id = ?", (default_id,))
                    trainer_row = cursor.fetchone()
                    if trainer_row:
                        trainer = self._row_to_trainer(trainer_row)
                        self._active_trainer_id = trainer.id
                        return trainer

            cursor.execute("SELECT * FROM trainer ORDER BY id LIMIT 1")
            row = cursor.fetchone()
            if row:
                trainer = self._row_to_trainer(row)
                self._active_trainer_id = trainer.id
                return trainer

            trainer = self._create_trainer(cursor, name)
            self._active_trainer_id = trainer.id
            return trainer

    def create_trainer(self, name: str = "Trainer") -> Trainer:
        """Create a new trainer profile."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            trainer = self._create_trainer(cursor, name)
            self._active_trainer_id = trainer.id
            return trainer

    def get_trainer_by_name(self, name: str) -> Trainer | None:
        """Get a trainer by name."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM trainer WHERE name = ? ORDER BY created_at DESC LIMIT 1",
                (name,),
            )
            row = cursor.fetchone()
            return self._row_to_trainer(row) if row else None

    def list_trainers(self) -> list[Trainer]:
        """List all trainer profiles."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM trainer ORDER BY created_at")
            return [self._row_to_trainer(row) for row in cursor.fetchall()]

    def get_trainer_by_id(self, trainer_id: int) -> Trainer | None:
        """Get a trainer by database ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM trainer WHERE id = ?", (trainer_id,))
            row = cursor.fetchone()
            return self._row_to_trainer(row) if row else None

    def get_default_trainer_id(self) -> int | None:
        """Get the default trainer ID if configured."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT value FROM app_settings WHERE key = ?",
                ("default_trainer_id",),
            )
            row = cursor.fetchone()
            if not row or not row["value"]:
                return None
            try:
                return int(row["value"])
            except ValueError:
                return None

    def set_default_trainer_id(self, trainer_id: int) -> None:
        """Persist the default trainer ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO app_settings (key, value)
                VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
                ("default_trainer_id", str(trainer_id)),
            )
        self._active_trainer_id = trainer_id

    def save_trainer(self, trainer: Trainer) -> None:
        """Save trainer data."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            badges_data = [
                {"id": b.id, "earned_at": b.earned_at.isoformat() if b.earned_at else None}
                for b in trainer.badges
                if b.is_earned
            ]
            cursor.execute(
                """
                UPDATE trainer SET
                    name = ?, trainer_class = ?, total_xp = ?, tasks_completed = ?, tasks_completed_today = ?,
                    pokemon_caught = ?, pokemon_released = ?, evolutions_triggered = ?,
                    pokedex_seen = ?, pokedex_caught = ?,
                    daily_streak_count = ?, daily_streak_best = ?, daily_streak_last_date = ?,
                    wellbeing_streak_count = ?, wellbeing_streak_best = ?, wellbeing_streak_last_date = ?,
                    badges = ?, inventory = ?, favorite_pokemon_id = ?, last_active_date = ?
                WHERE id = ?
            """,
                (
                    trainer.name,
                    trainer.trainer_class.value,
                    trainer.total_xp,
                    trainer.tasks_completed,
                    trainer.tasks_completed_today,
                    trainer.pokemon_caught,
                    trainer.pokemon_released,
                    trainer.evolutions_triggered,
                    trainer.pokedex_seen,
                    trainer.pokedex_caught,
                    trainer.daily_streak.current_count,
                    trainer.daily_streak.best_count,
                    (
                        trainer.daily_streak.last_activity_date.isoformat()
                        if trainer.daily_streak.last_activity_date
                        else None
                    ),
                    trainer.wellbeing_streak.current_count,
                    trainer.wellbeing_streak.best_count,
                    (
                        trainer.wellbeing_streak.last_activity_date.isoformat()
                        if trainer.wellbeing_streak.last_activity_date
                        else None
                    ),
                    json.dumps(badges_data),
                    json.dumps(trainer.inventory),
                    trainer.favorite_pokemon_id,
                    trainer.last_active_date.isoformat() if trainer.last_active_date else None,
                    trainer.id,
                ),
            )

    def _create_trainer(self, cursor: sqlite3.Cursor, name: str) -> Trainer:
        """Insert a new trainer row using an existing cursor."""
        trainer = Trainer(name=name)
        cursor.execute(
            """
            INSERT INTO trainer (name, trainer_class, created_at, total_xp, tasks_completed,
                pokemon_caught, badges, inventory)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                trainer.name,
                trainer.trainer_class.value,
                trainer.created_at.isoformat(),
                trainer.total_xp,
                trainer.tasks_completed,
                trainer.pokemon_caught,
                json.dumps([]),
                json.dumps({}),
            ),
        )
        trainer.id = cursor.lastrowid
        if trainer.id is not None:
            self._set_default_trainer_id_with_cursor(cursor, trainer.id)
        return trainer

    def _set_default_trainer_id_with_cursor(
        self, cursor: sqlite3.Cursor, trainer_id: int
    ) -> None:
        """Persist the default trainer ID using an existing cursor."""
        cursor.execute(
            "SELECT value FROM app_settings WHERE key = ?",
            ("default_trainer_id",),
        )
        row = cursor.fetchone()
        if row and row["value"]:
            return
        cursor.execute(
            """
            INSERT INTO app_settings (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
            ("default_trainer_id", str(trainer_id)),
        )

    def _row_to_trainer(self, row: sqlite3.Row) -> Trainer:
        """Convert database row to Trainer model."""
        daily_streak = Streak(
            streak_type="daily",
            current_count=row["daily_streak_count"],
            best_count=row["daily_streak_best"],
            last_activity_date=(
                date.fromisoformat(row["daily_streak_last_date"])
                if row["daily_streak_last_date"]
                else None
            ),
        )
        wellbeing_streak = Streak(
            streak_type="wellbeing",
            current_count=row["wellbeing_streak_count"] or 0,
            best_count=row["wellbeing_streak_best"] or 0,
            last_activity_date=(
                date.fromisoformat(row["wellbeing_streak_last_date"])
                if row["wellbeing_streak_last_date"]
                else None
            ),
        )

        return Trainer(
            id=row["id"],
            name=row["name"],
            trainer_class=(
                TrainerClass(row["trainer_class"])
                if "trainer_class" in row.keys()
                else TrainerClass.ACE_TRAINER
            ),
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
            last_active_date=(
                date.fromisoformat(row["last_active_date"]) if row["last_active_date"] else None
            ),
        )

    # Wellbeing operations
    def save_mood(self, entry: MoodEntry, trainer_id: int | None = None) -> MoodEntry:
        """Save a mood entry."""
        resolved_trainer_id = self._resolve_trainer_id(trainer_id, ensure=True)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO mood_entries (trainer_id, date, timestamp, mood, note, energy_level)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (
                    resolved_trainer_id,
                    entry.date.isoformat(),
                    entry.timestamp.isoformat(),
                    entry.mood.value,
                    entry.note,
                    entry.energy_level,
                ),
            )
            entry.id = cursor.lastrowid
            return entry

    def save_exercise(
        self, entry: ExerciseEntry, trainer_id: int | None = None
    ) -> ExerciseEntry:
        """Save an exercise entry."""
        resolved_trainer_id = self._resolve_trainer_id(trainer_id, ensure=True)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO exercise_entries (trainer_id, date, timestamp, exercise_type,
                    duration_minutes, intensity, note)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    resolved_trainer_id,
                    entry.date.isoformat(),
                    entry.timestamp.isoformat(),
                    entry.exercise_type.value,
                    entry.duration_minutes,
                    entry.intensity,
                    entry.note,
                ),
            )
            entry.id = cursor.lastrowid
            return entry

    def save_sleep(self, entry: SleepEntry, trainer_id: int | None = None) -> SleepEntry:
        """Save a sleep entry."""
        resolved_trainer_id = self._resolve_trainer_id(trainer_id, ensure=True)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO sleep_entries (trainer_id, date, hours, quality, note)
                VALUES (?, ?, ?, ?, ?)
            """,
                (
                    resolved_trainer_id,
                    entry.date.isoformat(),
                    entry.hours,
                    entry.quality,
                    entry.note,
                ),
            )
            entry.id = cursor.lastrowid
            return entry

    def save_hydration(
        self, entry: HydrationEntry, trainer_id: int | None = None
    ) -> HydrationEntry:
        """Save a hydration entry."""
        resolved_trainer_id = self._resolve_trainer_id(trainer_id, ensure=True)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO hydration_entries (trainer_id, date, glasses, note)
                VALUES (?, ?, ?, ?)
            """,
                (resolved_trainer_id, entry.date.isoformat(), entry.glasses, entry.note),
            )
            entry.id = cursor.lastrowid
            return entry

    def save_meditation(
        self, entry: MeditationEntry, trainer_id: int | None = None
    ) -> MeditationEntry:
        """Save a meditation entry."""
        resolved_trainer_id = self._resolve_trainer_id(trainer_id, ensure=True)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO meditation_entries (trainer_id, date, timestamp, minutes, note)
                VALUES (?, ?, ?, ?, ?)
            """,
                (
                    resolved_trainer_id,
                    entry.date.isoformat(),
                    entry.timestamp.isoformat(),
                    entry.minutes,
                    entry.note,
                ),
            )
            entry.id = cursor.lastrowid
            return entry

    def save_journal(self, entry: JournalEntry, trainer_id: int | None = None) -> JournalEntry:
        """Save a journal entry."""
        resolved_trainer_id = self._resolve_trainer_id(trainer_id, ensure=True)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO journal_entries (trainer_id, date, timestamp, content, gratitude_items)
                VALUES (?, ?, ?, ?, ?)
            """,
                (
                    resolved_trainer_id,
                    entry.date.isoformat(),
                    entry.timestamp.isoformat(),
                    entry.content,
                    json.dumps(entry.gratitude_items),
                ),
            )
            entry.id = cursor.lastrowid
            return entry

    def get_mood_for_date(
        self, target_date: date, trainer_id: int | None = None
    ) -> MoodEntry | None:
        """Get mood entry for a date."""
        resolved_trainer_id = self._resolve_trainer_id(trainer_id)
        if resolved_trainer_id is None:
            return None
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM mood_entries
                WHERE date = ? AND trainer_id = ?
                ORDER BY timestamp DESC LIMIT 1
            """,
                (target_date.isoformat(), resolved_trainer_id),
            )
            row = cursor.fetchone()
            if row:
                return MoodEntry(
                    id=row["id"],
                    date=date.fromisoformat(row["date"]),
                    timestamp=datetime.fromisoformat(row["timestamp"]),
                    mood=MoodLevel(row["mood"]),
                    note=row["note"],
                    energy_level=row["energy_level"],
                )
            return None

    def get_exercises_for_date(
        self, target_date: date, trainer_id: int | None = None
    ) -> list[ExerciseEntry]:
        """Get exercise entries for a date."""
        resolved_trainer_id = self._resolve_trainer_id(trainer_id)
        if resolved_trainer_id is None:
            return []
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM exercise_entries WHERE date = ? AND trainer_id = ?
            """,
                (target_date.isoformat(), resolved_trainer_id),
            )
            return [
                ExerciseEntry(
                    id=row["id"],
                    date=date.fromisoformat(row["date"]),
                    timestamp=datetime.fromisoformat(row["timestamp"]),
                    exercise_type=ExerciseType(row["exercise_type"]),
                    duration_minutes=row["duration_minutes"],
                    intensity=row["intensity"],
                    note=row["note"],
                )
                for row in cursor.fetchall()
            ]


# Global database instance
db = Database()
