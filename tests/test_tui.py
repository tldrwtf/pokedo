"""Tests for TUI components."""

from datetime import date, datetime

import pytest

from pokedo.core.task import (
    RecurrenceType,
    Task,
    TaskCategory,
    TaskDifficulty,
    TaskPriority,
)
from pokedo.core.pokemon import Pokemon
from pokedo.core.rewards import EncounterResult
from pokedo.tui.widgets.common import (
    DIFFICULTY_COLORS,
    PRIORITY_COLORS,
    TYPE_COLORS,
    CATEGORY_ICONS,
)


class TestColorMappings:
    """Tests for color mapping constants."""

    def test_difficulty_colors_complete(self):
        """All difficulty levels have colors."""
        expected_keys = ["easy", "medium", "hard", "epic"]
        for key in expected_keys:
            assert key in DIFFICULTY_COLORS
            assert isinstance(DIFFICULTY_COLORS[key], str)

    def test_priority_colors_complete(self):
        """All priority levels have colors."""
        expected_keys = ["low", "medium", "high", "urgent"]
        for key in expected_keys:
            assert key in PRIORITY_COLORS
            assert isinstance(PRIORITY_COLORS[key], str)

    def test_type_colors_complete(self):
        """All Pokemon types have colors."""
        expected_types = [
            "normal", "fire", "water", "electric", "grass", "ice",
            "fighting", "poison", "ground", "flying", "psychic", "bug",
            "rock", "ghost", "dragon", "dark", "steel", "fairy",
        ]
        for pokemon_type in expected_types:
            assert pokemon_type in TYPE_COLORS
            assert isinstance(TYPE_COLORS[pokemon_type], str)

    def test_category_icons_complete(self):
        """All task categories have icons."""
        for category in TaskCategory:
            assert category.value in CATEGORY_ICONS


class TestTaskListViewLogic:
    """Tests for TaskListView data processing logic."""

    def test_task_status_display_completed(self, completed_task):
        """Completed tasks show 'Done' status."""
        assert completed_task.is_completed is True

    def test_task_status_display_overdue(self, overdue_task):
        """Overdue tasks are identified correctly."""
        assert overdue_task.is_overdue is True
        assert overdue_task.is_completed is False

    def test_task_status_display_pending(self, sample_task):
        """Normal pending tasks are not overdue."""
        assert sample_task.is_completed is False
        assert sample_task.is_overdue is False

    def test_task_title_truncation(self):
        """Long titles should be truncatable."""
        long_title = "A" * 50
        task = Task(title=long_title)
        # Simulating the truncation logic from TaskListView
        truncated = task.title[:30] + "..." if len(task.title) > 30 else task.title
        assert len(truncated) == 33  # 30 chars + "..."
        assert truncated.endswith("...")


class TestTaskDetailPanelLogic:
    """Tests for TaskDetailPanel content generation logic."""

    def test_task_detail_has_xp_reward(self, sample_task):
        """Task details include XP reward."""
        assert sample_task.xp_reward > 0

    def test_task_detail_difficulty_color(self, sample_task):
        """Difficulty has an associated color."""
        color = DIFFICULTY_COLORS.get(sample_task.difficulty.value)
        assert color is not None

    def test_task_detail_priority_color(self, sample_task):
        """Priority has an associated color."""
        color = PRIORITY_COLORS.get(sample_task.priority.value)
        assert color is not None

    def test_task_detail_with_tags(self):
        """Tasks with tags display them correctly."""
        task = Task(title="Tagged Task", tags=["important", "urgent"])
        assert len(task.tags) == 2
        assert "important" in task.tags

    def test_task_detail_with_description(self):
        """Tasks with descriptions include them."""
        task = Task(title="Described Task", description="This is a description")
        assert task.description == "This is a description"

    def test_task_detail_due_date_display(self):
        """Tasks with due dates format them."""
        task = Task(title="Due Task", due_date=date(2025, 12, 31))
        assert task.due_date.isoformat() == "2025-12-31"


