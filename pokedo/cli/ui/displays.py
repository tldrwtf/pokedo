"""Rich display components for the CLI."""

from rich import box
from rich.columns import Columns
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from pokedo.core.pokemon import Pokemon
from pokedo.core.task import Task, TaskDifficulty, TaskPriority
from pokedo.core.trainer import Trainer
from pokedo.core.wellbeing import DailyWellbeing, MoodLevel

console = Console()


# Color mappings
DIFFICULTY_COLORS = {
    TaskDifficulty.EASY: "green",
    TaskDifficulty.MEDIUM: "yellow",
    TaskDifficulty.HARD: "red",
    TaskDifficulty.EPIC: "magenta",
}

PRIORITY_COLORS = {
    TaskPriority.LOW: "dim",
    TaskPriority.MEDIUM: "white",
    TaskPriority.HIGH: "yellow",
    TaskPriority.URGENT: "red bold",
}

TYPE_COLORS = {
    "normal": "white",
    "fire": "red",
    "water": "blue",
    "electric": "yellow",
    "grass": "green",
    "ice": "cyan",
    "fighting": "red",
    "poison": "magenta",
    "ground": "yellow",
    "flying": "cyan",
    "psychic": "magenta",
    "bug": "green",
    "rock": "yellow",
    "ghost": "magenta",
    "dragon": "blue",
    "dark": "white",
    "steel": "white",
    "fairy": "magenta",
}

MOOD_DISPLAY = {
    MoodLevel.VERY_LOW: (":(", "red"),
    MoodLevel.LOW: (":|", "yellow"),
    MoodLevel.NEUTRAL: (":|", "white"),
    MoodLevel.GOOD: (":)", "green"),
    MoodLevel.GREAT: (":D", "bright_green"),
}


def display_task_list(tasks: list[Task], title: str = "Tasks") -> None:
    """Display a formatted task list."""
    if not tasks:
        console.print(f"[dim]No {title.lower()} found.[/dim]")
        return

    table = Table(title=title, box=box.ROUNDED)
    table.add_column("ID", style="dim", width=4)
    table.add_column("Title", min_width=20)
    table.add_column("Category", width=10)
    table.add_column("Diff", width=6)
    table.add_column("Due", width=12)
    table.add_column("Status", width=8)

    for task in tasks:
        diff_color = DIFFICULTY_COLORS.get(task.difficulty, "white")
        status = "[green]Done[/green]" if task.is_completed else ""
        if task.is_overdue and not task.is_completed:
            status = "[red]Overdue[/red]"

        due_str = task.due_date.isoformat() if task.due_date else "-"

        table.add_row(
            str(task.id),
            task.title,
            task.category.value,
            f"[{diff_color}]{task.difficulty.value}[/{diff_color}]",
            due_str,
            status,
        )

    console.print(table)


def display_task_detail(task: Task) -> None:
    """Display detailed task information."""
    diff_color = DIFFICULTY_COLORS.get(task.difficulty, "white")
    priority_style = PRIORITY_COLORS.get(task.priority, "white")

    content = f"""[bold]{task.title}[/bold]

[dim]Category:[/dim] {task.category.value}
[dim]Difficulty:[/dim] [{diff_color}]{task.difficulty.value}[/{diff_color}]
[dim]Priority:[/dim] [{priority_style}]{task.priority.value}[/{priority_style}]
[dim]XP Reward:[/dim] {task.xp_reward}

[dim]Created:[/dim] {task.created_at.strftime('%Y-%m-%d %H:%M')}
[dim]Due:[/dim] {task.due_date.isoformat() if task.due_date else 'No deadline'}
[dim]Status:[/dim] {'Completed' if task.is_completed else 'Pending'}"""

    if task.description:
        content += f"\n\n[dim]Description:[/dim]\n{task.description}"

    if task.tags:
        content += f"\n\n[dim]Tags:[/dim] {', '.join(task.tags)}"

    console.print(Panel(content, title=f"Task #{task.id}", box=box.ROUNDED))


