# engine/Plastic/Board.py
from collections import deque

from .Hatchway import Hatchway
from engine.geometry import INCH
from engine.geometry import segment_intersects_aabb
import math


STEP_MM = 10.0
DIRECTIONS = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)]

class Board:


    def __init__(self, width_mm: float = 762.0, height_mm: float = 558.8):
        """Default to ~30" x 22" (in mm)."""
        self.width = float(width_mm)
        self.height = float(height_mm)
        self.models = []   # List of in-play models (instances with .position, .radius_mm, .team, .ap, etc.)
        self.terrain = []  # Objectives, walls, hatchways, etc.
        # tuning for visibility sampling
        self._vis_samples = 16
        self._vis_nudge_mm = 0.1

    def add_model(self, model):
        self.models.append(model)

    def add_terrain(self, obj):
        self.terrain.append(obj)

    def can_place_model(self, model, pos) -> bool:
        x, y = pos
        r = float(getattr(model, 'radius_mm', 0.0) or 0.0)
        # Board bounds
        if not (r <= x <= self.width - r and r <= y <= self.height - r):
            return False
        # No overlap with other models
        for other in self.models:
            if other is model:
                continue
            ro = float(getattr(other, 'radius_mm', 0.0) or 0.0)
            dx = other.position[0] - x
            dy = other.position[1] - y
            if dx*dx + dy*dy <= (r + ro) * (r + ro):
                return False
        # (Optional) add wall collision checks later
        return True

    def move_model(self, model, new_pos, max_distance_mm: float | None = None) -> bool:
        if max_distance_mm is not None:
            dx = new_pos[0] - model.position[0]
            dy = new_pos[1] - model.position[1]
            if math.hypot(dx, dy) > float(max_distance_mm):
                return False
        if self.can_place_model(model, new_pos):
            model.move_to(new_pos)
            return True
        return False

    def find_path(self, actor, dest: tuple[float, float], max_dist) -> bool:
        """Fast path check with straight-line stepping; falls back to BFS only if needed.

        - First, verify Euclidean distance within max_dist; if not, early reject.
        - Then, attempt to 'walk' along the straight line from start to dest in STEP_MM increments,
          requiring every intermediate point to be placeable. This is O(range/STEP_MM) and very fast.
        - If the straight line is blocked (typically by other models) but the destination might still be
          reachable around them, fall back to a lightweight BFS on the STEP_MM grid.
        """
        start = actor.position
        dx = dest[0] - start[0]
        dy = dest[1] - start[1]
        direct_dist = math.hypot(dx, dy)
        if direct_dist > float(max_dist):
            return False

        # Ensure destination is placeable
        if not self.can_place_model(actor, dest):
            return False

        # Try straight-line stepping (discrete sampling along the segment)
        if direct_dist <= 1e-6:
            return True
        steps = max(1, int(direct_dist // STEP_MM))
        step_x = dx / steps
        step_y = dy / steps
        cx, cy = start
        straight_clear = True
        for _ in range(steps):
            cx += step_x
            cy += step_y
            if not self.can_place_model(actor, (cx, cy)):
                straight_clear = False
                break
        if straight_clear:
            return True

        # Fall back to BFS on a coarse grid
        visited = set([start])
        queue = deque([(start, 0.0)])  # (position, distance_so_far)
        while queue:
            pos, dist = queue.popleft()

            # Close enough to destination and within movement budget
            if math.hypot(pos[0] - dest[0], pos[1] - dest[1]) <= STEP_MM and dist <= max_dist:
                return True

            for dx_i, dy_i in DIRECTIONS:
                nx = pos[0] + dx_i * STEP_MM
                ny = pos[1] + dy_i * STEP_MM
                new_pos = (nx, ny)
                if new_pos in visited:
                    continue

                step_dist = math.hypot(nx - pos[0], ny - pos[1])
                total_dist = dist + step_dist
                if total_dist > max_dist:
                    continue

                if self.can_place_model(actor, new_pos):
                    visited.add(new_pos)
                    queue.append((new_pos, total_dist))

        return False

    def models_within_objective_ring(self, objective, band_mm: float = INCH):
        """Return models whose base is within `band_mm` of the objective’s circumference.
        Uses condition: abs(D - R_obj) <= r_model + band_mm
        """
        cx, cy = objective.position
        R = getattr(objective, 'radius', getattr(objective, 'radius_mm', 0)) or 0
        results = []
        for m in self.models:
            if hasattr(m, 'is_alive') and not m.is_alive():
                continue
            mx, my = m.position
            r = getattr(m, 'radius_mm', 0) or 0
            D = ((mx - cx) ** 2 + (my - cy) ** 2) ** 0.5
            if abs(D - R) <= (r + band_mm):
                results.append(m)
        return results

    def controller_of_objective(self, objective, band_mm: float = INCH):
        """Determine controller by summing AP of models within 1" of the objective circumference.
        Ties are contested (return None). Incapacitated models do not contribute.
        Accepts models that expose `ap` or `apl` (falls back to 0 if missing).
        """
        eligible = self.models_within_objective_ring(objective, band_mm=band_mm)
        if not eligible:
            return None

        ap_by_team = {}
        for m in eligible:
            team = getattr(m, 'team', None)
            if not team:
                continue
            # Use whichever the model exposes: prefer 'apl', then 'ap', else 0
            ap_base = getattr(m, 'apl', getattr(m, 'ap', 0))
            icon = getattr(m, 'is_icon_bearer', False) or ('icon_bearer' in getattr(m, 'abilities', [])) or (
                        'icon_bearer' in getattr(m, 'passives', [])) or ('icon_bearer' in getattr(m, 'tags', []))
            ap_val = int(ap_base) + (1 if icon else 0)
            try:
                ap = int(ap_val)
            except (ValueError, TypeError):
                ap = 0
            ap_by_team[team] = ap_by_team.get(team, 0) + ap

        if not ap_by_team:
            return None

        # Determine best; ties are contested
        best_team = max(ap_by_team, key=ap_by_team.get)
        best_val = ap_by_team[best_team]
        tie = sum(1 for v in ap_by_team.values() if v == best_val) > 1
        return None if tie else best_team

    def legal_steps(self, operative, remaining_mm: float):
        cx, cy = operative.position
        legal = []
        for dx, dy in DIRECTIONS:
            nx = cx + dx * STEP_MM
            ny = cy + dy * STEP_MM
            if math.hypot(nx - cx, ny - cy) <= remaining_mm and self.can_place_model(operative, (nx, ny)):
                legal.append((nx, ny))
        return legal

    def _segment_blocked_by_terrain(self, p0, p1) -> bool:
        """Return True if segment p0->p1 intersects any active blocking AABB."""
        for terr in self.terrain:
            aabb = getattr(terr, 'aabb', None)
            is_active = getattr(terr, 'is_active', True)
            if callable(aabb) and is_active:
                if segment_intersects_aabb(p0, p1, terr.aabb()):
                    return True
        return False

    def has_los(self, attacker, defender, samples: int = None, nudge_mm: float = None) -> bool:
        """LOS exists if the attacker's center can see any point on the defender's base.

        - samples: number of sample points around the defender's base circumference.
        - nudge_mm: small inward shift of the target point along the ray to avoid
          grazing false-positives when a ray just touches a wall edge.
        """
        samples = samples or self._vis_samples
        nudge_mm = nudge_mm or self._vis_nudge_mm
        p0 = attacker.position
        cx, cy = defender.position
        r = float(getattr(defender, 'radius_mm', 0.0) or 0.0)
        if r <= 0.0:
            # Fallback: no base radius, behave like center-to-center
            return not self._segment_blocked_by_terrain(p0, (cx, cy))

        # Sample points on the defender's circumference
        two_pi = 2.0 * math.pi
        for i in range(samples):
            theta = two_pi * (i / samples)
            tx = cx + r * math.cos(theta)
            ty = cy + r * math.sin(theta)

            # Nudge the target point slightly towards the attacker to avoid
            # classifying tangential contacts as blocked due to AABB edges.
            dx = tx - p0[0]
            dy = ty - p0[1]
            L = math.hypot(dx, dy) or 1.0
            ntx = tx - (dx / L) * nudge_mm
            nty = ty - (dy / L) * nudge_mm

            if not self._segment_blocked_by_terrain(p0, (ntx, nty)):
                return True  # Found at least one visible point on the base

        return False

    def is_in_cover(self, defender) -> bool:
        """Simplified light cover: defender's base overlaps any terrain AABB band within ~1".
        Terrain pieces provide cover if within 1" of the base edge.
        """
        cx, cy = defender.position
        r = float(getattr(defender, 'radius_mm', 0.0) or 0.0)
        pad = r + INCH
        for terr in self.terrain:
            aabb_fn = getattr(terr, 'aabb', None)
            is_active = getattr(terr, 'is_active', True)
            if callable(aabb_fn) and is_active:
                minx, miny, maxx, maxy = aabb_fn()
                # Quick check: center within padded box bounds
                if (minx - pad) <= cx <= (maxx + pad) and (miny - pad) <= cy <= (maxy + pad):
                    return True
        return False



    def is_obscured(self, attacker, defender) -> bool:
        """Simplified obscured: some (but not all) sample rays are blocked by terrain."""
        samples = self._vis_samples
        nudge_mm = self._vis_nudge_mm
        p0 = attacker.position
        cx, cy = defender.position
        r = float(getattr(defender, 'radius_mm', 0.0) or 0.0)
        if r <= 0.0:
            # Center-to-center
            return self._segment_blocked_by_terrain(p0, (cx, cy))
        two_pi = 2.0 * math.pi
        blocked = 0
        for i in range(samples):
            theta = two_pi * (i / samples)
            tx = cx + r * math.cos(theta)
            ty = cy + r * math.sin(theta)
            dx = tx - p0[0]
            dy = ty - p0[1]
            L = math.hypot(dx, dy) or 1.0
            ntx = tx - (dx / L) * nudge_mm
            nty = ty - (dy / L) * nudge_mm
            if self._segment_blocked_by_terrain(p0, (ntx, nty)):
                blocked += 1
        # If at least one ray is blocked and not all rays are blocked, consider obscured
        return 0 < blocked < samples

    def control_range(self, op1, op2) -> bool:
        """Returns True if op1 and op2 are within 1 inch (25.4mm) of each other, and terrain does not block the path."""
        dx = op1.position[0] - op2.position[0]
        dy = op1.position[1] - op2.position[1]
        dist_sq = dx * dx + dy * dy
        threshold = op1.radius_mm + op2.radius_mm + 25.4

        if dist_sq > threshold * threshold:
            return False

        # Terrain blocking check — assumes terrain has a method like blocks_path(p1, p2)
        for terrain_piece in self.terrain:
            if terrain_piece.blocks_path(op1.position, op2.position):
                return False

        return True

    def control_range_point_to_operative(self, pos: tuple[float, float], source_radius: float, target_op) -> bool:
        """
        Returns True if `pos` is within 1 inch (25.4mm) of the edge of `target_op`'s base,
        accounting for the source's own base radius. Terrain must not block the path.
        """
        px, py = pos
        tx, ty = target_op.position
        tr = float(getattr(target_op, "radius_mm", 0.0) or 0.0)

        dx = px - tx
        dy = py - ty
        dist_sq = dx * dx + dy * dy

        threshold = source_radius + tr + 25.4
        if dist_sq > threshold * threshold:
            return False

        for terrain_piece in self.terrain:
            if hasattr(terrain_piece, "blocks_path") and terrain_piece.blocks_path(pos, target_op.position):
                return False

        return True
