---
name: prepare-sign-language-dataset
description: Analyze, quality-check, stage, segment, anonymize, transcode, and catalog isolated sign-language recording sessions. Use for full-session MP4/MOV/HEVC recordings, candidate action-boundary detection, H.264 clip generation, UNKNOWN-class collection, signer-disjoint dataset preparation, Windows-to-WSL synchronization, or updating sign_dataset metadata without modifying original videos.
---

# Prepare Sign Language Dataset

Preserve full recordings, generate reviewable candidate segments, and materialize only human-approved clips. Treat motion detection as a proposal mechanism, never ground truth.

## Safety invariants

1. Never edit, transcode over, rename, or delete files under `raw/full`.
2. Stage copies when Windows Chinese paths do not survive WSL argument encoding.
3. Map real names to anonymous IDs such as `P001`; keep identity mapping outside the training dataset.
4. Remove audio from derived clips. Spoken prompts can leak the class label and contain personal data.
5. Require `status=approved` before creating clips or appending metadata.
6. Split train/validation/test by `person_id`, never randomly by video.
7. Keep `UNKNOWN` as a real class and include ordinary, incomplete, and non-target signs.

## Workflow

### 1. Inventory and stage

Inspect source files first. Record count, size, codec, duration, resolution, and frame rate.

If WSL cannot read a Windows path or Unicode is mangled, stage a read-only copy while preserving label/person subdirectories:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/stage_windows_dataset.ps1 `
  -SourceRoot 'E:\...\sign_dataset\raw\full'
```

Verify hashes in `source_manifest.csv`. Do not delete the staged copy until approved outputs are verified.

### 2. Analyze sessions

Run inside an environment with Python, OpenCV, NumPy, FFmpeg, and FFprobe:

```bash
python3 scripts/analyze_sign_videos.py \
  /home/bestfunc/sign-dataset-stage \
  --output /home/bestfunc/sign-analysis \
  --person-id P001
```

Review:

- `analysis_report.json` for codec and quality gates.
- `*_contact.jpg` for framing and repeated-action coverage.
- `*_motion.svg` for motion peaks and merged actions.
- `candidate_segments.csv` for proposed start/end times.

Read [references/quality-gates.md](references/quality-gates.md) when deciding whether to accept, re-cut, or re-record.

### 3. Human review

Edit a copy of `candidate_segments.csv`:

- Set `status=approved` only after watching the full proposed interval.
- Adjust `start` and `end` so preparation and completion are both present.
- Use `rejected`, `needs_manual_split`, or `needs_rerecord` otherwise.
- Confirm `person_id`, `label_code`, `label_folder`, and `speed`.
- Do not approve an action solely because its directory name claims a label.

For semantically similar target signs, require a signer/teacher review before training.

### 4. Materialize approved clips

```bash
python3 scripts/materialize_approved_segments.py reviewed_segments.csv \
  --output /path/to/sign_dataset/processed/clips \
  --metadata /path/to/sign_dataset/metadata.csv
```

The script creates H.264/yuv420p MP4 clips, removes audio, refuses overwrite by default, and appends metadata. Use `--overwrite` only after explicitly verifying the exact derived targets.

### 5. Validate outputs

Verify all of the following:

- Each clip contains exactly one complete action.
- No clip is mislabeled, empty, truncated, or duplicated.
- H.264 clips open in the target browser.
- Metadata paths exist and sample IDs are unique.
- Class counts are reasonably balanced.
- Participant IDs do not overlap across split files.
- UNKNOWN covers every participant and intended environment.

Read [references/dataset-contract.md](references/dataset-contract.md) for directory and metadata requirements.

## Parameter tuning

Keep defaults for initial review. If separate actions merge, reduce `--merge-gap` from `0.55` toward `0.30`. If one action fragments, increase it gradually. Adjust `--pad` only to retain neutral preparation/completion frames. Never optimize parameters merely to force the expected number of repetitions.

## Dependencies

On Ubuntu/WSL:

```bash
sudo apt-get install -y ffmpeg python3-opencv python3-numpy
```

Do not install dependencies during a read-only review unless the user has authorized environment changes.