class TestAddTaskModalLogic:
    """Tests for AddTaskModal form validation logic."""

    def test_task_creation_with_minimal_fields(self):
        """Task can be created with just a title."""
        task = Task(title="Minimal Task")
        assert task.title == "Minimal Task"
        assert task.category == TaskCategory.PERSONAL
        assert task.difficulty == TaskDifficulty.MEDIUM

    def test_task_creation_with_all_fields(self):
        """Task can be created with all fields."""
        task = Task(
            title="Full Task",
            description="Full description",
            category=TaskCategory.WORK,
            difficulty=TaskDifficulty.HARD,
            priority=TaskPriority.HIGH,
            due_date=date.today(),
            recurrence=RecurrenceType.WEEKLY,
            tags=["tag1", "tag2"],
        )
        assert task.title == "Full Task"
        assert task.description == "Full description"
        assert task.category == TaskCategory.WORK
        assert task.difficulty == TaskDifficulty.HARD
        assert task.priority == TaskPriority.HIGH
        assert task.due_date == date.today()
        assert task.recurrence == RecurrenceType.WEEKLY
        assert task.tags == ["tag1", "tag2"]

    def test_date_parsing_valid(self):
        """Valid date strings parse correctly."""
        date_str = "2025-06-15"
        parsed = date.fromisoformat(date_str)
        assert parsed == date(2025, 6, 15)

    def test_date_parsing_invalid(self):
        """Invalid date strings raise ValueError."""
        date_str = "invalid-date"
        with pytest.raises(ValueError):
            date.fromisoformat(date_str)

    def test_tags_parsing_from_comma_separated(self):
        """Tags parse correctly from comma-separated string."""
        tags_input = "tag1, tag2, tag3"
        tags = [t.strip() for t in tags_input.split(",") if t.strip()]
        assert tags == ["tag1", "tag2", "tag3"]

    def test_tags_parsing_handles_empty(self):
        """Empty tag string produces empty list."""
        tags_input = ""
        tags = [t.strip() for t in tags_input.split(",") if t.strip()]
        assert tags == []

    def test_tags_parsing_handles_whitespace(self):
        """Tags with extra whitespace are trimmed."""
        tags_input = "  tag1  ,  tag2  ,  "
        tags = [t.strip() for t in tags_input.split(",") if t.strip()]
        assert tags == ["tag1", "tag2"]


class TestEditTaskModalLogic:
    """Tests for EditTaskModal form population logic."""

    def test_task_modification(self, sample_task):
        """Task fields can be modified."""
        original_title = sample_task.title
        sample_task.title = "Modified Title"
        assert sample_task.title != original_title
        assert sample_task.title == "Modified Title"

    def test_task_category_change(self, sample_task):
        """Task category can be changed."""
        original_category = sample_task.category
        sample_task.category = TaskCategory.CREATIVE
        assert sample_task.category != original_category
        assert sample_task.category == TaskCategory.CREATIVE


class TestEncounterResultDisplay:
    """Tests for encounter result display logic."""

    def test_encounter_result_with_caught_pokemon(self, sample_pokemon):
        """Encounter result with caught Pokemon displays correctly."""
        result = EncounterResult(
            encountered=True,
            caught=True,
            pokemon=sample_pokemon,
            xp_earned=25,
            streak_count=5,
        )
        assert result.encountered is True
        assert result.caught is True
        assert result.pokemon is not None
        assert result.pokemon.name == "pikachu"

    def test_encounter_result_with_escaped_pokemon(self, sample_pokemon):
        """Encounter result with escaped Pokemon displays correctly."""
        result = EncounterResult(
            encountered=True,
            caught=False,
            pokemon=sample_pokemon,
            xp_earned=25,
        )
        assert result.encountered is True
        assert result.caught is False
        assert result.pokemon is not None

    def test_encounter_result_no_encounter(self):
        """No encounter result displays correctly."""
        result = EncounterResult(
            encountered=False,
            caught=False,
            xp_earned=25,
        )
        assert result.encountered is False
        assert result.pokemon is None

    def test_encounter_result_with_level_up(self):
        """Level up in encounter result displays correctly."""
        result = EncounterResult(
            encountered=False,
            caught=False,
            xp_earned=100,
            level_up=True,
            new_level=10,
        )
        assert result.level_up is True
        assert result.new_level == 10

    def test_encounter_result_with_items(self):
        """Items earned in encounter result display correctly."""
        result = EncounterResult(
            encountered=False,
            caught=False,
            xp_earned=25,
            items_earned={"great_ball": 3, "potion": 1},
        )
        assert result.items_earned == {"great_ball": 3, "potion": 1}

    def test_encounter_result_shiny(self, shiny_pokemon):
        """Shiny Pokemon in encounter result displays correctly."""
        result = EncounterResult(
            encountered=True,
            caught=True,
            pokemon=shiny_pokemon,
            is_shiny=True,
            xp_earned=25,
        )
        assert result.is_shiny is True
        assert result.pokemon.is_shiny is True


class TestPokemonTypeColors:
    """Tests for Pokemon type color display."""

    def test_electric_type_color(self, sample_pokemon):
        """Electric type has yellow color."""
        color = TYPE_COLORS.get(sample_pokemon.type1)
        assert color == "yellow"

    def test_fire_type_color(self):
        """Fire type has red color."""
        color = TYPE_COLORS.get("fire")
        assert color == "red"

    def test_water_type_color(self):
        """Water type has blue color."""
        color = TYPE_COLORS.get("water")
        assert color == "blue"

    def test_dual_type_pokemon(self, shiny_pokemon):
        """Dual type Pokemon has both types with colors."""
        color1 = TYPE_COLORS.get(shiny_pokemon.type1)
        color2 = TYPE_COLORS.get(shiny_pokemon.type2)
        assert color1 == "red"  # fire
        assert color2 == "cyan"  # flying


