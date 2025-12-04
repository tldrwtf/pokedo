import typer
from enum import Enum
from dataclasses import dataclass, field

app = typer.Typer()

class Stat(str, Enum):
    HP='hp'
    ATK='atk'
    DEF='def'
    SPA='spa'
    SPD='spd'
    SPE='spe'

@dataclass
class Pokemon:
    id: int
    name: str
    evs: dict = field(default_factory=lambda: {s.value:0 for s in Stat})
    ivs: dict = field(default_factory=lambda: {s.value:0 for s in Stat})


def add_evs(pokemon: Pokemon, stat: Stat, amount: int):
    per_cap=252
    total_cap=510
    key=stat.value
    available_for_stat = per_cap - pokemon.evs[key]
    available_total = total_cap - sum(pokemon.evs.values())
    to_add = min(available_for_stat, available_total, amount)
    pokemon.evs[key] += to_add
    return to_add

@app.command()
def complete_task(task_title: str, pokemon_id: int, difficulty: int = 1):
    """Mocked example: apply EVs to a Pokemon based on difficulty."""
    # In a real app, fetch the Pokemon from DB
    p = Pokemon(id=pokemon_id, name="Example")
    added = add_evs(p, Stat.SPA, difficulty)
    typer.echo(f"Applied {added} EV(s) to {p.name}: {p.evs}")

if __name__ == '__main__':
    app()
