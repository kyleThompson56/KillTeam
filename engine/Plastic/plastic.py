# engine/Plastic/plastic.py
class Plastic:
    def __init__(self, name, position, footprint=None, radius_mm=None):
        self.name = name
        self.position = position  # (x, y) in mm
        self.footprint = footprint  # optional polygon [(dx, dy), ...]
        self.radius_mm = radius_mm  # optional circle radius

    def distance_to(self, point):
        cx, cy = self.position
        px, py = point
        return ((cx - px) ** 2 + (cy - py) ** 2) ** 0.5

    def contains_point(self, point):
        # Prefer circle if defined; fall back to polygon vertices proximity
        if self.radius_mm is not None:
            return self.distance_to(point) <= self.radius_mm
        if self.footprint:
            cx, cy = self.position
            # Very naive polygon check: treat vertices as samples
            # Replace with point-in-polygon if needed.
            px, py = point
            for dx, dy in self.footprint:
                if abs((cx + dx) - px) < 1 and abs((cy + dy) - py) < 1:
                    return True
        return False

    def overlaps_circle(self, center, radius):
        # Circle-circle overlap if we have a radius, else conservative check
        if self.radius_mm is not None:
            return self.distance_to(center) <= (self.radius_mm + radius)
        # If polygon: coarse check via vertex samples
        cx, cy = center
        if self.footprint:
            ox, oy = self.position
            rr = radius * radius
            for dx, dy in self.footprint:
                vx, vy = ox + dx, oy + dy
                if (vx - cx) * (vx - cx) + (vy - cy) * (vy - cy) <= rr:
                    return True
        return False

    def get_absolute_vertices(self):
        # Keep this for terrain polygons; no rotation.
        if not self.footprint:
            return []
        cx, cy = self.position
        return [(cx + dx, cy + dy) for dx, dy in self.footprint]