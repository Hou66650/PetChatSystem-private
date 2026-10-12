#!/usr/bin/env python3
"""Create H.264, audio-free clips only from rows explicitly marked approved."""
from __future__ import annotations
import argparse, csv, json, subprocess
from pathlib import Path


def main() -> int:
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("reviewed_csv")
    ap.add_argument("--output", required=True)
    ap.add_argument("--metadata", required=True)
    ap.add_argument("--overwrite", action="store_true")
    args=ap.parse_args()
    out=Path(args.output).expanduser().resolve(); out.mkdir(parents=True,exist_ok=True)
    metadata_path=Path(args.metadata).expanduser().resolve(); metadata_path.parent.mkdir(parents=True,exist_ok=True)
    rows=list(csv.DictReader(Path(args.reviewed_csv).open(encoding="utf-8-sig")))
    approved=[r for r in rows if r.get("status","").strip().lower()=="approved"]
    if not approved:
        raise SystemExit("No rows have status=approved; review candidates before materializing clips.")
    header=["sample_id","person_id","label_code","label_name","file_path","speed","scene","lighting","camera","resolution","fps","duration_seconds","handedness","quality","reviewer","review_status","recorded_at","notes"]
    new_meta=[]; counters={}
    for r in approved:
        person=r["person_id"].strip(); label=r["label_code"].strip().upper()
        if not person.startswith("P") or not label:
            raise ValueError(f"Missing anonymous person_id or label_code: {r}")
        key=(person,label); counters[key]=counters.get(key,0)+1
        sample_id=f"{person}_{label}_{counters[key]:03d}_{r.get('speed','normal') or 'normal'}"
        label_dir=out/(r.get("label_folder") or label)/person; label_dir.mkdir(parents=True,exist_ok=True)
        target=label_dir/f"{sample_id}.mp4"
        if target.exists() and not args.overwrite:
            raise FileExistsError(f"Refusing to overwrite {target}")
        start=float(r["start"]); end=float(r["end"])
        cmd=["ffmpeg","-hide_banner","-loglevel","error","-y" if args.overwrite else "-n",
             "-ss",f"{start:.3f}","-to",f"{end:.3f}","-i",r["source"],
             "-map","0:v:0","-c:v","libx264","-preset","medium","-crf","20","-pix_fmt","yuv420p","-an",str(target)]
        subprocess.run(cmd,check=True)
        new_meta.append([sample_id,person,label,"",str(target),r.get("speed","normal"),"","","","","",round(end-start,3),"","pending","","approved","",r.get("notes","")])
    exists=metadata_path.exists() and metadata_path.stat().st_size>0
    with metadata_path.open("a",newline="",encoding="utf-8-sig") as fh:
        wr=csv.writer(fh)
        if not exists: wr.writerow(header)
        wr.writerows(new_meta)
    print(json.dumps({"approved":len(approved),"created":len(new_meta),"output":str(out),"audio_removed":True},ensure_ascii=False))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
