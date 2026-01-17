"""Textual TUI application for PokeDo."""

from __future__ import annotations

from datetime import date

from rich.box import ROUNDED
from rich.panel import Panel
from rich.table import Table
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Footer, Header, Select, Static

from pokedo.data.database import db


class TrainerSummary(Static):
    """Trainer stats summary panel."""

    def refresh_content(self) -> None:
        trainer = self.app.get_active_trainer()
        xp_current, xp_needed = trainer.xp_progress
        content = (
            f"[bold]{trainer.name}[/bold]\n"
            f"Level {trainer.level} | XP {xp_current}/{xp_needed}\n"
            f"Class: {trainer.trainer_class.value.replace('_', ' ').title()}\n"
            f"Streak: {trainer.daily_streak.current_count} days\n"
            f"Pokemon caught: {trainer.pokemon_caught}\n"
        )
        self.update(Panel(content, title="Trainer", box=ROUNDED))


class TeamSummary(Static):
    """Active team summary panel."""

    def refresh_content(self) -> None:
        team = db.get_active_team()
        if not team:
            content = "[dim]No active Pokemon yet. Catch one by completing tasks![/dim]"
            self.update(Panel(content, title="Team", box=ROUNDED))
            return

        lines = []
        for member in team[:6]:
            shiny = " ✨" if member.is_shiny else ""
            lines.append(f"{member.display_name} Lv.{member.level}{shiny}")
        content = "\n".join(lines)
        self.update(Panel(content, title="Team", box=ROUNDED))


class TasksSummary(Static):
    """Tasks list panel."""

    def refresh_content(self) -> None:
        pending_tasks = db.get_tasks(include_completed=False)
        today_tasks = db.get_tasks_for_date(date.today())
        table = Table(box=ROUNDED, expand=True)
        table.add_column("ID", style="dim", width=4)
        table.add_column("Task", min_width=20)
        table.add_column("Due", width=12)
        table.add_column("Status", width=10)

        if not pending_tasks:
            table.add_row("-", "All tasks completed!", "-", "✅")
        else:
            for task in pending_tasks[:8]:
                due_str = task.due_date.isoformat() if task.due_date else "-"
                status = "Overdue" if task.is_overdue else "Pending"
                table.add_row(str(task.id), task.title, due_str, status)

        summary = f"Today: {len([t for t in today_tasks if t.is_completed])}/{len(today_tasks)}"
        panel = Panel(table, title=f"Tasks ({summary})", box=ROUNDED)
        self.update(panel)


class QuickHelp(Static):
    """Quick help panel for navigation."""

    def refresh_content(self) -> None:
        content = (
            "[bold]Shortcuts[/bold]\n"
            "r - Refresh dashboard\n"
            "p - Switch profile\n"
            "q - Quit\n"
            "\n"
            "Use the CLI for now to manage tasks and Pokemon."
        )
        self.update(Panel(content, title="Help", box=ROUNDED))


class Dashboard(Container):
    """Main dashboard layout."""

    def compose(self) -> ComposeResult:
        with Horizontal():
            with Vertical():
                yield TrainerSummary(id="trainer-summary")
                yield TeamSummary(id="team-summary")
            with Vertical():
                yield TasksSummary(id="tasks-summary")
                yield QuickHelp(id="quick-help")


class ProfileSelectScreen(ModalScreen[int]):
    """Modal dialog for selecting a trainer profile."""

    CSS = """
    ProfileSelectScreen {
        align: center middle;
    }

    #profile-dialog {
        width: 60%;
        max-width: 60;
        padding: 1 2;
        border: round $accent;
        background: $panel;
    }

    #profile-actions {
        margin-top: 1;
        height: auto;
        align: right middle;
    }
    """

    def __init__(self, trainer_options: list[tuple[str, str]], default_value: str | None):
        super().__init__()
        self.trainer_options = trainer_options
        self.default_value = default_value

    def compose(self) -> ComposeResult:
        default_value = self.default_value or self.trainer_options[0][1]
        with Container(id="profile-dialog"):
            yield Static("[bold]Select Trainer Profile[/bold]")
            yield Select(
                self.trainer_options,
                value=default_value,
                id="profile-select",
            )
            yield Checkbox("Set as default profile", id="set-default")
            with Horizontal(id="profile-actions"):
                yield Button("Continue", id="profile-continue", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "profile-continue":
            return
        select = self.query_one("#profile-select", Select)
        value = select.value
        if value is None:
            return
        trainer_id = int(value)
        set_default = self.query_one("#set-default", Checkbox).value
        if set_default:
            db.set_default_trainer_id(trainer_id)
        self.dismiss(trainer_id)


class PokeDoApp(App):
    """Textual app entry point."""

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "refresh", "Refresh"),
        ("p", "switch_profile", "Profiles"),
    ]

    CSS = """
    Dashboard {
        padding: 1 2;
    }

    Vertical {
        width: 1fr;
    }

    #trainer-summary, #team-summary, #tasks-summary, #quick-help {
        height: auto;
        margin: 0 1 1 0;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.active_trainer_id: int | None = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Dashboard()
        yield Footer()

    def on_mount(self) -> None:
        self._ensure_active_trainer()

    def action_refresh(self) -> None:
        self.refresh_dashboard()

    def action_switch_profile(self) -> None:
        trainers = db.list_trainers()
        if len(trainers) < 2:
            return
        default_id = db.get_default_trainer_id()
        trainer_ids = {str(t.id) for t in trainers}
        options = [(f"{t.name} (Lv {t.level})", str(t.id)) for t in trainers]
        default_value = (
            str(default_id) if default_id is not None and str(default_id) in trainer_ids else None
        )
        self.push_screen(
            ProfileSelectScreen(options, default_value),
            self._on_profile_selected,
        )

    def _ensure_active_trainer(self) -> None:
        trainers = db.list_trainers()
        if not trainers:
            trainer = db.get_or_create_trainer()
            self.active_trainer_id = trainer.id
            db.set_active_trainer_id(trainer.id)
            self.refresh_dashboard()
            return
        if len(trainers) == 1:
            self.active_trainer_id = trainers[0].id
            db.set_active_trainer_id(trainers[0].id)
            self.refresh_dashboard()
            return
        default_id = db.get_default_trainer_id()
        if default_id is not None and any(t.id == default_id for t in trainers):
            self.active_trainer_id = default_id
            db.set_active_trainer_id(default_id)
            self.refresh_dashboard()
            return
        options = [(f"{t.name} (Lv {t.level})", str(t.id)) for t in trainers]
        self.push_screen(ProfileSelectScreen(options, None), self._on_profile_selected)

    def _on_profile_selected(self, trainer_id: int | None) -> None:
        if trainer_id is None:
            return
        self.active_trainer_id = trainer_id
        db.set_active_trainer_id(trainer_id)
        self.refresh_dashboard()

    def get_active_trainer(self):
        """Return the currently active trainer for the TUI session."""
        if self.active_trainer_id is not None:
            trainer = db.get_trainer_by_id(self.active_trainer_id)
            if trainer is not None:
                db.set_active_trainer_id(trainer.id)
                return trainer
        trainer = db.get_or_create_trainer()
        self.active_trainer_id = trainer.id
        db.set_active_trainer_id(trainer.id)
        return trainer

    def refresh_dashboard(self) -> None:
        for widget in self.query(TrainerSummary):
            widget.refresh_content()
        for widget in self.query(TeamSummary):
            widget.refresh_content()
        for widget in self.query(TasksSummary):
            widget.refresh_content()
        for widget in self.query(QuickHelp):
            widget.refresh_content()
