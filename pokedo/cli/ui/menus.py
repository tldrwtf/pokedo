"""Interactive menu components for the CLI."""

from typing import Optional, Callable
from rich.console import Console
from rich.prompt import Prompt, IntPrompt, Confirm
from rich.panel import Panel
from rich import box

console = Console()


def show_main_menu() -> str:
    """Display main interactive menu and get user choice."""
    console.print()
    console.print(Panel(
        """[bold]PokeDo Main Menu[/bold]

[1] Tasks
[2] Pokemon
[3] Wellbeing
[4] Stats & Profile
[5] Daily Overview
[0] Exit""",
        box=box.ROUNDED
    ))

    choice = Prompt.ask("Select option", choices=["0", "1", "2", "3", "4", "5"], default="5")
    return choice


def show_task_menu() -> str:
    """Display task management menu."""
    console.print()
    console.print(Panel(
        """[bold]Task Management[/bold]

[1] List pending tasks
[2] Add new task
[3] Complete a task
[4] Show today's tasks
[5] Edit task
[6] Delete task
[0] Back""",
        box=box.ROUNDED
    ))

    choice = Prompt.ask("Select option", choices=["0", "1", "2", "3", "4", "5", "6"], default="1")
    return choice


def show_pokemon_menu() -> str:
    """Display Pokemon management menu."""
    console.print()
    console.print(Panel(
        """[bold]Pokemon[/bold]

[1] View active team
[2] View Pokemon box
[3] View Pokedex
[4] Add to team
[5] Remove from team
[6] Nickname Pokemon
[7] Evolve Pokemon
[8] Release Pokemon
[0] Back""",
        box=box.ROUNDED
    ))

    choice = Prompt.ask("Select option", choices=["0", "1", "2", "3", "4", "5", "6", "7", "8"], default="1")
    return choice


def show_wellbeing_menu() -> str:
    """Display wellbeing tracking menu."""
    console.print()
    console.print(Panel(
        """[bold]Wellbeing Tracking[/bold]

[1] Log mood
[2] Log exercise
[3] Log sleep
[4] Log water intake
[5] Log meditation
[6] Write journal entry
[7] Today's summary
[0] Back""",
        box=box.ROUNDED
    ))

    choice = Prompt.ask("Select option", choices=["0", "1", "2", "3", "4", "5", "6", "7"], default="7")
    return choice


def show_stats_menu() -> str:
    """Display stats and profile menu."""
    console.print()
    console.print(Panel(
        """[bold]Stats & Profile[/bold]

[1] Trainer profile
[2] Streaks
[3] Badges
[4] Inventory
[5] History
[6] Change trainer name
[0] Back""",
        box=box.ROUNDED
    ))

    choice = Prompt.ask("Select option", choices=["0", "1", "2", "3", "4", "5", "6"], default="1")
    return choice


def prompt_task_details() -> dict:
    """Prompt for new task details."""
    from pokedo.core.task import TaskCategory, TaskDifficulty, TaskPriority

    title = Prompt.ask("Task title")

    console.print("\nCategories: work, exercise, learning, personal, health, creative")
    category = Prompt.ask("Category", default="personal")

    console.print("\nDifficulty: easy, medium, hard, epic")
    difficulty = Prompt.ask("Difficulty", default="medium")

    console.print("\nPriority: low, medium, high, urgent")
    priority = Prompt.ask("Priority", default="medium")

    due = Prompt.ask("Due date (YYYY-MM-DD, today, tomorrow, or blank)", default="")

    description = Prompt.ask("Description (optional)", default="")

    return {
        "title": title,
        "category": TaskCategory(category),
        "difficulty": TaskDifficulty(difficulty),
        "priority": TaskPriority(priority),
        "due": due if due else None,
        "description": description if description else None
    }


def prompt_mood() -> tuple[int, Optional[str]]:
    """Prompt for mood entry."""
    console.print("\nMood levels: 1=Very Low, 2=Low, 3=Neutral, 4=Good, 5=Great")
    level = IntPrompt.ask("How are you feeling?", default=3)
    level = max(1, min(5, level))

    note = Prompt.ask("Any notes? (optional)", default="")
    return level, note if note else None


def prompt_exercise() -> dict:
    """Prompt for exercise entry."""
    from pokedo.core.wellbeing import ExerciseType

    console.print("\nExercise types: cardio, strength, yoga, swimming, cycling, walking, running, sports, hiking, dancing, other")
    exercise_type = Prompt.ask("Exercise type", default="cardio")

    duration = IntPrompt.ask("Duration (minutes)")
    intensity = IntPrompt.ask("Intensity (1-5)", default=3)
    intensity = max(1, min(5, intensity))

    return {
        "exercise_type": ExerciseType(exercise_type),
        "duration": duration,
        "intensity": intensity
    }


def confirm_action(message: str) -> bool:
    """Confirm an action with the user."""
    return Confirm.ask(message)


def select_from_list(items: list, prompt: str = "Select") -> Optional[int]:
    """Let user select from a numbered list."""
    if not items:
        return None

    for i, item in enumerate(items, 1):
        console.print(f"[{i}] {item}")

    try:
        choice = IntPrompt.ask(prompt, default=1)
        if 1 <= choice <= len(items):
            return choice - 1
    except ValueError:
        pass
    return None