def display_pokemon(pokemon: Pokemon, detailed: bool = False) -> None:
    """Display a Pokemon."""
    type_color = TYPE_COLORS.get(pokemon.type1, "white")
    shiny_marker = "[yellow]*SHINY*[/yellow] " if pokemon.is_shiny else ""

    name_display = pokemon.display_name
    if pokemon.nickname and pokemon.nickname != pokemon.name:
        name_display = f"{pokemon.nickname} ({pokemon.name.capitalize()})"
    else:
        name_display = pokemon.name.capitalize()

    content = f"""{shiny_marker}[bold]{name_display}[/bold]
[dim]#{pokemon.pokedex_id:03d}[/dim]

[dim]Type:[/dim] [{type_color}]{pokemon.types_display}[/{type_color}]
[dim]Level:[/dim] {pokemon.level}
[dim]Happiness:[/dim] {pokemon.happiness}/255"""

    if detailed:
        content += f"""

[dim]XP:[/dim] {pokemon.xp}
[dim]Caught:[/dim] {pokemon.caught_at.strftime('%Y-%m-%d')}
[dim]Location:[/dim] {pokemon.catch_location or 'Unknown'}
[dim]Active:[/dim] {'Yes' if pokemon.is_active else 'No'}"""

        if pokemon.can_evolve and pokemon.evolution_id:
            content += "\n[green]Ready to evolve![/green]"

    console.print(Panel(content, box=box.ROUNDED))


def display_pokemon_list(pokemon_list: list[Pokemon], title: str = "Pokemon") -> None:
    """Display a list of Pokemon in a table."""
    if not pokemon_list:
        console.print(f"[dim]No {title.lower()} found.[/dim]")
        return

    table = Table(title=title, box=box.ROUNDED)
    table.add_column("ID", style="dim", width=4)
    table.add_column("Name", min_width=15)
    table.add_column("#", width=4)
    table.add_column("Type", width=15)
    table.add_column("Lv", width=4)
    table.add_column("Status", width=10)

    for p in pokemon_list:
        type_color = TYPE_COLORS.get(p.type1, "white")
        shiny = "[yellow]*[/yellow]" if p.is_shiny else ""
        active = "[green]Active[/green]" if p.is_active else ""

        table.add_row(
            str(p.id),
            f"{shiny}{p.display_name}",
            f"{p.pokedex_id:03d}",
            f"[{type_color}]{p.types_display}[/{type_color}]",
            str(p.level),
            active,
        )

    console.print(table)


def display_trainer_card(trainer: Trainer) -> None:
    """Display trainer profile card."""
    xp_current, xp_needed = trainer.xp_progress

    content = f"""[bold]{trainer.name}[/bold]

[dim]Level:[/dim] {trainer.level}
[dim]XP:[/dim] {xp_current}/{xp_needed} to next level
[dim]Total XP:[/dim] {trainer.total_xp}

[dim]Tasks Completed:[/dim] {trainer.tasks_completed}
[dim]Pokemon Caught:[/dim] {trainer.pokemon_caught}
[dim]Pokedex:[/dim] {trainer.pokedex_caught}/{151} ({trainer.pokedex_completion:.1f}%)

[dim]Current Streak:[/dim] {trainer.daily_streak.current_count} days
[dim]Best Streak:[/dim] {trainer.daily_streak.best_count} days"""

    if trainer.badges:
        badge_str = " ".join([b.icon for b in trainer.badges if b.is_earned])
        content += f"\n\n[dim]Badges:[/dim] {badge_str}"

    console.print(Panel(content, title="Trainer Card", box=box.DOUBLE))


