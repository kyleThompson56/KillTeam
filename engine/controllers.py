# engine/controllers.py
from typing import Protocol, List
import random
from engine.actions import Action, Move, Dash, Charge, Shoot, Fight, End

class Controller(Protocol):
    def select_action(self, game, operative, legal_actions: List[Action]) -> Action: ...

class RandomController:
    def __init__(self, seed: int = 42):
        self._rng = random.Random(seed)
    def select_action(self, game, operative, legal_actions):
        # Pick any legal action; prefers Shoot if available
        if not legal_actions:
            return End()
        shoots = [a for a in legal_actions if isinstance(a, Shoot)]
        if shoots:
            return shoots[0]
        try:
            return self._rng.choice(legal_actions)
        except Exception:
            return End()

class HumanCLIController:
    def select_action(self, game, operative, legal_actions):
        # Very basic console prompt; replace with GUI later
        print(f"\n[{operative.team}] {operative.name} AP={game.ap_remaining.get(operative,0)} @ {operative.position}")
        for i, a in enumerate(legal_actions):
            if isinstance(a, Move):
                print(f"  {i}) Move -> {a.dest}")
            elif isinstance(a, Shoot):
                try:
                    target = game.board.models[a.target_id]
                    print(f"  {i}) Shoot -> {target.name} [{target.team}] HP={getattr(target,'hp','?')}")
                except Exception:
                    print(f"  {i}) Shoot -> target #{getattr(a,'target_id','?')}")
            else:
                print(f"  {i}) End activation")
        while True:
            try:
                raw = input("Choose action #: ")
                idx = int(raw)
                if 0 <= idx < len(legal_actions):
                    return legal_actions[idx]
            except Exception:
                pass
            print("Invalid selection. Try again.")
            
class NNController(Controller):
    def __init__(self, policy):
        self.policy = policy  # callable(obs, mask)-> index
    def select_action(self, game, op, legal):
        from engine.env_rl import KTEnv, KTEnvConfig
        # Build a temporary env view for observation
        env_like = KTEnv(game, KTEnvConfig())
        obs = env_like._obs()
        mask = env_like.legal_mask()  # np.ndarray of length max_actions with 1s for legal prefixes
        # Count legal choices as the number of 1s in the mask (prefix semantics)
        n = int(mask.sum()) if hasattr(mask, 'sum') else int(sum(mask))
        if n <= 0:
            return End()
        try:
            idx = int(self.policy(obs, mask))
        except Exception:
            return End()
        # Clamp/validate index; map into the provided legal set
        if idx < 0 or idx >= n:
            return End()
        # Ensure we don't index past the provided legal list
        if idx >= len(legal):
            return End()
        return legal[idx]