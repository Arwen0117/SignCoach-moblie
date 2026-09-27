# Synthetic test fixtures only

- `baseline_evaluator/keypoints/*.csv`: eight-frame artificial coordinate sequences
  (one landmark per frame), including static no-hand input; no captured human frames.
- `baseline_evaluator/manifest.csv`: `synthetic:*` sample IDs and `signer-synth-*` IDs
  link those artificial sequences. The PopSign source value tests the schema only.
- `calibration_rows.csv`: hand-authored numeric cases, `synthetic:*` IDs and
  `synthetic_smoke` source; not measurements, learner accuracy or a production model.
- Packaging tests create small one-hot vectors in temporary directories. API tests
  use generated blank JPEGs and mocked detector results.
- Benchmark tests create text payloads named `.mp4` inside temporary directories;
  they exercise archive/filename parsing, not real video decoding. The six old
  `popsign_smoke` text placeholders were inspected and omitted as unused.

No reference index, real video, recording, trained checkpoint or calibration artifact
is distributed in this directory. Synthetic pass/retry tests are UI/API contract tests,
not recognition-quality evidence.
