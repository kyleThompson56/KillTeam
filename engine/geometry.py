# engine/geometry.py (new, tiny file)
INCH = 25.4

def circle_vs_aabb_overlap(center, r, aabb):
    cx, cy = center
    minx, miny, maxx, maxy = aabb
    qx = min(max(cx, minx), maxx)
    qy = min(max(cy, miny), maxy)
    dx = cx - qx
    dy = cy - qy
    return (dx*dx + dy*dy) <= (r*r)

def aabb_of_polygon(verts):
    xs = [x for x, _ in verts]
    ys = [y for _, y in verts]
    return (min(xs), min(ys), max(xs), max(ys))

def segment_intersects_aabb(p0, p1, aabb, samples=32):
    minx, miny, maxx, maxy = aabb
    for i in range(1, samples):
        t = i / samples
        x = p0[0] + t * (p1[0] - p0[0])
        y = p0[1] + t * (p1[1] - p0[1])
        if (minx <= x <= maxx) and (miny <= y <= maxy):
            return True
    return False