def display_encounter(pokemon: Pokemon, caught: bool) -> None:
    """Display a Pokemon encounter result."""
    type_color = TYPE_COLORS.get(pokemon.type1, "white")
    shiny_text = "[yellow]SHINY [/yellow]" if pokemon.is_shiny else ""

    if caught:
        console.print()
        console.print(
            Panel(
                f"""[bold green]CAUGHT![/bold green]

A wild {shiny_text}[{type_color}]{pokemon.name.upper()}[/{type_color}] appeared!

[green]You caught it![/green]

Type: [{type_color}]{pokemon.types_display}[/{type_color}]
Level: {pokemon.level}""",
                title="Pokemon Encounter",
                box=box.DOUBLE,
            )
        )
    else:
        console.print()
        console.print(
            Panel(
                f"""[bold yellow]GOT AWAY![/bold yellow]

A wild {shiny_text}[{type_color}]{pokemon.name.upper()}[/{type_color}] appeared!

[red]It got away...[/red]

Better luck next time!""",
                title="Pokemon Encounter",
                box=box.DOUBLE,
            )
        )


def display_task_completion_result(
    task: Task,
    xp_earned: int,
    level_up: bool,
    new_level: int,
    streak_count: int,
    items_earned: dict,
) -> None:
    """Display task completion summary."""
    content = f"""[bold green]Task Completed![/bold green]

"{task.title}"

[dim]XP Earned:[/dim] +{xp_earned}"""

    if level_up:
        content += f"\n[bold yellow]LEVEL UP! You are now level {new_level}![/bold yellow]"

    content += f"\n[dim]Current Streak:[/dim] {streak_count} days"

    if items_earned:
        items_str = ", ".join([f"{v}x {k}" for k, v in items_earned.items()])
        content += f"\n[green]Items Earned:[/green] {items_str}"

    console.print(Panel(content, box=box.ROUNDED))


def display_stats_dashboard(
    trainer: Trainer, today_tasks: int, wellbeing: DailyWellbeing | None = None
) -> None:
    """Display stats dashboard."""
    # Left panel - Trainer stats
    xp_current, xp_needed = trainer.xp_progress

    left = f"""[bold]Trainer Stats[/bold]

Level: {trainer.level}
XP: {xp_current}/{xp_needed}

Tasks Today: {today_tasks}
Total Tasks: {trainer.tasks_completed}

Pokemon: {trainer.pokemon_caught}
Pokedex: {trainer.pokedex_completion:.1f}%"""

    # Right panel - Streaks
    right = f"""[bold]Streaks[/bold]

Daily: {trainer.daily_streak.current_count} days
Best: {trainer.daily_streak.best_count} days

Wellbeing: {trainer.wellbeing_streak.current_count} days"""

    if wellbeing:
        mood_icon, mood_color = MOOD_DISPLAY.get(
            wellbeing.mood.mood if wellbeing.mood else MoodLevel.NEUTRAL, (":|", "white")
        )
        right += f"""

[bold]Today's Wellbeing[/bold]
Mood: [{mood_color}]{mood_icon}[/{mood_color}]
Completion: {wellbeing.completion_score:.0f}%"""

    left_panel = Panel(left, box=box.ROUNDED)
    right_panel = Panel(right, box=box.ROUNDED)

    console.print(Columns([left_panel, right_panel]))


def display_streak_info(trainer: Trainer) -> None:
    """Display streak information."""
    content = f"""[bold]Current Streaks[/bold]

[dim]Daily Tasks:[/dim]
  Current: {trainer.daily_streak.current_count} days
  Best: {trainer.daily_streak.best_count} days

[dim]Wellbeing Logging:[/dim]
  Current: {trainer.wellbeing_streak.current_count} days
  Best: {trainer.wellbeing_streak.best_count} days

[bold]Streak Milestones[/bold]
  3 days  - Great Balls
  7 days  - Evolution Stone
  14 days - Rare Encounter
  30 days - Legendary Encounter
  100 days - Mythical Pokemon"""

    console.print(Panel(content, title="Streaks", box=box.ROUNDED))
