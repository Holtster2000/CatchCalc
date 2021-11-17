from dataclasses import dataclass
from enum import Enum
import math
import pprint
from typing import List, Tuple
import requests

class Pokeball(Enum):
    POKE_BALL = 1
    PREMIER_BALL = 2
    LUXURY_BALL = 3
    HEAL_BALL = 4
    GREAT_BALL = 5
    ULTRA_BALL = 6
    MASTER_BALL = 7
    NET_BALL = 8
    NEST_BALL = 9
    DIVE_BALL = 10
    REPEAT_BALL = 11
    TIMER_BALL = 12
    QUICK_BALL = 13
    DUSK_BALL = 14
    FAST_BALL = 15
    LEVEL_BALL = 16
    LOVE_BALL = 17
    LURE_BALL = 18
    MOON_BALL = 19
    BEAST_BALL = 20
    DREAM_BALL = 21


class Status(Enum):
    NONE = 1
    SLEEP = 2
    FROZEN = 3
    POISON = 4
    PARALYZE = 5
    BURN = 6
    

@dataclass(frozen=True)
class WobbleProbability:
    zero_wobbles: float
    one_wobble: float
    two_wobbles: float
    three_wobbles: float


@dataclass(frozen=True)
class CatchProbability:
    hp_iv_range: Tuple[int, int]
    CC_chance: float
    CC_success: float
    catch_chance: float
    total_chance: float
    wobble_probabilities: WobbleProbability
    

@dataclass(frozen=True)
class CatchCalcResult:
    catch_probabilities: List[CatchProbability]
    
    def average_probability(self) -> CatchProbability:
        max_iv = 0
        avg_CC_chance = avg_CC_success = 0.0
        avg_catch_chance = avg_total_chance = 0.0
        avg_wobble_probabilities = [0.0, 0.0, 0.0, 0.0]
        for cp in self.catch_probabilities:
            if cp.hp_iv_range[1] > max_iv:
                max_iv = cp.hp_iv_range[1]
            avg_CC_chance += cp.CC_chance
            avg_CC_success += cp.CC_success
            avg_catch_chance += cp.catch_chance
            avg_total_chance += cp.total_chance
            avg_wobble_probabilities[0] += cp.wobble_probabilities.zero_wobbles
            avg_wobble_probabilities[1] += cp.wobble_probabilities.one_wobble
            avg_wobble_probabilities[2] += cp.wobble_probabilities.two_wobbles
            avg_wobble_probabilities[3] += cp.wobble_probabilities.three_wobbles
            
        return CatchProbability(
            hp_iv_range=(0, max_iv),
            CC_chance=round(avg_CC_chance/len(self.catch_probabilities), 5),
            CC_success=round(avg_CC_success/len(self.catch_probabilities), 5),
            catch_chance=round(avg_catch_chance/len(self.catch_probabilities), 5),
            total_chance=round(avg_total_chance/len(self.catch_probabilities), 5),
            wobble_probabilities=WobbleProbability(
                zero_wobbles=round(avg_wobble_probabilities[0]/len(self.catch_probabilities), 5),
                one_wobble=round(avg_wobble_probabilities[1]/len(self.catch_probabilities), 5),
                two_wobbles=round(avg_wobble_probabilities[2]/len(self.catch_probabilities), 5),
                three_wobbles=round(avg_wobble_probabilities[3]/len(self.catch_probabilities), 5)
            )
        )


