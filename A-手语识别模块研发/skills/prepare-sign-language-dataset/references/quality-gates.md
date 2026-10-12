# Quality gates

## File-level gates

| Check | Accept | Action when failed |
|---|---|---|
| Resolution | At least 1280×720 for the current study | Re-record if hands are not distinguishable |
| Frame rate | 24–35 FPS, stable | Re-record severe variable-rate/stutter cases |
| Browser codec | H.264 preferred | Preserve original; create H.264 derived clips |
| Full session | May contain repeated actions | Segment before training |
| Audio | Allowed only in immutable original | Remove from all training clips |

## Visual gates

- Keep head, face, both hands, wrists, and elbows visible throughout the action.
- Reject severe motion blur, clipping, hand-out-of-frame, occlusion, or exposure failure.
- Avoid hands being disproportionately close to the camera; collect distance variation intentionally rather than accidentally.
- Keep enough neutral frames before and after the action to learn temporal boundaries.
- Flag background motion and other people making gestures.

## Semantic gates

- Confirm the target action using an authoritative reference and a proficient signer/reviewer.
- Record handshape, palm direction, location, path, handedness, non-manual cues, and known confusions.
- Treat regional variants as separate versioned definitions unless the product intentionally accepts both.
- Never infer correctness from spoken audio or the containing folder name.

## Dataset gates

- Use at least 5 people for a technical pilot and 10+ for formal research.
- Keep test signers unseen during training.
- Maintain class ratio max/min ≤ 1.2 when practical.
- Collect UNKNOWN at no less than 30% of positive samples for formal research.
- Report per-class recall, confusion matrix, macro-F1, and false activation rate on UNKNOWN.
