#!/usr/bin/env python3
"""Analyze full-session sign videos without modifying originals.

Outputs per-video motion CSV/SVG/contact sheet plus a JSON report and a combined
candidate_segments.csv. Candidate cuts always require human review.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
import subprocess
from dataclasses import dataclass, asdict
from pathlib import Path

import cv2
import numpy as np

VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}


def infer_label(path: Path) -> tuple[str, str]:
    for part in reversed(path.parts):
        if part.upper() == "UNKNOWN":
            return "UNKNOWN", "UNKNOWN"
        match = re.match(r"^(SL\d{2})_", part, re.IGNORECASE)
        if match:
            return match.group(1).upper(), part
    return "", ""


@dataclass
class Segment:
    start: float
    end: float
    peak_time: float
    peak_motion: float
    status: str = "needs_review"


def video_paths(inputs: list[str]) -> list[Path]:
    found: list[Path] = []
    for raw in inputs:
        p = Path(raw).expanduser().resolve()
        if p.is_file() and p.suffix.lower() in VIDEO_EXTS:
            found.append(p)
        elif p.is_dir():
            found.extend(x for x in p.rglob("*") if x.is_file() and x.suffix.lower() in VIDEO_EXTS)
        else:
            raise FileNotFoundError(raw)
    return sorted(set(found))


def ffprobe(path: Path) -> dict:
    cmd = ["ffprobe", "-v", "error", "-show_entries",
           "format=duration,size:stream=index,codec_type,codec_name,width,height,r_frame_rate",
           "-of", "json", str(path)]
    try:
        return json.loads(subprocess.check_output(cmd, text=True))
    except (FileNotFoundError, subprocess.CalledProcessError, json.JSONDecodeError):
        return {}


def close_gaps(mask: np.ndarray, max_gap: int) -> np.ndarray:
    out = mask.copy()
    false_runs = runs(~out)
    for a, b in false_runs:
        if a > 0 and b < len(out) and b - a <= max_gap:
            out[a:b] = True
    return out


def runs(mask: np.ndarray) -> list[tuple[int, int]]:
    padded = np.r_[False, mask, False].astype(np.int8)
    edges = np.diff(padded)
    starts = np.flatnonzero(edges == 1)
    ends = np.flatnonzero(edges == -1)
    return list(zip(starts.tolist(), ends.tolist()))


def detect_segments(times: np.ndarray, motion: np.ndarray, fps: float,
                    min_motion_s: float, merge_gap_s: float, pad_s: float,
                    max_segment_s: float) -> tuple[list[Segment], dict]:
    if len(motion) < 3:
        return [], {"baseline": 0.0, "low_threshold": 0.0, "high_threshold": 0.0}
    window = max(1, int(round(fps * 0.16)))
    kernel = np.ones(window, dtype=np.float32) / window
    smooth = np.convolve(motion, kernel, mode="same")
    baseline = float(np.percentile(smooth, 25))
    p90 = float(np.percentile(smooth, 90))
    spread = max(p90 - baseline, float(np.std(smooth)) * 0.35, 0.05)
    low = baseline + 0.18 * spread
    high = baseline + 0.48 * spread
    active = close_gaps(smooth >= low, max(1, int(round(merge_gap_s * fps))))
    min_frames = max(2, int(round(min_motion_s * fps)))
    candidates: list[tuple[int, int]] = []
    for a, b in runs(active):
        if b - a < min_frames or float(np.max(smooth[a:b])) < high:
            continue
        candidates.append((a, b))
    pad = int(round(pad_s * fps))
    merged: list[tuple[int, int]] = []
    for a, b in candidates:
        a, b = max(0, a - pad), min(len(times), b + pad)
        if merged and a <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], b))
        else:
            merged.append((a, b))
    segments: list[Segment] = []
    for a, b in merged:
        peak = a + int(np.argmax(smooth[a:b]))
        status = "needs_review"
        if times[min(b - 1, len(times) - 1)] - times[a] > max_segment_s:
            status = "needs_manual_split"
        segments.append(Segment(round(float(times[a]), 3),
                                round(float(times[min(b - 1, len(times) - 1)]), 3),
                                round(float(times[peak]), 3),
                                round(float(smooth[peak]), 4), status))
    return segments, {"baseline": baseline, "low_threshold": low,
                      "high_threshold": high, "p90": p90, "smooth": smooth}


def save_svg(path: Path, times: np.ndarray, values: np.ndarray, thresholds: dict,
             segments: list[Segment]) -> None:
    w, h, m = 1200, 360, 45
    vmax = max(float(np.max(values)), thresholds["high_threshold"], 1e-6)
    duration = max(float(times[-1]), 1e-6)
    def xy(t: float, v: float) -> tuple[float, float]:
        return m + t / duration * (w - 2*m), h - m - v / vmax * (h - 2*m)
    pts = " ".join(f"{xy(float(t), float(v))[0]:.1f},{xy(float(t), float(v))[1]:.1f}" for t, v in zip(times, values))
    shades = []
    for s in segments:
        x1, _ = xy(s.start, 0); x2, _ = xy(s.end, 0)
        shades.append(f'<rect x="{x1:.1f}" y="{m}" width="{max(1,x2-x1):.1f}" height="{h-2*m}" fill="#86efac" opacity=".24"/>')
    lines = []
    for key, color in (("low_threshold", "#f59e0b"), ("high_threshold", "#ef4444")):
        _, y = xy(0, thresholds[key]); lines.append(f'<line x1="{m}" y1="{y:.1f}" x2="{w-m}" y2="{y:.1f}" stroke="{color}" stroke-dasharray="6 5"/>')
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">
<rect width="100%" height="100%" fill="#f8fafc"/><rect x="{m}" y="{m}" width="{w-2*m}" height="{h-2*m}" fill="#fff" stroke="#cbd5e1"/>
{''.join(shades)}{''.join(lines)}<polyline points="{pts}" fill="none" stroke="#2563eb" stroke-width="1.5"/>
<text x="{m}" y="24" font-family="sans-serif" font-size="16" fill="#172033">Motion energy and candidate segments</text>
<text x="{m}" y="{h-12}" font-family="sans-serif" font-size="12" fill="#64748b">0s</text><text x="{w-m-55}" y="{h-12}" font-family="sans-serif" font-size="12" fill="#64748b">{duration:.1f}s</text></svg>'''
    path.write_text(svg, encoding="utf-8")


def save_contact(path: Path, frames: list[np.ndarray], cols: int = 5) -> None:
    if not frames:
        return
    thumbs = [cv2.resize(f, (320, 180), interpolation=cv2.INTER_AREA) for f in frames]
    rows = math.ceil(len(thumbs) / cols)
    canvas = np.zeros((rows * 180, cols * 320, 3), np.uint8)
    for i, frame in enumerate(thumbs):
        canvas[(i//cols)*180:(i//cols+1)*180, (i%cols)*320:(i%cols+1)*320] = frame
    cv2.imwrite(str(path), canvas)


def analyze(path: Path, out: Path, args: argparse.Namespace) -> dict:
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {path}")
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
    width, height = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = frame_count / fps if fps else 0.0
    times, motion, brightness, blur = [], [], [], []
    contacts: list[np.ndarray] = []
    prev = None; idx = 0; next_contact = 0.0
    while True:
        ok, frame = cap.read()
        if not ok: break
        t = idx / fps
        small = cv2.resize(frame, (320, 180), interpolation=cv2.INTER_AREA)
        gray = cv2.GaussianBlur(cv2.cvtColor(small, cv2.COLOR_BGR2GRAY), (5,5), 0)
        times.append(t); brightness.append(float(np.mean(gray))); blur.append(float(cv2.Laplacian(gray, cv2.CV_64F).var()))
        motion.append(0.0 if prev is None else float(np.mean(cv2.absdiff(gray, prev))))
        prev = gray
        if t + 1e-6 >= next_contact and len(contacts) < 10:
            contacts.append(frame.copy()); next_contact += max(duration / 9.0, 1.0)
        idx += 1
    cap.release()
    times_a, motion_a = np.asarray(times), np.asarray(motion)
    segments, thresholds = detect_segments(times_a, motion_a, fps, args.min_motion,
                                           args.merge_gap, args.pad, args.max_segment)
    stem = path.stem
    with (out / f"{stem}_motion.csv").open("w", newline="", encoding="utf-8-sig") as fh:
        wr = csv.writer(fh); wr.writerow(["time_seconds", "motion_energy"]); wr.writerows(zip(np.round(times_a,3), np.round(motion_a,4)))
    save_svg(out / f"{stem}_motion.svg", times_a, thresholds.pop("smooth"), thresholds, segments)
    save_contact(out / f"{stem}_contact.jpg", contacts)
    probe = ffprobe(path)
    video_stream = next((s for s in probe.get("streams", []) if s.get("codec_type") == "video"), {})
    checks = {
        "resolution_ok": width >= 1280 and height >= 720,
        "fps_ok": 24 <= fps <= 35,
        "duration_requires_segmentation": duration > 8,
        "browser_codec_ok": video_stream.get("codec_name") in {"h264", "vp8", "vp9", "av1"},
        "brightness_warning": float(np.mean(brightness)) < 45 or float(np.mean(brightness)) > 220,
    }
    label_code, label_folder = infer_label(path)
    return {"source": str(path), "label_code": label_code, "label_folder": label_folder,
            "metadata": {"duration": round(duration,3), "fps": round(fps,3),
            "width": width, "height": height, "frames": frame_count, "codec": video_stream.get("codec_name"),
            "mean_brightness": round(float(np.mean(brightness)),2), "mean_blur_score": round(float(np.mean(blur)),2)},
            "thresholds": {k: round(float(v),4) for k,v in thresholds.items()}, "checks": checks,
            "candidate_segments": [asdict(s) for s in segments]}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("inputs", nargs="+", help="Video file(s) or directories")
    ap.add_argument("--output", required=True, help="Analysis output directory")
    ap.add_argument("--person-id", default="P001")
    ap.add_argument("--min-motion", type=float, default=0.22)
    ap.add_argument("--merge-gap", type=float, default=0.55)
    ap.add_argument("--pad", type=float, default=0.55)
    ap.add_argument("--max-segment", type=float, default=6.0)
    args = ap.parse_args()
    out = Path(args.output).expanduser().resolve(); out.mkdir(parents=True, exist_ok=True)
    reports=[]
    for p in video_paths(args.inputs):
        reports.append(analyze(p, out, args))
    (out / "analysis_report.json").write_text(json.dumps({"person_id":args.person_id,"videos":reports},ensure_ascii=False,indent=2),encoding="utf-8")
    with (out / "candidate_segments.csv").open("w",newline="",encoding="utf-8-sig") as fh:
        wr=csv.writer(fh);wr.writerow(["person_id","label_code","label_folder","source","candidate_index","start","end","duration","peak_time","peak_motion","status","speed","notes"])
        for r in reports:
            for i,s in enumerate(r["candidate_segments"],1):wr.writerow([args.person_id,r["label_code"],r["label_folder"],r["source"],i,s["start"],s["end"],round(s["end"]-s["start"],3),s["peak_time"],s["peak_motion"],s["status"],"normal",""])
    print(json.dumps({"videos":len(reports),"candidates":sum(len(r["candidate_segments"]) for r in reports),"output":str(out)},ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
