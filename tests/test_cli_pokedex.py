"""CLI regression tests for the Pokedex commands."""

from pokedo.cli.app import app
from pokedo.core.pokemon import PokedexEntry, PokemonRarity


def _make_entry(**overrides) -> PokedexEntry:
    base = dict(
        name="testmon",
        type1="normal",
        rarity=PokemonRarity.COMMON,
    )
    base.update(overrides)
    return PokedexEntry(**base)


def test_pokemon_pokedex_command_filters_caught(cli_runner, isolated_db):
    """`pokedo pokemon pokedex --caught` should only list caught entries."""
    isolated_db.save_pokedex_entry(
        _make_entry(
            pokedex_id=25,
            name="bulbasaur",
            is_seen=True,
            is_caught=False,
        )
    )
    isolated_db.save_pokedex_entry(
        _make_entry(
            pokedex_id=93,
            name="haunter",
            type1="ghost",
            is_seen=True,
            is_caught=True,
            times_caught=1,
        )
    )

    result = cli_runner.invoke(app, ["pokemon", "pokedex", "--caught"])

    assert result.exit_code == 0
    assert "Haunter" in result.output
    assert "Bulbasaur" not in result.output


def test_root_pokedex_shortcut_auto_focuses_seen_entries(cli_runner, isolated_db):
    """Top-level `pokedo pokedex` should jump to the first seen/caught entry."""
    for pokedex_id in range(1, 51):
        isolated_db.save_pokedex_entry(
            _make_entry(
                pokedex_id=pokedex_id,
                name=f"mon{pokedex_id}",
                is_seen=False,
                is_caught=False,
            )
        )

    isolated_db.save_pokedex_entry(
        _make_entry(
            pokedex_id=150,
            name="haunter",
            type1="ghost",
            is_seen=True,
            is_caught=True,
            times_caught=1,
        )
    )

    result = cli_runner.invoke(app, ["pokedex"])

    assert result.exit_code == 0
    assert "Haunter" in result.output
    assert "(Page 3/" in result.output
