# demo_objective_control.py
from engine.Plastic.Board import Board
from engine.Plastic.Objective import ObjectivePoint
from engine.Plastic.operative import Operative
from engine.geometry import INCH

board = Board()
obj = ObjectivePoint("A", position=(381, 279), radius=45.4)
board.add_terrain(obj)

# Two models on different teams
mA = Operative("PM1", team="A", position=(381 + 45.4 + 10, 279), base_radius_mm=16, ap=2, is_icon_bearer=True)
mB = Operative("IM1", team="B", position=(381 + 45.4 + 20, 279), base_radius_mm=16, ap=3)
board.add_model(mA)
board.add_model(mB)

# Both should be within 1" of circumference (abs(D-R) <= r + 25.4)
print("Eligible:", [m.name for m in board.models_within_objective_ring(obj, INCH)])
print("Controller:", board.controller_of_objective(obj))  # Expect tie/None: A has 2+1(icon)=3 vs B 3

# Move B farther out so only A controls
board.move_model(mB, (381 + 45.4 + 60, 279))
print("Controller after B moves out:", board.controller_of_objective(obj))  # Expect "A"