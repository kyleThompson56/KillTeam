# engine/eng_minimal.py
from collections import deque
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
import math
import random

from engine.Plastic.Board import Board
from engine.Plastic.operative import Operative
from engine.Plastic.Objective import ObjectivePoint
from engine.actions import Action, Move, Dash, Charge, Shoot, Fight, End, ScoutEnemyMovement
from typing import Callable, Any
from engine.geometry import INCH
from engine.loader import load_all_data
from engine.Plastic.Board import DIRECTIONS

STEP_MM = 3.0


@dataclass
class GameConfig:
    turning_points: int = 3
    move_cost_ap: int = 1
    dash_cost_ap: int = 1
    charge_cost_ap: int = 1
    shoot_cost_ap: int = 1
    fight_cost_ap: int = 1
    mission_cost_ap: int = 1
    move_budget_mm: float = 76.2  # default small step if movement stat missing
    seed: Optional[int] = None
    rng: random.Random = field(default_factory=random.Random)
    from engine.controllers import Controller
    controllers: dict[str, Controller] = field(default_factory=dict)  # team_name -> controller




@dataclass
class Game:
    board: Board
    objectives: List[ObjectivePoint]
    teams: List[str]  # e.g., ["A", "B"]
    cfg: GameConfig = field(default_factory=GameConfig)
    render_hook: Optional[Callable[[Optional[Operative], list[Action] | None], Any]] = None
    # NEW: a simple text logger function (e.g., gui.log)
    log_hook: Optional[Callable[[str], Any]] = None
    seed: Optional[int] = None
    rng: random.Random = field(default_factory=random.Random)
    selected_tac_ops: Dict[str, str] = field(default_factory=dict)
    GameState: str = field(default_factory=str)


    tp: int = 1
    current_team_idx: int = 0  # index into teams
    vp: Dict[str, int] = field(default_factory=dict)
    ap_remaining: Dict[Operative, int] = field(default_factory=dict)
    activated_this_tp: set = field(default_factory=set)

    # Initiative (2025) state
    reroll_card_team: Optional[str] = None  # team with one-time reroll card
    tp1_tie_adv_team: Optional[str] = None  # team that wins ties in TP1
    bonus_tokens: Dict[str, list[int]] = field(default_factory=dict)  # team -> list of available bonuses e.g., [1,2]
    losses_count: Dict[str, int] = field(default_factory=dict)  # team -> #times lost initiative (for awarding next value)

    def setup(self):
        if self.seed is not None:
            self.rng = random.Random(self.seed)
        self.vp = {t: 0 for t in self.teams}
        # Default controllers to Random if not supplied
        from engine.controllers import RandomController
        for t in self.teams:
            if t not in self.controllers:
                self.controllers[t] = RandomController()
        self._reset_tp_state()

    def _render(self, actor=None, legal=None):
        try:
            if self.render_hook:
                self.render_hook(actor, legal)
        except Exception:
            pass

    def _log(self, msg: str):
        # If a GUI/file log hook exists, use it exclusively; otherwise print to console
        try:
            if self.log_hook:
                self.log_hook(msg)
                return
        except Exception:
            # Fallback to console if GUI logging fails
            pass
        try:
            print(msg)
        except Exception:
            pass

    def _reset_tp_state(self):
        # AP refresh at the start of each Turning Point
        self.ap_remaining.clear()
        self.activated_this_tp.clear()
        for op in self.board.models:
            if op.is_alive():
                # Refresh to base AP each TP
                self.ap_remaining[op] = int(getattr(op, 'ap', 2))
            if hasattr(op, 'monitored_by'):
                del op.monitored_by

    def current_team(self) -> str:
        return self.teams[self.current_team_idx]

    def other_team(self) -> str:
        return self.teams[1 - self.current_team_idx]

    def living_team_ops(self, team: str) -> List[Operative]:
        return [op for op in self.board.models if op.team == team and op.is_alive()]

    def can_act(self, op: Operative) -> bool:
        return op.is_alive() and self.ap_remaining.get(op, 0) > 0 and op.team == self.current_team()

    def _engaged(self, op: Operative) -> bool:
        enemy_team = next(t for t in self.teams if t != op.team)
        for enemy in self.living_team_ops(enemy_team):
            dx = enemy.position[0] - op.position[0]
            dy = enemy.position[1] - op.position[1]
            rsum = getattr(enemy, 'radius_mm', 0) + getattr(op, 'radius_mm', 0) + INCH
            if dx * dx + dy * dy <= rsum * rsum:
                return True
        return False

    def get_valid_destinations(self, actor, action_type: str) -> set[tuple[float, float]]:
        max_range = {
            "dash": 76.2,
            "charge": actor.movement + 50.8,
            "reposition": actor.movement,
            "fallback": actor.movement,
        }.get(action_type, 0.0)

        source_radius = float(getattr(actor, "radius_mm", 0.0) or 0.0)
        legal = set()
        enemies = [e for e in self.board.models if e.team != actor.team and e.is_alive()]

        # --- Charge logic ---
        if action_type == "charge":
            if actor.order == "Conceal":
                return set()

            for enemy in enemies:
                target_radius = float(getattr(enemy, "radius_mm", 0.0) or 0.0)
                threshold = source_radius + target_radius + 25.4
                ex, ey = enemy.position

                step_i = max(1, int(round(STEP_MM)))
                for dx in range(-int(threshold), int(threshold) + 1, step_i):
                    for dy in range(-int(threshold), int(threshold) + 1, step_i):
                        px = round(ex + dx, 1)
                        py = round(ey + dy, 1)
                        if math.hypot(px - ex, py - ey) > threshold:
                            continue

                        pos = (px, py)
                        if not self.board.can_place_model(actor, pos):
                            continue
                        if not self.board.find_path(actor, pos, max_range):
                            continue
                        if self.board.control_range_point_to_operative(pos, source_radius, enemy):
                            legal.add(pos)

            return legal

        # --- Fallback pre-check ---
        if action_type == "fallback" and not self._engaged(actor):
            return set()

        # --- BFS for dash, reposition, fallback ---
        visited = set()
        queue = deque([actor.position])
        visited.add(actor.position)

        while queue:
            pos = queue.popleft()

            dx = pos[0] - actor.position[0]
            dy = pos[1] - actor.position[1]
            dist = math.hypot(dx, dy)
            if dist > max_range:
                continue

            if not self.board.can_place_model(actor, pos):
                continue

            # Fallback: must break engagement
            if action_type == "fallback":
                if pos == actor.position:
                    pass  # allow expansion from engaged tile
                elif any(self.board.control_range_point_to_operative(pos, source_radius, e) for e in enemies):
                    continue

            # Dash and Reposition: must not enter engagement
            elif action_type in ["dash", "reposition"]:
                if any(self.board.control_range_point_to_operative(pos, source_radius, e) for e in enemies):
                    continue

            # Only check path once tile is otherwise valid
            if not self.board.find_path(actor, pos, max_range):
                continue

            if action_type != "fallback" or pos != actor.position:
                legal.add(pos)

            for dx in [-STEP_MM, 0, STEP_MM]:
                for dy in [-STEP_MM, 0, STEP_MM]:
                    if dx == 0 and dy == 0:
                        continue
                    neighbor = (round(pos[0] + dx, 1), round(pos[1] + dy, 1))
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append(neighbor)

        return legal

    # ---- Actions ----
    def act_reposition(self, actor: Operative, dest: tuple[float, float]) -> bool:
        if not self.can_act(actor) or self.ap_remaining[actor] < 1:
            return False

        if math.hypot(dest[0] - actor.position[0], dest[1] - actor.position[1]) > actor.movement:
            return False

        if not self.board.find_path(actor, dest, actor.movement):
            return False

        actor.move_to(dest)

        if any(self.board.control_range(actor, enemy) for enemy in self.living_team_ops(self.other_team())):
            return False

        self.ap_remaining[actor] -= 1
        self.activated_this_tp.add(actor)
        self._log(f"[MOVE] {actor.name} repositions to {dest}")
        return True

    def act_dash(self, actor: Operative, dest: tuple[float, float]) -> bool:
        dash_cost = 0 if "free_dash" in actor.passives else 1
        if not self.can_act(actor) or self.ap_remaining[actor] < dash_cost:
            return False

        if math.hypot(dest[0] - actor.position[0], dest[1] - actor.position[1]) > 76.2:
            return False

        if not self.board.find_path(actor, dest, 76.2):
            return False

        actor.move_to(dest)

        if any(self.board.control_range(actor, enemy) for enemy in self.living_team_ops(self.other_team())):
            return False

        self.ap_remaining[actor] -= dash_cost
        self.activated_this_tp.add(actor)
        self._log(f"[MOVE] {actor.name} dashes to {dest} (cost {dash_cost} AP)")
        return True

    def act_charge(self, actor: Operative, dest: tuple[float, float]) -> bool:

        if actor.order == "Conceal":
            return False
        if not self.can_act(actor) or self.ap_remaining[actor] < 1:
            return False

        if any(self.board.control_range(actor, enemy) for enemy in self.living_team_ops(self.other_team())):
            return False

        max_range = actor.movement + 50.8
        if math.hypot(dest[0] - actor.position[0], dest[1] - actor.position[1]) > max_range:
            return False

        if not self.board.find_path(actor, dest, max_range):
            return False

        actor.move_to(dest)

        if not any(self.board.control_range(actor, enemy) for enemy in self.living_team_ops(self.other_team())):
            return False

        self.ap_remaining[actor] -= 1
        self.activated_this_tp.add(actor)
        self._log(f"[MOVE] {actor.name} charges to {dest}")
        return True

    def act_fallback(self, actor: Operative, dest: tuple[float, float]) -> bool:
        if not self.can_act(actor) or self.ap_remaining[actor] < 2:
            return False

        if not any(self.board.control_range(actor, enemy) for enemy in self.living_team_ops(self.other_team())):
            return False

        if math.hypot(dest[0] - actor.position[0], dest[1] - actor.position[1]) > actor.movement:
            return False

        if not self.board.find_path(actor, dest, actor.movement):
            return False

        actor.move_to(dest)

        self.ap_remaining[actor] -= 2
        self.activated_this_tp.add(actor)
        self._log(f"[MOVE] {actor.name} falls back to {dest}")
        return True

    def legal_move_targets(self, op: Operative) -> List[Tuple[float, float]]:
        return self.board.legal_steps(op, self.cfg.move_budget_mm)

    def act_shoot(self, attacker: Operative, defender: Operative) -> Optional[int]:
        # Returns damage dealt or None if action invalid
        if attacker.order == "Conceal":
            return None
        if not self.can_act(attacker) or self.ap_remaining[attacker] < self.cfg.shoot_cost_ap:
            return None
        if not defender.is_alive() or attacker.team == defender.team:
            return None
        if not self.is_valid_target(attacker, defender):
            return None
        # Minimal fixed weapon profile
        dmg = self._fixed_ranged_attack(attacker, defender)
        self.ap_remaining[attacker] -= self.cfg.shoot_cost_ap
        self.activated_this_tp.add(attacker)
        # NEW: log outcome
        try:
            self._log(f"[RESULT] {attacker.name} shoots {defender.name} for {dmg} dmg (HP now {getattr(defender,'hp','?')})")
        except Exception:
            pass
        return dmg

    def _fixed_ranged_attack(self, attacker: Operative, defender: Operative) -> int:
        # 4 dice hitting on 4+, flat 3 dmg per hit; no saves for v0
        import random
        hits = sum(1 for _ in range(4) if random.randint(1,6) >= 4)
        dmg = 3 * hits
        defender.take_damage(dmg, Game)
        return dmg

    def act_fight(self, attacker: Operative, defender: Operative) -> Optional[int]:
        if not self.can_act(attacker) or self.ap_remaining[attacker] < self.cfg.fight_cost_ap:
            return None
        if not defender.is_alive() or attacker.team == defender.team:
            return None
        if not self.board.control_range(attacker, defender):
            return None

        # Basic melee resolution: 4 dice hitting on 4+, 3 dmg per hit
        hits = sum(1 for _ in range(4) if self.rng.randint(1, 6) >= 4)
        dmg = 3 * hits
        defender.take_damage(dmg)

        self.ap_remaining[attacker] -= self.cfg.fight_cost_ap
        self.activated_this_tp.add(attacker)

        # Log outcome
        try:
            self._log(
                f"[RESULT] {attacker.name} fights {defender.name} for {dmg} dmg (HP now {getattr(defender, 'hp', '?')})")
        except Exception:
            pass

        return dmg

    def end_activation(self):
        # Advance turn to the other team
        self.current_team_idx = 1 - self.current_team_idx

    def end_of_tp_scoring(self):
        # Objective control scoring
        for obj in self.objectives:
            ctrl = self.board.controller_of_objective(obj)
            if ctrl is not None:
                self.vp[ctrl] = self.vp.get(ctrl, 0) + 1

        # Tac Ops scoring
        from engine.Plastic.TacOps.TacOps import score_martyr, score_track_enemy, score_dominate, score_scout_enemy_movement

        for team, tacop in self.selected_tac_ops.items():
            if tacop == "Martyr":
                score_martyr(self, team)
            elif tacop == "Track Enemy":
                score_track_enemy(self, team)
            elif tacop == "Dominate":
                score_dominate(self, team)
            elif tacop == "Scout Enemy Movement":
                score_scout_enemy_movement(self, team)

    def all_ops_spent_or_dead(self) -> bool:
        # Both teams have no AP left on any living operative
        for team in self.teams:
            for op in self.living_team_ops(team):
                if self.ap_remaining.get(op, 0) > 0:
                    return False
        return True

    def _initiative_roll_off(self) -> str:
        """Implements 2025 initiative: d6 roll until someone wins; TP1 loser gets reroll card and TP1 tie advantage.
        Loser of each TP gains a cumulative bonus token (+1 then +2 then +3) that can be spent in any future roll.
        Auto-spend heuristic: spend the smallest set of tokens (if any) needed to flip a loss into a win; otherwise keep.
        Returns the team that wins initiative for the current TP.
        """
        # Ensure state maps are initialized
        for t in self.teams:
            self.bonus_tokens.setdefault(t, [])
            self.losses_count.setdefault(t, 0)
        # Determine spending for this roll (both sides may spend)
        def total_available(team: str) -> int:
            return sum(self.bonus_tokens.get(team, []))
        def spend_min_to_win(my_roll: int, opp_roll: int, team: str) -> int:
            # Sort tokens ascending and spend minimally to exceed opp_roll - my_roll
            need = max(0, opp_roll - my_roll + 1)
            if need <= 0:
                return 0
            tokens = sorted(self.bonus_tokens.get(team, []))
            used = 0
            acc = 0
            for v in tokens:
                acc += v
                used += 1
                if acc >= need:
                    # remove first 'used' tokens
                    for _ in range(used):
                        self.bonus_tokens[team].remove(tokens.pop(0))
                    return acc
            return 0  # not enough to flip
        # Reroll card applies only once and the holder wins ties in TP1. We'll apply TP1 tie rule outside the loop when needed.
        # Roll until someone wins
        winner: Optional[str] = None
        applied_tie_adv = False
        while winner is None:
            r0 = self.rng.randint(1,6)
            r1 = self.rng.randint(1,6)
            team0, team1 = self.teams[0], self.teams[1]
            # Consider auto-spend for both sides (simulate simultaneous spending)
            # Copy tokens to decide spending but mutate only when spending occurs
            s0 = spend_min_to_win(r0, r1, team0)
            s1 = spend_min_to_win(r1, r0, team1)
            a0 = r0 + s0
            a1 = r1 + s1
            self._log(f"[INIT] Rolls: {team0} {r0}+{s0} vs {team1} {r1}+{s1}")
            if a0 > a1:
                winner = team0
            elif a1 > a0:
                winner = team1
            else:
                # Tie handling: On TP1, the team with tp1_tie_adv_team wins ties
                if self.tp == 1 and self.tp1_tie_adv_team in (team0, team1) and not applied_tie_adv:
                    winner = self.tp1_tie_adv_team
                    applied_tie_adv = True
                else:
                    # If someone has a reroll card, allow them to reroll once; prefer the non-winner side if both have
                    reroll_team = self.reroll_card_team
                    if reroll_team:
                        self._log(f"[INIT] Tie — {reroll_team} uses reroll card")
                        # consume the card
                        self.reroll_card_team = None
                        # Continue loop to reroll both dice
                        continue
                    # Otherwise roll again
                    continue
        # Award a bonus token to the loser for future TPs
        loser = self.teams[0] if winner == self.teams[1] else self.teams[1]
        self.losses_count[loser] = int(self.losses_count.get(loser, 0)) + 1
        k = self.losses_count[loser]
        if k <= 3:
            self.bonus_tokens[loser].append(k)  # +1 then +2 then +3
            self._log(f"[INIT] {loser} gains a +{k} initiative bonus token (banked)")
        # If this is TP1, the loser also gains the reroll card and tie-advantage for TP1
        if self.tp == 1:
            self.reroll_card_team = loser
            self.tp1_tie_adv_team = loser
            self._log(f"[INIT] {loser} receives reroll card and TP1 tie-advantage")
        return winner

    def _set_initiative_order(self, winner: str):
        # current_team_idx is the index in self.teams of the team that will act first this TP
        self.current_team_idx = self.teams.index(winner)
        self._log(f"[INIT] TP {self.tp} initiative: {winner} will act first")

    def initialize_game(self, mode: str = "player_vs_ai")->GameState:
        self._log("[INIT] Which team would you like to play?")

    def play_turning_point(self):
        # Initiative at start of TP
        init_winner = self._initiative_roll_off()
        self._set_initiative_order(init_winner)
        self._reset_tp_state()
        while not self.all_ops_spent_or_dead():
            team = self.current_team()
            actor = next((op for op in self.living_team_ops(team) if self.ap_remaining.get(op, 0) > 0), None)
            if actor is None:
                self.end_activation()
                self._render()  # update view after activation switch
                continue
            legal = self.legal_actions_for(actor)
            self._render(actor, legal if team in self.controllers and hasattr(self.controllers[team],
                                                                              'select_action') else None)
            ctrl = self.controllers[team]
            # NEW: pre-action context
            self._log(f"[TURN] TP {self.tp} — Team {team} acting: {actor.name} (AP {self.ap_remaining.get(actor,0)})")

            action = ctrl.select_action(self, actor, legal)

            # NEW: describe the chosen action (guess source by controller class name)
            try:
                source = "HUMAN" if ctrl.__class__.__name__.lower().startswith("gui") else "AI"
                desc = None
                if isinstance(action, Move):
                    dx, dy = action.dest
                    desc = f"Move to ({dx:.1f}, {dy:.1f})"
                elif isinstance(action, Shoot):
                    desc = f"Shoot target #{action.target_id}"
                elif isinstance(action, End):
                    desc = "End Activation"
                if desc:
                    self._log(f"[{source}] {actor.name} -> {desc}")
            except Exception:
                pass

            spent = self.apply_action(actor, action)
            self._render()  # reflect the result
            if not spent or self.ap_remaining.get(actor, 0) == 0:
                self.end_activation()
                self._render()
        self.end_of_tp_scoring()
        self.tp += 1

    def play_game(self) -> Dict[str, int]:
        self.setup()
        while self.tp <= self.cfg.turning_points and all(self.living_team_ops(t) for t in self.teams):
            self.play_turning_point()
        return dict(self.vp)

    def _model_index(self, m):
        # Simple way to expose ids to Shoot actions
        return self.board.models.index(m)

    def legal_actions_for(self, op) -> list[Action]:
        if not self.can_act(op):
            return [End()]

        actions: list[Action] = []

        # Movement actions by mode
        for mode in ["dash", "reposition", "charge", "fallback"]:
            for dest in self.get_valid_destinations(op, mode):
                actions.append(Move(dest, mode=mode))

        # Shooting actions (only if not engaged)
        if not self._engaged(op):
            for enemy in self.living_team_ops(self.other_team()):
                if self.is_valid_target(op, enemy):
                    actions.append(Shoot(target=enemy))

        # Fight actions (only if engaged)
        if self._engaged(op):
            for enemy in self.living_team_ops(self.other_team()):
                if self.is_valid_target(op, enemy):
                    actions.append(Fight(target=enemy))

        actions.append(End())
        return actions

    def apply_action(self, op, action: Action) -> bool:
        # Returns True if any AP was spent or activation advanced
        if isinstance(action, Move):
            mode = getattr(action, "mode", "dash")  # default to "dash" if missing

            if mode == "dash":
                if self.board.move_model(op, action.dest, max_distance_mm=76.2):
                    self._log(f"{op.name} dashes to {action.dest}")
                    self.ap_remaining[op] -= 1
                    return True

            elif mode == "reposition":
                if self.board.move_model(op, action.dest, max_distance_mm=op.movement):
                    self._log(f"{op.name} repositions to {action.dest}")
                    self.ap_remaining[op] -= 1
                    return True


            elif mode == "charge":
                if self.board.move_model(op, action.dest, max_distance_mm=op.movement + 50.8):
                    self._log(f"{op.name} charges to {action.dest}")
                    self.ap_remaining[op] -= 1
                    return True

                else:
                    self._log(f"{op.name} failed to move via charge")
                    return False


            elif mode == "fallback":
                if self.board.move_model(op, action.dest, max_distance_mm=op.movement):
                    self._log(f"{op.name} falls back to {action.dest}")
                    self.ap_remaining[op] -= 2  # fallback usually costs 2 AP
                    return True

            self._log(f"{op.name} failed to move via {mode}")
            return False

        elif isinstance(action, Shoot):
            target = action.target
            dmg = self.act_shoot(op, target)
            return dmg is not None

        elif isinstance(action, End):
            self.end_activation()
            return True

        elif isinstance(action, ScoutEnemyMovement):
            target = self.board.models[action.target]
            if self.tp == 1:
                return False
            if op.order == "Engage":
                return False
            if any(self.board.control_range(op, enemy) for enemy in self.living_team_ops(self.other_team())):
                return False
            if not self.board.has_los(op, target):
                return False
            dx = op.position[0] - target.position[0]
            dy = op.position[1] - target.position[1]
            if dx * dx + dy * dy <= 152.4 * 152.4:
                return False

            op.monitored_by = op.team
            self.ap_remaining[op] -= self.cfg.mission_cost_ap
            self.activated_this_tp.add(op)
            self._log(f"[TACOP] {op.name} scouts {target.name} for movement tracking")
            return True

        return False

    def is_valid_target(self, attacker, target):
        if not target.is_alive() or attacker.team == target.team:
            return False
        if target.order == "Conceal" and self.board.is_in_cover(target):
            return False
        return self.board.has_los(attacker, target)