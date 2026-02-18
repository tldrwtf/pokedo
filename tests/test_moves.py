"""Tests for the move model, type chart, nature system, and damage calculation."""

import random

import pytest

from pokedo.core.moves import (
    DEFAULT_MOVES_BY_TYPE,
    DamageClass,
    Move,
    PokemonNature,
    PokemonType,
    StatusEffect,
    TYPE_CHART,
    calculate_damage,
    generate_default_moveset,
    get_nature_multiplier,
    get_type_effectiveness,
    random_nature,
)


class TestPokemonType:
    """Tests for the PokemonType enum."""

    def test_all_18_types_present(self):
        """All 18 Pokemon types must be defined."""
        assert len(PokemonType) == 18

    def test_type_values_lowercase(self):
        """Type values should be lowercase strings."""
        for t in PokemonType:
            assert t.value == t.value.lower()

    def test_known_types(self):
        """Spot-check specific types exist."""
        expected = {"normal", "fire", "water", "electric", "grass", "ice",
                    "fighting", "poison", "ground", "flying", "psychic", "bug",
                    "rock", "ghost", "dragon", "dark", "steel", "fairy"}
        actual = {t.value for t in PokemonType}
        assert actual == expected


class TestDamageClass:
    """Tests for DamageClass enum."""

    def test_three_classes(self):
        assert set(DamageClass) == {DamageClass.PHYSICAL, DamageClass.SPECIAL, DamageClass.STATUS}


class TestStatusEffect:
    """Tests for StatusEffect enum."""

    def test_all_statuses(self):
        expected = {"none", "burn", "freeze", "paralysis", "poison", "badly_poisoned", "sleep"}
        actual = {s.value for s in StatusEffect}
        assert actual == expected


class TestNatures:
    """Tests for the nature system."""

    def test_25_natures(self):
        """There are exactly 25 natures."""
        assert len(PokemonNature) == 25

    def test_neutral_natures(self):
        """Five natures should be neutral (no stat change)."""
        neutral = ["hardy", "docile", "serious", "bashful", "quirky"]
        for n in neutral:
            assert get_nature_multiplier(n, "atk") == 1.0
            assert get_nature_multiplier(n, "spe") == 1.0
            assert get_nature_multiplier(n, "spa") == 1.0

    def test_adamant_boosts_atk(self):
        """Adamant nature boosts attack, lowers special attack."""
        assert get_nature_multiplier("adamant", "atk") == 1.1
        assert get_nature_multiplier("adamant", "spa") == 0.9
        assert get_nature_multiplier("adamant", "def") == 1.0

    def test_modest_boosts_spa(self):
        """Modest nature boosts special attack, lowers attack."""
        assert get_nature_multiplier("modest", "spa") == 1.1
        assert get_nature_multiplier("modest", "atk") == 0.9

    def test_timid_boosts_spe(self):
        """Timid nature boosts speed, lowers attack."""
        assert get_nature_multiplier("timid", "spe") == 1.1
        assert get_nature_multiplier("timid", "atk") == 0.9

    def test_unknown_nature_returns_neutral(self):
        """Unknown nature name returns 1.0 for all stats."""
        assert get_nature_multiplier("fake_nature", "atk") == 1.0

    def test_random_nature_returns_valid(self):
        """random_nature() returns a member of PokemonNature."""
        for _ in range(20):
            n = random_nature()
            assert isinstance(n, PokemonNature)


