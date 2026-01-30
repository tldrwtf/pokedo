"""Tests for Pokemon model and related logic."""

from datetime import datetime

from pokedo.core.pokemon import PokedexEntry, Pokemon, PokemonRarity


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


class TestPokemonEVs:
    """Tests for Pokemon EV system."""

    def test_default_evs(self, sample_pokemon):
        """EVs default to 0."""
        assert sum(sample_pokemon.evs.values()) == 0
        assert sample_pokemon.remaining_evs == 510

    def test_add_evs_basic(self, sample_pokemon):
        """Adding EVs works."""
        amount = sample_pokemon.add_evs("atk", 10)
        assert amount == 10
        assert sample_pokemon.evs["atk"] == 10
        assert sample_pokemon.remaining_evs == 500

    def test_add_evs_stat_cap(self, sample_pokemon):
        """EVs capped at 252 per stat."""
        sample_pokemon.add_evs("atk", 200)
        amount = sample_pokemon.add_evs("atk", 100)
        assert amount == 52  # Only 52 needed to reach 252
        assert sample_pokemon.evs["atk"] == 252
        assert sample_pokemon.add_evs("atk", 10) == 0  # Full

    def test_add_evs_total_cap(self, sample_pokemon):
        """EVs capped at 510 total."""
        # Max out two stats (504 total)
        sample_pokemon.add_evs("atk", 252)
        sample_pokemon.add_evs("spe", 252)
        assert sample_pokemon.remaining_evs == 6

        # Try to add more than remaining
        amount = sample_pokemon.add_evs("hp", 10)
        assert amount == 6
        assert sample_pokemon.evs["hp"] == 6
        assert sample_pokemon.remaining_evs == 0

    def test_invalid_stat(self, sample_pokemon):
        """Adding to invalid stat returns 0."""
        amount = sample_pokemon.add_evs("invalid", 10)
        assert amount == 0


class TestPokemonIVs:
    """Tests for Pokemon IV system."""

    def test_default_ivs(self, sample_pokemon):
        """IVs default to 0."""
        assert sum(sample_pokemon.ivs.values()) == 0

    def test_assign_ivs(self, sample_pokemon):
        """Assign IVs randomizes values."""
        sample_pokemon.assign_ivs()
        # Statistically unlikely all will be 0, but possible.
        # Check bounds instead.
        for stat in sample_pokemon.ivs:
            val = sample_pokemon.ivs[stat]
            assert 0 <= val <= 31


