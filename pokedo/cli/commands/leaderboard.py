"""CLI commands for the PvP leaderboard."""

import time

import httpx
import typer
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

app = typer.Typer(name="leaderboard", help="PvP leaderboard and rankings")
console = Console()

SERVER_URL = "http://localhost:8000"


def _get_server_url() -> str:
    import os

    return os.getenv("POKEDO_SERVER_URL", SERVER_URL)


def _request(method: str, url: str, *, retries: int = 1, **kwargs) -> httpx.Response | None:
    """HTTP request with friendly network-error handling (mirrors battle client)."""
    kwargs.setdefault("timeout", 10)
    for attempt in range(retries + 1):
        try:
            return httpx.request(method, url, **kwargs)
        except (httpx.ConnectError, httpx.TimeoutException):
            if attempt >= retries:
                console.print(
                    "[red]Cannot reach the PokeDo server.[/red] Is it running "
                    f"at {_get_server_url()}?"
                )
                return None
            time.sleep(1.0)
        except httpx.HTTPError as exc:
            console.print(f"[red]Request failed:[/red] {exc}")
            return None
    return None


def _error_detail(resp: httpx.Response) -> str:
    """Extract a safe error message from a non-2xx response."""
    try:
        data = resp.json()
    except ValueError:
        text = resp.text.strip()
        return text[:200] or f"HTTP {resp.status_code}"
    if isinstance(data, dict):
        return str(data.get("detail", resp.text.strip()[:200] or f"HTTP {resp.status_code}"))
    return str(data)[:200]


@app.command("show")
def show_leaderboard(
    sort_by: str = typer.Option(
        "elo_rating", "--sort", "-s", help="Sort by: elo_rating, battle_wins, xp, pokemon_caught"
    ),
    limit: int = typer.Option(20, "--limit", "-n", help="Number of entries to show"),
    offset: int = typer.Option(0, "--offset", "-o", help="Offset for pagination"),
) -> None:
    """Display the global leaderboard."""
    url = f"{_get_server_url()}/leaderboard"
    resp = _request(
        "GET",
        url,
        params={"sort_by": sort_by, "limit": limit, "offset": offset},
    )
    if resp is None:
        return

    if resp.status_code != 200:
        console.print(f"[red]Error:[/red] {_error_detail(resp)}")
        return

    entries = resp.json()
    if not entries:
        console.print("[dim]Leaderboard is empty.[/dim]")
        return

    label_map = {
        "elo_rating": "ELO Rating",
        "battle_wins": "Wins",
        "xp": "XP",
        "pokemon_caught": "Pokemon Caught",
    }
    sort_label = label_map.get(sort_by, sort_by)

    table = Table(title=f"Leaderboard (by {sort_label})", box=box.ROUNDED)
    table.add_column("#", justify="right", style="dim")
    table.add_column("Trainer", style="bold")
    table.add_column("ELO", justify="right", style="cyan")
    table.add_column("Rank")
    table.add_column("W", justify="right", style="green")
    table.add_column("L", justify="right", style="red")
    table.add_column("Win%", justify="right")

    for i, entry in enumerate(entries, start=offset + 1):
        wins = entry.get("battle_wins", 0)
        losses = entry.get("battle_losses", 0)
        total = wins + losses
        win_pct = f"{(wins / total * 100):.0f}%" if total > 0 else "-"

        # Highlight the top 3
        rank_num = str(i)
        if i == 1:
            rank_num = "[bold gold1]1[/bold gold1]"
        elif i == 2:
            rank_num = "[bold silver]2[/bold silver]"
        elif i == 3:
            rank_num = "[bold dark_orange3]3[/bold dark_orange3]"

        table.add_row(
            rank_num,
            entry.get("trainer_name") or entry.get("username", "?"),
            str(entry.get("elo_rating", 1000)),
            entry.get("pvp_rank", "Unranked"),
            str(wins),
            str(losses),
            win_pct,
        )

    console.print(table)
    console.print(f"[dim]Showing {len(entries)} entries (offset {offset})[/dim]")


@app.command("me")
def my_ranking(
    username: str = typer.Option(..., "--username", "-u", prompt=True),
) -> None:
    """Show your own ranking on the leaderboard."""
    url = f"{_get_server_url()}/leaderboard/{username}"
    resp = _request("GET", url)
    if resp is None:
        return

    if resp.status_code == 404:
        console.print(f"[red]User '{username}' not found on the server.[/red]")
        return
    if resp.status_code != 200:
        console.print(f"[red]Error:[/red] {_error_detail(resp)}")
        return

    data = resp.json()
    wins = data.get("battle_wins", 0)
    losses = data.get("battle_losses", 0)
    draws = data.get("battle_draws", 0)
    total = wins + losses + draws
    win_pct = f"{(wins / total * 100):.1f}%" if total > 0 else "N/A"

    console.print(
        Panel(
            f"[bold]{data.get('trainer_name') or data.get('username')}[/bold]\n\n"
            f"ELO Rating : [cyan]{data.get('elo_rating', 1000)}[/cyan]\n"
            f"PvP Rank   : {data.get('pvp_rank', 'Unranked')}\n"
            f"Record     : [green]{wins}W[/green] / [red]{losses}L[/red] / {draws}D  ({total} total)\n"
            f"Win Rate   : {win_pct}",
            title="Your PvP Profile",
            border_style="cyan",
        )
    )
