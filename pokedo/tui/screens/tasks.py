"""Task management screen for the TUI."""

from __future__ import annotations

import asyncio
from datetime import date
from typing import ClassVar

from textual import work
from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.screen import Screen
from textual.widgets import Footer, Header, Static, TabbedContent, TabPane

from pokedo.core.rewards import EncounterResult, reward_engine
from pokedo.core.task import Task
from pokedo.core.trainer import Trainer
from pokedo.data.database import db
from pokedo.tui.widgets.common import ConfirmModal
from pokedo.tui.widgets.encounter import TaskCompletionModal
from pokedo.tui.widgets.task_forms import AddTaskModal, EditTaskModal
from pokedo.tui.widgets.task_list import TaskDetailPanel, TaskListView, TaskSelected


class TaskManagementScreen(Screen):
    """Screen for managing tasks with tabbed filtering."""

    BINDINGS: ClassVar[list[tuple[str, str, str]]] = [
        ("escape", "go_back", "Back"),
        ("a", "add_task", "Add Task"),
        ("c", "complete_task", "Complete"),
        ("e", "edit_task", "Edit"),
        ("d", "delete_task", "Delete"),
        ("r", "refresh", "Refresh"),
    ]

    CSS = """
    TaskManagementScreen {
        background: $surface;
    }

    #task-content {
        height: 100%;
        padding: 1;
    }

    #task-main {
        height: 1fr;
    }

    #task-list-container {
        width: 2fr;
        height: 100%;
        padding: 0 1 0 0;
    }

    #task-detail-container {
        width: 1fr;
        height: 100%;
    }

    #help-bar {
        height: 3;
        padding: 0 1;
        background: $panel;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._selected_task: Task | None = None
        self._current_tab: str = "active"
        self._completion_worker = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        with Container(id="task-content"):
            with TabbedContent(id="task-tabs"):
                with TabPane("Active", id="tab-active"):
                    with Horizontal(id="task-main"):
                        with Container(id="task-list-container"):
                            yield TaskListView(id="task-list-active")
                        with Container(id="task-detail-container"):
                            yield TaskDetailPanel(id="task-detail")

                with TabPane("Due Today", id="tab-today"):
                    with Horizontal(id="task-main-today"):
                        with Container(id="task-list-container-today"):
                            yield TaskListView(id="task-list-today")

                with TabPane("All", id="tab-all"):
                    with Horizontal(id="task-main-all"):
                        with Container(id="task-list-container-all"):
                            yield TaskListView(id="task-list-all")

                with TabPane("Archived", id="tab-archived"):
                    with Horizontal(id="task-main-archived"):
                        with Container(id="task-list-container-archived"):
                            yield TaskListView(id="task-list-archived")

            yield Static(
                "[green]a[/green] Add | [yellow]c[/yellow] Complete | [cyan]e[/cyan] Edit | [red]d[/red] Delete | [dim]Esc[/dim] Back",
                id="help-bar",
            )

        yield Footer()

    def on_mount(self) -> None:
        self.refresh_all_lists()

    def refresh_all_lists(self) -> None:
        """Refresh all task lists."""
        # Active tasks (pending, not archived)
        active_tasks = [
            t for t in db.get_tasks(include_completed=False)
            if not t.is_archived
        ]
        active_list = self.query_one("#task-list-active", TaskListView)
        active_list.refresh_tasks(active_tasks)

        # Due today
        today_tasks = db.get_tasks_for_date(date.today())
        today_list = self.query_one("#task-list-today", TaskListView)
        today_list.refresh_tasks(today_tasks)

        # All tasks (not archived)
        all_tasks = [t for t in db.get_tasks(include_completed=True) if not t.is_archived]
        all_list = self.query_one("#task-list-all", TaskListView)
        all_list.refresh_tasks(all_tasks)

        # Archived tasks
        archived_tasks = [t for t in db.get_tasks(include_completed=True) if t.is_archived]
        archived_list = self.query_one("#task-list-archived", TaskListView)
        archived_list.refresh_tasks(archived_tasks)

    def _get_current_list(self) -> TaskListView:
        """Get the currently visible task list."""
        tabs = self.query_one("#task-tabs", TabbedContent)
        active_tab = tabs.active

        list_ids = {
            "tab-active": "#task-list-active",
            "tab-today": "#task-list-today",
            "tab-all": "#task-list-all",
            "tab-archived": "#task-list-archived",
        }

        list_id = list_ids.get(active_tab, "#task-list-active")
        return self.query_one(list_id, TaskListView)

    def on_task_selected(self, event: TaskSelected) -> None:
        """Handle task selection."""
        self._selected_task = event.task
        detail_panel = self.query_one("#task-detail", TaskDetailPanel)
        detail_panel.set_task(event.task)

    def action_go_back(self) -> None:
        """Return to the main dashboard."""
        self.app.pop_screen()

    def action_refresh(self) -> None:
        """Refresh all task lists."""
        self.refresh_all_lists()
        self.notify("Tasks refreshed")

    def action_add_task(self) -> None:
        """Open the add task modal."""
        def on_task_added(task: Task | None) -> None:
            if task is not None:
                trainer = db.get_or_create_trainer()
                db.create_task(task, trainer.id)
                self.refresh_all_lists()
                self.notify(f"Task '{task.title}' added")

        self.app.push_screen(AddTaskModal(), on_task_added)

    async def action_complete_task(self) -> None:
        """Calculate rewards in a worker, then commit completion on the UI thread."""
        if self._completion_worker is not None and not self._completion_worker.is_finished:
            self.notify("Task completion is already in progress", severity="warning")
            return

        current_list = self._get_current_list()
        task = current_list.get_selected_task()

        if task is None:
            self.notify("No task selected", severity="warning")
            return

        if task.is_completed:
            self.notify("Task is already completed", severity="warning")
            return

        trainer = db.get_or_create_trainer()
        self._completion_worker = self._calculate_completion_rewards(task, trainer)

        try:
            result = await self._completion_worker.wait()
            db.complete_task_with_rewards(task, trainer, result)
        except Exception as exc:
            self.notify(f"Task completion failed: {exc}", severity="error")
            self.refresh_all_lists()
            return

        self._completion_worker = None
        self.refresh_all_lists()
        self.app.push_screen(
            TaskCompletionModal(task, result),
            lambda _: self.refresh_all_lists(),
        )

    @work(thread=True)
    def _calculate_completion_rewards(self, task: Task, trainer: Trainer) -> EncounterResult:
        """Run reward calculation in a worker without touching the database."""
        return asyncio.run(reward_engine.process_task_completion_async(task, trainer))

    def action_edit_task(self) -> None:
        """Edit the selected task."""
        current_list = self._get_current_list()
        task = current_list.get_selected_task()

        if task is None:
            self.notify("No task selected", severity="warning")
            return

        def on_task_edited(edited_task: Task | None) -> None:
            if edited_task is not None:
                db.update_task(edited_task)
                self.refresh_all_lists()
                self.notify(f"Task '{edited_task.title}' updated")

        self.app.push_screen(EditTaskModal(task), on_task_edited)

    def action_delete_task(self) -> None:
        """Delete the selected task."""
        current_list = self._get_current_list()
        task = current_list.get_selected_task()

        if task is None:
            self.notify("No task selected", severity="warning")
            return

        def on_confirm(confirmed: bool) -> None:
            if confirmed:
                db.delete_task(task.id)
                self.refresh_all_lists()
                self.notify(f"Task '{task.title}' deleted")

        self.app.push_screen(
            ConfirmModal(
                message=f"Delete task '{task.title}'?",
                title="Confirm Delete",
            ),
            on_confirm,
        )