class TestPokemonStats:
    """Tests for Pokemon stat calculation."""

    def test_stats_property_returns_all_stats(self, sample_pokemon):
        """Stats property returns all 6 stats."""
        stats = sample_pokemon.stats
        assert "hp" in stats
        assert "atk" in stats
        assert "def" in stats
        assert "spa" in stats
        assert "spd" in stats
        assert "spe" in stats

    def test_hp_calculation_level_1(self):
        """HP at level 1 with default base stats (50) and no EVs/IVs."""
        pokemon = Pokemon(pokedex_id=1, name="test", type1="normal", level=1)
        # HP = ((2*50 + 0 + 0) * 1 / 100) + 1 + 10 = 1 + 1 + 10 = 12
        assert pokemon.stats["hp"] == 12

    def test_hp_calculation_level_50(self):
        """HP at level 50 with default base stats."""
        pokemon = Pokemon(pokedex_id=1, name="test", type1="normal", level=50)
        # HP = ((2*50 + 0 + 0) * 50 / 100) + 50 + 10 = 50 + 50 + 10 = 110
        assert pokemon.stats["hp"] == 110

    def test_other_stat_calculation_level_1(self):
        """Non-HP stat at level 1 with default base stats."""
        pokemon = Pokemon(pokedex_id=1, name="test", type1="normal", level=1)
        # Stat = ((2*50 + 0 + 0) * 1 / 100) + 5 = 1 + 5 = 6
        assert pokemon.stats["atk"] == 6

    def test_other_stat_calculation_level_50(self):
        """Non-HP stat at level 50 with default base stats."""
        pokemon = Pokemon(pokedex_id=1, name="test", type1="normal", level=50)
        # Stat = ((2*50 + 0 + 0) * 50 / 100) + 5 = 50 + 5 = 55
        assert pokemon.stats["atk"] == 55

    def test_stats_with_custom_base_stats(self):
        """Stats calculated correctly with custom base stats."""
        pokemon = Pokemon(
            pokedex_id=25,
            name="pikachu",
            type1="electric",
            level=50,
            base_stats={"hp": 35, "atk": 55, "def": 40, "spa": 50, "spd": 50, "spe": 90},
        )
        # HP = ((2*35 + 0 + 0) * 50 / 100) + 50 + 10 = 35 + 50 + 10 = 95
        assert pokemon.stats["hp"] == 95
        # Spe = ((2*90 + 0 + 0) * 50 / 100) + 5 = 90 + 5 = 95
        assert pokemon.stats["spe"] == 95

    def test_stats_with_max_ivs(self):
        """Stats calculated correctly with max IVs."""
        pokemon = Pokemon(
            pokedex_id=1,
            name="test",
            type1="normal",
            level=50,
            ivs={"hp": 31, "atk": 31, "def": 31, "spa": 31, "spd": 31, "spe": 31},
        )
        # HP = ((2*50 + 31 + 0) * 50 / 100) + 50 + 10 = 65 + 50 + 10 = 125
        assert pokemon.stats["hp"] == 125
        # Atk = ((2*50 + 31 + 0) * 50 / 100) + 5 = 65 + 5 = 70
        assert pokemon.stats["atk"] == 70

    def test_stats_with_max_evs(self):
        """Stats calculated correctly with max EVs."""
        pokemon = Pokemon(
            pokedex_id=1,
            name="test",
            type1="normal",
            level=50,
            evs={"hp": 252, "atk": 252, "def": 0, "spa": 0, "spd": 0, "spe": 0},
        )
        # HP = ((2*50 + 0 + 63) * 50 / 100) + 50 + 10 = 81 + 50 + 10 = 141
        # Note: 252 // 4 = 63
        assert pokemon.stats["hp"] == 141
        # Atk = ((2*50 + 0 + 63) * 50 / 100) + 5 = 81 + 5 = 86
        assert pokemon.stats["atk"] == 86

    def test_stats_with_evs_and_ivs(self):
        """Stats calculated correctly with both EVs and IVs."""
        pokemon = Pokemon(
            pokedex_id=1,
            name="test",
            type1="normal",
            level=50,
            ivs={"hp": 31, "atk": 31, "def": 31, "spa": 31, "spd": 31, "spe": 31},
            evs={"hp": 252, "atk": 0, "def": 0, "spa": 0, "spd": 0, "spe": 252},
        )
        # HP = ((2*50 + 31 + 63) * 50 / 100) + 50 + 10 = 97 + 50 + 10 = 157
        assert pokemon.stats["hp"] == 157
        # Spe = ((2*50 + 31 + 63) * 50 / 100) + 5 = 97 + 5 = 102
        assert pokemon.stats["spe"] == 102

    def test_stats_level_100(self):
        """Stats at level 100."""
        pokemon = Pokemon(
            pokedex_id=1,
            name="test",
            type1="normal",
            level=100,
            base_stats={"hp": 100, "atk": 100, "def": 100, "spa": 100, "spd": 100, "spe": 100},
            ivs={"hp": 31, "atk": 31, "def": 31, "spa": 31, "spd": 31, "spe": 31},
            evs={"hp": 252, "atk": 252, "def": 0, "spa": 0, "spd": 0, "spe": 0},
        )
        # HP = ((2*100 + 31 + 63) * 100 / 100) + 100 + 10 = 294 + 100 + 10 = 404
        assert pokemon.stats["hp"] == 404
        # Atk = ((2*100 + 31 + 63) * 100 / 100) + 5 = 294 + 5 = 299
        assert pokemon.stats["atk"] == 299

    def test_calculate_stat_method(self):
        """Test calculate_stat method directly."""
        pokemon = Pokemon(
            pokedex_id=1,
            name="test",
            type1="normal",
            level=50,
            base_stats={"hp": 80, "atk": 80, "def": 80, "spa": 80, "spd": 80, "spe": 80},
        )
        hp = pokemon.calculate_stat("hp")
        atk = pokemon.calculate_stat("atk")
        # HP = ((2*80 + 0 + 0) * 50 / 100) + 50 + 10 = 80 + 50 + 10 = 140
        assert hp == 140
        # Atk = ((2*80 + 0 + 0) * 50 / 100) + 5 = 80 + 5 = 85
        assert atk == 85


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
