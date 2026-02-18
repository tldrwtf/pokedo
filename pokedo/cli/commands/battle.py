"""CLI commands for PvP battles.

All battle interactions go through the PokeDo server. The CLI acts as
a thin client that sends requests and renders the results.
"""

from typing import Optional

import requests
import typer
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from pokedo.data.database import db
from pokedo.utils.config import config

app = typer.Typer(name="battle", help="PvP Pokemon battles")
console = Console()

# Server URL -- can be overridden via env or config
SERVER_URL = "http://localhost:8000"


def _get_server_url() -> str:
    """Resolve the server URL from config or env."""
    import os

    return os.getenv("POKEDO_SERVER_URL", SERVER_URL)


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _login(username: str, password: str) -> str | None:
    """Authenticate and return a JWT token."""
    url = f"{_get_server_url()}/token"
    try:
        resp = requests.post(url, data={"username": username, "password": password}, timeout=10)
        if resp.status_code == 200:
            return resp.json()["access_token"]
        console.print(f"[red]Login failed:[/red] {resp.json().get('detail', resp.text)}")
    except requests.ConnectionError:
        console.print("[red]Cannot connect to PokeDo server.[/red] Is it running?")
    return None


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@app.command("register")
def register_account(
    username: str = typer.Option(..., "--username", "-u", prompt=True),
    password: str = typer.Option(..., "--password", "-p", prompt=True, hide_input=True),
    email: Optional[str] = typer.Option(None, "--email", "-e"),
) -> None:
    """Register a new account on the PokeDo server."""
    trainer = db.get_or_create_trainer()
    url = f"{_get_server_url()}/register"
    try:
        resp = requests.post(
            url,
            json={
                "username": username,
                "password": password,
                "email": email,
                "trainer_name": trainer.name,
            },
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            console.print(
                Panel(
                    f"Account created: [bold]{data['username']}[/bold]\n"
                    f"Trainer: {data.get('trainer_name', 'N/A')}\n"
                    f"ELO: {data.get('elo_rating', 1000)} | Rank: {data.get('pvp_rank', 'Unranked')}",
                    title="Registration Successful",
                    border_style="green",
                )
            )
        else:
            console.print(f"[red]Registration failed:[/red] {resp.json().get('detail', resp.text)}")
    except requests.ConnectionError:
        console.print("[red]Cannot connect to PokeDo server.[/red] Is it running?")


@app.command("challenge")
def send_challenge(
    opponent: str = typer.Argument(..., help="Username of the player to challenge"),
    format: str = typer.Option("singles_3v3", "--format", "-f", help="Battle format"),
    username: str = typer.Option(..., "--username", "-u", prompt=True),
    password: str = typer.Option(..., "--password", "-p", prompt=True, hide_input=True),
) -> None:
    """Challenge another player to a battle."""
    token = _login(username, password)
    if not token:
        return

    url = f"{_get_server_url()}/battles/challenge"
    resp = requests.post(
        url,
        json={"opponent_username": opponent, "format": format},
        headers=_auth_headers(token),
        timeout=10,
    )
    if resp.status_code == 200:
        data = resp.json()
        console.print(
            Panel(
                f"Battle ID: [bold cyan]{data['battle_id']}[/bold cyan]\n"
                f"vs. [bold]{data['opponent']}[/bold]\n"
                f"Format: {data['format']} | Status: {data['status']}",
                title="Challenge Sent!",
                border_style="yellow",
            )
        )
        console.print("[dim]Share the Battle ID with your opponent so they can accept.[/dim]")
    else:
        console.print(f"[red]Challenge failed:[/red] {resp.json().get('detail', resp.text)}")


@app.command("pending")
def list_pending(
    username: str = typer.Option(..., "--username", "-u", prompt=True),
    password: str = typer.Option(..., "--password", "-p", prompt=True, hide_input=True),
) -> None:
    """List your pending and active battles."""
    token = _login(username, password)
    if not token:
        return

    url = f"{_get_server_url()}/battles/pending"
    resp = requests.get(url, headers=_auth_headers(token), timeout=10)
    if resp.status_code != 200:
        console.print(f"[red]Error:[/red] {resp.text}")
        return

    battles = resp.json()
    if not battles:
        console.print("[dim]No pending or active battles.[/dim]")
        return

    table = Table(title="Your Battles", box=box.ROUNDED)
    table.add_column("Battle ID", style="cyan", max_width=12)
    table.add_column("Opponent", style="bold")
    table.add_column("Format")
    table.add_column("Status", style="yellow")
    table.add_column("Turn")

    for b in battles:
        opp = b["opponent"] if b["challenger"] == username else b["challenger"]
        table.add_row(
            b["battle_id"][:12] + "...",
            opp,
            b["format"],
            b["status"],
            str(b.get("turn_number", 0)),
        )

    console.print(table)


@app.command("accept")
def accept_battle(
    battle_id: str = typer.Argument(..., help="Battle ID to accept"),
    username: str = typer.Option(..., "--username", "-u", prompt=True),
    password: str = typer.Option(..., "--password", "-p", prompt=True, hide_input=True),
) -> None:
    """Accept a battle challenge."""
    token = _login(username, password)
    if not token:
        return

    url = f"{_get_server_url()}/battles/{battle_id}/accept"
    resp = requests.post(url, headers=_auth_headers(token), timeout=10)
    if resp.status_code == 200:
        data = resp.json()
        console.print(
            Panel(
                f"Battle accepted! Status: [bold green]{data['status']}[/bold green]\n"
                f"Now submit your team with: [bold]pokedo battle team {battle_id}[/bold]",
                title="Challenge Accepted",
                border_style="green",
            )
        )
    else:
        console.print(f"[red]Error:[/red] {resp.json().get('detail', resp.text)}")


@app.command("decline")
def decline_battle(
    battle_id: str = typer.Argument(..., help="Battle ID to decline"),
    username: str = typer.Option(..., "--username", "-u", prompt=True),
    password: str = typer.Option(..., "--password", "-p", prompt=True, hide_input=True),
) -> None:
    """Decline a battle challenge."""
    token = _login(username, password)
    if not token:
        return

    url = f"{_get_server_url()}/battles/{battle_id}/decline"
    resp = requests.post(url, headers=_auth_headers(token), timeout=10)
    if resp.status_code == 200:
        console.print("[yellow]Battle declined.[/yellow]")
    else:
        console.print(f"[red]Error:[/red] {resp.json().get('detail', resp.text)}")


@app.command("team")
def submit_team(
    battle_id: str = typer.Argument(..., help="Battle ID to submit team for"),
    username: str = typer.Option(..., "--username", "-u", prompt=True),
    password: str = typer.Option(..., "--password", "-p", prompt=True, hide_input=True),
) -> None:
    """Submit your active team for a battle.

    Uses your current active team (up to 6 Pokemon). Each Pokemon
    is snapshotted with its current stats, moves, and nature.
    """
    token = _login(username, password)
    if not token:
        return

    # Get the player's active team from local DB
    team_pokemon = db.get_active_team()
    if not team_pokemon:
        console.print("[red]You have no active team![/red] Set team members first with: pokedo pokemon team")
        return

    # Convert to BattlePokemon snapshots
    battle_team = []
    for p in team_pokemon:
        bp = p.to_battle_pokemon()
        battle_team.append(bp.model_dump(mode="json"))

    url = f"{_get_server_url()}/battles/{battle_id}/team"
    resp = requests.post(
        url,
        json={"pokemon": battle_team},
        headers=_auth_headers(token),
        timeout=10,
    )
    if resp.status_code == 200:
        data = resp.json()
        console.print(
            Panel(
                f"Team submitted! ({data.get('your_team_size', 0)} Pokemon)\n"
                f"Status: [bold]{data.get('status', '?')}[/bold]",
                title="Team Ready",
                border_style="green",
            )
        )
        if data.get("status") == "active":
            console.print("[bold green]Both teams are in -- the battle is LIVE![/bold green]")
            console.print(f"Submit moves with: [bold]pokedo battle move {battle_id}[/bold]")
    else:
        console.print(f"[red]Error:[/red] {resp.json().get('detail', resp.text)}")


@app.command("move")
def submit_move(
    battle_id: str = typer.Argument(..., help="Battle ID"),
    move_index: int = typer.Option(0, "--move", "-m", help="Move index (0-3)"),
    username: str = typer.Option(..., "--username", "-u", prompt=True),
    password: str = typer.Option(..., "--password", "-p", prompt=True, hide_input=True),
) -> None:
    """Submit an attack move for the current turn."""
    token = _login(username, password)
    if not token:
        return

    url = f"{_get_server_url()}/battles/{battle_id}/action"
    resp = requests.post(
        url,
        json={"action_type": "attack", "move_index": move_index},
        headers=_auth_headers(token),
        timeout=10,
    )
    _handle_action_response(resp)


@app.command("switch")
def switch_pokemon(
    battle_id: str = typer.Argument(..., help="Battle ID"),
    slot: int = typer.Argument(..., help="Team slot to switch to (0-indexed)"),
    username: str = typer.Option(..., "--username", "-u", prompt=True),
    password: str = typer.Option(..., "--password", "-p", prompt=True, hide_input=True),
) -> None:
    """Switch to a different Pokemon during battle."""
    token = _login(username, password)
    if not token:
        return

    url = f"{_get_server_url()}/battles/{battle_id}/action"
    resp = requests.post(
        url,
        json={"action_type": "switch", "switch_to": slot},
        headers=_auth_headers(token),
        timeout=10,
    )
    _handle_action_response(resp)


@app.command("forfeit")
def forfeit_battle(
    battle_id: str = typer.Argument(..., help="Battle ID to forfeit"),
    username: str = typer.Option(..., "--username", "-u", prompt=True),
    password: str = typer.Option(..., "--password", "-p", prompt=True, hide_input=True),
) -> None:
    """Forfeit an active battle."""
    token = _login(username, password)
    if not token:
        return

    url = f"{_get_server_url()}/battles/{battle_id}/action"
    resp = requests.post(
        url,
        json={"action_type": "forfeit"},
        headers=_auth_headers(token),
        timeout=10,
    )
    _handle_action_response(resp)


@app.command("status")
def battle_status(
    battle_id: str = typer.Argument(..., help="Battle ID to check"),
    username: str = typer.Option(..., "--username", "-u", prompt=True),
    password: str = typer.Option(..., "--password", "-p", prompt=True, hide_input=True),
) -> None:
    """View the current state of a battle."""
    token = _login(username, password)
    if not token:
        return

    url = f"{_get_server_url()}/battles/{battle_id}"
    resp = requests.get(url, headers=_auth_headers(token), timeout=10)
    if resp.status_code != 200:
        console.print(f"[red]Error:[/red] {resp.json().get('detail', resp.text)}")
        return

    data = resp.json()
    console.print(
        Panel(
            f"Status: [bold]{data['status']}[/bold]  |  Turn: {data['turn_number']}  |  Format: {data['format']}",
            title=f"Battle {data['battle_id'][:12]}...",
            border_style="cyan",
        )
    )

    # Show your team
    if data.get("your_team"):
        table = Table(title="Your Team", box=box.SIMPLE)
        table.add_column("Slot", justify="center")
        table.add_column("Pokemon", style="bold")
        table.add_column("HP", justify="right")
        table.add_column("Status")
        table.add_column("Moves")

        roster = data["your_team"].get("roster", [])
        active_idx = data["your_team"].get("active_index", 0)
        for i, p in enumerate(roster):
            marker = " >> " if i == active_idx else ""
            hp_str = f"{p['current_hp']}/{p['max_hp']}"
            status_str = p.get("status", "none")
            if status_str == "none":
                status_str = ""
            move_names = ", ".join(m.get("display_name", m.get("name", "?")) for m in p.get("moves", []))
            style = "green" if not p.get("is_fainted") else "red dim"
            table.add_row(f"{marker}{i}", p.get("name", "?").capitalize(), hp_str, status_str, move_names, style=style)

        console.print(table)

    # Show opponent team (censored)
    if data.get("opponent_team"):
        table = Table(title="Opponent Team", box=box.SIMPLE)
        table.add_column("Slot", justify="center")
        table.add_column("Pokemon", style="bold")
        table.add_column("HP", justify="right")

        roster = data["opponent_team"].get("roster", [])
        opp_active = data["opponent_team"].get("active_index", 0)
        for i, p in enumerate(roster):
            marker = " >> " if i == opp_active else ""
            hp_str = f"{p['current_hp']}/{p['max_hp']}" if p.get("current_hp") is not None else "???"
            style = "red dim" if p.get("is_fainted") else ""
            table.add_row(f"{marker}{i}", p.get("name", "?").capitalize(), hp_str, style=style)

        console.print(table)

    if data.get("winner"):
        winner = data["winner"]
        if winner == username:
            console.print("[bold green]You won![/bold green]")
        else:
            console.print(f"[bold red]{winner} won the battle.[/bold red]")

    # Show last turn events if any
    turn_log = data.get("turn_log", [])
    if turn_log:
        last_turn = turn_log[-1]
        console.print(f"\n[bold]Turn {len(turn_log)} Events:[/bold]")
        for ev in last_turn:
            msg = ev.get("message", "")
            if msg:
                console.print(f"  {msg}")


@app.command("history")
def battle_history(
    username: str = typer.Option(..., "--username", "-u", prompt=True),
    password: str = typer.Option(..., "--password", "-p", prompt=True, hide_input=True),
    limit: int = typer.Option(10, "--limit", "-n"),
) -> None:
    """View your completed battle history from the server."""
    token = _login(username, password)
    if not token:
        return

    url = f"{_get_server_url()}/battles/history/me"
    resp = requests.get(url, headers=_auth_headers(token), params={"limit": limit}, timeout=10)
    if resp.status_code != 200:
        console.print(f"[red]Error:[/red] {resp.text}")
        return

    battles = resp.json()
    if not battles:
        console.print("[dim]No completed battles yet.[/dim]")
        return

    table = Table(title="Battle History", box=box.ROUNDED)
    table.add_column("Date", style="dim")
    table.add_column("Opponent", style="bold")
    table.add_column("Format")
    table.add_column("Result", justify="center")
    table.add_column("Turns", justify="right")

    for b in battles:
        opp = b["opponent"] if b["challenger"] == username else b["challenger"]
        result = "WIN" if b.get("winner") == username else "LOSS"
        result_style = "green bold" if result == "WIN" else "red"
        table.add_row(
            b.get("created_at", "?")[:10],
            opp,
            b["format"],
            f"[{result_style}]{result}[/{result_style}]",
            str(b.get("turn_number", 0)),
        )

    console.print(table)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _handle_action_response(resp: requests.Response) -> None:
    """Handle and display the response from an action submission."""
    if resp.status_code != 200:
        console.print(f"[red]Error:[/red] {resp.json().get('detail', resp.text)}")
        return

    data = resp.json()

    if data.get("both_submitted"):
        console.print(f"\n[bold cyan]Turn {data.get('turn_number', '?')} resolved![/bold cyan]")
        for ev in data.get("events", []):
            msg = ev.get("message", "")
            if msg:
                etype = ev.get("event_type", "")
                if etype == "damage":
                    if ev.get("critical"):
                        console.print(f"  [yellow]{msg}[/yellow]")
                    elif ev.get("effectiveness", 1.0) > 1.0:
                        console.print(f"  [green]{msg}[/green]")
                    elif ev.get("effectiveness", 1.0) < 1.0:
                        console.print(f"  [dim]{msg}[/dim]")
                    else:
                        console.print(f"  {msg}")
                elif etype == "faint":
                    console.print(f"  [red bold]{msg}[/red bold]")
                elif etype == "switch":
                    console.print(f"  [cyan]{msg}[/cyan]")
                elif etype == "forfeit":
                    console.print(f"  [yellow bold]{msg}[/yellow bold]")
                else:
                    console.print(f"  {msg}")

        if data.get("winner"):
            console.print(f"\n[bold]Winner: {data['winner']}[/bold]")
        else:
            console.print("\n[dim]Waiting for next turn...[/dim]")
    else:
        console.print("[dim]Action submitted. Waiting for opponent...[/dim]")
