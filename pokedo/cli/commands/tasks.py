"""Task management CLI commands."""

from datetime import date, datetime, timedelta

import typer
from rich.console import Console
from rich.prompt import Confirm

from pokedo.cli.ui.displays import (
    display_encounter,
    display_task_completion_result,
    display_task_detail,
    display_task_list,
)
from pokedo.core.rewards import reward_engine
from pokedo.core.task import RecurrenceType, Task, TaskCategory, TaskDifficulty, TaskPriority
from pokedo.data.database import db

app = typer.Typer(help="Task management commands")
console = Console()


def parse_due_date(due: str) -> date | None:
    """Parse due date from string."""
    due_lower = due.lower()
    today = date.today()

    if due_lower == "today":
        return today
    elif due_lower == "tomorrow":
        return today + timedelta(days=1)
    elif due_lower == "next week":
        return today + timedelta(weeks=1)
    else:
        try:
            return date.fromisoformat(due)
        except ValueError:
            return None


@app.command("add")
def add_task(
    title: str = typer.Argument(..., help="Task title"),
    category: TaskCategory = typer.Option(
        TaskCategory.PERSONAL, "--category", "-c", help="Task category"
    ),
    difficulty: TaskDifficulty = typer.Option(
        TaskDifficulty.MEDIUM, "--difficulty", "-d", help="Task difficulty"
    ),
    priority: TaskPriority = typer.Option(
        TaskPriority.MEDIUM, "--priority", "-p", help="Task priority"
    ),
    due: str | None = typer.Option(None, "--due", help="Due date (YYYY-MM-DD, today, tomorrow)"),
    description: str | None = typer.Option(None, "--desc", help="Task description"),
    tags: str | None = typer.Option(None, "--tags", "-t", help="Comma-separated tags"),
    recurrence: RecurrenceType = typer.Option(
        RecurrenceType.NONE, "--recur", "-r", help="Recurrence pattern"
    ),
) -> None:
    """Add a new task."""
    due_date = parse_due_date(due) if due else None
    tag_list = [t.strip() for t in tags.split(",")] if tags else []

    task = Task(
        title=title,
        description=description,
        category=category,
        difficulty=difficulty,
        priority=priority,
        due_date=due_date,
        recurrence=recurrence,
        tags=tag_list,
    )

    task = db.create_task(task)
    console.print(f"[green]Task created![/green] ID: {task.id}")
    console.print(
        f"  Category: {category.value} | Difficulty: {difficulty.value} | XP: {task.xp_reward}"
    )


@app.command("list")
def list_tasks(
    today: bool = typer.Option(False, "--today", help="Show only today's tasks"),
    week: bool = typer.Option(False, "--week", help="Show this week's tasks"),
    all_tasks: bool = typer.Option(False, "--all", "-a", help="Include completed tasks"),
    category: TaskCategory | None = typer.Option(
        None, "--category", "-c", help="Filter by category"
    ),
) -> None:
    """List tasks."""
    if today:
        tasks = db.get_tasks_for_date(date.today())
        title = "Today's Tasks"
    elif week:
        # Get tasks for the next 7 days
        tasks = []
        for i in range(7):
            day = date.today() + timedelta(days=i)
            tasks.extend(db.get_tasks_for_date(day))
        title = "This Week's Tasks"
    else:
        tasks = db.get_tasks(include_completed=all_tasks)
        title = "All Tasks" if all_tasks else "Pending Tasks"

    if category:
        tasks = [t for t in tasks if t.category == category]
        title = f"{title} ({category.value})"

    display_task_list(tasks, title)


@app.command("show")
def show_task(task_id: int = typer.Argument(..., help="Task ID")) -> None:
    """Show task details."""
    task = db.get_task(task_id)
    if not task:
        console.print(f"[red]Task {task_id} not found.[/red]")
        raise typer.Exit(1)

    display_task_detail(task)


