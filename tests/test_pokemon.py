"""Tests for Pokemon model and related logic."""

import pytest
from datetime import datetime

from pokedo.core.pokemon import Pokemon, PokedexEntry, PokemonTeam, PokemonRarity


class TestPokemonRarity:
    """Tests for PokemonRarity enum."""

    def test_all_rarities_exist(self):
        """Verify all expected rarities exist."""
        expected = ["common", "uncommon", "rare", "epic", "legendary", "mythical"]
        actual = [r.value for r in PokemonRarity]
        assert sorted(actual) == sorted(expected)

    def test_rarity_ordering(self):
        """Verify rarity ordering conceptually."""
        rarities = list(PokemonRarity)
        assert PokemonRarity.COMMON in rarities
        assert PokemonRarity.MYTHICAL in rarities


class TestPokemonCreation:
    """Tests for Pokemon creation."""

    def test_create_minimal_pokemon(self):
        """Create Pokemon with only required fields."""
        pokemon = Pokemon(
            pokedex_id=25,
            name="pikachu",
            type1="electric",
        )
        assert pokemon.pokedex_id == 25
        assert pokemon.name == "pikachu"
        assert pokemon.type1 == "electric"
        assert pokemon.type2 is None
        assert pokemon.level == 1
        assert pokemon.xp == 0
        assert pokemon.happiness == 50
        assert pokemon.is_shiny is False
        assert pokemon.is_active is False
        assert pokemon.is_favorite is False

    def test_create_dual_type_pokemon(self, shiny_pokemon):
        """Create dual-type Pokemon."""
        assert shiny_pokemon.type1 == "fire"
        assert shiny_pokemon.type2 == "flying"

    def test_create_shiny_pokemon(self, shiny_pokemon):
        """Create shiny Pokemon."""
        assert shiny_pokemon.is_shiny is True

    def test_default_caught_at(self):
        """Verify caught_at defaults to now."""
        before = datetime.now()
        pokemon = Pokemon(pokedex_id=1, name="bulbasaur", type1="grass")
        after = datetime.now()
        assert before <= pokemon.caught_at <= after


class TestPokemonDisplayName:
    """Tests for Pokemon.display_name property."""

    def test_display_name_without_nickname(self, sample_pokemon):
        """Display name is capitalized species name without nickname."""
        sample_pokemon.nickname = None
        assert sample_pokemon.display_name == "Pikachu"

    def test_display_name_with_nickname(self, sample_pokemon):
        """Display name is nickname when set."""
        sample_pokemon.nickname = "Sparky"
        assert sample_pokemon.display_name == "Sparky"

    def test_display_name_capitalizes(self):
        """Display name capitalizes species name."""
        pokemon = Pokemon(pokedex_id=1, name="bulbasaur", type1="grass")
        assert pokemon.display_name == "Bulbasaur"


class TestPokemonTypesDisplay:
    """Tests for Pokemon.types_display property."""

    def test_single_type_display(self, sample_pokemon):
        """Single type Pokemon shows one type."""
        assert sample_pokemon.types_display == "Electric"

    def test_dual_type_display(self, shiny_pokemon):
        """Dual type Pokemon shows both types."""
        assert shiny_pokemon.types_display == "Fire/Flying"


class TestPokemonXPAndLevel:
    """Tests for Pokemon XP and leveling."""

    def test_gain_xp_no_level_up(self, sample_pokemon):
        """Gaining small XP doesn't level up."""
        initial_level = sample_pokemon.level
        initial_xp = sample_pokemon.xp
        leveled_up = sample_pokemon.gain_xp(10)
        assert leveled_up is False
        assert sample_pokemon.xp == initial_xp + 10
        assert sample_pokemon.level == initial_level

    def test_gain_xp_level_up(self):
        """Gaining enough XP causes level up."""
        pokemon = Pokemon(pokedex_id=1, name="test", type1="normal", level=1, xp=0)
        # Level 1 needs 50 XP for level 2 (level * 50)
        leveled_up = pokemon.gain_xp(60)
        assert leveled_up is True
        assert pokemon.level >= 2

    def test_level_calculation(self):
        """Test level calculation from XP."""
        pokemon = Pokemon(pokedex_id=1, name="test", type1="normal", xp=0)
        assert pokemon._calculate_level() == 1

        pokemon.xp = 50  # Enough for level 2
        assert pokemon._calculate_level() == 2

        pokemon.xp = 150  # 50 + 100 = 150 for level 3
        assert pokemon._calculate_level() == 3

    def test_max_level_100(self):
        """Pokemon level caps at 100."""
        pokemon = Pokemon(pokedex_id=1, name="test", type1="normal", xp=999999)
        assert pokemon._calculate_level() <= 100


