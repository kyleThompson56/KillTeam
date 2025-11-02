# engine/actions.py
from dataclasses import dataclass
from typing import Tuple, Optional
from engine.Plastic.operative import Operative

# Movement actions
@dataclass()
class Move:
    def __init__(self, dest: tuple[float, float], mode: str = "dash"):
        self.dest = dest
        self.mode = mode

@dataclass(frozen=True)
class Reposition:
    dest: Tuple[float, float]


@dataclass(frozen=True)
class Dash:
    dest: Tuple[float, float]  # fixed 3" (76.2mm)

@dataclass(frozen=True)
class Charge:
    dest: Tuple[float, float]  # up to movement + 2"

@dataclass(frozen=True)
class Fallback:
    dest: Tuple[float, float]  # up to ~2" to break engagement

# Combat actions
@dataclass(frozen=True)
class Shoot:
    target: Operative  # index into board.models or a stable id you assign
    weapon_name: Optional[str] = None  # optional explicit weapon; defaults to first ranged weapon

@dataclass(frozen=True)
class Fight:
    target: Operative
    weapon_name: Optional[str] = None  # optional explicit melee weapon; defaults to first melee weapon

# Mission/utility actions
@dataclass(frozen=True)
class MissionAction:
    objective_id: int

#dataclass(frozen=True)
class ScoutEnemyMovement:
    target: Operative

# Utility
@dataclass(frozen=True)
class End:
    pass

Action = Reposition | Dash | Charge | Fallback | Shoot | Fight | MissionAction | End