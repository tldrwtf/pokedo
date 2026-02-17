"""Tests for the Pokemon sprite CLI command and identifier resolution."""

import importlib
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image
from typer.testing import CliRunner

from pokedo.cli.app import app
from pokedo.cli.commands.pokemon import _resolve_pokemon_identifier
from pokedo.core.pokemon import PokedexEntry, PokemonRarity


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_sprite_file(directory: Path, pokemon_id: int, shiny: bool = False) -> Path:
    """Create a tiny dummy sprite PNG in the given directory."""
    directory.mkdir(parents=True, exist_ok=True)
    tag = "shiny" if shiny else "normal"
    path = directory / f"{pokemon_id}_{tag}.png"
    img = Image.new("RGBA", (4, 4), (255, 0, 0, 255))
    img.save(path, format="PNG")
    return path


def _make_entry(**overrides) -> PokedexEntry:
    base = dict(
        name="pikachu",
        type1="electric",
        rarity=PokemonRarity.COMMON,
        pokedex_id=25,
    )
    base.update(overrides)
    return PokedexEntry(**base)


# ---------------------------------------------------------------------------
# _resolve_pokemon_identifier
# ---------------------------------------------------------------------------

class TestResolvePokemonIdentifier:
    """Tests for name/ID resolution logic."""

    def test_numeric_id_returns_int(self, isolated_db):
        """A pure numeric string returns the integer directly."""
        result = _resolve_pokemon_identifier("25")
        assert result == 25

    def test_numeric_id_zero(self, isolated_db):
        """Edge case: '0' is still numeric."""
        result = _resolve_pokemon_identifier("0")
        assert result == 0

    def test_name_found_in_local_pokedex(self, isolated_db):
        """A name matching a local Pokedex entry returns its ID."""
        isolated_db.save_pokedex_entry(_make_entry(pokedex_id=25, name="pikachu"))
        result = _resolve_pokemon_identifier("pikachu")
        assert result == 25

    def test_name_case_insensitive(self, isolated_db):
        """Name lookup should be case-insensitive."""
        isolated_db.save_pokedex_entry(_make_entry(pokedex_id=25, name="pikachu"))
        assert _resolve_pokemon_identifier("Pikachu") == 25
        assert _resolve_pokemon_identifier("PIKACHU") == 25

    def test_name_not_found_locally_falls_back_to_api(self, isolated_db):
        """When name is not in local Pokedex, fall back to PokeAPI."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": 133}

        with patch("httpx.get", return_value=mock_response):
            result = _resolve_pokemon_identifier("eevee")
        assert result == 133

    def test_name_not_found_anywhere_returns_none(self, isolated_db):
        """When both local and API lookup fail, return None."""
        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch("httpx.get", return_value=mock_response):
            result = _resolve_pokemon_identifier("fakemon")
        assert result is None

    def test_api_network_error_returns_none(self, isolated_db):
        """Network errors during API fallback should not crash."""
        import httpx

        with patch("httpx.get", side_effect=httpx.ConnectError("offline")):
            result = _resolve_pokemon_identifier("eevee")
        assert result is None

    def test_whitespace_stripped(self, isolated_db):
        """Leading/trailing whitespace in names is stripped."""
        isolated_db.save_pokedex_entry(_make_entry(pokedex_id=25, name="pikachu"))
        assert _resolve_pokemon_identifier("  pikachu  ") == 25


# ---------------------------------------------------------------------------
# CLI: pokedo pokemon sprite
# ---------------------------------------------------------------------------

class TestSpriteCommand:
    """Integration tests for the CLI sprite command."""

    def test_sprite_by_id(self, cli_runner, isolated_db, tmp_path, monkeypatch):
        """pokedo pokemon sprite 25 should render the sprite."""
        from pokedo.utils import config as config_module

        sprites_dir = tmp_path / "sprites"
        monkeypatch.setattr(config_module.config, "sprites_dir", sprites_dir)
        sprite_path = _make_sprite_file(sprites_dir, 25)

        isolated_db.save_pokedex_entry(_make_entry(pokedex_id=25, name="pikachu"))

        # Mock download_sprite to return the pre-made file
        async def mock_download(pid, is_shiny=False):
            return sprite_path

        with patch("pokedo.cli.commands.pokemon.pokeapi") as mock_api:
            mock_api.download_sprite = mock_download
            result = cli_runner.invoke(app, ["pokemon", "sprite", "25"])

        assert result.exit_code == 0
        assert "Pikachu" in result.output

    def test_sprite_by_name(self, cli_runner, isolated_db, tmp_path, monkeypatch):
        """pokedo pokemon sprite pikachu should resolve name and render."""
        from pokedo.utils import config as config_module

        sprites_dir = tmp_path / "sprites"
        monkeypatch.setattr(config_module.config, "sprites_dir", sprites_dir)
        sprite_path = _make_sprite_file(sprites_dir, 25)

        isolated_db.save_pokedex_entry(_make_entry(pokedex_id=25, name="pikachu"))

        async def mock_download(pid, is_shiny=False):
            return sprite_path

        with patch("pokedo.cli.commands.pokemon.pokeapi") as mock_api:
            mock_api.download_sprite = mock_download
            result = cli_runner.invoke(app, ["pokemon", "sprite", "pikachu"])

        assert result.exit_code == 0
        assert "Pikachu" in result.output

    def test_sprite_shiny_flag(self, cli_runner, isolated_db, tmp_path, monkeypatch):
        """--shiny flag should pass through and show shiny label."""
        from pokedo.utils import config as config_module

        sprites_dir = tmp_path / "sprites"
        monkeypatch.setattr(config_module.config, "sprites_dir", sprites_dir)
        sprite_path = _make_sprite_file(sprites_dir, 25, shiny=True)

        isolated_db.save_pokedex_entry(_make_entry(pokedex_id=25, name="pikachu"))

        async def mock_download(pid, is_shiny=False):
            return sprite_path

        with patch("pokedo.cli.commands.pokemon.pokeapi") as mock_api:
            mock_api.download_sprite = mock_download
            result = cli_runner.invoke(app, ["pokemon", "sprite", "25", "--shiny"])

        assert result.exit_code == 0
        assert "Shiny" in result.output

    def test_sprite_not_found_pokemon(self, cli_runner, isolated_db):
        """An unknown Pokemon name should show an error."""
        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch("httpx.get", return_value=mock_response):
            result = cli_runner.invoke(app, ["pokemon", "sprite", "fakemon"])

        assert result.exit_code == 1
        assert "Could not find" in result.output

    def test_sprite_download_failure(self, cli_runner, isolated_db, tmp_path, monkeypatch):
        """When sprite download fails, show appropriate error."""
        isolated_db.save_pokedex_entry(_make_entry(pokedex_id=25, name="pikachu"))

        async def mock_download(pid, is_shiny=False):
            return None

        with patch("pokedo.cli.commands.pokemon.pokeapi") as mock_api:
            mock_api.download_sprite = mock_download
            result = cli_runner.invoke(app, ["pokemon", "sprite", "25"])

        assert result.exit_code == 1
        assert "Could not download" in result.output

    def test_sprite_shows_type_info(self, cli_runner, isolated_db, tmp_path, monkeypatch):
        """Sprite output should include type information as subtitle."""
        from pokedo.utils import config as config_module

        sprites_dir = tmp_path / "sprites"
        monkeypatch.setattr(config_module.config, "sprites_dir", sprites_dir)
        sprite_path = _make_sprite_file(sprites_dir, 6)

        isolated_db.save_pokedex_entry(
            _make_entry(pokedex_id=6, name="charizard", type1="fire", type2="flying")
        )

        async def mock_download(pid, is_shiny=False):
            return sprite_path

        with patch("pokedo.cli.commands.pokemon.pokeapi") as mock_api:
            mock_api.download_sprite = mock_download
            result = cli_runner.invoke(app, ["pokemon", "sprite", "6"])

        assert result.exit_code == 0
        assert "Fire" in result.output
        assert "Flying" in result.output


# ---------------------------------------------------------------------------
# CLI: pokedo sprite (top-level shortcut)
# ---------------------------------------------------------------------------

class TestSpriteShortcut:
    """Tests for the top-level sprite shortcut."""

    def test_shortcut_delegates_to_pokemon_sprite(self, cli_runner, isolated_db, tmp_path, monkeypatch):
        """pokedo sprite <id> should work the same as pokedo pokemon sprite <id>."""
        from pokedo.utils import config as config_module

        sprites_dir = tmp_path / "sprites"
        monkeypatch.setattr(config_module.config, "sprites_dir", sprites_dir)
        sprite_path = _make_sprite_file(sprites_dir, 25)

        isolated_db.save_pokedex_entry(_make_entry(pokedex_id=25, name="pikachu"))

        async def mock_download(pid, is_shiny=False):
            return sprite_path

        with patch("pokedo.cli.commands.pokemon.pokeapi") as mock_api:
            mock_api.download_sprite = mock_download
            result = cli_runner.invoke(app, ["sprite", "25"])

        assert result.exit_code == 0
        assert "Pikachu" in result.output

    def test_shortcut_help(self, cli_runner):
        """pokedo sprite --help should show usage info."""
        result = cli_runner.invoke(app, ["sprite", "--help"])
        assert result.exit_code == 0
        assert "IDENTIFIER" in result.output
