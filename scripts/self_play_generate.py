# scripts\self_play_generate.py
import numpy as np
from engine.Plastic.Board import Board
from engine.Plastic.Objective import ObjectivePoint
from engine.Plastic.operative import Operative
from engine.eng_minimal import Game, GameConfig
from engine.env_rl import KTEnv, KTEnvConfig

def make_game(seed=123):
    board = Board()
    obj = ObjectivePoint("A", position=(381.0, 279.0), radius=45.4)
    board.add_terrain(obj)
    A1 = Operative("A1", team="A", position=(320.0, 279.0), base_radius_mm=16.0, ap=2, wounds=12, move=76.2)
    B1 = Operative("B1", team="B", position=(442.0, 279.0), base_radius_mm=16.0, ap=2, wounds=12, move=76.2)
    board.add_model(A1); board.add_model(B1)
    G = Game(board=board, objectives=[obj], teams=["A","B"], cfg=GameConfig(turning_points=2), seed=seed)
    # No controllers, no hooks for headless
    return G

def random_policy(mask):
    valid = np.flatnonzero(mask > 0)
    return int(np.random.choice(valid)) if len(valid) else 0

if __name__ == "__main__":
    G = make_game(seed=42)
    env = KTEnv(G, KTEnvConfig())
    obs, info = env.reset(seed=42)
    done = False
    traj = []
    while not done:
        a = random_policy(info["legal_mask"])  # replace with NN policy later
        obs, r, done, trunc, info = env.step(a)
        traj.append((a, r))
    print("episode reward:", sum(r for _, r in traj))