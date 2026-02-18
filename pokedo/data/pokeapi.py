"""PokeAPI client for fetching Pokemon data and sprites."""

import asyncio
import json
from datetime import datetime
from pathlib import Path

import httpx

from pokedo.core.moves import DamageClass, Move, StatusEffect, random_nature
from pokedo.core.pokemon import PokedexEntry, Pokemon, PokemonRarity
from pokedo.utils.config import config

# Comprehensive rarity classification for all Pokemon generations

# Legendary Pokemon (all generations)
LEGENDARY_IDS = {
    # Gen 1
    144,
    145,
    146,
    150,  # Articuno, Zapdos, Moltres, Mewtwo
    # Gen 2
    243,
    244,
    245,
    249,
    250,  # Raikou, Entei, Suicune, Lugia, Ho-Oh
    # Gen 3
    377,
    378,
    379,
    380,
    381,
    382,
    383,
    384,  # Regis, Lati@s, Weather trio
    # Gen 4
    480,
    481,
    482,
    483,
    484,
    485,
    486,
    487,
    488,  # Lake trio, Creation trio, Heatran, Regigigas, Giratina, Cresselia
    # Gen 5
    638,
    639,
    640,
    641,
    642,
    643,
    644,
    645,
    646,  # Swords of Justice, Forces of Nature, Tao trio
    # Gen 6
    716,
    717,
    718,  # Xerneas, Yveltal, Zygarde
    # Gen 7
    785,
    786,
    787,
    788,
    789,
    790,
    791,
    792,
    800,  # Tapus, Cosmog line, Necrozma
    # Gen 8
    888,
    889,
    890,
    891,
    892,
    894,
    895,
    896,
    897,
    898,  # Sword/Shield legends
    # Gen 9
    1001,
    1002,
    1003,
    1004,
    1007,
    1008,
    1014,
    1015,
    1016,
    1017,
    1024,  # Paldea legends
}

# Mythical Pokemon (all generations)
MYTHICAL_IDS = {
    151,  # Mew
    251,  # Celebi
    385,
    386,  # Jirachi, Deoxys
    489,
    490,
    491,
    492,
    493,  # Phione, Manaphy, Darkrai, Shaymin, Arceus
    494,
    647,
    648,
    649,  # Victini, Keldeo, Meloetta, Genesect
    719,
    720,
    721,  # Diancie, Hoopa, Volcanion
    801,
    802,
    807,
    808,
    809,  # Magearna, Marshadow, Zeraora, Meltan, Melmetal
    893,  # Zarude
    1025,  # Pecharunt
}

# Pseudo-Legendary Pokemon (600 BST, 3-stage evolution)
PSEUDO_LEGENDARY_IDS = {
    149,  # Dragonite
    248,  # Tyranitar
    373,  # Salamence
    376,  # Metagross
    445,  # Garchomp
    635,  # Hydreigon
    706,  # Goodra
    784,  # Kommo-o
    887,  # Dragapult
    998,  # Baxcalibur (if exists)
    1018,
    1019,
    1020,
    1021,
    1022,
    1023,  # Paldea pseudo-legendaries
}

# Final evolution starters (all generations) - Epic rarity
STARTER_FINAL_IDS = {
    # Gen 1
    3,
    6,
    9,  # Venusaur, Charizard, Blastoise
    # Gen 2
    154,
    157,
    160,  # Meganium, Typhlosion, Feraligatr
    # Gen 3
    254,
    257,
    260,  # Sceptile, Blaziken, Swampert
    # Gen 4
    389,
    392,
    395,  # Torterra, Infernape, Empoleon
    # Gen 5
    497,
    500,
    503,  # Serperior, Emboar, Samurott
    # Gen 6
    652,
    655,
    658,  # Chesnaught, Delphox, Greninja
    # Gen 7
    724,
    727,
    730,  # Decidueye, Incineroar, Primarina
    # Gen 8
    812,
    815,
    818,  # Rillaboom, Cinderace, Inteleon
    # Gen 9
    908,
    911,
    914,  # Meowscarada, Skeledirge, Quaquaval
}

