"""Server collision validation uses the same measured layout as browser routing."""
import json
import math
from pathlib import Path

LAYOUT = json.loads((Path(__file__).resolve().parents[2] / 'static/models/paw-commons-v2/navigation.json').read_text(encoding='utf-8'))

FACILITIES = {f['id']: f for f in LAYOUT.get('facilities', [])}

def facility_length(f):
    return sum(math.hypot(b[0]-a[0], b[2]-a[2]) for a, b in zip(f['path'], f['path'][1:]))

def facility_sample(f, progress):
    distance = max(0, min(facility_length(f), progress))
    for i, (a, b) in enumerate(zip(f['path'], f['path'][1:])):
        n = math.hypot(b[0]-a[0], b[2]-a[2])
        if distance <= n or i == len(f['path'])-2:
            t = min(1, distance/n)
            return dict(x=a[0]+(b[0]-a[0])*t, y=a[1]+(b[1]-a[1])*t,
                        z=a[2]+(b[2]-a[2])*t, yaw=math.atan2(b[0]-a[0], b[2]-a[2]))
        distance -= n


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