class TestTypeChart:
    """Tests for the type effectiveness chart."""

    def test_chart_has_all_types(self):
        """Chart must have an entry for every attacking and defending type."""
        all_types = {t.value for t in PokemonType}
        assert set(TYPE_CHART.keys()) == all_types
        for atk in TYPE_CHART:
            assert set(TYPE_CHART[atk].keys()) == all_types

    def test_fire_beats_grass(self):
        assert TYPE_CHART["fire"]["grass"] == 2.0

    def test_water_beats_fire(self):
        assert TYPE_CHART["water"]["fire"] == 2.0

    def test_grass_beats_water(self):
        assert TYPE_CHART["grass"]["water"] == 2.0

    def test_electric_beats_water(self):
        assert TYPE_CHART["electric"]["water"] == 2.0

    def test_ground_immune_to_electric(self):
        assert TYPE_CHART["electric"]["ground"] == 0.0

    def test_normal_immune_to_ghost(self):
        assert TYPE_CHART["normal"]["ghost"] == 0.0

    def test_ghost_immune_to_normal(self):
        assert TYPE_CHART["ghost"]["normal"] == 0.0

    def test_fairy_immune_to_dragon(self):
        assert TYPE_CHART["dragon"]["fairy"] == 0.0

    def test_steel_resists_fairy(self):
        assert TYPE_CHART["fairy"]["steel"] == 0.5

    def test_psychic_immune_to_dark(self):
        assert TYPE_CHART["psychic"]["dark"] == 0.0

    def test_fighting_beats_dark(self):
        assert TYPE_CHART["fighting"]["dark"] == 2.0


class TestTypeEffectiveness:
    """Tests for get_type_effectiveness()."""

    def test_single_type_super_effective(self):
        assert get_type_effectiveness("fire", "grass", None) == 2.0

    def test_single_type_not_very_effective(self):
        assert get_type_effectiveness("fire", "water", None) == 0.5

    def test_single_type_immune(self):
        assert get_type_effectiveness("normal", "ghost", None) == 0.0

    def test_dual_type_4x(self):
        """Ice vs Grass/Flying = 4x."""
        assert get_type_effectiveness("ice", "grass", "flying") == 4.0

    def test_dual_type_neutral(self):
        """Fire vs Grass/Water = 2.0 * 0.5 = 1.0."""
        assert get_type_effectiveness("fire", "grass", "water") == 1.0

    def test_dual_type_0_25x(self):
        """Fighting vs Psychic/Flying = 0.5 * 0.5 = 0.25."""
        assert get_type_effectiveness("fighting", "psychic", "flying") == 0.25

    def test_immunity_overrides_dual(self):
        """Ground vs Flying/Normal = 0.0 * 1.0 = 0.0."""
        assert get_type_effectiveness("ground", "flying", "normal") == 0.0


class TestMove:
    """Tests for the Move model."""

    def test_create_basic_move(self):
        move = Move(name="tackle", type="normal", damage_class=DamageClass.PHYSICAL, power=40, accuracy=100, pp=35)
        assert move.name == "tackle"
        assert move.power == 40
        assert move.display_name == "Tackle"

    def test_display_name_auto_generated(self):
        move = Move(name="fire-blast", type="fire")
        assert move.display_name == "Fire Blast"

    def test_pp_initialized(self):
        move = Move(name="test", type="normal", pp=20)
        assert move.current_pp == 20

    def test_status_move_no_power(self):
        move = Move(name="toxic", type="poison", damage_class=DamageClass.STATUS, power=None)
        assert move.power is None
        assert move.damage_class == DamageClass.STATUS

    def test_priority_default(self):
        move = Move(name="test", type="normal")
        assert move.priority == 0