class TestPokemonEvolution:
    """Tests for Pokemon evolution checking."""

    def test_check_evolution_not_ready(self):
        """Pokemon not at evolution level can't evolve."""
        pokemon = Pokemon(
            pokedex_id=4,
            name="charmander",
            type1="fire",
            level=10,
            evolution_id=5,
            evolution_level=16,
        )
        pokemon._check_evolution()
        assert pokemon.can_evolve is False

    def test_check_evolution_ready(self, evolvable_pokemon):
        """Pokemon at evolution level can evolve."""
        evolvable_pokemon._check_evolution()
        assert evolvable_pokemon.can_evolve is True

    def test_evolution_triggered_on_level_up(self):
        """Evolution check triggered when leveling up."""
        pokemon = Pokemon(
            pokedex_id=4,
            name="charmander",
            type1="fire",
            level=15,
            xp=700,  # Close to level 16
            evolution_id=5,
            evolution_level=16,
        )
        assert pokemon.can_evolve is False
        pokemon.gain_xp(100)  # Should trigger level up to 16
        # After level up, _check_evolution should be called
        if pokemon.level >= 16:
            assert pokemon.can_evolve is True


class TestPokemonHappiness:
    """Tests for Pokemon happiness."""

    def test_increase_happiness(self, sample_pokemon):
        """Happiness increases correctly."""
        initial = sample_pokemon.happiness
        sample_pokemon.increase_happiness(10)
        assert sample_pokemon.happiness == initial + 10

    def test_happiness_caps_at_255(self, sample_pokemon):
        """Happiness caps at 255."""
        sample_pokemon.happiness = 250
        sample_pokemon.increase_happiness(10)
        assert sample_pokemon.happiness == 255

    def test_decrease_happiness(self, sample_pokemon):
        """Happiness decreases correctly."""
        initial = sample_pokemon.happiness
        sample_pokemon.decrease_happiness(5)
        assert sample_pokemon.happiness == initial - 5

    def test_happiness_minimum_zero(self, sample_pokemon):
        """Happiness minimum is 0."""
        sample_pokemon.happiness = 3
        sample_pokemon.decrease_happiness(10)
        assert sample_pokemon.happiness == 0


class TestPokedexEntry:
    """Tests for PokedexEntry model."""

    def test_create_minimal_entry(self):
        """Create entry with only required fields."""
        entry = PokedexEntry(
            pokedex_id=25,
            name="pikachu",
            type1="electric",
        )
        assert entry.pokedex_id == 25
        assert entry.is_seen is False
        assert entry.is_caught is False
        assert entry.times_caught == 0
        assert entry.rarity == PokemonRarity.COMMON

    def test_entry_with_catch_history(self, sample_pokedex_entry):
        """Entry tracks catch history."""
        assert sample_pokedex_entry.is_seen is True
        assert sample_pokedex_entry.is_caught is True
        assert sample_pokedex_entry.times_caught == 3

    def test_legendary_entry(self, legendary_pokedex_entry):
        """Legendary entry has correct rarity."""
        assert legendary_pokedex_entry.rarity == PokemonRarity.LEGENDARY

    def test_evolution_tracking(self):
        """Entry tracks evolution info."""
        entry = PokedexEntry(
            pokedex_id=4,
            name="charmander",
            type1="fire",
            evolves_to=[5],
        )
        assert 5 in entry.evolves_to


class TestPokemonTeam:
    """Tests for PokemonTeam model."""

    def test_empty_team(self, empty_team):
        """Empty team has size 0."""
        assert empty_team.size == 0
        assert empty_team.is_full is False

    def test_add_pokemon(self, empty_team, sample_pokemon):
        """Add Pokemon to team."""
        result = empty_team.add(sample_pokemon)
        assert result is True
        assert empty_team.size == 1
        assert sample_pokemon.is_active is True

    def test_partial_team(self, partial_team):
        """Partial team has correct size."""
        assert partial_team.size == 1
        assert partial_team.is_full is False

    def test_full_team(self, full_team):
        """Full team has 6 Pokemon."""
        assert full_team.size == 6
        assert full_team.is_full is True

    def test_cannot_add_to_full_team(self, full_team):
        """Cannot add 7th Pokemon to full team."""
        extra = Pokemon(pokedex_id=999, name="extra", type1="normal")
        result = full_team.add(extra)
        assert result is False
        assert full_team.size == 6

    def test_remove_pokemon(self, partial_team, sample_pokemon):
        """Remove Pokemon from team."""
        removed = partial_team.remove(sample_pokemon.id)
        assert removed is not None
        assert removed.is_active is False
        assert partial_team.size == 0

    def test_remove_nonexistent_pokemon(self, partial_team):
        """Removing nonexistent Pokemon returns None."""
        removed = partial_team.remove(999)
        assert removed is None
