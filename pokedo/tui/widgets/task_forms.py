"""Task form modals for adding and editing tasks."""

from __future__ import annotations

from datetime import date, datetime

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, Static, TextArea

from pokedo.core.task import (
    RecurrenceType,
    Task,
    TaskCategory,
    TaskDifficulty,
    TaskPriority,
)


# Select options for task forms
CATEGORY_OPTIONS = [
    ("Work", TaskCategory.WORK.value),
    ("Exercise", TaskCategory.EXERCISE.value),
    ("Learning", TaskCategory.LEARNING.value),
    ("Personal", TaskCategory.PERSONAL.value),
    ("Health", TaskCategory.HEALTH.value),
    ("Creative", TaskCategory.CREATIVE.value),
]

DIFFICULTY_OPTIONS = [
    ("Easy (10 XP)", TaskDifficulty.EASY.value),
    ("Medium (25 XP)", TaskDifficulty.MEDIUM.value),
    ("Hard (50 XP)", TaskDifficulty.HARD.value),
    ("Epic (100 XP)", TaskDifficulty.EPIC.value),
]

PRIORITY_OPTIONS = [
    ("Low", TaskPriority.LOW.value),
    ("Medium", TaskPriority.MEDIUM.value),
    ("High", TaskPriority.HIGH.value),
    ("Urgent", TaskPriority.URGENT.value),
]

RECURRENCE_OPTIONS = [
    ("None", RecurrenceType.NONE.value),
    ("Daily", RecurrenceType.DAILY.value),
    ("Weekly", RecurrenceType.WEEKLY.value),
    ("Monthly", RecurrenceType.MONTHLY.value),
]