def catch_calc_gen8(
    pokemon_name: str,
    pokemon_level: int,
    pokemon_hp_percent: int,
    your_pokemon_name: str,
    your_pokemon_level: int,
    ball_type: Pokeball,
    status: Status,
    completed_main_story: bool,
    pokedex_count: int,
    catching_charm: bool,
    on_or_in_water: bool = False,
    previously_caught: bool = False,
    turn_count: int = 1,
    night_or_cave: bool = False,
    opposite_gender: bool = False,
    exactly_one_hp: bool = False,
) -> CatchCalcResult:
    
    def get_max_hp(base_hp: int, level: int, iv: int) -> int:
        if base_hp == 1:
            return 1  # shedinja always has 1 hp
        else:
            return math.floor(((2 * base_hp + iv) * level) / 100) + level + 10
    
    # Formula:
    # X = ( [ ( 3M - 2H ) * G * C * B ] / 3M ) * L * S * D
    # If X >= 255: catch will succeed.

    G = 1       # grass modifier (unused?)
    C = 255     # catch rate
    B = 1       # ball bonus
    L = 1       # low-level modifier
    S = 1       # status
    D = 1       # difficulty

    # Critical capture formula:
    # CC = floor( [ min(255,X) * P * Ch] / 6 )
    # Capture chance = CC/256

    P = 0       # number of species caught
    Ch = 1      # catching charm

    # If X < 255: calculate Y from X
    # Formula:
    # Y = floor(65536 / [ (255/X) ** (3/16) ] )
    # Chance ball holds = Y / 65536
    #
    # Four checks:
    # ( Y / 65536 ) ** 4
    # ( X / 255 ) ** 0.75
    # 
    # Crit (one chance):
    # Y / 65536
    # ( X / 255 ) ** 0.1875
    # 
    # Overall chance (non-raid):
    # ( CC / 256 ) * ( X / 255 ) ** 0.1875 + ( 1 - CC / 256 ) * ( X / 255 ) ** 0.75
    
    #
    # Obtain pokemon catch rate from PokeApi.co
    #
    response = requests.get(f"https://pokeapi.co/api/v2/pokemon-species/{pokemon_name}/")
    
    if response.status_code == 200:
        C = int(response.json()["capture_rate"])
    else:
        print(f"Error: Failed to get capture rate for '{pokemon_name}'. Status code = {response.status_code}")
    
    #
    # Get ball bonus
    #
    if ball_type == Pokeball.GREAT_BALL:
        B = 1.5
    elif ball_type == Pokeball.ULTRA_BALL:
        B = 2
    elif ball_type == Pokeball.MASTER_BALL:
        return CatchProbability(
            CC_chance=0,
            CC_success=0,
            catch_chance=1,
            total_chance=1
        )
    elif ball_type == Pokeball.NET_BALL:
        response = requests.get(f"https://pokeapi.co/api/v2/pokemon/{pokemon_name}/")
        if response.status_code == 200:
            p_types = [x["type"]["name"] for x in response.json()["types"]]
            if "bug" in p_types or "water" in p_types:
                B = 3.5
        else:
            print(f"Error: Failed to obtain data for '{pokemon_name}'. Status code = {response.status_code}")
    elif ball_type == Pokeball.NEST_BALL:
        if pokemon_level < 31:
            B = ((41 - pokemon_level) / 10)
    elif ball_type == Pokeball.DIVE_BALL:
        if on_or_in_water:
            B = 3.5
    elif ball_type == Pokeball.REPEAT_BALL:
        if previously_caught:
            B = 3.5
    elif ball_type == Pokeball.TIMER_BALL:
        B = min(1 + (turn_count * 1229/4096), 4)  # max of 4
    elif ball_type == Pokeball.QUICK_BALL:
        if turn_count == 1:
            B = 5
    elif ball_type == Pokeball.DUSK_BALL:
        if night_or_cave:
            B = 3
    elif ball_type == Pokeball.FAST_BALL:
        response = requests.get(f"https://pokeapi.co/api/v2/pokemon/{pokemon_name}/")
        if response.status_code == 200:
            p_stats = response.json()["stats"]
            for p_stat in p_stats:
                if p_stat["stat"]["name"] == "speed":
                    if p_stat["base_stat"] >= 100:
                        B = 4
        else:
            print(f"Error: Failed to obtain data for '{pokemon_name}'. Status code = {response.status_code}")
    elif ball_type == Pokeball.LEVEL_BALL:
        if your_pokemon_level // 4 > pokemon_level:
            B = 8
        elif your_pokemon_level // 2 > pokemon_level:
            B = 4
        elif your_pokemon_level > pokemon_level:
            B = 2
    elif ball_type == Pokeball.LOVE_BALL:
        if opposite_gender and pokemon_name == your_pokemon_name:
            B = 8
    elif ball_type == Pokeball.MOON_BALL:
        moon_pkmn = [
            "skitty",
            "delcatty",
            "cleffa",
            "clefable",
            "clefairy",
            "jigglypuff",
            "igglybuff",
            "wigglytuff",
            "nidoran-m",
            "nidoran-f",
            "nidorino",
            "nidorina",
            "nidoking",
            "nidoqueen"
        ]
        if str.lower(pokemon_name) in moon_pkmn:
            B = 4
    elif ball_type == Pokeball.BEAST_BALL:
        ultra_beasts = [
            "nihilego",
            "buzzwole",
            "pheromosa",
            "xurkitree",
            "celesteela",
            "kartana",
            "guzzlord",
            "poipole",
            "naganadel",
            "stakataka",
            "blacephalon"
        ]
        if str.lower(pokemon_name) in ultra_beasts:
            B = 5
        else:
            B = 410/4096
    elif ball_type == Pokeball.DREAM_BALL:
        if status == Status.SLEEP or str.lower(pokemon_name) == "komala":
            B = 4
            
    #
    # Calc Low-Level Modifier
    #
    if pokemon_level < 21:
        L = (30 - pokemon_level) / 10
    
    #
    # Calc Status Modifier
    #
    if status is not Status.NONE:
        if status in [Status.SLEEP, Status.FROZEN] and str.lower(pokemon_name) != "komala":
            S = 2.5  # not applied to comatose
        elif status in [Status.POISON, Status.PARALYZE, Status.BURN]:
            S = 1.5
            
    #
    # Calc Difficulty Modifier
    #
    if not completed_main_story:
        if your_pokemon_level < pokemon_level:
            D = 410/4096

    #
    # Calc Critical Capture vars
    #
    if catching_charm:
        Ch = 2
        
    if pokedex_count > 600:
        P = 2.5
    elif pokedex_count in range(451, 601):
        P = 2
    elif pokedex_count in range(301, 451):
        P = 1.5
    elif pokedex_count in range(151, 301):
        P = 1
    elif pokedex_count in range(31, 151):
        P = 0.5
    else:
        P = 0

    #
    # Calc Final Capture Rates
    #
    response = requests.get(f"https://pokeapi.co/api/v2/pokemon/{pokemon_name}/")
    base_hp = 0
    if response.status_code == 200:
        p_stats = response.json()["stats"]
        for p_stat in p_stats:
            if p_stat["stat"]["name"] == "hp":
               base_hp = int(p_stat["base_stat"])
               break
    else:
        print(f"Error: Failed to obtain data for '{pokemon_name}'. Status code = {response.status_code}")
    
    #
    # Calc for all possible IVs
    #
    min_iv = 0
    current_CC_chance = current_CC_success = 0.0
    current_catch_chance = current_total_chance = 0.0
    current_wobble_probabilities = [0.0, 0.0, 0.0, 0.0]
    cp_list = []
    for iv in range(32):
        M = get_max_hp(base_hp=base_hp, level=pokemon_level, iv=iv)
        H = 1 if exactly_one_hp or M == 1 else math.floor((pokemon_hp_percent / 100) * M)
        
        X = (((3*M - 2*H) * G * C * B) / (3 * M)) * L * S * D
        
        #
        # Calc Critical Capture chance
        #
        CC = math.floor( ( min(255,X) * P * Ch ) / 6 )
        CC_chance = round(CC / 256, 5)
        CC_success = round(math.pow(X / 255, 0.1875), 5)
        
        #
        # Calc Break out attempts
        #
        Y = math.floor(65536 / (math.pow(255 / X, 3 / 16)))
        temp_wobble_probs = [0.0, 0.0, 0.0, 0.0]
        for wobble in range(4):
            temp_wobble_probs[wobble] = round((1 - CC_chance) * (1 - (Y / 65536)) * math.pow(Y / 65536, wobble), 5)
        
        #
        # Calc Overall Capture chance
        #
        catch_chance = round(math.pow(X / 255, 0.75), 5)
        overall_chance = round((CC_chance * CC_success) + ((1-CC_chance) * catch_chance), 5)
        
        if iv == 0:  # first run
            current_CC_chance = CC_chance
            current_CC_success = CC_success
            current_catch_chance = catch_chance
            current_total_chance = overall_chance
            current_wobble_probabilities = temp_wobble_probs[:]
        else:
            if current_CC_chance != CC_chance or \
               current_CC_success != CC_success or \
               current_catch_chance != catch_chance or \
               current_total_chance != overall_chance or \
               current_wobble_probabilities != temp_wobble_probs:  # different result
                cp_list.append(CatchProbability(
                    hp_iv_range=(min_iv, iv-1),
                    CC_chance=current_CC_chance,
                    CC_success=current_CC_success,
                    catch_chance=current_catch_chance,
                    total_chance=current_total_chance,
                    wobble_probabilities=WobbleProbability(
                        zero_wobbles=current_wobble_probabilities[0],
                        one_wobble=current_wobble_probabilities[1],
                        two_wobbles=current_wobble_probabilities[2],
                        three_wobbles=current_wobble_probabilities[3]
                    )
                ))
                min_iv = iv
                current_CC_chance = CC_chance
                current_CC_success = CC_success
                current_catch_chance = catch_chance
                current_total_chance = overall_chance
                current_wobble_probabilities = temp_wobble_probs[:]
            if iv == 31:
                cp_list.append(CatchProbability(
                    hp_iv_range=(min_iv, iv),
                    CC_chance=current_CC_chance,
                    CC_success=current_CC_success,
                    catch_chance=current_catch_chance,
                    total_chance=current_total_chance,
                    wobble_probabilities=WobbleProbability(
                        zero_wobbles=current_wobble_probabilities[0],
                        one_wobble=current_wobble_probabilities[1],
                        two_wobbles=current_wobble_probabilities[2],
                        three_wobbles=current_wobble_probabilities[3]
                    )
                ))
    
    return CatchCalcResult(
        catch_probabilities=cp_list
    )


result_obj = catch_calc_gen8(
    pokemon_name="beldum",
    pokemon_level=68,
    pokemon_hp_percent=1,
    your_pokemon_name="gallade",
    your_pokemon_level=81,
    status=Status.SLEEP,
    completed_main_story=True,
    pokedex_count=300,
    catching_charm=True,
    ball_type=Pokeball.ULTRA_BALL,
    exactly_one_hp=True
)

result = result_obj.average_probability()

print(f"CC={result.CC_chance}")
print(f"CC_success={result.CC_success}")
print(f"Catch={result.catch_chance}")
print(f"Total={result.total_chance}")
print(f"0:{result.wobble_probabilities.zero_wobbles}, 1:{result.wobble_probabilities.one_wobble}, 2:{result.wobble_probabilities.two_wobbles}, 3:{result.wobble_probabilities.three_wobbles}")

print(len(result_obj.catch_probabilities))
for cp in result_obj.catch_probabilities:
    print(f"IV: {cp.hp_iv_range[0]}-{cp.hp_iv_range[1]}")
