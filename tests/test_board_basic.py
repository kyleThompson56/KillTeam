from engine.Plastic.Board import Board
from engine.Plastic.terrain import Wall
from engine.Plastic.operative import Operative

board = Board(200, 200)
A = Operative("A", team="T1", position=(50, 50), base_radius_mm=16)
B = Operative("B", team="T2", position=(80, 50), base_radius_mm=16)
board.add_model(A); board.add_model(B)

# Overlap move should fail
assert not board.can_place_model(A, B.position)

# LOS blocked by wall
w = Wall("W", position=(100, 50), width_mm=10, height_mm=60, is_active=True)
board.add_terrain(w)
assert hasattr(board, 'has_los')
assert board.has_los(A, B) is False