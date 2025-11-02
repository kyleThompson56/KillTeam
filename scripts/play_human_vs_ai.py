# scripts\play_human_vs_ai.py
from engine.Plastic.Board import Board
from engine.Plastic.Objective import ObjectivePoint
from engine.Plastic.operative import Operative
from engine.eng_minimal import Game, GameConfig
from engine.controllers import RandomController
from engine.gui_tk import GuiController

board = Board()
obj = ObjectivePoint("A", position=(381.0, 279.0), radius=45.4)
board.add_terrain(obj)

# Simple deployment near center
A1 = Operative("A1", team="A", position=(320.0, 279.0), base_radius_mm=16.0, ap=2, wounds=12, move=76.2)
B1 = Operative("B1", team="B", position=(442.0, 279.0), base_radius_mm=16.0, ap=2, wounds=12, move=76.2)
board.add_model(A1); board.add_model(B1)

G = Game(board=board, objectives=[obj], teams=["A", "B"], cfg=GameConfig(turning_points=2))

gui = GuiController(board)
G.controllers = {"A": gui, "B": RandomController(seed=7)}

# NEW: send engine log lines to the GUI panel
G.log_hook = gui.log

# Optional: keep your render hook
try:
    G.render_hook = lambda actor=None, legal=None: gui.draw_board(actor, legal)
except AttributeError:
    pass

vp = G.play_game()
print("Final VP:", vp)