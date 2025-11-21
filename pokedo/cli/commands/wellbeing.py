"""Wellbeing tracking CLI commands."""

from datetime import date

import typer
from rich import box
from rich.console import Console
from rich.table import Table

from pokedo.cli.ui.displays import MOOD_DISPLAY
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
from pokedo.data.database import db

app = typer.Typer(help="Wellbeing tracking commands")
console = Console()


@app.command("mood")
def log_mood(
    level: int = typer.Argument(..., min=1, max=5, help="Mood level (1-5)"),
    note: str | None = typer.Option(None, "--note", "-n", help="Optional note"),
    energy: int | None = typer.Option(None, "--energy", "-e", min=1, max=5, help="Energy level (1-5)")
) -> None:
    """Log your current mood (1=very low, 5=great)."""
    mood = MoodLevel(level)
    entry = MoodEntry(
        mood=mood,
        note=note,
        energy_level=energy
    )
    entry = db.save_mood(entry)

    icon, color = MOOD_DISPLAY.get(mood, (":|", "white"))
    console.print(f"[{color}]Mood logged: {icon} ({mood.name.replace('_', ' ').title()})[/{color}]")

    # Show impact on Pokemon
    modifier = entry.get_pokemon_happiness_modifier()
    if modifier > 0:
        console.print(f"[green]Your Pokemon feel your positive energy! (+{modifier} happiness)[/green]")
    elif modifier < 0:
        console.print("[dim]Your Pokemon sense you're feeling down.[/dim]")


@app.command("exercise")
def log_exercise(
    exercise_type: ExerciseType = typer.Argument(..., help="Type of exercise"),
    duration: int = typer.Option(..., "--duration", "-d", help="Duration in minutes"),
    intensity: int = typer.Option(3, "--intensity", "-i", min=1, max=5, help="Intensity (1-5)"),
    note: str | None = typer.Option(None, "--note", "-n", help="Optional note")
) -> None:
    """Log an exercise session."""
    entry = ExerciseEntry(
        exercise_type=exercise_type,
        duration_minutes=duration,
        intensity=intensity,
        note=note
    )
    entry = db.save_exercise(entry)

    console.print("[green]Exercise logged![/green]")
    console.print(f"  Type: {exercise_type.value}")
    console.print(f"  Duration: {duration} minutes")
    console.print(f"  Bonus XP: +{entry.xp_bonus}")

    types = entry.get_type_affinity()
    console.print(f"  [dim]Increased chance to encounter: {', '.join(t.capitalize() for t in types)} types[/dim]")


@app.command("sleep")
def log_sleep(
    hours: float = typer.Argument(..., help="Hours of sleep"),
    quality: int = typer.Option(3, "--quality", "-q", min=1, max=5, help="Sleep quality (1-5)"),
    note: str | None = typer.Option(None, "--note", "-n", help="Optional note")
) -> None:
    """Log last night's sleep."""
    entry = SleepEntry(
        hours=hours,
        quality=quality,
        note=note
    )
    entry = db.save_sleep(entry)

    console.print(f"[green]Sleep logged: {hours} hours[/green]")

    modifier = entry.get_catch_rate_modifier()
    if modifier > 1.0:
        console.print(f"[green]Well rested! Catch rate bonus: +{(modifier-1)*100:.0f}%[/green]")
    elif modifier < 1.0:
        console.print(f"[yellow]Tired... Catch rate: {(modifier-1)*100:.0f}%[/yellow]")


@app.command("water")
def log_hydration(
    glasses: int = typer.Option(1, "--glasses", "-g", help="Number of 8oz glasses"),
    note: str | None = typer.Option(None, "--note", "-n", help="Optional note")
) -> None:
    """Log water intake."""
    entry = HydrationEntry(
        glasses=glasses,
        note=note
    )
    entry = db.save_hydration(entry)

    console.print(f"[cyan]Water logged: {glasses} glasses[/cyan]")

    if entry.is_goal_met:
        console.print("[green]Daily goal reached! Water-type Pokemon bonus active.[/green]")
    else:
        console.print(f"[dim]Progress: {glasses}/8 glasses[/dim]")


@app.command("meditate")
def log_meditation(
    minutes: int = typer.Argument(..., help="Minutes meditated"),
    note: str | None = typer.Option(None, "--note", "-n", help="Optional note")
) -> None:
    """Log a meditation session."""
    entry = MeditationEntry(
        minutes=minutes,
        note=note
    )
    entry = db.save_meditation(entry)

    console.print(f"[magenta]Meditation logged: {minutes} minutes[/magenta]")

    bonus = entry.get_psychic_type_bonus()
    if bonus > 1.0:
        console.print(f"[magenta]Mind clear! Psychic/Fairy type bonus: +{(bonus-1)*100:.0f}%[/magenta]")


@app.command("journal")
def log_journal(
    content: str = typer.Argument(..., help="Journal entry content"),
    gratitude: str | None = typer.Option(None, "--gratitude", "-g", help="Comma-separated gratitude items")
) -> None:
    """Write a journal entry."""
    gratitude_items = [g.strip() for g in gratitude.split(",")] if gratitude else []

    entry = JournalEntry(
        content=content,
        gratitude_items=gratitude_items
    )
    entry = db.save_journal(entry)

    console.print("[green]Journal entry saved![/green]")

    bonus = entry.get_friendship_bonus()
    if bonus > 1:
        console.print(f"[green]Reflection time! Pokemon friendship bonus: +{bonus}[/green]")


@app.command("today")
def show_today() -> None:
    """Show today's wellbeing summary."""
    today = date.today()

    mood = db.get_mood_for_date(today)
    exercises = db.get_exercises_for_date(today)

    console.print(f"\n[bold]Wellbeing Summary - {today}[/bold]\n")

    table = Table(box=box.SIMPLE)
    table.add_column("Metric", style="dim")
    table.add_column("Status")

    # Mood
    if mood:
        icon, color = MOOD_DISPLAY.get(mood.mood, (":|", "white"))
        table.add_row("Mood", f"[{color}]{icon} {mood.mood.name.replace('_', ' ').title()}[/{color}]")
    else:
        table.add_row("Mood", "[dim]Not logged[/dim]")

    # Exercise
    if exercises:
        total_minutes = sum(e.duration_minutes for e in exercises)
        table.add_row("Exercise", f"[green]{len(exercises)} session(s), {total_minutes} min[/green]")
    else:
        table.add_row("Exercise", "[dim]Not logged[/dim]")

    # Sleep, Hydration, Meditation would need similar getters
    table.add_row("Sleep", "[dim]Check with 'pokedo sleep'[/dim]")
    table.add_row("Hydration", "[dim]Check with 'pokedo water'[/dim]")
    table.add_row("Meditation", "[dim]Check with 'pokedo meditate'[/dim]")

    console.print(table)

    # Completion
    logged_count = sum([mood is not None, len(exercises) > 0])
    console.print(f"\n[dim]Completion: {logged_count}/5 metrics logged[/dim]")
