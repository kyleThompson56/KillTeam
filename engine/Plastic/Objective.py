# engine/Plastic/Objective.py
from .Interactable import Interactable

class ObjectivePoint(Interactable):
    def __init__(self, name, position, radius=45.4):
        super().__init__(name, position, radius=radius, interactable=True)
        self.radius = radius
        self.captured_by = None