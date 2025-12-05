"""Tests for Task model and related logic."""

from datetime import date, datetime, timedelta

from pokedo.core.task import RecurrenceType, Task, TaskCategory, TaskDifficulty, TaskPriority


class TestTaskCategory:
    """Tests for TaskCategory enum."""

    def test_all_categories_exist(self):
        """Verify all expected categories exist."""
        expected = ["work", "exercise", "learning", "personal", "health", "creative"]
        actual = [c.value for c in TaskCategory]
        assert sorted(actual) == sorted(expected)

    def test_category_is_string_enum(self):
        """Verify categories are string enums."""
        assert TaskCategory.WORK == "work"
        assert isinstance(TaskCategory.WORK, str)


class TestTaskDifficulty:
    """Tests for TaskDifficulty enum."""

    def test_all_difficulties_exist(self):
        """Verify all expected difficulties exist."""
        expected = ["easy", "medium", "hard", "epic"]
        actual = [d.value for d in TaskDifficulty]
        assert sorted(actual) == sorted(expected)


class TestTaskPriority:
    """Tests for TaskPriority enum."""

    def test_all_priorities_exist(self):
        """Verify all expected priorities exist."""
        expected = ["low", "medium", "high", "urgent"]
        actual = [p.value for p in TaskPriority]
        assert sorted(actual) == sorted(expected)


class TestRecurrenceType:
    """Tests for RecurrenceType enum."""

    def test_all_recurrence_types_exist(self):
        """Verify all expected recurrence types exist."""
        expected = ["none", "daily", "weekly", "monthly"]
        actual = [r.value for r in RecurrenceType]
        assert sorted(actual) == sorted(expected)


class TestTaskCreation:
    """Tests for Task creation."""

    def test_create_minimal_task(self):
        """Create task with only required fields."""
        task = Task(title="Minimal Task")
        assert task.title == "Minimal Task"
        assert task.category == TaskCategory.PERSONAL  # default
        assert task.difficulty == TaskDifficulty.MEDIUM  # default
        assert task.priority == TaskPriority.MEDIUM  # default
        assert task.is_completed is False
        assert task.is_archived is False

    def test_create_full_task(self):
        """Create task with all fields."""
        task = Task(
            id=1,
            title="Full Task",
            description="Full description",
            category=TaskCategory.WORK,
            difficulty=TaskDifficulty.HARD,
            priority=TaskPriority.URGENT,
            due_date=date.today() + timedelta(days=7),
            recurrence=RecurrenceType.WEEKLY,
            tags=["important", "project"],
        )
        assert task.id == 1
        assert task.title == "Full Task"
        assert task.description == "Full description"
        assert task.category == TaskCategory.WORK
        assert task.difficulty == TaskDifficulty.HARD
        assert task.priority == TaskPriority.URGENT
        assert task.recurrence == RecurrenceType.WEEKLY
        assert "important" in task.tags

    def test_default_created_at(self):
        """Verify created_at defaults to now."""
        before = datetime.now()
        task = Task(title="Test")
        after = datetime.now()
        assert before <= task.created_at <= after

    def test_default_tags_are_empty_list(self):
        """Verify tags default to empty list."""
        task = Task(title="Test")
        assert task.tags == []


class TestTaskIsOverdue:
    """Tests for Task.is_overdue property."""

    def test_overdue_task(self, overdue_task):
        """Task with past due date is overdue."""
        assert overdue_task.is_overdue is True

    def test_not_overdue_future_due_date(self):
        """Task with future due date is not overdue."""
        task = Task(
            title="Future Task",
            due_date=date.today() + timedelta(days=7),
        )
        assert task.is_overdue is False

    def test_not_overdue_today_due_date(self):
        """Task due today is not overdue."""
        task = Task(
            title="Today Task",
            due_date=date.today(),
        )
        assert task.is_overdue is False

    def test_not_overdue_no_due_date(self):
        """Task without due date is not overdue."""
        task = Task(title="No Due Date")
        assert task.is_overdue is False

    def test_completed_task_not_overdue(self):
        """Completed task is not overdue even with past due date."""
        task = Task(
            title="Completed",
            due_date=date.today() - timedelta(days=1),
            is_completed=True,
        )
        assert task.is_overdue is False


class TestTaskXPReward:
    """Tests for Task.xp_reward property."""

    def test_easy_xp_reward(self, easy_task):
        """Easy task gives 10 XP."""
        assert easy_task.xp_reward == 10

    def test_medium_xp_reward(self, sample_task):
        """Medium task gives 25 XP."""
        assert sample_task.xp_reward == 25

    def test_hard_xp_reward(self, hard_task):
        """Hard task gives 50 XP."""
        assert hard_task.xp_reward == 50

    def test_epic_xp_reward(self, epic_task):
        """Epic task gives 100 XP."""
        assert epic_task.xp_reward == 100