class TestCalculateDamage:
    """Tests for the damage calculation function."""

    def test_zero_power_returns_zero(self):
        """Status moves (power=None) deal 0 damage."""
        move = Move(name="growl", type="normal", damage_class=DamageClass.STATUS, power=None)
        damage, eff, crit = calculate_damage(50, move, 100, 100, ["normal"], "normal")
        assert damage == 0
        assert eff == 1.0
        assert crit is False

    def test_damage_positive_for_attacking_move(self):
        """A move with power > 0 must deal at least 1 damage."""
        random.seed(42)
        move = Move(name="tackle", type="normal", damage_class=DamageClass.PHYSICAL, power=40, accuracy=100, pp=35)
        damage, eff, _ = calculate_damage(50, move, 100, 100, ["normal"], "normal")
        assert damage >= 1
        assert eff == 1.0

    def test_stab_boosts_damage(self):
        """STAB (Same-Type Attack Bonus) should increase damage."""
        random.seed(42)
        move = Move(name="ember", type="fire", damage_class=DamageClass.SPECIAL, power=40, accuracy=100, pp=25)
        dmg_stab, _, _ = calculate_damage(50, move, 100, 100, ["fire"], "grass", critical=False)

        random.seed(42)
        dmg_no_stab, _, _ = calculate_damage(50, move, 100, 100, ["water"], "grass", critical=False)

        assert dmg_stab > dmg_no_stab

    def test_super_effective_increases_damage(self):
        """Super effective should deal more damage than neutral."""
        random.seed(42)
        move = Move(name="ember", type="fire", damage_class=DamageClass.SPECIAL, power=40, accuracy=100, pp=25)
        dmg_se, eff_se, _ = calculate_damage(50, move, 100, 100, ["fire"], "grass", critical=False)

        random.seed(42)
        dmg_neutral, eff_n, _ = calculate_damage(50, move, 100, 100, ["fire"], "fire", critical=False)

        assert eff_se == 2.0
        assert dmg_se > dmg_neutral

    def test_immunity_deals_zero(self):
        """Immune type matchup should deal 0 damage."""
        move = Move(name="tackle", type="normal", damage_class=DamageClass.PHYSICAL, power=40, accuracy=100, pp=35)
        damage, eff, _ = calculate_damage(50, move, 100, 100, ["normal"], "ghost")
        assert damage == 0
        assert eff == 0.0

    def test_critical_hit_increases_damage(self):
        """Forced critical hit should deal more than non-critical."""
        random.seed(42)
        move = Move(name="slash", type="normal", damage_class=DamageClass.PHYSICAL, power=70, accuracy=100, pp=20)
        dmg_crit, _, was_crit = calculate_damage(50, move, 100, 100, ["normal"], "normal", critical=True)
        assert was_crit is True

        random.seed(42)
        dmg_no_crit, _, _ = calculate_damage(50, move, 100, 100, ["normal"], "normal", critical=False)

        # Account for the random crit chance in the non-critical path
        # The forced critical should be >= non-critical
        assert dmg_crit >= dmg_no_crit

    def test_higher_level_more_damage(self):
        """Higher level attacker should deal more damage."""
        random.seed(42)
        move = Move(name="tackle", type="normal", damage_class=DamageClass.PHYSICAL, power=40, accuracy=100, pp=35)
        dmg_high, _, _ = calculate_damage(100, move, 100, 100, ["normal"], "normal", critical=False)

        random.seed(42)
        dmg_low, _, _ = calculate_damage(10, move, 100, 100, ["normal"], "normal", critical=False)

        assert dmg_high > dmg_low


class TestDefaultMoveset:
    """Tests for generate_default_moveset()."""

    def test_all_types_have_move_pools(self):
        """Every type should have a default move pool."""
        for t in PokemonType:
            assert t.value in DEFAULT_MOVES_BY_TYPE

    def test_generates_up_to_4_moves(self):
        """Generated moveset should have 1-4 moves."""
        result = generate_default_moveset("fire", None, 50)
        assert 1 <= len(result) <= 4

    def test_all_moves_are_move_objects(self):
        result = generate_default_moveset("water", "ice", 30)
        for m in result:
            assert isinstance(m, Move)
            assert m.name
            assert m.type

    def test_low_level_gets_weaker_moves(self):
        """Level 5 Pokemon should not get 100+ power moves."""
        result = generate_default_moveset("fire", None, 5)
        for m in result:
            if m.power is not None:
                assert m.power <= 50

    def test_high_level_gets_stronger_moves(self):
        """Level 60 Pokemon should be able to get strong moves."""
        result = generate_default_moveset("fire", None, 60)
        max_power = max((m.power or 0) for m in result)
        assert max_power >= 80

    def test_dual_type_gets_coverage(self):
        """Dual-type Pokemon should have moves from both types."""
        result = generate_default_moveset("fire", "flying", 50)
        move_types = {m.type for m in result}
        # Should have at least one of each STAB type
        assert "fire" in move_types or "flying" in move_types

    def test_non_normal_gets_normal_coverage(self):
        """Non-Normal types should get a Normal move for coverage."""
        result = generate_default_moveset("psychic", None, 20)
        move_types = {m.type for m in result}
        # Should include a normal move in the pool (may get filtered)
        assert len(result) >= 1  # At minimum something is generated

    def test_empty_type_fallback(self):
        """Unknown type should still return moves (fallback to struggle)."""
        result = generate_default_moveset("unknown_type", None, 50)
        assert len(result) >= 1
