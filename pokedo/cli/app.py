"""Main CLI application for PokeDo."""

import typer
from rich import box
from rich.console import Console
from rich.panel import Panel

from pokedo import __version__
from pokedo.cli.commands import pokemon, stats, tasks, wellbeing
from pokedo.data.database import db

# Create main app
app = typer.Typer(
    name="pokedo",
    help="PokeDo - A Pokemon-themed task manager and wellbeing tracker",
    no_args_is_help=False,
)

# Register sub-commands
app.add_typer(tasks.app, name="task", help="Task management")
app.add_typer(pokemon.app, name="pokemon", help="Pokemon collection")
app.add_typer(wellbeing.app, name="wellbeing", help="Wellbeing tracking")
app.add_typer(stats.app, name="stats", help="Statistics and profile")

console = Console()


# Direct commands (shortcuts)
@app.command("mood")
def mood_shortcut(
    level: int = typer.Argument(..., min=1, max=5), note: str = typer.Option(None, "--note", "-n")
) -> None:
    """Quick mood log (1-5)."""
    wellbeing.log_mood(level, note, None)


@app.command("exercise")
def exercise_shortcut(
    exercise_type: wellbeing.ExerciseType = typer.Argument(...),
    duration: int = typer.Option(..., "--duration", "-d"),
    intensity: int = typer.Option(3, "--intensity", "-i", min=1, max=5),
) -> None:
    """Quick exercise log."""
    wellbeing.log_exercise(exercise_type, duration, intensity, None)


@app.command("sleep")
def sleep_shortcut(
    hours: float = typer.Argument(...),
    quality: int = typer.Option(3, "--quality", "-q", min=1, max=5),
) -> None:
    """Quick sleep log."""
    wellbeing.log_sleep(hours, quality, None)


@app.command("water")
def water_shortcut(glasses: int = typer.Option(1, "--glasses", "-g")) -> None:
    """Quick water log."""
    wellbeing.log_hydration(glasses, None)


@app.command("meditate")
def meditate_shortcut(minutes: int = typer.Argument(...)) -> None:
    """Quick meditation log."""
    wellbeing.log_meditation(minutes, None)


@app.command("profile")
def profile_shortcut() -> None:
    """Show trainer profile."""
    stats.show_profile()


@app.command("streaks")
def streaks_shortcut() -> None:
    """Show streak info."""
    stats.show_streaks()


@app.command("badges")
def badges_shortcut() -> None:
    """Show badges."""
    stats.show_badges()


@app.command("daily")
def daily_overview() -> None:
    """Show daily summary."""
    stats.show_overview()


@app.command("team")
def team_shortcut() -> None:
    """Show Pokemon team."""
    pokemon.show_team()


@app.command("pokedex")
def pokedex_shortcut() -> None:
    """Show Pokedex."""
    pokemon.render_pokedex(auto_focus=True)


@app.command("version")
def show_version() -> None:
    """Show version information."""
    console.print(f"PokeDo v{__version__}")

@app.command("tui")
def launch_tui() -> None:
    """Launch the Textual TUI dashboard."""
    from pokedo.tui.app import PokeDoApp

    PokeDoApp().run()



