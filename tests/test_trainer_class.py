"""Tests for Trainer Class system."""

from pokedo.core.trainer import Trainer, TrainerClass


class TestTrainerClass:
    """Tests for TrainerClass Enum and Model integration."""

    def test_enum_values(self):
        """Verify expected trainer classes exist."""
        assert TrainerClass.ACE_TRAINER == "ace_trainer"
        assert TrainerClass.HIKER == "hiker"
        assert TrainerClass.SCIENTIST == "scientist"
        assert TrainerClass.BLACK_BELT == "black_belt"
        assert TrainerClass.PSYCHIC == "psychic"
        assert TrainerClass.SWIMMER == "swimmer"
        assert TrainerClass.BREEDER == "breeder"
        assert TrainerClass.COORDINATOR == "coordinator"

    def test_default_trainer_class(self):
        """Trainer defaults to Ace Trainer."""
        trainer = Trainer(name="New Trainer")
        assert trainer.trainer_class == TrainerClass.ACE_TRAINER

    def test_set_trainer_class(self):
        """Trainer class can be set."""
        trainer = Trainer(name="Hiker Trainer", trainer_class=TrainerClass.HIKER)
        assert trainer.trainer_class == TrainerClass.HIKER

    def test_change_trainer_class(self):
        """Trainer class can be changed."""
        trainer = Trainer(name="Changer")
        trainer.trainer_class = TrainerClass.SCIENTIST
        assert trainer.trainer_class == TrainerClass.SCIENTIST
