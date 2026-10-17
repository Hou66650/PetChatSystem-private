"""Copy approved existing high-detail exports; never redesign or overwrite masters."""
import argparse
import hashlib
import json
import shutil
from pathlib import Path

parser=argparse.ArgumentParser()
parser.add_argument('--source',type=Path,required=True)
args=parser.parse_args()
project=Path(__file__).resolve().parents[1]
for theme in ('snow','camp'):
    source=args.source/theme
    report=json.loads((source/'build-report.json').read_text(encoding='utf-8'))
    out=project/'Saved/Art/CinematicIslands'/theme
    out.mkdir(parents=True,exist_ok=True)
    for module in report['modules']:
        src=source/module['file']
        assert hashlib.sha256(src.read_bytes()).hexdigest()==module['sha256'],src
        dest=out/src.name
        if dest.exists():
            assert hashlib.sha256(dest.read_bytes()).hexdigest()==module['sha256'],dest
        else:
            shutil.copy2(src,dest)
    report['original_source']=str(source)
    (out/'manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(theme, 'verified and staged', len(report['modules']), 'existing modules')
