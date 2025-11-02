class Hatchway:
    def __init__(self, name, position, is_closed=True):
        self.name = name
        self.position = position  # (x, y) in mm
        self.is_closed = is_closed

    def open(self):
        self.is_closed = False

    def close(self):
        self.is_closed = True

    def blocks_movement(self):
        return self.is_closed

    def distance_to(self, point):
        hx, hy = self.position
        px, py = point
        return ((hx - px) ** 2 + (hy - py) ** 2) ** 0.5
