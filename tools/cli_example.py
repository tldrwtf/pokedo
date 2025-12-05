"""
Example CLI tool using Pokedo's real domain models.
Demonstrates the EV/IV system logic.
"""

import typer

from pokedo.core.pokemon import Pokemon
from pokedo.core.task import Task, TaskCategory, TaskDifficulty

app = typer.Typer()


@app.command()
def train(task_title: str = "Training Session", difficulty: str = "medium", category: str = "work"):
    """
    Simulate a training session using Pokedo models.
    """
    try:
        diff = TaskDifficulty(difficulty.lower())
        cat = TaskCategory(category.lower())
    except ValueError:
        typer.echo("Invalid difficulty or category.")
        return

    # 1. Create Models
    task = Task(title=task_title, difficulty=diff, category=cat)
    pokemon = Pokemon(pokedex_id=25, name="Pikachu", type1="electric")
    pokemon.assign_ivs()

    typer.echo(f"--- Training: {pokemon.name} ---")
    typer.echo(f"IVs (Genetics): {pokemon.ivs}")
    typer.echo(f"Initial EVs: {pokemon.evs}")
    typer.echo(f"\nCompleting Task: {task.title}")
    typer.echo(f"Category: {task.category.name} -> Trains: {task.stat_affinity.upper()}")
    typer.echo(f"Difficulty: {task.difficulty.name} -> Yield: {task.ev_yield}")

    # 2. Apply Mechanics
    added = pokemon.add_evs(task.stat_affinity, task.ev_yield)

    typer.echo(f"\nResult: +{added} EVs to {task.stat_affinity}")
    typer.echo(f"New EVs: {pokemon.evs}")
    typer.echo(f"Remaining EV capacity: {pokemon.remaining_evs}")


if __name__ == "__main__":
    app()
