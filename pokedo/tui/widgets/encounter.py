"""Encounter and task completion widgets for the TUI."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static

from pokedo.core.pokemon import Pokemon
from pokedo.core.rewards import EncounterResult
from pokedo.core.task import Task
from pokedo.tui.widgets.common import TYPE_COLORS


class EncounterWidget(Static):
    """Widget for displaying a Pokemon encounter result."""

    DEFAULT_CSS = """
    EncounterWidget {
        height: auto;
        padding: 1 2;
        margin: 1;
        border: double $accent;
        text-align: center;
    }

    .encounter-caught {
        color: green;
        text-style: bold;
    }

    .encounter-escaped {
        color: red;
        text-style: bold;
    }
    """

    def __init__(self, pokemon: Pokemon, caught: bool, **kwargs):
        super().__init__(**kwargs)
        self._pokemon = pokemon
        self._caught = caught

    def on_mount(self) -> None:
        self.refresh_content()

    def refresh_content(self) -> None:
        pokemon = self._pokemon
        type_color = TYPE_COLORS.get(pokemon.type1, "white")
        shiny_text = "[yellow]SHINY [/yellow]" if pokemon.is_shiny else ""

        if self._caught:
            content = f"""[bold green]CAUGHT![/bold green]

A wild {shiny_text}[{type_color}]{pokemon.name.upper()}[/{type_color}] appeared!

[green]You caught it![/green]

Type: [{type_color}]{pokemon.types_display}[/{type_color}]
Level: {pokemon.level}"""
        else:
            content = f"""[bold yellow]GOT AWAY![/bold yellow]

A wild {shiny_text}[{type_color}]{pokemon.name.upper()}[/{type_color}] appeared!

[red]It got away...[/red]

Better luck next time!"""

        self.update(content)


class TaskCompletionModal(ModalScreen[None]):
    """Modal showing task completion results and encounter."""

    CSS = """
    TaskCompletionModal {
        align: center middle;
    }

    #completion-dialog {
        width: 60%;
        max-width: 70;
        max-height: 80%;
        padding: 1 2;
        border: round $accent;
        background: $panel;
    }

    #completion-title {
        text-align: center;
        text-style: bold;
        color: green;
        margin-bottom: 1;
    }

    #completion-summary {
        margin-bottom: 1;
    }

    #encounter-section {
        margin-top: 1;
    }

    #completion-actions {
        margin-top: 1;
        height: auto;
        align: center middle;
    }
    """

    def __init__(self, task: Task, result: EncounterResult):
        super().__init__()
        self._completed_task = task
        self._result = result

    def compose(self) -> ComposeResult:
        task = self._completed_task
        result = self._result

        with Container(id="completion-dialog"):
            yield Static("[bold green]Task Completed![/bold green]", id="completion-title")

            # Task completion summary
            summary_content = f"""[bold]"{task.title}"[/bold]

[dim]XP Earned:[/dim] +{result.xp_earned}"""

            if result.level_up:
                summary_content += f"\n[bold yellow]LEVEL UP! You are now level {result.new_level}![/bold yellow]"

            summary_content += f"\n[dim]Current Streak:[/dim] {result.streak_count} days"

            if result.items_earned:
                items_str = ", ".join([f"{v}x {k}" for k, v in result.items_earned.items()])
                summary_content += f"\n[green]Items Earned:[/green] {items_str}"

            if result.evs_earned:
                ev_info = result.evs_earned
                summary_content += f"\n[cyan]EV Training:[/cyan] {ev_info['pokemon']} gained +{ev_info['amount']} {ev_info['stat'].upper()}"

            yield Static(summary_content, id="completion-summary")

            # Pokemon encounter section
            if result.encountered:
                with Vertical(id="encounter-section"):
                    if result.pokemon:
                        yield EncounterWidget(result.pokemon, result.caught)
                    else:
                        yield Static("[dim]No Pokemon encountered.[/dim]")
            else:
                yield Static("\n[dim]No wild Pokemon appeared this time.[/dim]", id="encounter-section")

            with Container(id="completion-actions"):
                yield Button("Continue", id="continue-btn", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "continue-btn":
            self.dismiss(None)

    def on_key(self, event) -> None:
        if event.key in ("escape", "enter", "space"):
            self.dismiss(None)
