"""Task management screen for the TUI."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Static, TabbedContent, TabPane

from pokedo.core.rewards import reward_engine
from pokedo.core.task import RecurrenceType, Task
from pokedo.data.database import db
from pokedo.tui.widgets.common import ConfirmModal
from pokedo.tui.widgets.encounter import TaskCompletionModal
from pokedo.tui.widgets.task_forms import AddTaskModal, EditTaskModal
from pokedo.tui.widgets.task_list import TaskDetailPanel, TaskListView, TaskSelected


class TaskManagementScreen(Screen):
    """Screen for managing tasks with tabbed filtering."""

    BINDINGS = [
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

    def action_complete_task(self) -> None:
        """Complete the selected task."""
        current_list = self._get_current_list()
        task = current_list.get_selected_task()

        if task is None:
            self.notify("No task selected", severity="warning")
            return

        if task.is_completed:
            self.notify("Task is already completed", severity="warning")
            return

        # Mark task as completed
        task.is_completed = True
        task.completed_at = datetime.now()
        db.update_task(task)

        # Get trainer and process rewards
        trainer = db.get_or_create_trainer()
        result = reward_engine.process_task_completion(task, trainer)

        # Add items to inventory
        for item, count in result.items_earned.items():
            trainer.add_item(item, count)

        # Handle Pokemon encounter
        if result.encountered and result.caught and result.pokemon:
            result.pokemon = db.save_pokemon(result.pokemon)
            trainer.pokemon_caught += 1

            # Update Pokedex
            entry = db.get_pokedex_entry(result.pokemon.pokedex_id)
            if entry:
                if not entry.is_seen:
                    trainer.pokedex_seen += 1
                entry.is_seen = True
                entry.is_caught = True
                entry.times_caught += 1
                if result.is_shiny:
                    entry.shiny_caught = True
                if not entry.first_caught_at:
                    entry.first_caught_at = datetime.now()
                    trainer.pokedex_caught += 1
                db.save_pokedex_entry(entry)
        elif result.encountered and result.pokemon:
            # Pokemon got away - still mark as seen
            entry = db.get_pokedex_entry(result.pokemon.pokedex_id)
            if entry and not entry.is_seen:
                entry.is_seen = True
                trainer.pokedex_seen += 1
                db.save_pokedex_entry(entry)

        # Save trainer
        db.save_trainer(trainer)

        # Handle recurring tasks
        if task.recurrence != RecurrenceType.NONE:
            self._create_recurring_task(task, trainer.id)

        # Show completion modal
        def on_modal_closed(_) -> None:
            self.refresh_all_lists()

        self.app.push_screen(TaskCompletionModal(task, result), on_modal_closed)

    def _create_recurring_task(self, task: Task, trainer_id: int) -> None:
        """Create the next occurrence of a recurring task."""
        if task.recurrence == RecurrenceType.DAILY:
            delta = timedelta(days=1)
        elif task.recurrence == RecurrenceType.WEEKLY:
            delta = timedelta(weeks=1)
        elif task.recurrence == RecurrenceType.MONTHLY:
            delta = timedelta(days=30)  # Approximate
        else:
            return

        new_task = Task(
            title=task.title,
            description=task.description,
            category=task.category,
            difficulty=task.difficulty,
            priority=task.priority,
            due_date=date.today() + delta if task.due_date else None,
            recurrence=task.recurrence,
            parent_task_id=task.id,
            tags=task.tags,
        )
        db.create_task(new_task, trainer_id)

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
