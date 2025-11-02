# engine/combat_minimal.py
import random

FIXED_WEAPON = {
    'attacks': 4, 'hit_on': 4, 'damage': (3, 4)  # normal, crit ignored for now
}

def roll_attack(board, attacker, defender, rng=random):
    if not board.has_los(attacker, defender):
        return 0
    hits = sum(1 for _ in range(FIXED_WEAPON['attacks']) if rng.randint(1,6) >= FIXED_WEAPON['hit_on'])
    dmg = hits * FIXED_WEAPON['damage'][0]
    defender.take_damage(dmg)
    return dmg