"""CLI tests for profile commands."""

from pokedo.cli.app import app


def test_profile_set_default_by_name(cli_runner, isolated_db):
    """Set default profile by trainer name."""
    trainer_a = isolated_db.create_trainer("Alpha")
    trainer_b = isolated_db.create_trainer("Beta")

    result = cli_runner.invoke(app, ["profile", "set-default", "Beta"])
    assert result.exit_code == 0
    assert "Default profile set to: Beta" in result.output
    assert isolated_db.get_default_trainer_id() == trainer_b.id

    result = cli_runner.invoke(app, ["profile", "set-default", "Alpha"])
    assert result.exit_code == 0
    assert isolated_db.get_default_trainer_id() == trainer_a.id


def test_profile_set_default_by_id(cli_runner, isolated_db):
    """Set default profile by trainer ID."""
    trainer = isolated_db.create_trainer("Gamma")
    result = cli_runner.invoke(app, ["profile", "set-default", str(trainer.id)])
    assert result.exit_code == 0
    assert isolated_db.get_default_trainer_id() == trainer.id
