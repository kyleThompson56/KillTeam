# engine/Plastic/terrain.py
from .plastic import Plastic

class Wall(Plastic):
    def __init__(self, name, position, width_mm, height_mm, is_active=True):
        # Centered AABB as polygon footprint for compatibility
        w2, h2 = width_mm/2, height_mm/2
        footprint = [(-w2, -h2), (w2, -h2), (w2, h2), (-w2, h2)]
        super().__init__(name, position, footprint=footprint)
        self.is_active = is_active

    def get_absolute_vertices(self):
        return super().get_absolute_vertices() if self.is_active else []

    def aabb(self):
        # returns (minx, miny, maxx, maxy)
        ox, oy = self.position
        verts = self.get_absolute_vertices()
        xs = [x for x, _ in verts]
        ys = [y for _, y in verts]
        return (min(xs), min(ys), max(xs), max(ys))

    def blocks_path(self, p1: tuple[float, float], p2: tuple[float, float]) -> bool:
        """Returns True if this terrain piece blocks the straight path between p1 and p2."""
        # Simple bounding box check for now
        return self.intersects_line(p1, p2)

    def intersects_line(self, p1: tuple[float, float], p2: tuple[float, float]) -> bool:
        """
        Returns True if the straight line from p1 to p2 intersects this terrain's footprint.
        Assumes terrain has a polygonal footprint defined as a list of (x, y) vertices.
        """
        if not hasattr(self, 'footprint') or not self.footprint:
            return False  # No footprint to check against

        def ccw(a, b, c):
            return (c[1] - a[1]) * (b[0] - a[0]) > (b[1] - a[1]) * (c[0] - a[0])

        def segments_intersect(a, b, c, d):
            return ccw(a, c, d) != ccw(b, c, d) and ccw(a, b, c) != ccw(a, b, d)

        # Check line segment (p1, p2) against each edge of the terrain footprint
        vertices = self.footprint
        n = len(vertices)
        for i in range(n):
            edge_start = vertices[i]
            edge_end = vertices[(i + 1) % n]
            if segments_intersect(p1, p2, edge_start, edge_end):
                return True

        return False