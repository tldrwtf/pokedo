"""Common TUI widgets shared across screens."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Static


class ConfirmModal(ModalScreen[bool]):
    """A confirmation dialog modal."""

    CSS = """
    ConfirmModal {
        align: center middle;
    }

    #confirm-dialog {
        width: 50%;
        max-width: 60;
        padding: 1 2;
        border: round $accent;
        background: $panel;
    }

    #confirm-message {
        text-align: center;
        margin-bottom: 1;
    }

    #confirm-actions {
        margin-top: 1;
        height: auto;
        align: center middle;
    }

    #confirm-actions Button {
        margin: 0 1;
    }
    """

    def __init__(
        self,
        message: str,
        title: str = "Confirm",
        confirm_label: str = "Yes",
        cancel_label: str = "No",
    ):
        super().__init__()
        self.message = message
        self.title_text = title
        self.confirm_label = confirm_label
        self.cancel_label = cancel_label

    def compose(self) -> ComposeResult:
        with Container(id="confirm-dialog"):
            yield Static(f"[bold]{self.title_text}[/bold]", id="confirm-title")
            yield Static(self.message, id="confirm-message")
            with Horizontal(id="confirm-actions"):
                yield Button(self.confirm_label, id="confirm-yes", variant="primary")
                yield Button(self.cancel_label, id="confirm-no", variant="default")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm-yes":
            self.dismiss(True)
        elif event.button.id == "confirm-no":
            self.dismiss(False)

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.dismiss(False)
        elif event.key == "enter":
            self.dismiss(True)


class NotificationWidget(Static):
    """A widget for displaying notifications."""

    DEFAULT_CSS = """
    NotificationWidget {
        height: auto;
        padding: 0 1;
        margin: 0 0 1 0;
    }

    NotificationWidget.info {
        background: $primary-darken-2;
        color: $text;
    }

    NotificationWidget.warning {
        background: yellow 20%;
        color: yellow;
    }

    NotificationWidget.error {
        background: red 20%;
        color: red;
    }

    NotificationWidget.success {
        background: green 20%;
        color: green;
    }
    """

    def __init__(
        self,
        message: str,
        level: str = "info",
        **kwargs,
    ):
        super().__init__(message, **kwargs)
        self.add_class(level)


# Color mappings for use in TUI widgets
DIFFICULTY_COLORS = {
    "easy": "green",
    "medium": "yellow",
    "hard": "red",
    "epic": "magenta",
}

PRIORITY_COLORS = {
    "low": "dim",
    "medium": "white",
    "high": "yellow",
    "urgent": "red bold",
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

CATEGORY_ICONS = {
    "work": "[blue]W[/blue]",
    "exercise": "[red]E[/red]",
    "learning": "[magenta]L[/magenta]",
    "personal": "[white]P[/white]",
    "health": "[green]H[/green]",
    "creative": "[cyan]C[/cyan]",
}
