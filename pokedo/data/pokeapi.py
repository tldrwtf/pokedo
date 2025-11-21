"""PokeAPI client for fetching Pokemon data and sprites."""

import json
import httpx
from pathlib import Path
from typing import Optional
from datetime import datetime

from pokedo.utils.config import config
from pokedo.core.pokemon import Pokemon, PokedexEntry, PokemonRarity


# Comprehensive rarity classification for all Pokemon generations

# Legendary Pokemon (all generations)
LEGENDARY_IDS = {
    # Gen 1
    144, 145, 146, 150,  # Articuno, Zapdos, Moltres, Mewtwo
    # Gen 2
    243, 244, 245, 249, 250,  # Raikou, Entei, Suicune, Lugia, Ho-Oh
    # Gen 3
    377, 378, 379, 380, 381, 382, 383, 384,  # Regis, Lati@s, Weather trio
    # Gen 4
    480, 481, 482, 483, 484, 485, 486, 487, 488,  # Lake trio, Creation trio, Heatran, Regigigas, Giratina, Cresselia
    # Gen 5
    638, 639, 640, 641, 642, 643, 644, 645, 646,  # Swords of Justice, Forces of Nature, Tao trio
    # Gen 6
    716, 717, 718,  # Xerneas, Yveltal, Zygarde
    # Gen 7
    785, 786, 787, 788, 789, 790, 791, 792, 800,  # Tapus, Cosmog line, Necrozma
    # Gen 8
    888, 889, 890, 891, 892, 894, 895, 896, 897, 898,  # Sword/Shield legends
    # Gen 9
    1001, 1002, 1003, 1004, 1007, 1008, 1014, 1015, 1016, 1017, 1024,  # Paldea legends
}

# Mythical Pokemon (all generations)
MYTHICAL_IDS = {
    151,  # Mew
    251,  # Celebi
    385, 386,  # Jirachi, Deoxys
    489, 490, 491, 492, 493,  # Phione, Manaphy, Darkrai, Shaymin, Arceus
    494, 647, 648, 649,  # Victini, Keldeo, Meloetta, Genesect
    719, 720, 721,  # Diancie, Hoopa, Volcanion
    801, 802, 807, 808, 809,  # Magearna, Marshadow, Zeraora, Meltan, Melmetal
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
    1018, 1019, 1020, 1021, 1022, 1023,  # Paldea pseudo-legendaries
}

# Final evolution starters (all generations) - Epic rarity
STARTER_FINAL_IDS = {
    # Gen 1
    3, 6, 9,  # Venusaur, Charizard, Blastoise
    # Gen 2
    154, 157, 160,  # Meganium, Typhlosion, Feraligatr
    # Gen 3
    254, 257, 260,  # Sceptile, Blaziken, Swampert
    # Gen 4
    389, 392, 395,  # Torterra, Infernape, Empoleon
    # Gen 5
    497, 500, 503,  # Serperior, Emboar, Samurott
    # Gen 6
    652, 655, 658,  # Chesnaught, Delphox, Greninja
    # Gen 7
    724, 727, 730,  # Decidueye, Incineroar, Primarina
    # Gen 8
    812, 815, 818,  # Rillaboom, Cinderace, Inteleon
    # Gen 9
    908, 911, 914,  # Meowscarada, Skeledirge, Quaquaval
}

# Ultra Beasts - Rare/Epic
ULTRA_BEAST_IDS = {
    793, 794, 795, 796, 797, 798, 799, 803, 804, 805, 806,  # All Ultra Beasts
}

# Paradox Pokemon - Rare
PARADOX_IDS = {
    984, 985, 986, 987, 988, 989, 990, 991, 992, 993, 994, 995, 1005, 1006, 1009, 1010,
}