@app.command("complete")
def complete_task(task_id: int = typer.Argument(..., help="Task ID to complete")) -> None:
    """Complete a task and trigger Pokemon encounter."""
    task = db.get_task(task_id)
    if not task:
        console.print(f"[red]Task {task_id} not found.[/red]")
        raise typer.Exit(1)

    if task.is_completed:
        console.print(f"[yellow]Task {task_id} is already completed.[/yellow]")
        raise typer.Exit(1)

    # Mark task as completed
    task.is_completed = True
    task.completed_at = datetime.now()
    db.update_task(task)

    # Get trainer
    trainer = db.get_or_create_trainer()

    # Process rewards and encounter
    result = reward_engine.process_task_completion(task, trainer)

    # Display completion summary
    display_task_completion_result(
        task=task,
        xp_earned=result.xp_earned,
        level_up=result.level_up,
        new_level=result.new_level,
        streak_count=result.streak_count,
        items_earned=result.items_earned,
    )

    # Add items to inventory
    for item, count in result.items_earned.items():
        trainer.add_item(item, count)

    # Handle Pokemon encounter
    if result.encountered:
        if result.caught and result.pokemon:
            # Save the Pokemon
            result.pokemon = db.save_pokemon(result.pokemon)
            trainer.pokemon_caught += 1

            # Update Pokedex
            entry = db.get_pokedex_entry(result.pokemon.pokedex_id)
            if entry:
                if not entry.is_seen:
                    trainer.pokedex_seen += 1
                entry.is_seen = True
                entry.is_caught = True
                entry.times_caught += 1
                if result.is_shiny:
                    entry.shiny_caught = True
                if not entry.first_caught_at:
                    entry.first_caught_at = datetime.now()
                    trainer.pokedex_caught += 1
                db.save_pokedex_entry(entry)

            display_encounter(result.pokemon, caught=True)
        elif result.pokemon:
            # Pokemon got away
            display_encounter(result.pokemon, caught=False)

            # Still mark as seen in Pokedex
            entry = db.get_pokedex_entry(result.pokemon.pokedex_id)
            if entry and not entry.is_seen:
                entry.is_seen = True
                trainer.pokedex_seen += 1
                db.save_pokedex_entry(entry)

    # Save trainer
    db.save_trainer(trainer)

    # Handle recurring tasks
    if task.recurrence != RecurrenceType.NONE:
        _create_recurring_task(task)


def _create_recurring_task(original: Task) -> None:
    """Create the next occurrence of a recurring task."""
    if not original.due_date:
        return

    if original.recurrence == RecurrenceType.DAILY:
        next_due = original.due_date + timedelta(days=1)
    elif original.recurrence == RecurrenceType.WEEKLY:
        next_due = original.due_date + timedelta(weeks=1)
    elif original.recurrence == RecurrenceType.MONTHLY:
        next_due = original.due_date + timedelta(days=30)
    else:
        return

    new_task = Task(
        title=original.title,
        description=original.description,
        category=original.category,
        difficulty=original.difficulty,
        priority=original.priority,
        due_date=next_due,
        recurrence=original.recurrence,
        tags=original.tags,
    )
    db.create_task(new_task)
    console.print(f"[dim]Next occurrence created for {next_due}[/dim]")


@app.command("edit")
def edit_task(
    task_id: int = typer.Argument(..., help="Task ID"),
    title: str | None = typer.Option(None, "--title", help="New title"),
    category: TaskCategory | None = typer.Option(None, "--category", "-c"),
    difficulty: TaskDifficulty | None = typer.Option(None, "--difficulty", "-d"),
    priority: TaskPriority | None = typer.Option(None, "--priority", "-p"),
    due: str | None = typer.Option(None, "--due"),
    description: str | None = typer.Option(None, "--desc"),
) -> None:
    """Edit a task."""
    task = db.get_task(task_id)
    if not task:
        console.print(f"[red]Task {task_id} not found.[/red]")
        raise typer.Exit(1)

    if title:
        task.title = title
    if category:
        task.category = category
    if difficulty:
        task.difficulty = difficulty
    if priority:
        task.priority = priority
    if due:
        task.due_date = parse_due_date(due)
    if description:
        task.description = description

    db.update_task(task)
    console.print(f"[green]Task {task_id} updated.[/green]")


@app.command("delete")
def delete_task(
    task_id: int = typer.Argument(..., help="Task ID"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
) -> None:
    """Delete a task."""
    task = db.get_task(task_id)
    if not task:
        console.print(f"[red]Task {task_id} not found.[/red]")
        raise typer.Exit(1)

    if not force:
        if not Confirm.ask(f"Delete task '{task.title}'?"):
            raise typer.Exit(0)

    db.delete_task(task_id)
    console.print(f"[green]Task {task_id} deleted.[/green]")


@app.command("archive")
def archive_task(task_id: int = typer.Argument(..., help="Task ID")) -> None:
    """Archive a completed task."""
    task = db.get_task(task_id)
    if not task:
        console.print(f"[red]Task {task_id} not found.[/red]")
        raise typer.Exit(1)

    task.is_archived = True
    db.update_task(task)
    console.print(f"[green]Task {task_id} archived.[/green]")
