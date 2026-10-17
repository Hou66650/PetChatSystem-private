"""Evaluate ONE normalized PresentMon capture; never pool independent runs.
Input CSV: frame_ms (positive finite milliseconds). Source process filtering and
warmup/capture boundaries must be performed explicitly, with raw source retained.
This is a frame-time gate only, not the whole visual/memory/CPU/GPU acceptance.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path


def nearest_rank(values: list[float], fraction: float) -> float:
    if not values or not 0 < fraction <= 1:
        raise ValueError("Need nonempty values and fraction in (0,1]")
    return sorted(values)[math.ceil(fraction * len(values)) - 1]


def summarize(values: list[float]) -> dict:
    if not values or any(not math.isfinite(value) or value <= 0 for value in values):
        raise ValueError("Every frame_ms must be finite and greater than zero; no silent exclusions")
    count = len(values)
    duration = math.fsum(values)
    slow = sorted(values, reverse=True)[:math.ceil(count * .01)]
    stats = {"frames": count, "duration_seconds": duration / 1000,
             "mean_fps": count * 1000 / duration,
             "p95_ms": nearest_rank(values, .95), "p99_ms": nearest_rank(values, .99),
             "one_percent_low_fps": 1000 / (math.fsum(slow) / len(slow)),
             "over_50ms_ratio": sum(value > 50 for value in values) / count,
             "over_100ms_count": sum(value > 100 for value in values)}
    checks = {"mean_fps_at_least_60": stats["mean_fps"] >= 60,
              "p95_at_most_18ms": stats["p95_ms"] <= 18,
              "p99_at_most_25ms": stats["p99_ms"] <= 25,
              "over_50ms_below_0_001": stats["over_50ms_ratio"] < .001}
    return {"statistics": stats, "checks": checks}


def evaluate(values: list[float], metadata: dict) -> dict:
    result = summarize(values)
    problems = []
    for key in ("run_id", "scene_id", "build_hash", "asset_manifest_hash", "raw_capture_sha256",
                "raw_capture_path", "gpu_name", "driver", "profile", "capture_tool_version"):
        if not isinstance(metadata.get(key), str) or not metadata[key].strip():
            problems.append("Missing " + key)
    for key in ("raw_capture_sha256", "asset_manifest_hash", "build_hash"):
        value = metadata.get(key, "")
        if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
            problems.append(key + " must be lowercase SHA256")
    for key in ("frame_generation", "vsync", "vrr", "frame_cap"):
        if metadata.get(key) is not False:
            problems.append(key + " must explicitly be false for capability capture")
    if metadata.get("interval_kind") != "actual_rendered_frame":
        problems.append("Capture must identify actual rendered frames, not generated/display-only frames")
    warmup = metadata.get("warmup_seconds")
    if not isinstance(warmup, (int, float)) or isinstance(warmup, bool) or not math.isfinite(warmup) or warmup < 120:
        problems.append("Warmup must be at least 120 seconds")
    kind = metadata.get("run_kind")
    minimum = 600 if kind == "standard" else 120 if kind == "stress" else None
    if minimum is None:
        problems.append("run_kind must be standard or stress")
    elif result["statistics"]["duration_seconds"] < minimum:
        problems.append("Capture duration below required independent run length")
    ratio = metadata.get("internal_render_percent")
    if not isinstance(ratio, (int, float)) or isinstance(ratio, bool) or not 80 <= ratio <= 100:
        problems.append("Flagship profile requires a declared 80..100 percent internal resolution")
    if metadata.get("output_resolution") != [2560, 1600]:
        problems.append("Flagship output resolution must be 2560x1600")
    if metadata.get("excluded_rows") != []:
        problems.append("Excluded rows require reviewer attribution; no automatic pass")
    if result["statistics"]["over_100ms_count"]:
        problems.append("Over-100ms frames require attribution and rerun; repeatable app hitch is a failure")
    result["evidence_issues"] = problems
    result["status"] = "fail" if not all(result["checks"].values()) else \
        "needs_evidence_review" if problems else "frame_time_gate_pass"
    result["scope"] = "One capture only. Visual, resource, input latency, three runs and heat tests remain."
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv", type=Path)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with args.csv.open(encoding="utf-8-sig", newline="") as handle:
        rows = csv.DictReader(handle)
        if not rows.fieldnames or "frame_ms" not in rows.fieldnames:
            raise ValueError("Expected normalized frame_ms column")
        values = [float(row["frame_ms"]) for row in rows]
    metadata = json.loads(args.metadata.read_text(encoding="utf-8"))
    raw = Path(metadata.get("raw_capture_path", ""))
    if not raw.is_absolute():
        raw = args.metadata.parent / raw
    if not raw.is_file() or hashlib.sha256(raw.read_bytes()).hexdigest() != metadata.get("raw_capture_sha256"):
        raise ValueError("Retained raw capture missing or SHA256 mismatch")
    result = evaluate(values, metadata)
    result["metadata"] = metadata
    result["normalized_csv_sha256"] = hashlib.sha256(args.csv.read_bytes()).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "frame_time_gate_pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
