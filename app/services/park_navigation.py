"""Server collision validation uses the same measured layout as browser routing."""
import json
import math
from pathlib import Path

LAYOUT = json.loads((Path(__file__).resolve().parents[2] / 'static/models/paw-commons-v2/navigation.json').read_text(encoding='utf-8'))


def inside(x, z):
    return (math.isfinite(x) and math.isfinite(z)
            and (x / LAYOUT['ellipse']['x']) ** 2 + (z / LAYOUT['ellipse']['z']) ** 2 <= 1 + 1e-9
            and all(math.hypot(x-o['x'], z-o['z']) >= o['radius']-1e-9 for o in LAYOUT['obstacles']))


def segment(ax, az, bx, bz):
    if not inside(ax, az) or not inside(bx, bz):
        return False
    dx, dz = bx-ax, bz-az
    length = dx*dx + dz*dz
    for o in LAYOUT['obstacles']:
        t = max(0, min(1, ((o['x']-ax)*dx + (o['z']-az)*dz)/length)) if length else 0
        if math.hypot(ax+t*dx-o['x'], az+t*dz-o['z']) < o['radius']-1e-9:
            return False
    return True
