"""Lossless format conversion for UE import; no image generation or repainting."""
from pathlib import Path
import hashlib
import json
from PIL import Image

repo = Path(__file__).resolve().parents[3]
out = repo / 'native/windows/Saved/Art/WebBackground'
out.mkdir(parents=True, exist_ok=True)
records = []
for name, theme in [('Cloud', 'cloud-sky-v1'), ('Mountain', 'mistwood-sky-v1'),
                    ('Sakura', 'realistic-sakura-sky-v1'), ('Snow', 'realistic-snow-sky-v1')]:
    source = repo / 'static/textures' / theme / 'day.webp'
    with Image.open(source) as image:
        assert image.size == (1672, 941), f'Review cover aspect before changing {source}'
        image.convert('RGB').save(out / (name + '.png'))
    records.append(dict(theme=name, source=source.relative_to(repo).as_posix(),
                        sha256=hashlib.sha256(source.read_bytes()).hexdigest()))
(out / 'sources.json').write_text(json.dumps(records, indent=2), encoding='utf-8')
print('Prepared four existing Web backgrounds for native import')
