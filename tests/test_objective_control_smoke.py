# tests/test_objective_control_smoke.py
from engine.Plastic.Board import Board
from engine.Plastic.Objective import ObjectivePoint
from engine.Plastic.operative import Operative
from engine.geometry import INCH

board = Board()
obj = ObjectivePoint("A", position=(381, 279), radius=45.4)
board.add_terrain(obj)

# APL tie → contested
A = Operative("A1", team="A", position=(381 + 45.4 + 10, 279), base_radius_mm=16, ap=2, is_icon_bearer=True)
B = Operative("B1", team="B", position=(381 + 45.4 + 20, 279), base_radius_mm=16, ap=3)
board.add_model(A); board.add_model(B)
assert set(m.name for m in board.models_within_objective_ring(obj, INCH)) == {"A1", "B1"}
assert board.controller_of_objective(obj) is None

# Move B out → A controls
board.move_model(B, (381 + 45.4 + 60, 279))
assert board.controller_of_objective(obj) == "A"