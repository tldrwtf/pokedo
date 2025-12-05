"""CLI tests for stats/profile commands."""

from pokedo.cli.app import app
from pokedo.core.trainer import TrainerClass


def test_set_trainer_class(cli_runner, isolated_db):
    """Test setting trainer class via CLI."""
    result = cli_runner.invoke(app, ["stats", "set-class", "hiker"])
    assert result.exit_code == 0
    assert "Trainer class updated to: Hiker!" in result.output

    trainer = isolated_db.get_or_create_trainer()
    assert trainer.trainer_class == TrainerClass.HIKER


def test_set_invalid_class(cli_runner, isolated_db):
    """Test setting invalid trainer class."""
    result = cli_runner.invoke(app, ["stats", "set-class", "invalid_class"])
    assert result.exit_code != 0
    assert "Invalid value" in result.output
