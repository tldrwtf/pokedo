# Contributing to PokeDo

## Table of Contents

- [Development Setup](#development-setup)
- [Project Structure](#project-structure)
- [Code Style](#code-style)
- [Testing](#testing)
- [Adding New Features](#adding-new-features)
- [Pull Request Process](#pull-request-process)

---

## Development Setup

### Prerequisites

- Python 3.10 or higher
- pip (Python package manager)
- Git

### Installation

1. Clone the repository:
```bash
git clone https://github.com/tldrwtf/pokedo.git
cd pokedo
```

2. Create a virtual environment:
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

3. Install development dependencies:
```bash
pip install -e ".[dev]"
```

4. Initialize the application (for testing):
```bash
pokedo init --name "Developer" --quick
```

### Development Commands

```bash
# Run the CLI
pokedo

# Run with Python module
python -m pokedo

# Run tests
pytest

# Run tests with coverage
pytest --cov=pokedo

# Run specific test file
pytest tests/test_tasks.py

# Run with verbose output
pytest -v
```

---

## Project Structure

```
pokedo/
├── cli/                  # Command-line interface
│   ├── app.py            # Main Typer application
│   ├── commands/         # CLI command modules
│   │   ├── tasks.py      # Task commands
│   │   ├── pokemon.py    # Pokemon commands
│   │   ├── wellbeing.py  # Wellbeing commands
│   │   └── stats.py      # Stats commands
│   └── ui/               # UI components
│       ├── displays.py   # Display helpers
│       └── menus.py      # Interactive menus
├── core/                 # Business logic
│   ├── task.py           # Task model
│   ├── trainer.py        # Trainer model
│   ├── pokemon.py        # Pokemon model
│   ├── rewards.py        # Reward system
│   └── wellbeing.py      # Wellbeing models
├── data/                 # Data layer
│   ├── database.py       # Database operations
│   └── pokeapi.py        # PokeAPI client
└── utils/                # Utilities
    ├── config.py         # Configuration
    └── helpers.py        # Helper functions
```

### Layer Responsibilities

| Layer | Responsibility |
|-------|----------------|
| `cli/` | User interaction, input validation, output formatting |
| `core/` | Business logic, game mechanics, domain models |
| `data/` | Database operations, external API calls |
| `utils/` | Configuration, shared utilities |

### Import Guidelines

- CLI can import from core, data, utils
- Core can import from utils only
- Data can import from core, utils
- Utils should have no internal imports

---

## Code Style

### General Guidelines

- Follow PEP 8 style guide
- Use type hints for function parameters and return values
- Write docstrings for public functions and classes
- Keep functions focused and under 50 lines when possible
- Use descriptive variable names

### Type Hints

```python
# Good
def calculate_xp(difficulty: TaskDifficulty, streak: int) -> int:
    """Calculate XP reward for completing a task."""
    base_xp = TASK_XP[difficulty]
    bonus = min(streak * 0.1, 0.5)
    return int(base_xp * (1 + bonus))

# Avoid
def calculate_xp(difficulty, streak):
    base_xp = TASK_XP[difficulty]
    bonus = min(streak * 0.1, 0.5)
    return int(base_xp * (1 + bonus))
```

### Pydantic Models

```python
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum

class TaskStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    ARCHIVED = "archived"

class Task(BaseModel):
    """Represents a task in the system."""

    id: int | None = None
    title: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.now)

    class Config:
        use_enum_values = True
```

### CLI Commands

```python
import typer
from rich.console import Console

app = typer.Typer()
console = Console()

@app.command()
def example(
    name: str = typer.Argument(..., help="The name to greet"),
    count: int = typer.Option(1, "--count", "-c", help="Number of greetings"),
) -> None:
    """Example command that greets a user."""
    for _ in range(count):
        console.print(f"Hello, [bold]{name}[/bold]!")
```

### Error Handling

```python
from rich.console import Console

console = Console()

def safe_operation() -> None:
    try:
        risky_function()
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error:[/red] {e}")
        raise typer.Exit(1)
```

---

## Testing

### Test Structure

```
tests/
├── __init__.py
├── conftest.py           # Shared fixtures
├── test_tasks.py         # Task tests
├── test_pokemon.py       # Pokemon tests
├── test_trainer.py       # Trainer tests
├── test_wellbeing.py     # Wellbeing tests
└── test_database.py      # Database tests
```

### Writing Tests

```python
import pytest
from pokedo.core.task import Task, TaskDifficulty, TaskCategory

class TestTask:
    """Tests for the Task model."""

    def test_create_task(self):
        """Test creating a basic task."""
        task = Task(
            title="Test task",
            category=TaskCategory.WORK,
            difficulty=TaskDifficulty.MEDIUM
        )
        assert task.title == "Test task"
        assert task.category == TaskCategory.WORK
        assert not task.is_completed

    def test_xp_reward(self):
        """Test XP reward calculation."""
        task = Task(
            title="Hard task",
            difficulty=TaskDifficulty.HARD
        )
        assert task.xp_reward == 50

    @pytest.mark.parametrize("difficulty,expected_xp", [
        (TaskDifficulty.EASY, 10),
        (TaskDifficulty.MEDIUM, 25),
        (TaskDifficulty.HARD, 50),
        (TaskDifficulty.EPIC, 100),
    ])
    def test_difficulty_xp_values(self, difficulty, expected_xp):
        """Test XP values for each difficulty level."""
        task = Task(title="Test", difficulty=difficulty)
        assert task.xp_reward == expected_xp
```

### Fixtures

```python
# conftest.py
import pytest
from pathlib import Path
import tempfile

@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        yield db_path

@pytest.fixture
def sample_task():
    """Create a sample task for testing."""
    return Task(
        id=1,
        title="Sample Task",
        category=TaskCategory.WORK,
        difficulty=TaskDifficulty.MEDIUM
    )
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=pokedo --cov-report=html

# Run specific test
pytest tests/test_tasks.py::TestTask::test_create_task

# Run tests matching pattern
pytest -k "xp"

# Run with verbose output
pytest -v
```

---

## Adding New Features

### Adding a New CLI Command

1. Create or update the command module in `cli/commands/`:

```python
# cli/commands/example.py
import typer
from rich.console import Console

app = typer.Typer(help="Example commands")
console = Console()

@app.command()
def new_command(
    arg: str = typer.Argument(..., help="Description"),
    option: bool = typer.Option(False, "--flag", "-f", help="Description"),
) -> None:
    """Command description."""
    console.print(f"Running with {arg}")
```

2. Register in `cli/app.py`:

```python
from pokedo.cli.commands import example

app.add_typer(example.app, name="example")
```

### Adding a New Model

1. Create the model in `core/`:

```python
# core/newmodel.py
from pydantic import BaseModel
from datetime import datetime

class NewModel(BaseModel):
    id: int | None = None
    name: str
    created_at: datetime = Field(default_factory=datetime.now)
```

2. Add database operations in `data/database.py`:

```python
def create_new_model_table(self) -> None:
    self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS new_models (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

def insert_new_model(self, model: NewModel) -> int:
    self.cursor.execute(
        "INSERT INTO new_models (name) VALUES (?)",
        (model.name,)
    )
    self.conn.commit()
    return self.cursor.lastrowid
```

### Adding a New Wellbeing Tracker

1. Add the model in `core/wellbeing.py`:

```python
class NewWellbeingEntry(BaseModel):
    id: int | None = None
    date: date = Field(default_factory=date.today)
    value: int
    note: str | None = None
```

2. Add database table in `data/database.py`

3. Add CLI command in `cli/commands/wellbeing.py`:

```python
@app.command()
def new_tracker(
    value: int = typer.Argument(..., help="Value to track"),
    note: str = typer.Option(None, "--note", "-n"),
) -> None:
    """Track new wellbeing metric."""
    entry = NewWellbeingEntry(value=value, note=note)
    db.insert_new_wellbeing_entry(entry)
    console.print("[green]Tracked successfully![/green]")
```

### Adding New Pokemon Mechanics

1. Update `core/pokemon.py` or `core/rewards.py`
2. Add any new database fields
3. Update CLI commands as needed
4. Add tests for new mechanics

---

## Pull Request Process

### Before Submitting

1. **Create an issue** (if one doesn't exist) describing the feature or bug
2. **Fork the repository** and create a feature branch
3. **Write tests** for new functionality
4. **Update documentation** if needed
5. **Run the test suite** and ensure all tests pass

### Branch Naming

```
feature/add-trading-system
bugfix/fix-evolution-crash
docs/update-readme
refactor/simplify-catch-rate
```

### Commit Messages

Follow conventional commit format:

```
feat: add Pokemon trading system
fix: resolve crash when evolving shiny Pokemon
docs: update installation instructions
refactor: simplify catch rate calculation
test: add tests for wellbeing tracker
```

### PR Description Template

```markdown
## Description
Brief description of changes.

## Type of Change
[ ] Bug fix
[ ] New feature
[ ] Documentation update
[ ] Refactoring

## Testing
Describe how you tested the changes.

## Checklist
[ ] Tests pass locally
[ ] Code follows style guidelines
[ ] Documentation updated
[ ] No breaking changes (or documented if necessary)
```

### Review Process

1. Submit PR with clear description
2. Address any review feedback
3. Ensure CI passes
4. Maintainer will merge when approved

---

## Getting Help

- **Issues:** Report bugs or request features via GitHub Issues
- **Discussions:** Ask questions in GitHub Discussions
- **Documentation:** See `docs/` folder for detailed docs

---

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