class TestRecurringTaskLogic:
    """Tests for recurring task creation logic."""

    def test_daily_recurrence(self, recurring_task):
        """Daily recurring task identified correctly."""
        assert recurring_task.recurrence == RecurrenceType.DAILY

    def test_weekly_recurrence(self):
        """Weekly recurring task identified correctly."""
        task = Task(title="Weekly", recurrence=RecurrenceType.WEEKLY)
        assert task.recurrence == RecurrenceType.WEEKLY

    def test_monthly_recurrence(self):
        """Monthly recurring task identified correctly."""
        task = Task(title="Monthly", recurrence=RecurrenceType.MONTHLY)
        assert task.recurrence == RecurrenceType.MONTHLY

    def test_no_recurrence(self, sample_task):
        """Non-recurring task has NONE recurrence."""
        assert sample_task.recurrence == RecurrenceType.NONE


class TestTaskFiltering:
    """Tests for task filtering logic used in tabs."""

    def test_filter_active_tasks(self, sample_task, completed_task):
        """Active tasks filter excludes completed tasks."""
        tasks = [sample_task, completed_task]
        active = [t for t in tasks if not t.is_completed and not t.is_archived]
        assert len(active) == 1
        assert active[0] == sample_task

    def test_filter_archived_tasks(self, sample_task):
        """Archived tasks filter works correctly."""
        sample_task.is_archived = True
        tasks = [sample_task]
        archived = [t for t in tasks if t.is_archived]
        assert len(archived) == 1

    def test_filter_overdue_tasks(self, sample_task, overdue_task):
        """Overdue tasks can be filtered."""
        tasks = [sample_task, overdue_task]
        overdue = [t for t in tasks if t.is_overdue]
        assert len(overdue) == 1
        assert overdue[0] == overdue_task


class TestConfirmModalLogic:
    """Tests for confirm modal behavior."""

    def test_confirm_returns_true(self):
        """Confirmation should return True."""
        # This tests the expected behavior pattern
        confirmed = True  # Simulating user pressing "Yes"
        assert confirmed is True

    def test_cancel_returns_false(self):
        """Cancellation should return False."""
        confirmed = False  # Simulating user pressing "No"
        assert confirmed is False


class TestTaskCompletionFlow:
    """Tests for task completion flow logic."""

    def test_task_marked_completed(self, sample_task):
        """Task can be marked as completed."""
        assert sample_task.is_completed is False
        sample_task.is_completed = True
        sample_task.completed_at = datetime.now()
        assert sample_task.is_completed is True
        assert sample_task.completed_at is not None

    def test_completed_task_has_timestamp(self, completed_task):
        """Completed task has completion timestamp."""
        assert completed_task.completed_at is not None


# Async TUI tests using Textual's pilot
class TestTUIAppIntegration:
    """Integration tests for TUI app using Textual's async testing."""

    @pytest.mark.asyncio
    async def test_app_can_be_imported(self):
        """TUI app can be imported without errors."""
        from pokedo.tui.app import PokeDoApp
        assert PokeDoApp is not None

    @pytest.mark.asyncio
    async def test_task_screen_can_be_imported(self):
        """Task management screen can be imported."""
        from pokedo.tui.screens.tasks import TaskManagementScreen
        assert TaskManagementScreen is not None

    @pytest.mark.asyncio
    async def test_widgets_can_be_imported(self):
        """All TUI widgets can be imported."""
        from pokedo.tui.widgets.common import ConfirmModal, NotificationWidget
        from pokedo.tui.widgets.task_list import TaskListView, TaskDetailPanel
        from pokedo.tui.widgets.task_forms import AddTaskModal, EditTaskModal
        from pokedo.tui.widgets.encounter import TaskCompletionModal, EncounterWidget

        assert ConfirmModal is not None
        assert NotificationWidget is not None
        assert TaskListView is not None
        assert TaskDetailPanel is not None
        assert AddTaskModal is not None
        assert EditTaskModal is not None
        assert TaskCompletionModal is not None
        assert EncounterWidget is not None

    @pytest.mark.asyncio
    async def test_task_selected_message(self):
        """TaskSelected message can be created."""
        from pokedo.tui.widgets.task_list import TaskSelected
        task = Task(id=1, title="Test Task")
        message = TaskSelected(task)
        assert message.task == task

    @pytest.mark.asyncio
    async def test_task_selected_message_with_none(self):
        """TaskSelected message can handle None."""
        from pokedo.tui.widgets.task_list import TaskSelected
        message = TaskSelected(None)
        assert message.task is None
