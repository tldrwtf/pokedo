"""Trainer profile CLI commands."""

import typer
from rich.console import Console

from pokedo.cli.commands import stats
from pokedo.data.database import db

app = typer.Typer(help="Trainer profile commands", invoke_without_command=True)
console = Console()


@app.callback()
def profile_default(ctx: typer.Context) -> None:
    """Show profile when no subcommand is provided."""
    if ctx.invoked_subcommand is None:
        stats.show_profile()


@app.command("set-default")
def set_default(identifier: str = typer.Argument(..., help="Trainer name or ID")) -> None:
    """Set the default trainer profile."""
    trainer = None
    if identifier.isdigit():
        trainer = db.get_trainer_by_id(int(identifier))
    if trainer is None:
        trainer = db.get_trainer_by_name(identifier)

    if trainer is None or trainer.id is None:
        console.print(f"[red]Trainer not found: {identifier}[/red]")
        trainers = db.list_trainers()
        if trainers:
            console.print("[dim]Available trainers:[/dim]")
            for existing in trainers:
                console.print(f"  {existing.id}: {existing.name}")
        raise typer.Exit(1)

    db.set_default_trainer_id(trainer.id)
    console.print(f"[green]Default profile set to: {trainer.name}[/green]")
