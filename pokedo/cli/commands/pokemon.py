"""Pokemon management CLI commands."""

import asyncio
from datetime import datetime

import typer
from rich import box
from rich.console import Console
from rich.prompt import Confirm
from rich.table import Table

from pokedo.cli.ui.displays import TYPE_COLORS, display_pokemon, display_pokemon_list
from pokedo.data.database import db
from pokedo.data.pokeapi import create_pokemon_sync, pokeapi

app = typer.Typer(help="Pokemon management commands")
console = Console()


@app.command("team")
def show_team() -> None:
    """Show your active Pokemon team."""
    team = db.get_active_team()
    display_pokemon_list(team, "Active Team")

    if len(team) < 6:
        console.print(f"\n[dim]Team slots: {len(team)}/6[/dim]")


@app.command("box")
def show_box(
    page: int = typer.Option(1, "--page", "-p", help="Page number"),
    per_page: int = typer.Option(20, "--limit", "-l", help="Pokemon per page"),
) -> None:
    """Show all Pokemon in your box."""
    all_pokemon = db.get_all_pokemon()

    # Pagination
    start = (page - 1) * per_page
    end = start + per_page
    pokemon_page = all_pokemon[start:end]

    total_pages = (len(all_pokemon) + per_page - 1) // per_page

    display_pokemon_list(pokemon_page, f"Pokemon Box (Page {page}/{total_pages})")
    console.print(f"\n[dim]Total Pokemon: {len(all_pokemon)}[/dim]")


@app.command("info")
def pokemon_info(
    pokemon_id: int = typer.Argument(..., help="Pokemon ID in your collection")
) -> None:
    """Show detailed Pokemon information."""
    pokemon = db.get_pokemon(pokemon_id)
    if not pokemon:
        console.print(f"[red]Pokemon with ID {pokemon_id} not found in your collection.[/red]")
        raise typer.Exit(1)

    display_pokemon(pokemon, detailed=True)


