"""Configuration management for PokeDo."""

from pathlib import Path

from pydantic import BaseModel


class Config(BaseModel):
    """Application configuration."""

    # Paths
    data_dir: Path = Path.home() / ".pokedo"
    db_path: Path = Path.home() / ".pokedo" / "pokedo.db"
    cache_dir: Path = Path.home() / ".pokedo" / "cache"
    sprites_dir: Path = Path.home() / ".pokedo" / "cache" / "sprites"

    # PokeAPI settings
    pokeapi_base_url: str = "https://pokeapi.co/api/v2"
    max_pokemon_id: int = 1025  # All Pokemon through Gen 9

    # Generation ranges for filtering
    generation_ranges: dict = {
        1: (1, 151),  # Kanto
        2: (152, 251),  # Johto
        3: (252, 386),  # Hoenn
        4: (387, 493),  # Sinnoh
        5: (494, 649),  # Unova
        6: (650, 721),  # Kalos
        7: (722, 809),  # Alola
        8: (810, 905),  # Galar
        9: (906, 1025),  # Paldea
    }

    # Game settings
    base_catch_rate: float = 0.6
    shiny_rate: float = 0.01
    streak_shiny_bonus: float = 0.005  # Per day of streak
    max_team_size: int = 6

    # XP settings
    task_xp_easy: int = 10
    task_xp_medium: int = 25
    task_xp_hard: int = 50
    task_xp_epic: int = 100

    # Streak rewards
    streak_milestones: dict = {
        3: "pokeball_upgrade",
        7: "evolution_stone",
        14: "rare_encounter",
        30: "legendary_encounter",
        100: "mythical_encounter",
    }

    def ensure_dirs(self) -> None:
        """Create necessary directories if they don't exist."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.sprites_dir.mkdir(parents=True, exist_ok=True)


# Global config instance
config = Config()