class TestTaskRarityWeights:
    """Tests for Task.get_pokemon_rarity_weights method."""

    def test_easy_task_weights(self, easy_task):
        """Easy task has high common weight."""
        weights = easy_task.get_pokemon_rarity_weights()
        assert weights["common"] == 0.70
        assert weights["legendary"] == 0.00

    def test_medium_task_weights(self, sample_task):
        """Medium task has balanced weights."""
        weights = sample_task.get_pokemon_rarity_weights()
        assert weights["common"] == 0.50
        assert weights["uncommon"] == 0.35
        assert weights["legendary"] == 0.00

    def test_hard_task_weights(self, hard_task):
        """Hard task has chance for legendaries."""
        weights = hard_task.get_pokemon_rarity_weights()
        assert weights["legendary"] == 0.01
        assert weights["epic"] == 0.09

    def test_epic_task_weights(self, epic_task):
        """Epic task has best legendary chances."""
        weights = epic_task.get_pokemon_rarity_weights()
        assert weights["legendary"] == 0.05
        assert weights["epic"] == 0.25
        assert weights["common"] == 0.10

    def test_weights_sum_to_one(self, easy_task, sample_task, hard_task, epic_task):
        """All weight dicts should sum to approximately 1.0."""
        for task in [easy_task, sample_task, hard_task, epic_task]:
            weights = task.get_pokemon_rarity_weights()
            total = sum(weights.values())
            assert abs(total - 1.0) < 0.01


class TestTaskTypeAffinity:
    """Tests for Task.get_type_affinity method."""

    def test_work_type_affinity(self):
        """Work tasks have steel/electric/normal affinity."""
        task = Task(title="Work", category=TaskCategory.WORK)
        types = task.get_type_affinity()
        assert "steel" in types
        assert "electric" in types
        assert "normal" in types

    def test_exercise_type_affinity(self):
        """Exercise tasks have fighting/fire/rock affinity."""
        task = Task(title="Exercise", category=TaskCategory.EXERCISE)
        types = task.get_type_affinity()
        assert "fighting" in types
        assert "fire" in types
        assert "rock" in types

    def test_learning_type_affinity(self):
        """Learning tasks have psychic/ghost/dark affinity."""
        task = Task(title="Learning", category=TaskCategory.LEARNING)
        types = task.get_type_affinity()
        assert "psychic" in types
        assert "ghost" in types
        assert "dark" in types

    def test_personal_type_affinity(self):
        """Personal tasks have normal/fairy/flying affinity."""
        task = Task(title="Personal", category=TaskCategory.PERSONAL)
        types = task.get_type_affinity()
        assert "normal" in types
        assert "fairy" in types
        assert "flying" in types

    def test_health_type_affinity(self):
        """Health tasks have grass/water/poison affinity."""
        task = Task(title="Health", category=TaskCategory.HEALTH)
        types = task.get_type_affinity()
        assert "grass" in types
        assert "water" in types
        assert "poison" in types

    def test_creative_type_affinity(self):
        """Creative tasks have fairy/dragon/ice affinity."""
        task = Task(title="Creative", category=TaskCategory.CREATIVE)
        types = task.get_type_affinity()
        assert "fairy" in types
        assert "dragon" in types
        assert "ice" in types

    def test_each_category_has_three_types(self):
        """Each category should have exactly 3 type affinities."""
        for category in TaskCategory:
            task = Task(title="Test", category=category)
            types = task.get_type_affinity()
            assert len(types) == 3


class TestTaskStatAffinity:
    """Tests for Task.stat_affinity property."""

    def test_stat_affinities(self):
        """Verify categories map to correct stats."""
        mappings = {
            TaskCategory.WORK: "spa",
            TaskCategory.EXERCISE: "atk",
            TaskCategory.LEARNING: "spd",
            TaskCategory.HEALTH: "hp",
            TaskCategory.PERSONAL: "def",
            TaskCategory.CREATIVE: "spe",
        }
        for category, expected_stat in mappings.items():
            task = Task(title="Test", category=category)
            assert task.stat_affinity == expected_stat


class TestTaskEVYield:
    """Tests for Task.ev_yield property."""

    def test_ev_yields(self):
        """Verify difficulties map to correct EV yields."""
        mappings = {
            TaskDifficulty.EASY: 1,
            TaskDifficulty.MEDIUM: 2,
            TaskDifficulty.HARD: 4,
            TaskDifficulty.EPIC: 8,
        }
        for difficulty, expected_yield in mappings.items():
            task = Task(title="Test", difficulty=difficulty)
            assert task.ev_yield == expected_yield