class PokeAPIClient:
    """Client for interacting with PokeAPI."""

    def __init__(self):
        self.base_url = config.pokeapi_base_url
        self.cache_dir = config.cache_dir
        self.sprites_dir = config.sprites_dir
        self._pokemon_cache: dict[int, dict] = {}
        self._species_cache: dict[int, dict] = {}
        config.ensure_dirs()

    async def get_pokemon(self, pokemon_id: int) -> Optional[dict]:
        """Fetch Pokemon data from API or cache."""
        if pokemon_id in self._pokemon_cache:
            return self._pokemon_cache[pokemon_id]

        cache_file = self.cache_dir / f"pokemon_{pokemon_id}.json"
        if cache_file.exists():
            with open(cache_file, "r") as f:
                data = json.load(f)
                self._pokemon_cache[pokemon_id] = data
                return data

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(f"{self.base_url}/pokemon/{pokemon_id}")
                response.raise_for_status()
                data = response.json()

                # Cache the result
                with open(cache_file, "w") as f:
                    json.dump(data, f)
                self._pokemon_cache[pokemon_id] = data
                return data
            except httpx.HTTPError:
                return None

    async def get_species(self, pokemon_id: int) -> Optional[dict]:
        """Fetch Pokemon species data (for evolution info)."""
        if pokemon_id in self._species_cache:
            return self._species_cache[pokemon_id]

        cache_file = self.cache_dir / f"species_{pokemon_id}.json"
        if cache_file.exists():
            with open(cache_file, "r") as f:
                data = json.load(f)
                self._species_cache[pokemon_id] = data
                return data

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(f"{self.base_url}/pokemon-species/{pokemon_id}")
                response.raise_for_status()
                data = response.json()

                with open(cache_file, "w") as f:
                    json.dump(data, f)
                self._species_cache[pokemon_id] = data
                return data
            except httpx.HTTPError:
                return None

    async def get_evolution_chain(self, chain_url: str) -> Optional[dict]:
        """Fetch evolution chain data."""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(chain_url)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError:
                return None

    async def download_sprite(self, pokemon_id: int, is_shiny: bool = False) -> Optional[Path]:
        """Download and cache Pokemon sprite."""
        sprite_type = "shiny" if is_shiny else "normal"
        sprite_file = self.sprites_dir / f"{pokemon_id}_{sprite_type}.png"

        if sprite_file.exists():
            return sprite_file

        pokemon_data = await self.get_pokemon(pokemon_id)
        if not pokemon_data:
            return None

        sprites = pokemon_data.get("sprites", {})
        if is_shiny:
            sprite_url = sprites.get("front_shiny")
        else:
            sprite_url = sprites.get("front_default")

        if not sprite_url:
            return None

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(sprite_url)
                response.raise_for_status()
                with open(sprite_file, "wb") as f:
                    f.write(response.content)
                return sprite_file
            except httpx.HTTPError:
                return None

    def get_sprite_url(self, pokemon_id: int, is_shiny: bool = False) -> str:
        """Get sprite URL without downloading."""
        if is_shiny:
            return f"https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/shiny/{pokemon_id}.png"
        else:
            return f"https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/{pokemon_id}.png"

    async def create_pokedex_entry(self, pokemon_id: int) -> Optional[PokedexEntry]:
        """Create a PokedexEntry from API data."""
        pokemon_data = await self.get_pokemon(pokemon_id)
        if not pokemon_data:
            return None

        species_data = await self.get_species(pokemon_id)

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

        return PokedexEntry(
            pokedex_id=pokemon_id,
            name=pokemon_data["name"],
            type1=type1,
            type2=type2,
            sprite_url=self.get_sprite_url(pokemon_id),
            rarity=rarity,
            evolves_from=evolves_from,
            evolves_to=evolves_to
        )

    async def create_pokemon_instance(
        self,
        pokemon_id: int,
        is_shiny: bool = False,
        catch_location: Optional[str] = None
    ) -> Optional[Pokemon]:
        """Create a Pokemon instance from API data."""
        pokemon_data = await self.get_pokemon(pokemon_id)
        if not pokemon_data:
            return None

        species_data = await self.get_species(pokemon_id)

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
            chain_data = await self.get_evolution_chain(chain_url)
            if chain_data:
                evo_info = self._parse_evolution_chain(chain_data["chain"], pokemon_id)
                evolution_id = evo_info.get("evolves_to")
                evolution_level = evo_info.get("min_level")
                evolution_method = evo_info.get("method")

        return Pokemon(
            pokedex_id=pokemon_id,
            name=pokemon_data["name"],
            type1=type1,
            type2=type2,
            is_shiny=is_shiny,
            catch_location=catch_location,
            sprite_url=self.get_sprite_url(pokemon_id, is_shiny),
            evolution_id=evolution_id,
            evolution_level=evolution_level,
            evolution_method=evolution_method,
            caught_at=datetime.now()
        )

    def _classify_rarity(self, pokemon_id: int, species_data: Optional[dict]) -> PokemonRarity:
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
        result: dict[str, Optional[int | str]] = {"evolves_to": None, "min_level": None, "method": None}

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
def get_pokemon_sync(pokemon_id: int) -> Optional[dict]:
    """Synchronous wrapper for getting Pokemon data."""
    import asyncio
    client = PokeAPIClient()
    return asyncio.run(client.get_pokemon(pokemon_id))


def create_pokemon_sync(
    pokemon_id: int,
    is_shiny: bool = False,
    catch_location: Optional[str] = None
) -> Optional[Pokemon]:
    """Synchronous wrapper for creating Pokemon instance."""
    import asyncio
    client = PokeAPIClient()
    return asyncio.run(client.create_pokemon_instance(pokemon_id, is_shiny, catch_location))


def create_pokedex_entry_sync(pokemon_id: int) -> Optional[PokedexEntry]:
    """Synchronous wrapper for creating Pokedex entry."""
    import asyncio
    client = PokeAPIClient()
    return asyncio.run(client.create_pokedex_entry(pokemon_id))


# Global client instance
pokeapi = PokeAPIClient()
