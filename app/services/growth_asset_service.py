"""Apply the public stage manifest to server-owned travel and desktop appearances."""
import json
from pathlib import Path

from ..config import BASE_DIR
from ..db import get_db
from . import growth_service as growth

MANIFEST = Path(BASE_DIR) / 'static' / 'data' / 'pet-growth-models.json'


def manifest():
    return json.loads(MANIFEST.read_text(encoding='utf-8'))


def apply_stage(owner, pet, spec):
    if spec.get('custom'):
        return spec
    profile = growth.get(get_db(), owner, int(pet))
    if not profile or not growth.enabled(get_db(), owner):
        return spec
    appearance = growth.appearance(profile)
    item = next((value for value in manifest()['stages']
                 if value['pet'] == int(pet) and value['stage'] == appearance['stage']), None)
    if not item:
        return spec
    identity = spec.get('coat', 'default')
    asset = item['assets'].get(identity) or item['assets'].get('default')
    if not asset:
        spec['growthFallback'] = 'appearance-unsupported'
        return spec
    spec['model'] = asset['path']
    spec['height'] = item['height']
    spec['growthStage'] = item['stage']
    spec['growthKey'] = f"{pet}:{item['stage']}:{identity}"
    return spec