def render_pokedex(
    caught_only: bool = False, page: int = 1, gen: int = 0, auto_focus: bool = False
) -> None:
    """Render the Pokedex view for both CLI commands and shortcuts."""
    from pokedo.utils.config import config

    entries = db.get_pokedex()

    if not entries:
        console.print("[yellow]Pokedex is empty. Run 'pokedo init' to populate it![/yellow]")
        return

    # Filter by generation if specified
    if gen > 0 and gen in config.generation_ranges:
        start_id, end_id = config.generation_ranges[gen]
        entries = [e for e in entries if start_id <= e.pokedex_id <= end_id]

    if caught_only:
        entries = [e for e in entries if e.is_caught]

    # Pagination
    per_page = 20
    if auto_focus and entries and page == 1:
        focus_index = next(
            (i for i, entry in enumerate(entries) if entry.is_caught),
            next((i for i, entry in enumerate(entries) if entry.is_seen), 0),
        )
        page = (focus_index // per_page) + 1

    page = max(1, page)
    start = (page - 1) * per_page
    end = start + per_page
    entries_page = entries[start:end]
    total_pages = max(1, (len(entries) + per_page - 1) // per_page)

    # Stats
    total_seen = sum(1 for e in entries if e.is_seen)
    total_caught = sum(1 for e in entries if e.is_caught)
    total_pokemon = config.max_pokemon_id

    gen_label = f" (Gen {gen})" if gen > 0 else ""
    table = Table(title=f"Pokedex{gen_label} (Page {page}/{total_pages})", box=box.ROUNDED)
    table.add_column("#", width=5)
    table.add_column("Name", min_width=12)
    table.add_column("Type", width=15)
    table.add_column("Caught", width=8)
    table.add_column("Shiny", width=6)

    for entry in entries_page:
        type_color = TYPE_COLORS.get(entry.type1, "white")
        caught_str = f"[green]x{entry.times_caught}[/green]" if entry.is_caught else "[dim]-[/dim]"
        shiny_str = "[yellow]*[/yellow]" if entry.shiny_caught else ""

        if entry.is_seen:
            name = entry.name.capitalize()
        else:
            name = "[dim]???[/dim]"

        table.add_row(
            f"{entry.pokedex_id:04d}",
            name,
            (
                f"[{type_color}]{entry.type1.capitalize()}[/{type_color}]"
                if entry.is_seen
                else "[dim]???[/dim]"
            ),
            caught_str,
            shiny_str,
        )

    console.print(table)

    if gen > 0 and gen in config.generation_ranges:
        gen_total = config.generation_ranges[gen][1] - config.generation_ranges[gen][0] + 1
        console.print(
            f"\n[dim]Gen {gen}: Seen {total_seen}/{gen_total} | Caught {total_caught}/{gen_total}[/dim]"
        )
    else:
        console.print(
            f"\n[dim]Seen: {total_seen}/{total_pokemon} | Caught: {total_caught}/{total_pokemon} ({(total_caught/total_pokemon)*100:.1f}%)[/dim]"
        )


@app.command("pokedex")
def show_pokedex(
    caught_only: bool = typer.Option(False, "--caught", "-c", help="Show only caught Pokemon"),
    page: int = typer.Option(1, "--page", "-p", help="Page number"),
    gen: int = typer.Option(0, "--gen", "-g", help="Filter by generation (1-9)"),
) -> None:
    """Show your Pokedex progress."""
    render_pokedex(caught_only=caught_only, page=page, gen=gen)


@app.command("set-active")
def set_active(
    pokemon_id: int = typer.Argument(..., help="Pokemon ID to add to active team")
) -> None:
    """Add a Pokemon to your active team."""
    pokemon = db.get_pokemon(pokemon_id)
    if not pokemon:
        console.print(f"[red]Pokemon with ID {pokemon_id} not found.[/red]")
        raise typer.Exit(1)

    if pokemon.is_active:
        console.print(f"[yellow]{pokemon.display_name} is already in your active team.[/yellow]")
        raise typer.Exit(0)

    team = db.get_active_team()
    if len(team) >= 6:
        console.print("[red]Your team is full! Remove a Pokemon first.[/red]")
        raise typer.Exit(1)

    pokemon.is_active = True
    db.save_pokemon(pokemon)
    console.print(f"[green]{pokemon.display_name} added to your active team![/green]")


@app.command("remove-active")
def remove_active(
    pokemon_id: int = typer.Argument(..., help="Pokemon ID to remove from active team")
) -> None:
    """Remove a Pokemon from your active team."""
    pokemon = db.get_pokemon(pokemon_id)
    if not pokemon:
        console.print(f"[red]Pokemon with ID {pokemon_id} not found.[/red]")
        raise typer.Exit(1)

    if not pokemon.is_active:
        console.print(f"[yellow]{pokemon.display_name} is not in your active team.[/yellow]")
        raise typer.Exit(0)

    pokemon.is_active = False
    db.save_pokemon(pokemon)
    console.print(f"[green]{pokemon.display_name} removed from active team.[/green]")


@app.command("nickname")
def set_nickname(
    pokemon_id: int = typer.Argument(..., help="Pokemon ID"),
    nickname: str = typer.Argument(..., help="New nickname"),
) -> None:
    """Give a Pokemon a nickname."""
    pokemon = db.get_pokemon(pokemon_id)
    if not pokemon:
        console.print(f"[red]Pokemon with ID {pokemon_id} not found.[/red]")
        raise typer.Exit(1)

    old_name = pokemon.display_name
    pokemon.nickname = nickname
    db.save_pokemon(pokemon)
    console.print(f"[green]{old_name} is now known as {nickname}![/green]")


@app.command("favorite")
def toggle_favorite(pokemon_id: int = typer.Argument(..., help="Pokemon ID")) -> None:
    """Toggle favorite status on a Pokemon."""
    pokemon = db.get_pokemon(pokemon_id)
    if not pokemon:
        console.print(f"[red]Pokemon with ID {pokemon_id} not found.[/red]")
        raise typer.Exit(1)

    pokemon.is_favorite = not pokemon.is_favorite
    db.save_pokemon(pokemon)

    status = "added to" if pokemon.is_favorite else "removed from"
    console.print(f"[green]{pokemon.display_name} {status} favorites![/green]")


@app.command("release")
def release_pokemon(
    pokemon_id: int = typer.Argument(..., help="Pokemon ID to release"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
) -> None:
    """Release a Pokemon back into the wild."""
    pokemon = db.get_pokemon(pokemon_id)
    if not pokemon:
        console.print(f"[red]Pokemon with ID {pokemon_id} not found.[/red]")
        raise typer.Exit(1)

    if pokemon.is_shiny and not force:
        console.print(f"[yellow]Warning: {pokemon.display_name} is SHINY![/yellow]")

    if not force:
        if not Confirm.ask(f"Release {pokemon.display_name}?"):
            raise typer.Exit(0)

    db.delete_pokemon(pokemon_id)

    # Update trainer stats
    trainer = db.get_or_create_trainer()
    trainer.pokemon_released += 1
    db.save_trainer(trainer)

    console.print(f"[green]{pokemon.display_name} was released. Goodbye, friend![/green]")


@app.command("evolve")
def evolve_pokemon(pokemon_id: int = typer.Argument(..., help="Pokemon ID to evolve")) -> None:
    """Evolve a Pokemon if eligible."""
    pokemon = db.get_pokemon(pokemon_id)
    if not pokemon:
        console.print(f"[red]Pokemon with ID {pokemon_id} not found.[/red]")
        raise typer.Exit(1)

    if not pokemon.can_evolve:
        console.print(f"[yellow]{pokemon.display_name} cannot evolve right now.[/yellow]")
        if pokemon.evolution_id and pokemon.evolution_level:
            console.print(
                f"[dim]Needs to reach level {pokemon.evolution_level}. Current: {pokemon.level}[/dim]"
            )
        raise typer.Exit(0)

    if not pokemon.evolution_id:
        console.print(f"[yellow]{pokemon.display_name} has no known evolution.[/yellow]")
        raise typer.Exit(0)

    # Create evolved Pokemon
    evolved = create_pokemon_sync(
        pokemon.evolution_id, is_shiny=pokemon.is_shiny, catch_location=pokemon.catch_location
    )

    if not evolved:
        console.print("[red]Error fetching evolution data.[/red]")
        raise typer.Exit(1)

    # Transfer stats
    evolved.nickname = pokemon.nickname
    evolved.level = pokemon.level
    evolved.xp = pokemon.xp
    evolved.happiness = pokemon.happiness
    evolved.is_active = pokemon.is_active
    evolved.is_favorite = pokemon.is_favorite
    evolved.caught_at = pokemon.caught_at

    console.print()
    console.print(f"[bold]What? {pokemon.display_name} is evolving![/bold]")
    console.print()

    # Delete old, save new
    db.delete_pokemon(pokemon_id)
    evolved = db.save_pokemon(evolved)

    # Update trainer and Pokedex
    trainer = db.get_or_create_trainer()

    entry = db.get_pokedex_entry(evolved.pokedex_id)
    if entry:
        newly_seen = not entry.is_seen
        newly_caught = not entry.is_caught
        entry.is_seen = True
        entry.is_caught = True
        entry.times_caught += 1
        if evolved.is_shiny:
            entry.shiny_caught = True
        if newly_seen:
            trainer.pokedex_seen += 1
        if newly_caught:
            trainer.pokedex_caught += 1
            if not entry.first_caught_at:
                entry.first_caught_at = datetime.now()
        db.save_pokedex_entry(entry)

    trainer.evolutions_triggered += 1
    db.save_trainer(trainer)

    console.print(
        f"[bold green]{pokemon.display_name} evolved into {evolved.name.upper()}![/bold green]"
    )
    display_pokemon(evolved)


def _resolve_pokemon_identifier(identifier: str) -> int | None:
    """Resolve a Pokemon name or Pokedex number to a Pokedex ID.

    Accepts:
        - A numeric string (e.g. "25") interpreted as Pokedex number.
        - A name string (e.g. "pikachu") looked up via the local Pokedex
          first, then falling back to the PokeAPI.

    Returns:
        The Pokedex ID, or None if the Pokemon could not be found.
    """
    # Direct numeric ID
    if identifier.isdigit():
        return int(identifier)

    name = identifier.strip().lower()

    # Search local Pokedex entries first
    entries = db.get_pokedex()
    for entry in entries:
        if entry.name.lower() == name:
            return entry.pokedex_id

    # Fallback: query PokeAPI by name (the API accepts lowercase names)
    import httpx
    from pokedo.utils.config import config

    try:
        resp = httpx.get(f"{config.pokeapi_base_url}/pokemon/{name}", timeout=10)
        if resp.status_code == 200:
            return resp.json().get("id")
    except Exception:
        pass

    return None


@app.command("sprite")
def show_sprite(
    identifier: str = typer.Argument(
        ..., help="Pokemon name or Pokedex number (e.g. 'pikachu' or '25')"
    ),
    shiny: bool = typer.Option(False, "--shiny", "-s", help="Show shiny variant"),
    bg: str = typer.Option(None, "--bg", help="Background hex color (e.g. '#1e1e2e')"),
) -> None:
    """Display a Pokemon sprite preview in the terminal.

    Accepts a Pokemon name (case-insensitive) or Pokedex number.
    Use --shiny to see the shiny variant.

    Examples:
        pokedo pokemon sprite pikachu
        pokedo pokemon sprite 25 --shiny
        pokedo pokemon sprite charizard --bg '#1e1e2e'
    """
    from pokedo.utils.sprites import display_sprite

    pokedex_id = _resolve_pokemon_identifier(identifier)
    if pokedex_id is None:
        console.print(f"[red]Could not find Pokemon '{identifier}'.[/red]")
        raise typer.Exit(1)

    # Download / retrieve cached sprite
    with console.status("[dim]Fetching sprite...[/dim]"):
        sprite_path = asyncio.run(pokeapi.download_sprite(pokedex_id, is_shiny=shiny))

    if sprite_path is None or not sprite_path.exists():
        console.print("[red]Could not download sprite. Check your internet connection.[/red]")
        raise typer.Exit(1)

    # Build display title
    # Try to get the name from the Pokedex or identifier
    entry = db.get_pokedex_entry(pokedex_id)
    if entry:
        name = entry.name.capitalize()
    else:
        name = identifier.capitalize() if not identifier.isdigit() else "Pokemon"

    shiny_label = " [yellow](Shiny)[/yellow]" if shiny else ""
    title = f"#{pokedex_id:04d} {name}{shiny_label}"

    # Resolve type for subtitle
    type_info = ""
    if entry:
        type_color = TYPE_COLORS.get(entry.type1, "white")
        type_info = f"[{type_color}]{entry.type1.capitalize()}[/{type_color}]"
        if entry.type2:
            type2_color = TYPE_COLORS.get(entry.type2, "white")
            type_info += f" / [{type2_color}]{entry.type2.capitalize()}[/{type2_color}]"

    display_sprite(
        sprite_path,
        title=title,
        bg_color=bg,
        subtitle=type_info or None,
        console=console,
    )
