"""Textual TUI application for PokeDo."""

from __future__ import annotations

from datetime import date

from rich.box import ROUNDED
from rich.panel import Panel
from rich.table import Table
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Footer, Header, Static

from pokedo.data.database import db


class TrainerSummary(Static):
    """Trainer stats summary panel."""

    def refresh_content(self) -> None:
        trainer = db.get_or_create_trainer()
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


class PokeDoApp(App):
    """Textual app entry point."""

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "refresh", "Refresh"),
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

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Dashboard()
        yield Footer()

    def on_mount(self) -> None:
        self.refresh_dashboard()

    def action_refresh(self) -> None:
        self.refresh_dashboard()

    def refresh_dashboard(self) -> None:
        for widget in self.query(TrainerSummary):
            widget.refresh_content()
        for widget in self.query(TeamSummary):
            widget.refresh_content()
        for widget in self.query(TasksSummary):
            widget.refresh_content()
        for widget in self.query(QuickHelp):
            widget.refresh_content()