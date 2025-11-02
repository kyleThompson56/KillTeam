from .plastic import Plastic


class Interactable(Plastic):
    def __init__(self, name, position, radius, interactable=True):
        super().__init__(name, position, radius)
        self.interactable = interactable  # Can be toggled off for passive terrain

    def is_active(self):
        return self.hp is None or self.hp > 0