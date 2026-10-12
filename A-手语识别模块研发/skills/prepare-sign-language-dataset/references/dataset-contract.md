# Dataset contract

## Layout

```text
sign_dataset/
├── raw/full/<label>/<person>/        # immutable recording sessions
├── processed/clips/<label>/<person>/ # approved H.264, audio-free clips
├── processed/keypoints/              # derived landmarks
├── splits/                           # signer-disjoint lists
├── consent/                          # restricted, never bundled with training exports
├── rejected/                         # rejected derived artifacts or references
├── references/                       # sign definitions and review records
├── exports/                          # reports and manifests
├── metadata.csv
└── label_map.json
```

## Clip naming

`P001_SL01_001_normal.mp4`

- `P001`: anonymous signer ID.
- `SL01`: stable label code.
- `001`: sequence within signer and label.
- `normal`: `normal`, `fast`, or `slow`.

## Required metadata

```csv
sample_id,person_id,label_code,label_name,file_path,speed,scene,lighting,camera,resolution,fps,duration_seconds,handedness,quality,reviewer,review_status,recorded_at,notes
```

Use ISO 8601 for `recorded_at`. Store paths relative to the dataset root in final exports when possible. Keep label codes stable even if the Chinese display name changes.
