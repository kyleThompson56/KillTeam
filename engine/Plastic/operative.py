# engine/Plastic/operative.py
from typing import List, Dict, Any
import csv
from .plastic import Plastic

# Common base-size (diameter) to radius(mm) mapping. Adjust as you prefer.
BASE_RADIUS_BY_SIZE = {
    25: 12.5,
    28: 14.0,
    32: 16.0,
    40: 20.0,
    50: 25.0,
    60: 30.0,
    80: 40.0,
}

class Operative(Plastic):
    """Unified in-play unit. Replaces `Model` and the older dataclass.

    Can be constructed directly (e.g., for tests) or via a CSV row using
    `spawn_operative_from_row` below.
    """
    def __init__(
        self,
        name: str,
        team: str,
        position: tuple[float, float],
        base_radius_mm: float | None = None,
        *,
        base_size: int | None = None,
        ap: int = 2,
        wounds: int = 10,
        move: float = 100.0,
        save: int = 3,
        is_icon_bearer: bool = False,
        abilities: List[str] | None = None,
        passives: List[str] | None = None,
        weapons: List[str] | None = None,
        tags: List[str] | None = None,
        order: str = "Engage"
    ):
        # Resolve radius from either explicit base_radius_mm or base_size
        self.order = order
        if base_radius_mm is None and base_size is not None:
            base_radius_mm = BASE_RADIUS_BY_SIZE.get(int(base_size), 16.0)
        if base_radius_mm is None:
            # Sensible default if nothing provided (32mm base)
            base_radius_mm = 16.0

        super().__init__(name, position, footprint=None, radius_mm=float(base_radius_mm))

        # Core identity and stats
        self.team = team
        self.ap = int(ap)
        self.hp = int(wounds)
        self.movement = float(move)
        self.save = int(save)
        self.is_icon_bearer = bool(is_icon_bearer)

        # Keywordy lists
        self.abilities = abilities or []
        self.passives = passives or []
        self.weapons = weapons or []
        self.tags = tags or []

    # --- Runtime helpers (moved from Model) ---
    def move_to(self, new_position: tuple[float, float]):
        self.position = new_position

    def take_damage(self, amount: int, game):
        self.hp = max(0, int(self.hp) - int(amount))
        if self.hp == 0:
            game.last_incapacitated = self  # pass game context or use callback

    def is_alive(self) -> bool:
        return self.hp > 0

    def effective_ap(self) -> int:
        """AP plus +1 if this operative is an icon bearer (by flag or tags)."""
        icon = self.is_icon_bearer \
               or ("icon_bearer" in self.tags) \
               or ("icon_bearer" in self.abilities) \
               or ("icon_bearer" in self.passives)
        return int(self.ap) + (1 if icon else 0)

# --- CSV helpers kept for data loading (non-breaking) ---

def _parse_bool(value: Any) -> bool:
    s = str(value).strip().lower()
    return s in {"1", "true", "yes", "y"}


def load_all_operatives(csv_path: str) -> List[Dict[str, Any]]:
    """Loads rows from CSV as dicts (unchanged behavior) with cleaned types.

    Use `spawn_operative_from_row(row, position)` to create an in-play Operative.
    """
    operatives: List[Dict[str, Any]] = []
    with open(csv_path, newline='', encoding='utf-8-sig') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            operative = {
                "name": row.get("name", ""),
                "team": row.get("team", ""),
                "ap": int(row["ap"]) if row.get("ap") not in (None, "") else 2,
                "wounds": int(row["wounds"]) if row.get("wounds") not in (None, "") else 10,
                "move": float(row["move"]) if row.get("move") not in (None, "") else 100.0,
                "save": int(row["save"]) if row.get("save") not in (None, "") else 3,
                "passives": [s for s in (row.get("passives", "") or "").split(".") if s] if "." in (row.get("passives", "") or "") else ([s for s in (row.get("passives", "") or "").split(",") if s]),
                "weapons": [s for s in (row.get("weapons", "") or "").split(",") if s],
                "abilities": [s for s in (row.get("abilities", "") or "").split(",") if s],
                "base_size": int(row["base_size"]) if row.get("base_size") not in (None, "") else 32,
                # Proper boolean parsing (bool("False") would be True otherwise)
                "is_icon_bearer": _parse_bool(row.get("is_icon_bearer", "")),
            }
            operatives.append(operative)
    return operatives


def filter_operatives_by_team(all_operatives: List[Dict[str, Any]], selected_teams: List[str]):
    team_rosters: Dict[str, List[Dict[str, Any]]] = {team: [] for team in selected_teams}
    for op in all_operatives:
        if op.get("team") in selected_teams:
            team_rosters[op["team"]].append(op)
    return team_rosters


def spawn_operative_from_row(row: Dict[str, Any], position: tuple[float, float]) -> Operative:
    """Factory: turn a CSV row (as returned by `load_all_operatives`) into an in-play Operative."""
    return Operative(
        name=row.get("name", "Unnamed"),
        team=row.get("team", ""),
        position=position,
        base_radius_mm=BASE_RADIUS_BY_SIZE.get(int(row.get("base_size", 32)), 16.0),
        ap=int(row.get("ap", 2)),
        wounds=int(row.get("wounds", 10)),
        move=float(row.get("move", 100.0)),
        save=int(row.get("save", 3)),
        is_icon_bearer=bool(row.get("is_icon_bearer", False)) if isinstance(row.get("is_icon_bearer"), bool) else _parse_bool(row.get("is_icon_bearer", "")),
        abilities=list(row.get("abilities", [])),
        passives=list(row.get("passives", [])),
        weapons=list(row.get("weapons", [])),
    )