@app.command("init")
def initialize(
    name: str = typer.Option("Trainer", "--name", "-n", help="Your trainer name"),
    quick: bool = typer.Option(False, "--quick", "-q", help="Quick init (Gen 1 only)"),
    gen: int = typer.Option(0, "--gen", "-g", help="Initialize specific generation (1-9, 0=all)"),
    concurrency: int = typer.Option(
        10, "--concurrency", help="Concurrent PokeAPI requests during init", min=1, max=50
    ),
) -> None:
    """Initialize PokeDo and create trainer profile."""
    import asyncio
    import httpx

    from pokedo.data.pokeapi import pokeapi
    from pokedo.utils.config import config

    console.print("[bold]Welcome to PokeDo![/bold]")
    console.print("Initializing your Pokemon journey...\n")

    # Ensure directories exist
    config.ensure_dirs()
    console.print("[green]+ Created data directories[/green]")

    # Initialize database
    trainer = db.get_trainer_by_name(name)
    if trainer is None:
        trainer = db.create_trainer(name)
        console.print(f"[green]+ Created trainer profile: {name}[/green]")
    else:
        console.print(f"[yellow]! Trainer profile already exists: {name}[/yellow]")
    if trainer.id is not None:
        db.set_default_trainer_id(trainer.id)

    # Determine range to initialize
    if quick:
        start_id, end_id = 1, 151
        gen_label = "Gen 1"
    elif gen > 0 and gen in config.generation_ranges:
        start_id, end_id = config.generation_ranges[gen]
        gen_label = f"Gen {gen}"
    else:
        start_id, end_id = 1, config.max_pokemon_id
        gen_label = "all generations"

    total = end_id - start_id + 1
    console.print(f"[dim]Loading Pokedex data from PokeAPI ({gen_label}: {total} Pokemon)...[/dim]")
    console.print("[dim]This may take a few minutes for the first run.[/dim]")

    async def init_pokedex() -> int:
        loaded = 0
        lock = asyncio.Lock()
        semaphore = asyncio.Semaphore(min(concurrency, total))

        async with httpx.AsyncClient() as client:
            async def fetch_and_save(pokemon_id: int) -> None:
                nonlocal loaded
                async with semaphore:
                    entry = await pokeapi.create_pokedex_entry(pokemon_id, client=client)
                if entry:
                    db.save_pokedex_entry(entry)
                    async with lock:
                        loaded += 1
                        if loaded % 50 == 0 or loaded == total:
                            console.print(f"[dim]  Loaded {loaded}/{total} Pokemon...[/dim]")

            tasks = [fetch_and_save(i) for i in range(start_id, end_id + 1)]
            await asyncio.gather(*tasks)
        return loaded

    try:
        loaded = asyncio.run(init_pokedex())
        if loaded < total:
            console.print(
                f"[yellow]Warning: Loaded {loaded}/{total} Pokemon ({gen_label}).[/yellow]"
            )
            console.print("[dim]Pokedex will populate as you catch Pokemon.[/dim]")
        else:
            console.print(f"[green]+ Initialized Pokedex with {loaded} Pokemon ({gen_label})[/green]")
    except Exception as e:
        console.print(f"[yellow]Warning: Could not fully initialize Pokedex: {e}[/yellow]")
        console.print("[dim]Pokedex will populate as you catch Pokemon.[/dim]")

    console.print("\n[bold green]Setup complete![/bold green]")
    console.print(f"\n[dim]Total Pokemon available: {config.max_pokemon_id}[/dim]")
    console.print("\nGet started:")
    console.print("  pokedo task add 'My first task' --difficulty easy")
    console.print("  pokedo task complete 1")
    console.print("  pokedo daily")


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    """PokeDo - Catch Pokemon by completing tasks!"""
    if ctx.invoked_subcommand is None:
        # Show dashboard when called without arguments
        show_dashboard()


def show_dashboard() -> None:
    """Show the main dashboard."""
    from datetime import date

    trainer = db.get_or_create_trainer()

    # Header
    console.print()
    console.print(Panel(f"[bold]PokeDo[/bold] - {trainer.name}'s Journey", box=box.DOUBLE))

    # Quick stats
    today = date.today()
    today_tasks = db.get_tasks_for_date(today)
    pending_tasks = db.get_tasks(include_completed=False)
    team = db.get_active_team()

    xp_current, xp_needed = trainer.xp_progress

    stats_text = f"""[dim]Level {trainer.level}[/dim] | XP: {xp_current}/{xp_needed}
Streak: {trainer.daily_streak.current_count} days | Pokemon: {trainer.pokemon_caught}
Tasks Today: {len([t for t in today_tasks if t.is_completed])}/{len(today_tasks)} | Pending: {len(pending_tasks)}"""

    console.print(stats_text)

    # Team preview
    if team:
        team_str = " | ".join(
            [f"{p.display_name} Lv.{p.level}" + (" *" if p.is_shiny else "") for p in team[:3]]
        )
        console.print(f"\n[dim]Team:[/dim] {team_str}")

    # Today's tasks
    if pending_tasks:
        console.print("\n[bold]Pending Tasks:[/bold]")
        for task in pending_tasks[:5]:
            due_str = f" [dim](due {task.due_date})[/dim]" if task.due_date else ""
            console.print(f"  [{task.id}] {task.title}{due_str}")
        if len(pending_tasks) > 5:
            console.print(f"  [dim]...and {len(pending_tasks) - 5} more[/dim]")
    else:
        console.print("\n[green]All tasks completed![/green]")

    # Commands hint
    console.print(
        "\n[dim]Commands: task add/complete | pokemon team/pokedex | daily | --help[/dim]"
    )


if __name__ == "__main__":
    app()
