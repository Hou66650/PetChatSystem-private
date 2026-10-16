"""Local operator review; never exposed as a browser approval endpoint.

Export a private inspection bundle, inspect its photos/models and record each
stage with evidence. Reading/exporting does not initialize the Flask app or
interrupt running jobs. See docs/pet-quality-gates.md.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import sqlite3

spec = importlib.util.spec_from_file_location('pet_quality', Path(__file__).resolve().parents[1]/'app/pet_quality.py')
quality = importlib.util.module_from_spec(spec)
spec.loader.exec_module(quality)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--database', required=True, type=Path)
    sub = p.add_subparsers(dest='command', required=True)
    export = sub.add_parser('export')
    export.add_argument('--task', required=True)
    export.add_argument('--output', required=True, type=Path)
    review = sub.add_parser('review')
    review.add_argument('--manifest', required=True, type=Path)
    review.add_argument('--stage', choices=quality.STAGES, required=True)
    review.add_argument('--result', choices=('pass', 'fail', 'unknown'), required=True)
    review.add_argument('--notes', required=True)
    review.add_argument('--evidence', type=Path, nargs='+', required=True)
    args = p.parse_args()
    # rw refuses accidental creation at a misspelled database path.
    db = sqlite3.connect(args.database.resolve().as_uri()+('?mode=ro' if args.command=='export' else '?mode=rw'), uri=True)
    try:
        if args.command == 'export':
            db.execute('BEGIN')
            if not db.execute('SELECT 1 FROM pet_studio_tasks WHERE id=?', (args.task,)).fetchone():
                raise ValueError('档案不存在')
            args.output.mkdir(parents=True, exist_ok=False)
            manifest = {'schema': 1, 'task': args.task, 'fingerprints': quality.fingerprints(db, args.task), 'files': {}}
            for slot, raw in db.execute('SELECT slot,data FROM pet_studio_assets WHERE task=?', (args.task,)):
                if slot not in ('front','left','right','back','detail','model','adapted','blend'): continue
                name = slot + ('.glb' if slot in ('model','adapted') else '.blend' if slot=='blend' else '.jpg')
                (args.output/name).write_bytes(raw)
                manifest['files'][name] = quality.digest(raw)
            (args.output/'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
            print('Private inspection bundle:', args.output.resolve())
        else:
            manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
            for name, digest in manifest['files'].items():
                path = (args.manifest.parent/name).resolve()
                if path.parent != args.manifest.parent.resolve() or quality.digest(path.read_bytes()) != digest:
                    raise ValueError('审核包文件已变化，请重新导出')
            evidence = {'notes': args.notes, 'files': [
                {'name': f.name, 'sha256': quality.digest(f.read_bytes())} for f in args.evidence],
                'method': 'local-human-review', 'manifestSha256': quality.digest(args.manifest.read_bytes())}
            db.execute('BEGIN IMMEDIATE')
            # The deployment must have initialized the quality schema first.
            quality.record(db, manifest['task'], args.stage, manifest['fingerprints'][args.stage], args.result, evidence)
            db.commit()
            print(args.stage, args.result, '(does not equip or generate anything)')
    finally:
        db.close()


if __name__ == '__main__':
    main()
