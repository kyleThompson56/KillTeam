# tests/test_play_minigame.py
from engine.Plastic.Board import Board
from engine.Plastic.operative import Operative
from engine.Plastic.Objective import ObjectivePoint
from engine.eng_minimal import Game, GameConfig

# Build board
board = Board(width_mm=762.0, height_mm=558.8)
obj_mid = ObjectivePoint("A", position=(381.0, 279.0), radius=45.4)
board.add_terrain(obj_mid)

# Deploy two teams (simple, opposing edges)
A1 = Operative("A1", team="A", position=(100.0, 279.0), base_radius_mm=16.0, ap=2, wounds=12, move=76.2)
A2 = Operative("A2", team="A", position=(130.0, 279.0), base_radius_mm=16.0, ap=2, wounds=12, move=76.2)
B1 = Operative("B1", team="B", position=(662.0, 279.0), base_radius_mm=16.0, ap=2, wounds=12, move=76.2)
B2 = Operative("B2", team="B", position=(632.0, 279.0), base_radius_mm=16.0, ap=2, wounds=12, move=76.2)
for op in [A1, A2, B1, B2]:
    board.add_model(op)

# Run game
G = Game(board=board, objectives=[obj_mid], teams=["A", "B"], cfg=GameConfig(turning_points=2))
result = G.play_game()
print("Final VP:", result)