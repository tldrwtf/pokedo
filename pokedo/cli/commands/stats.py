"""Statistics and profile CLI commands."""

from datetime import date

import typer
from rich import box
from rich.console import Console
from rich.table import Table

from pokedo.cli.ui.displays import (
    display_stats_dashboard,
    display_streak_info,
    display_trainer_card,
)
from pokedo.core.trainer import AVAILABLE_BADGES
from pokedo.data.database import db

app = typer.Typer(help="Statistics and profile commands")
console = Console()


@app.command("profile")
def show_profile() -> None:
    """Show your trainer profile."""
    trainer = db.get_or_create_trainer()
    display_trainer_card(trainer)


@app.command("overview")
def show_overview() -> None:
    """Show daily overview dashboard."""
    trainer = db.get_or_create_trainer()
    today_tasks = db.get_tasks_for_date(date.today())
    completed_today = len([t for t in today_tasks if t.is_completed])

    display_stats_dashboard(trainer, completed_today)


@app.command("streaks")
def show_streaks() -> None:
    """Show streak information."""
    trainer = db.get_or_create_trainer()
    display_streak_info(trainer)


@app.command("badges")
def show_badges() -> None:
    """Show all badges and achievement progress."""
    trainer = db.get_or_create_trainer()

    console.print("\n[bold]Badges & Achievements[/bold]\n")

    table = Table(box=box.ROUNDED)
    table.add_column("Badge", width=20)
    table.add_column("Description", min_width=30)
    table.add_column("Status", width=12)

    for badge in AVAILABLE_BADGES:
        # Check if earned
        earned = any(b.id == badge.id and b.is_earned for b in trainer.badges)

        if earned:
            status = f"[green]{badge.icon} Earned[/green]"
        else:
            # Calculate progress
            progress = _calculate_badge_progress(badge, trainer)
            status = f"[dim]{progress}/{badge.requirement_count}[/dim]"

        table.add_row(badge.name, badge.description, status)

    console.print(table)

    earned_count = len([b for b in trainer.badges if b.is_earned])
    console.print(f"\n[dim]Badges earned: {earned_count}/{len(AVAILABLE_BADGES)}[/dim]")


def _calculate_badge_progress(badge, trainer) -> int:
    """Calculate progress toward a badge."""
    if badge.requirement_type == "tasks":
        return trainer.tasks_completed
    elif badge.requirement_type == "pokemon":
        return trainer.pokemon_caught
    elif badge.requirement_type == "streak":
        return trainer.daily_streak.best_count
    elif badge.requirement_type == "wellbeing":
        # Would need to track this
        return 0
    return 0


@app.command("inventory")
def show_inventory() -> None:
    """Show your item inventory."""
    trainer = db.get_or_create_trainer()

    console.print("\n[bold]Inventory[/bold]\n")

    if not trainer.inventory:
        console.print("[dim]Your bag is empty. Complete tasks to earn items![/dim]")
        return

    table = Table(box=box.SIMPLE)
    table.add_column("Item", min_width=20)
    table.add_column("Quantity", width=10)
    table.add_column("Effect", min_width=30)

    item_descriptions = {
        "great_ball": "Improved catch rate (+10%)",
        "ultra_ball": "Great catch rate (+20%)",
        "master_ball": "Guaranteed catch!",
        "evolution_stone": "Evolve eligible Pokemon",
        "legendary_ticket": "Guaranteed legendary encounter",
        "rare_candy": "Increase Pokemon level by 1",
    }

    for item, count in trainer.inventory.items():
        description = item_descriptions.get(item, "Unknown item")
        table.add_row(item.replace("_", " ").title(), str(count), description)

    console.print(table)


@app.command("history")
def show_history(
    days: int = typer.Option(7, "--days", "-d", help="Number of days to show")
) -> None:
    """Show task completion history."""
    from datetime import timedelta

    console.print(f"\n[bold]Task History (Last {days} days)[/bold]\n")

    table = Table(box=box.SIMPLE)
    table.add_column("Date", width=12)
    table.add_column("Completed", width=10)
    table.add_column("XP Earned", width=10)

    total_completed = 0
    total_xp = 0

    for i in range(days):
        day = date.today() - timedelta(days=i)
        tasks = db.get_tasks_for_date(day)
        completed = [t for t in tasks if t.is_completed]
        xp = sum(t.xp_reward for t in completed)

        total_completed += len(completed)
        total_xp += xp

        bar = "[green]" + "#" * len(completed) + "[/green]" if completed else "[dim]-[/dim]"

        table.add_row(day.isoformat(), f"{len(completed)} {bar}", str(xp) if xp else "[dim]0[/dim]")

    console.print(table)
    console.print(f"\n[dim]Total: {total_completed} tasks, {total_xp} XP[/dim]")


@app.command("rename")
def rename_trainer(name: str = typer.Argument(..., help="New trainer name")) -> None:
    """Change your trainer name."""
    trainer = db.get_or_create_trainer()
    old_name = trainer.name
    trainer.name = name
    db.save_trainer(trainer)
    console.print(f"[green]Trainer renamed from {old_name} to {name}![/green]")
