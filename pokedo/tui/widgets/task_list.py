"""Task list and detail widgets for the TUI."""

from __future__ import annotations

from rich.box import ROUNDED
from rich.panel import Panel
from textual.app import ComposeResult
from textual.message import Message
from textual.widgets import DataTable, Static

from pokedo.core.task import Task
from pokedo.tui.widgets.common import DIFFICULTY_COLORS, PRIORITY_COLORS


class TaskListView(Static):
    """A DataTable-based task list widget with selection support."""

    DEFAULT_CSS = """
    TaskListView {
        height: 100%;
        width: 100%;
    }

    TaskListView DataTable {
        height: 100%;
    }
    """

    def __init__(self, tasks: list[Task] | None = None, **kwargs):
        super().__init__(**kwargs)
        self._tasks: list[Task] = tasks or []
        self._selected_task: Task | None = None

    def compose(self) -> ComposeResult:
        table = DataTable(id="task-table", cursor_type="row")
        yield table

    def on_mount(self) -> None:
        table = self.query_one("#task-table", DataTable)
        table.add_columns("ID", "Title", "Category", "Diff", "Due", "Status")
        self.refresh_tasks(self._tasks)

    def refresh_tasks(self, tasks: list[Task]) -> None:
        """Refresh the task list with new data."""
        self._tasks = tasks
        table = self.query_one("#task-table", DataTable)
        table.clear()

        for task in tasks:
            diff_color = DIFFICULTY_COLORS.get(task.difficulty.value, "white")

            if task.is_completed:
                status = "[green]Done[/green]"
            elif task.is_overdue:
                status = "[red]Overdue[/red]"
            else:
                status = "[yellow]Pending[/yellow]"

            due_str = task.due_date.isoformat() if task.due_date else "-"

            table.add_row(
                str(task.id),
                task.title[:30] + "..." if len(task.title) > 30 else task.title,
                task.category.value,
                f"[{diff_color}]{task.difficulty.value}[/{diff_color}]",
                due_str,
                status,
                key=str(task.id),
            )

    def get_selected_task(self) -> Task | None:
        """Return the currently selected task."""
        table = self.query_one("#task-table", DataTable)
        if table.cursor_row is None or table.cursor_row >= len(self._tasks):
            return None
        return self._tasks[table.cursor_row]

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection."""
        if event.row_key is not None:
            task_id = int(event.row_key.value)
            self._selected_task = next(
                (t for t in self._tasks if t.id == task_id), None
            )
            self.post_message(TaskSelected(self._selected_task))


class TaskSelected(Message):
    """Message sent when a task is selected."""

    def __init__(self, task: Task | None):
        super().__init__()
        self.task = task


class TaskDetailPanel(Static):
    """Panel showing detailed information about a selected task."""

    DEFAULT_CSS = """
    TaskDetailPanel {
        height: 100%;
        padding: 1;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._task: Task | None = None

    def set_task(self, task: Task | None) -> None:
        """Set the task to display."""
        self._task = task
        self.refresh_content()

    def refresh_content(self) -> None:
        """Refresh the panel content."""
        if self._task is None:
            content = "[dim]Select a task to view details[/dim]"
            self.update(Panel(content, title="Task Details", box=ROUNDED))
            return

        task = self._task
        diff_color = DIFFICULTY_COLORS.get(task.difficulty.value, "white")
        priority_style = PRIORITY_COLORS.get(task.priority.value, "white")

        status_text = "Completed" if task.is_completed else "Pending"
        if task.is_overdue and not task.is_completed:
            status_text = "[red]Overdue[/red]"

        content = f"""[bold]{task.title}[/bold]

[dim]Category:[/dim] {task.category.value}
[dim]Difficulty:[/dim] [{diff_color}]{task.difficulty.value}[/{diff_color}]
[dim]Priority:[/dim] [{priority_style}]{task.priority.value}[/{priority_style}]
[dim]XP Reward:[/dim] {task.xp_reward}

[dim]Created:[/dim] {task.created_at.strftime('%Y-%m-%d %H:%M')}
[dim]Due:[/dim] {task.due_date.isoformat() if task.due_date else 'No deadline'}
[dim]Status:[/dim] {status_text}"""

        if task.description:
            content += f"\n\n[dim]Description:[/dim]\n{task.description}"

        if task.tags:
            content += f"\n\n[dim]Tags:[/dim] {', '.join(task.tags)}"

        content += "\n\n[dim]Actions:[/dim]"
        if not task.is_completed:
            content += "\n  [green]c[/green] - Complete task"
            content += "\n  [yellow]e[/yellow] - Edit task"
        content += "\n  [red]d[/red] - Delete task"

        self.update(Panel(content, title=f"Task #{task.id}", box=ROUNDED))
