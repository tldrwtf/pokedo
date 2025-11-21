"""Persistence tests for the SQLite database layer."""

from datetime import date

from pokedo.core.pokemon import PokedexEntry, PokemonRarity


def test_save_and_load_pokedex_entry(isolated_db):
    """Saving a Pokedex entry should allow accurate retrieval."""
    entry = PokedexEntry(
        pokedex_id=133,
        name="eevee",
        type1="normal",
        type2=None,
        rarity=PokemonRarity.RARE,
        is_seen=True,
        is_caught=True,
        times_caught=2,
        shiny_caught=False,
        evolves_from=None,
        evolves_to=[134, 135],
    )

    isolated_db.save_pokedex_entry(entry)

    loaded = isolated_db.get_pokedex_entry(133)

    assert loaded is not None
    assert loaded.pokedex_id == entry.pokedex_id
    assert loaded.name == "eevee"
    assert loaded.is_caught is True
    assert loaded.times_caught == 2
    assert loaded.evolves_to == [134, 135]


def test_trainer_stats_roundtrip(isolated_db):
    """Trainer progress mutations should persist through save/load cycle."""
    trainer = isolated_db.get_or_create_trainer("Ash")
    trainer.total_xp = 420
    trainer.tasks_completed = 7
    trainer.pokemon_caught = 3
    trainer.pokedex_seen = 5
    trainer.pokedex_caught = 2
    trainer.daily_streak.current_count = 4
    trainer.daily_streak.best_count = 6
    trainer.daily_streak.last_activity_date = date.today()
    trainer.inventory = {"pokeball": 5, "great_ball": 1}

    isolated_db.save_trainer(trainer)

    reloaded = isolated_db.get_or_create_trainer("irrelevant")

    assert reloaded.total_xp == 420
    assert reloaded.tasks_completed == 7
    assert reloaded.pokemon_caught == 3
    assert reloaded.pokedex_seen == 5
    assert reloaded.pokedex_caught == 2
    assert reloaded.daily_streak.current_count == 4
    assert reloaded.daily_streak.best_count == 6
    assert reloaded.inventory["pokeball"] == 5
    assert reloaded.inventory["great_ball"] == 1