# Ultra Beasts - Rare/Epic
ULTRA_BEAST_IDS = {
    793,
    794,
    795,
    796,
    797,
    798,
    799,
    803,
    804,
    805,
    806,  # All Ultra Beasts
}

# Paradox Pokemon - Rare
PARADOX_IDS = {
    984,
    985,
    986,
    987,
    988,
    989,
    990,
    991,
    992,
    993,
    994,
    995,
    1005,
    1006,
    1009,
    1010,
}

# Mapping from PokeAPI stat names to internal stat abbreviations
STAT_NAME_MAP = {
    "hp": "hp",
    "attack": "atk",
    "defense": "def",
    "special-attack": "spa",
    "special-defense": "spd",
    "speed": "spe",
}


class PokeAPIClient:
    """Client for interacting with PokeAPI."""

    def __init__(self):
        self.base_url = config.pokeapi_base_url
        self.cache_dir = config.cache_dir
        self.sprites_dir = config.sprites_dir
        self._pokemon_cache: dict[int, dict] = {}
        self._species_cache: dict[int, dict] = {}
        self._move_cache: dict[str, dict] = {}
        config.ensure_dirs()

    async def _fetch_json(self, url: str, client: httpx.AsyncClient) -> dict | None:
        try:
            response = await client.get(url)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError:
            return None

    async def _fetch_bytes(self, url: str, client: httpx.AsyncClient) -> bytes | None:
        try:
            response = await client.get(url)
            response.raise_for_status()
            return response.content
        except httpx.HTTPError:
            return None

    async def get_pokemon(self, pokemon_id: int, client: httpx.AsyncClient | None = None) -> dict | None:
        """Fetch Pokemon data from API or cache."""
        if pokemon_id in self._pokemon_cache:
            return self._pokemon_cache[pokemon_id]

        cache_file = self.cache_dir / f"pokemon_{pokemon_id}.json"
        if cache_file.exists():
            with open(cache_file) as f:
                data = json.load(f)
                self._pokemon_cache[pokemon_id] = data
                return data

        url = f"{self.base_url}/pokemon/{pokemon_id}"
        if client is None:
            async with httpx.AsyncClient() as client:
                data = await self._fetch_json(url, client)
        else:
            data = await self._fetch_json(url, client)
        if not data:
            return None

        # Cache the result
        with open(cache_file, "w") as f:
            json.dump(data, f)
        self._pokemon_cache[pokemon_id] = data
        return data

    async def get_species(self, pokemon_id: int, client: httpx.AsyncClient | None = None) -> dict | None:
        """Fetch Pokemon species data (for evolution info)."""
        if pokemon_id in self._species_cache:
            return self._species_cache[pokemon_id]

        cache_file = self.cache_dir / f"species_{pokemon_id}.json"
        if cache_file.exists():
            with open(cache_file) as f:
                data = json.load(f)
                self._species_cache[pokemon_id] = data
                return data

        url = f"{self.base_url}/pokemon-species/{pokemon_id}"
        if client is None:
            async with httpx.AsyncClient() as client:
                data = await self._fetch_json(url, client)
        else:
            data = await self._fetch_json(url, client)
        if not data:
            return None

        with open(cache_file, "w") as f:
            json.dump(data, f)
        self._species_cache[pokemon_id] = data
        return data

    async def get_evolution_chain(
        self, chain_url: str, client: httpx.AsyncClient | None = None
    ) -> dict | None:
        """Fetch evolution chain data."""
        if client is None:
            async with httpx.AsyncClient() as client:
                return await self._fetch_json(chain_url, client)
        return await self._fetch_json(chain_url, client)

    async def download_sprite(
        self, pokemon_id: int, is_shiny: bool = False, client: httpx.AsyncClient | None = None
    ) -> Path | None:
        """Download and cache Pokemon sprite."""
        sprite_type = "shiny" if is_shiny else "normal"
        sprite_file = self.sprites_dir / f"{pokemon_id}_{sprite_type}.png"

        if sprite_file.exists():
            return sprite_file

        if client is None:
            async with httpx.AsyncClient() as client:
                return await self.download_sprite(pokemon_id, is_shiny=is_shiny, client=client)

        pokemon_data = await self.get_pokemon(pokemon_id, client=client)
        if not pokemon_data:
            return None

        sprites = pokemon_data.get("sprites", {})
        if is_shiny:
            sprite_url = sprites.get("front_shiny")
        else:
            sprite_url = sprites.get("front_default")

        if not sprite_url:
            return None

        content = await self._fetch_bytes(sprite_url, client)
        if not content:
            return None
        with open(sprite_file, "wb") as f:
            f.write(content)
        return sprite_file

    def get_sprite_url(self, pokemon_id: int, is_shiny: bool = False) -> str:
        """Get sprite URL without downloading."""
        if is_shiny:
            return f"https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/shiny/{pokemon_id}.png"
        else:
            return f"https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/{pokemon_id}.png"

    async def create_pokedex_entry(
        self, pokemon_id: int, client: httpx.AsyncClient | None = None
    ) -> PokedexEntry | None:
        """Create a PokedexEntry from API data."""
        pokemon_data, species_data = await asyncio.gather(
            self.get_pokemon(pokemon_id, client=client),
            self.get_species(pokemon_id, client=client),
        )
        if not pokemon_data:
            return None

        # Extract types
        types = pokemon_data.get("types", [])
        type1 = types[0]["type"]["name"] if types else "normal"
        type2 = types[1]["type"]["name"] if len(types) > 1 else None

        # Determine rarity
        rarity = self._classify_rarity(pokemon_id, species_data)

        # Get evolution info
        evolves_from = None
        evolves_to = []
        if species_data:
            if species_data.get("evolves_from_species"):
                # Extract ID from URL
                from_url = species_data["evolves_from_species"]["url"]
                evolves_from = int(from_url.rstrip("/").split("/")[-1])

        # Extract base stats
        base_stats = self._extract_base_stats(pokemon_data)

        return PokedexEntry(
            pokedex_id=pokemon_id,
            name=pokemon_data["name"],
            type1=type1,
            type2=type2,
            base_stats=base_stats,
            sprite_url=self.get_sprite_url(pokemon_id),
            rarity=rarity,
            evolves_from=evolves_from,
            evolves_to=evolves_to,
        )

    async def create_pokemon_instance(
        self,
        pokemon_id: int,
        is_shiny: bool = False,
        catch_location: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> Pokemon | None:
        """Create a Pokemon instance from API data."""
        pokemon_data, species_data = await asyncio.gather(
            self.get_pokemon(pokemon_id, client=client),
            self.get_species(pokemon_id, client=client),
        )
        if not pokemon_data:
            return None

        # Extract types
        types = pokemon_data.get("types", [])
        type1 = types[0]["type"]["name"] if types else "normal"
        type2 = types[1]["type"]["name"] if len(types) > 1 else None

        # Get evolution info
        evolution_id = None
        evolution_level = None
        evolution_method = None

        if species_data and species_data.get("evolution_chain"):
            chain_url = species_data["evolution_chain"]["url"]
            chain_data = await self.get_evolution_chain(chain_url, client=client)
            if chain_data:
                evo_info = self._parse_evolution_chain(chain_data["chain"], pokemon_id)
                evolution_id = evo_info.get("evolves_to")
                evolution_level = evo_info.get("min_level")
                evolution_method = evo_info.get("method")

        # Extract base stats
        base_stats = self._extract_base_stats(pokemon_data)

        return Pokemon(
            pokedex_id=pokemon_id,
            name=pokemon_data["name"],
            type1=type1,
            type2=type2,
            base_stats=base_stats,
            is_shiny=is_shiny,
            catch_location=catch_location,
            sprite_url=self.get_sprite_url(pokemon_id, is_shiny),
            evolution_id=evolution_id,
            evolution_level=evolution_level,
            evolution_method=evolution_method,
            caught_at=datetime.now(),
            nature=random_nature().value,
        )

    def _extract_base_stats(self, pokemon_data: dict) -> dict[str, int]:
        """Extract base stats from PokeAPI response."""
        base_stats = {"hp": 50, "atk": 50, "def": 50, "spa": 50, "spd": 50, "spe": 50}

        stats_list = pokemon_data.get("stats", [])
        for stat_entry in stats_list:
            api_stat_name = stat_entry.get("stat", {}).get("name", "")
            internal_name = STAT_NAME_MAP.get(api_stat_name)
            if internal_name:
                base_stats[internal_name] = stat_entry.get("base_stat", 50)

        return base_stats
    # --- Move fetching (multiplayer / battle support) ---

    async def get_move(self, move_name: str, client: httpx.AsyncClient | None = None) -> dict | None:
        """Fetch a single move's data from PokeAPI (with cache)."""
        move_key = move_name.lower()
        if move_key in self._move_cache:
            return self._move_cache[move_key]

        # Disk cache
        cache_path = self.cache_dir / f"move_{move_key}.json"
        if cache_path.exists():
            data = json.loads(cache_path.read_text())
            self._move_cache[move_key] = data
            return data

        # Fetch from API
        url = f"{self.base_url}/move/{move_key}"
        should_close = False
        if client is None:
            client = httpx.AsyncClient(timeout=30.0)
            should_close = True
        try:
            data = await self._fetch_json(url, client)
            if data:
                cache_path.write_text(json.dumps(data))
                self._move_cache[move_key] = data
            return data
        finally:
            if should_close:
                await client.aclose()

    def _parse_move_data(self, move_data: dict) -> Move:
        """Convert raw PokeAPI move JSON into a Move model."""
        name = move_data.get("name", "unknown")
        move_type = move_data.get("type", {}).get("name", "normal")
        damage_class_raw = move_data.get("damage_class", {}).get("name", "physical")
        power = move_data.get("power")  # None for status moves
        accuracy = move_data.get("accuracy")
        pp = move_data.get("pp", 20)
        priority = move_data.get("priority", 0)

        # Effect text (English short)
        effect_text = ""
        for entry in move_data.get("effect_entries", []):
            if entry.get("language", {}).get("name") == "en":
                effect_text = entry.get("short_effect", "")
                break

        effect_chance = move_data.get("effect_chance")

        # Meta info
        meta = move_data.get("meta", {}) or {}
        drain_percent = meta.get("drain", 0)
        healing_percent = meta.get("healing", 0)
        flinch_chance = meta.get("flinch_chance", 0)

        # Status ailment
        ailment_name = (meta.get("ailment", {}) or {}).get("name", "none")
        status_map = {
            "burn": StatusEffect.BURN,
            "freeze": StatusEffect.FREEZE,
            "paralysis": StatusEffect.PARALYSIS,
            "poison": StatusEffect.POISON,
            "sleep": StatusEffect.SLEEP,
        }
        status_effect = status_map.get(ailment_name, StatusEffect.NONE)

        # Stat changes
        stat_changes: dict[str, int] = {}
        for sc in move_data.get("stat_changes", []):
            api_name = sc.get("stat", {}).get("name", "")
            internal = STAT_NAME_MAP.get(api_name, api_name)
            stat_changes[internal] = sc.get("change", 0)

        try:
            dc = DamageClass(damage_class_raw)
        except ValueError:
            dc = DamageClass.PHYSICAL

        return Move(
            id=move_data.get("id"),
            name=name,
            type=move_type,
            damage_class=dc,
            power=power,
            accuracy=accuracy,
            pp=pp,
            priority=priority,
            effect_text=effect_text,
            effect_chance=effect_chance,
            status_effect=status_effect,
            stat_changes=stat_changes,
            drain_percent=drain_percent,
            healing_percent=healing_percent,
            flinch_chance=flinch_chance,
        )

    async def get_pokemon_moves(
        self,
        pokemon_id: int,
        level: int = 50,
        max_moves: int = 4,
        client: httpx.AsyncClient | None = None,
    ) -> list[Move]:
        """Fetch a curated moveset for a Pokemon from PokeAPI.

        Picks the best level-up moves the Pokemon can learn at the given level,
        prioritising STAB and higher-power moves.  Falls back to the default
        moveset generator if the API call fails.
        """
        pokemon_data = await self.get_pokemon(pokemon_id, client=client)
        if not pokemon_data:
            return []

        types = pokemon_data.get("types", [])
        type1 = types[0]["type"]["name"] if types else "normal"
        type2 = types[1]["type"]["name"] if len(types) > 1 else None

        # Gather candidate move names from level-up learnset
        candidates: list[tuple[str, int]] = []  # (move_name, level_learned)
        for move_entry in pokemon_data.get("moves", []):
            name = move_entry.get("move", {}).get("name", "")
            for vgd in move_entry.get("version_group_details", []):
                method = vgd.get("move_learn_method", {}).get("name", "")
                learned_at = vgd.get("level_learned_at", 0)
                if method == "level-up" and learned_at <= level:
                    candidates.append((name, learned_at))

        if not candidates:
            # Fallback to default generator
            from pokedo.core.moves import generate_default_moveset
            return generate_default_moveset(type1, type2, level)

        # Deduplicate, keep highest level_learned for each move
        best: dict[str, int] = {}
        for name, lv in candidates:
            if name not in best or lv > best[name]:
                best[name] = lv

        # Sort by level learned descending (most recent first)
        sorted_names = sorted(best.keys(), key=lambda n: best[n], reverse=True)

        # Fetch actual move data (batch, up to 10 candidates)
        should_close = False
        if client is None:
            client = httpx.AsyncClient(timeout=30.0)
            should_close = True
        try:
            moves: list[Move] = []
            for mname in sorted_names[:10]:
                raw = await self.get_move(mname, client=client)
                if raw:
                    moves.append(self._parse_move_data(raw))

            if not moves:
                from pokedo.core.moves import generate_default_moveset
                return generate_default_moveset(type1, type2, level)

            # Score and pick: prefer STAB, higher power, damaging
            pokemon_types = {type1}
            if type2:
                pokemon_types.add(type2)

            def score(m: Move) -> float:
                s = float(m.power or 0)
                if m.type in pokemon_types:
                    s *= 1.5  # STAB bonus in selection
                if m.damage_class == DamageClass.STATUS:
                    s = 10  # Keep status moves low priority but nonzero
                return s

            moves.sort(key=score, reverse=True)

            # Pick top moves, ensure type coverage diversity
            selected: list[Move] = []
            types_covered: set[str] = set()
            for m in moves:
                if len(selected) >= max_moves:
                    break
                selected.append(m)
                types_covered.add(m.type)

            return selected
        finally:
            if should_close:
                await client.aclose()
    def _classify_rarity(self, pokemon_id: int, species_data: dict | None) -> PokemonRarity:
        """Classify Pokemon rarity based on its characteristics."""
        # Check explicit rarity categories first
        if pokemon_id in MYTHICAL_IDS:
            return PokemonRarity.MYTHICAL
        if pokemon_id in LEGENDARY_IDS:
            return PokemonRarity.LEGENDARY
        if pokemon_id in PSEUDO_LEGENDARY_IDS or pokemon_id in STARTER_FINAL_IDS:
            return PokemonRarity.EPIC
        if pokemon_id in ULTRA_BEAST_IDS:
            return PokemonRarity.EPIC
        if pokemon_id in PARADOX_IDS:
            return PokemonRarity.RARE

        if species_data:
            # Check if legendary/mythical from API data
            if species_data.get("is_legendary"):
                return PokemonRarity.LEGENDARY
            if species_data.get("is_mythical"):
                return PokemonRarity.MYTHICAL

            # Use capture rate for classification
            capture_rate = species_data.get("capture_rate", 255)

            # Check evolution status
            has_evolution_from = species_data.get("evolves_from_species") is not None

            if has_evolution_from:
                # Evolved Pokemon tend to be rarer
                if capture_rate < 30:
                    return PokemonRarity.RARE
                elif capture_rate < 75:
                    return PokemonRarity.UNCOMMON
                elif capture_rate < 150:
                    return PokemonRarity.UNCOMMON
                return PokemonRarity.COMMON
            else:
                # Base Pokemon
                if capture_rate < 30:
                    return PokemonRarity.RARE
                elif capture_rate < 100:
                    return PokemonRarity.UNCOMMON
                return PokemonRarity.COMMON

        return PokemonRarity.COMMON

    def _parse_evolution_chain(self, chain: dict, pokemon_id: int) -> dict:
        """Parse evolution chain to find evolution info for a specific Pokemon."""
        result: dict[str, int | str | None] = {
            "evolves_to": None,
            "min_level": None,
            "method": None,
        }

        def search_chain(node: dict) -> bool:
            species_url = node["species"]["url"]
            current_id = int(species_url.rstrip("/").split("/")[-1])

            if current_id == pokemon_id:
                # Found our Pokemon, check what it evolves to
                if node.get("evolves_to"):
                    next_evo = node["evolves_to"][0]
                    next_url = next_evo["species"]["url"]
                    result["evolves_to"] = int(next_url.rstrip("/").split("/")[-1])

                    # Get evolution details
                    if next_evo.get("evolution_details"):
                        details = next_evo["evolution_details"][0]
                        result["min_level"] = details.get("min_level")

                        # Determine method
                        if details.get("min_level"):
                            result["method"] = "level"
                        elif details.get("item"):
                            result["method"] = "item"
                        elif details.get("min_happiness"):
                            result["method"] = "friendship"
                        elif details.get("trade_species"):
                            result["method"] = "trade"
                        else:
                            result["method"] = "level"
                return True

            # Recurse through evolutions
            for evo in node.get("evolves_to", []):
                if search_chain(evo):
                    return True
            return False

        search_chain(chain)
        return result

    async def initialize_pokedex(self, max_id: int = 151) -> list[PokedexEntry]:
        """Initialize Pokedex with all Pokemon up to max_id."""
        entries = []
        for pokemon_id in range(1, max_id + 1):
            entry = await self.create_pokedex_entry(pokemon_id)
            if entry:
                entries.append(entry)
        return entries


# Synchronous wrapper for CLI usage
def get_pokemon_sync(pokemon_id: int) -> dict | None:
    """Synchronous wrapper for getting Pokemon data."""
    import asyncio

    client = PokeAPIClient()
    return asyncio.run(client.get_pokemon(pokemon_id))


def create_pokemon_sync(
    pokemon_id: int, is_shiny: bool = False, catch_location: str | None = None
) -> Pokemon | None:
    """Synchronous wrapper for creating Pokemon instance."""
    import asyncio

    client = PokeAPIClient()
    return asyncio.run(client.create_pokemon_instance(pokemon_id, is_shiny, catch_location))


def create_pokedex_entry_sync(pokemon_id: int) -> PokedexEntry | None:
    """Synchronous wrapper for creating Pokedex entry."""
    import asyncio

    client = PokeAPIClient()
    return asyncio.run(client.create_pokedex_entry(pokemon_id))


# Global client instance
pokeapi = PokeAPIClient()
