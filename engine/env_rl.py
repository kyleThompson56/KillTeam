# engine/env_rl.py
from dataclasses import dataclass
from typing import Tuple, Dict, Any, List
import numpy as np

from engine.eng_minimal import Game
from engine.actions import Move, Shoot, End, Action

MAX_ACTIONS = 128  # pad/truncate legal sets

@dataclass
class KTEnvConfig:
    max_actions: int = MAX_ACTIONS
    reward_damage: float = 0.1        # per damage dealt
    reward_kill: float = 1.0          # bonus when target dies
    reward_vp: float = 2.0            # per VP delta at end of TP
    reward_step: float = -0.01        # small time penalty

class KTEnv:
    def __init__(self, game: Game, cfg: KTEnvConfig = KTEnvConfig()):
        self.G = game
        self.cfg = cfg
        self._last_vp = None
        self._cached_legal: List[Action] = []

    # ---- Public API ----
    def reset(self, seed: int | None = None):
        if seed is not None:
            self.G.seed = seed
        self.G.tp = 1
        self.G.setup()
        self._last_vp = dict(self.G.vp)
        obs = self._obs()
        info = {"legal_mask": self.legal_mask()}
        return obs, info

    def step(self, action_idx: int):
        legal = self._legal_actions()
        if not legal:
            # no actions: end activation
            action = End()
        else:
            idx = int(action_idx)
            if idx < 0 or idx >= min(len(legal), self.cfg.max_actions):
                # invalid index -> treat as End()
                action = End()
            else:
                action = legal[idx]
        # Apply action to current actor
        actor = self._current_actor()
        reward = self.cfg.reward_step
        pre_hp = self._hp_snapshot()

        spent = self.G.apply_action(actor, action)
        # If actor spent AP to 0, engine already ends activation inside apply/end logic
        # but eng_minimal’s play loop handles activation switching. Here we emulate a single decision-step then refresh state.

        # Compute incremental reward signals
        reward += self._reward_damage_delta(pre_hp)
        reward += self._reward_kills(pre_hp)

        # If end of TP occurred (detect via AP map reset heuristics), add VP delta
        # Simpler: recompute VP on demand when no AP left anywhere
        if self.G.all_ops_spent_or_dead():
            self.G.end_of_tp_scoring()
            reward += self._reward_vp_delta()
            self.G.tp += 1
            # Reset TP state for next TP unless game ended
            if self._game_continues():
                self.G._reset_tp_state()

        terminated = not self._game_continues()
        truncated = False
        obs = self._obs()
        info = {"legal_mask": self.legal_mask(), "actor": getattr(actor, 'name', None)}
        return obs, reward, terminated, truncated, info

    # ---- Helpers ----
    def _game_continues(self) -> bool:
        if self.G.tp > self.G.cfg.turning_points:
            return False
        return all(self.G.living_team_ops(t) for t in self.G.teams)

    def _current_actor(self):
        team = self.G.current_team()
        return next((op for op in self.G.living_team_ops(team)
                     if self.G.ap_remaining.get(op, 0) > 0), None)

    def _legal_actions(self) -> List[Action]:
        actor = self._current_actor()
        if actor is None:
            return [End()]
        legal = self.G.legal_actions_for(actor)
        self._cached_legal = legal[:self.cfg.max_actions]
        return self._cached_legal

    def legal_mask(self) -> np.ndarray:
        n = len(self._legal_actions())
        mask = np.zeros(self.cfg.max_actions, dtype=np.float32)
        mask[:min(n, self.cfg.max_actions)] = 1.0
        return mask

    def _hp_snapshot(self) -> Dict[int, int]:
        return {i: getattr(m, 'hp', 0) for i, m in enumerate(self.G.board.models)}

    def _reward_damage_delta(self, pre_hp: Dict[int,int]) -> float:
        post = self._hp_snapshot()
        delta = 0
        for i in pre_hp:
            delta += max(0, pre_hp[i] - post[i])
        return self.cfg.reward_damage * float(delta)

    def _reward_kills(self, pre_hp: Dict[int,int]) -> float:
        post = self._hp_snapshot()
        bonus = 0.0
        for i, m in enumerate(self.G.board.models):
            if pre_hp[i] > 0 and post[i] <= 0:
                bonus += self.cfg.reward_kill
        return bonus

    def _reward_vp_delta(self) -> float:
        r = 0.0
        for t in self.G.teams:
            before = self._last_vp.get(t, 0)
            after = self.G.vp.get(t, 0)
            r += self.cfg.reward_vp * float(after - before)
        self._last_vp = dict(self.G.vp)
        return r

    # ---- Observation encoding ----
    def _obs(self) -> Dict[str, np.ndarray]:
        # Keep it simple and explicit; you can switch to a single flat vector later
        board = self.G.board
        models = board.models
        # per-model tensor: [x, y, r, team_onehot(2), hp, ap, is_alive]
        M = len(models)
        obs_models = np.zeros((M, 8), dtype=np.float32)
        for i, m in enumerate(models):
            x, y = m.position
            team_onehot = [1.0 if m.team == self.G.current_team() else 0.0,
                           1.0 if m.team == self.G.other_team() else 0.0]
            obs_models[i] = [x, y, getattr(m, 'radius_mm', 0.0),
                             team_onehot[0], team_onehot[1],
                             float(getattr(m, 'hp', 0)),
                             float(self.G.ap_remaining.get(m, 0)),
                             1.0 if m.is_alive() else 0.0]
        # objectives: [x, y, r]
        O = len(self.G.objectives)
        obs_objs = np.zeros((O, 3), dtype=np.float32)
        for i, obj in enumerate(self.G.objectives):
            x, y = obj.position
            obs_objs[i] = [x, y, obj.radius]
        turn = np.array([float(self.G.tp), 1.0 if self.G.current_team() == self.G.teams[0] else 0.0], dtype=np.float32)
        mask = self.legal_mask()
        return {"models": obs_models, "objectives": obs_objs, "turn": turn, "mask": mask}