class AddTaskModal(ModalScreen[Task | None]):
    """Modal dialog for adding a new task."""

    CSS = """
    AddTaskModal {
        align: center middle;
    }

    #add-task-dialog {
        width: 70%;
        max-width: 80;
        max-height: 90%;
        padding: 1 2;
        border: round $accent;
        background: $panel;
    }

    #add-task-title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }

    .form-row {
        height: auto;
        margin-bottom: 1;
    }

    .form-row Label {
        width: 15;
    }

    .form-row Input, .form-row Select {
        width: 1fr;
    }

    #task-description {
        height: 4;
    }

    #add-task-actions {
        margin-top: 1;
        height: auto;
        align: right middle;
    }

    #add-task-actions Button {
        margin-left: 1;
    }
    """

    def compose(self) -> ComposeResult:
        with Container(id="add-task-dialog"):
            yield Static("[bold]Add New Task[/bold]", id="add-task-title")

            with Horizontal(classes="form-row"):
                yield Label("Title:")
                yield Input(placeholder="Task title", id="task-title")

            with Horizontal(classes="form-row"):
                yield Label("Description:")
                yield TextArea(id="task-description")

            with Horizontal(classes="form-row"):
                yield Label("Category:")
                yield Select(
                    CATEGORY_OPTIONS,
                    value=TaskCategory.PERSONAL.value,
                    id="task-category",
                )

            with Horizontal(classes="form-row"):
                yield Label("Difficulty:")
                yield Select(
                    DIFFICULTY_OPTIONS,
                    value=TaskDifficulty.MEDIUM.value,
                    id="task-difficulty",
                )

            with Horizontal(classes="form-row"):
                yield Label("Priority:")
                yield Select(
                    PRIORITY_OPTIONS,
                    value=TaskPriority.MEDIUM.value,
                    id="task-priority",
                )

            with Horizontal(classes="form-row"):
                yield Label("Due Date:")
                yield Input(
                    placeholder="YYYY-MM-DD (optional)",
                    id="task-due-date",
                )

            with Horizontal(classes="form-row"):
                yield Label("Recurrence:")
                yield Select(
                    RECURRENCE_OPTIONS,
                    value=RecurrenceType.NONE.value,
                    id="task-recurrence",
                )

            with Horizontal(classes="form-row"):
                yield Label("Tags:")
                yield Input(
                    placeholder="comma,separated,tags",
                    id="task-tags",
                )

            with Horizontal(id="add-task-actions"):
                yield Button("Cancel", id="cancel-btn", variant="default")
                yield Button("Add Task", id="add-btn", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel-btn":
            self.dismiss(None)
            return

        if event.button.id == "add-btn":
            title_input = self.query_one("#task-title", Input)
            title = title_input.value.strip()

            if not title:
                self.notify("Title is required", severity="error")
                title_input.focus()
                return

            description_area = self.query_one("#task-description", TextArea)
            description = description_area.text.strip() or None

            category_select = self.query_one("#task-category", Select)
            category = TaskCategory(category_select.value)

            difficulty_select = self.query_one("#task-difficulty", Select)
            difficulty = TaskDifficulty(difficulty_select.value)

            priority_select = self.query_one("#task-priority", Select)
            priority = TaskPriority(priority_select.value)

            due_date_input = self.query_one("#task-due-date", Input)
            due_date = None
            if due_date_input.value.strip():
                try:
                    due_date = date.fromisoformat(due_date_input.value.strip())
                except ValueError:
                    self.notify("Invalid date format. Use YYYY-MM-DD", severity="error")
                    due_date_input.focus()
                    return

            recurrence_select = self.query_one("#task-recurrence", Select)
            recurrence = RecurrenceType(recurrence_select.value)

            tags_input = self.query_one("#task-tags", Input)
            tags = [
                t.strip()
                for t in tags_input.value.split(",")
                if t.strip()
            ]

            task = Task(
                title=title,
                description=description,
                category=category,
                difficulty=difficulty,
                priority=priority,
                due_date=due_date,
                recurrence=recurrence,
                tags=tags,
            )

            self.dismiss(task)

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.dismiss(None)


class EditTaskModal(ModalScreen[Task | None]):
    """Modal dialog for editing an existing task."""

    CSS = """
    EditTaskModal {
        align: center middle;
    }

    #edit-task-dialog {
        width: 70%;
        max-width: 80;
        max-height: 90%;
        padding: 1 2;
        border: round $accent;
        background: $panel;
    }

    #edit-task-title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }

    .form-row {
        height: auto;
        margin-bottom: 1;
    }

    .form-row Label {
        width: 15;
    }

    .form-row Input, .form-row Select {
        width: 1fr;
    }

    #task-description {
        height: 4;
    }

    #edit-task-actions {
        margin-top: 1;
        height: auto;
        align: right middle;
    }

    #edit-task-actions Button {
        margin-left: 1;
    }
    """

    def __init__(self, task: Task):
        super().__init__()
        self._editing_task = task

    def compose(self) -> ComposeResult:
        task = self._editing_task

        with Container(id="edit-task-dialog"):
            yield Static(f"[bold]Edit Task #{task.id}[/bold]", id="edit-task-title")

            with Horizontal(classes="form-row"):
                yield Label("Title:")
                yield Input(value=task.title, id="task-title")

            with Horizontal(classes="form-row"):
                yield Label("Description:")
                area = TextArea(id="task-description")
                area.text = task.description or ""
                yield area

            with Horizontal(classes="form-row"):
                yield Label("Category:")
                yield Select(
                    CATEGORY_OPTIONS,
                    value=task.category.value,
                    id="task-category",
                )

            with Horizontal(classes="form-row"):
                yield Label("Difficulty:")
                yield Select(
                    DIFFICULTY_OPTIONS,
                    value=task.difficulty.value,
                    id="task-difficulty",
                )

            with Horizontal(classes="form-row"):
                yield Label("Priority:")
                yield Select(
                    PRIORITY_OPTIONS,
                    value=task.priority.value,
                    id="task-priority",
                )

            with Horizontal(classes="form-row"):
                yield Label("Due Date:")
                yield Input(
                    value=task.due_date.isoformat() if task.due_date else "",
                    placeholder="YYYY-MM-DD (optional)",
                    id="task-due-date",
                )

            with Horizontal(classes="form-row"):
                yield Label("Recurrence:")
                yield Select(
                    RECURRENCE_OPTIONS,
                    value=task.recurrence.value,
                    id="task-recurrence",
                )

            with Horizontal(classes="form-row"):
                yield Label("Tags:")
                yield Input(
                    value=",".join(task.tags),
                    placeholder="comma,separated,tags",
                    id="task-tags",
                )

            with Horizontal(id="edit-task-actions"):
                yield Button("Cancel", id="cancel-btn", variant="default")
                yield Button("Save Changes", id="save-btn", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel-btn":
            self.dismiss(None)
            return

        if event.button.id == "save-btn":
            title_input = self.query_one("#task-title", Input)
            title = title_input.value.strip()

            if not title:
                self.notify("Title is required", severity="error")
                title_input.focus()
                return

            description_area = self.query_one("#task-description", TextArea)
            description = description_area.text.strip() or None

            category_select = self.query_one("#task-category", Select)
            category = TaskCategory(category_select.value)

            difficulty_select = self.query_one("#task-difficulty", Select)
            difficulty = TaskDifficulty(difficulty_select.value)

            priority_select = self.query_one("#task-priority", Select)
            priority = TaskPriority(priority_select.value)

            due_date_input = self.query_one("#task-due-date", Input)
            due_date = None
            if due_date_input.value.strip():
                try:
                    due_date = date.fromisoformat(due_date_input.value.strip())
                except ValueError:
                    self.notify("Invalid date format. Use YYYY-MM-DD", severity="error")
                    due_date_input.focus()
                    return

            recurrence_select = self.query_one("#task-recurrence", Select)
            recurrence = RecurrenceType(recurrence_select.value)

            tags_input = self.query_one("#task-tags", Input)
            tags = [
                t.strip()
                for t in tags_input.value.split(",")
                if t.strip()
            ]

            # Update the task with new values
            self._editing_task.title = title
            self._editing_task.description = description
            self._editing_task.category = category
            self._editing_task.difficulty = difficulty
            self._editing_task.priority = priority
            self._editing_task.due_date = due_date
            self._editing_task.recurrence = recurrence
            self._editing_task.tags = tags

            self.dismiss(self._editing_task)

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.dismiss(None)
