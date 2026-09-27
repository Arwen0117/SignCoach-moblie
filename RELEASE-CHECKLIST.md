# Code snapshot release checklist

Prepared 2026-09-27 from source commit `ec989e8c64b648a514d656b356f813d892d25b1b`.
This snapshot has no Git history or origin. Only the new snapshot was edited; existing
source code, original data, the local Demo and parent-directory files were not changed.
No GitHub/Render access, push, deployment, system installation or history rewrite occurred.

## Publication boundaries

- [x] Explicit file whitelist; no whole-repository clone/archive.
- [x] No .git, restricted references/manifests/provenance, video, checkpoint, database,
  secret/env file, dependency/build directory, pyc/cache, IDE file, logs or old Colab copy.
- [x] Package lock, Python dependencies, application/test source and teaching SVGs retained.
- [x] Synthetic CSVs inspected: artificial coordinate sequences and synthetic sample IDs.
  Six old .mp4 files were inspected as text placeholders and excluded as unused.
  Benchmark tests create their own synthetic text archives in temporary directories.
- [x] Packaging tests generate artificial one-hot vectors. Real 187-entry/hash validation
  is an explicit independent script, not an optional/skipped unit-test branch.
- [x] Docker copies only the reference README, never data. Image build inputs need no
  reference assets. Runtime has no scoring fallback and fails without authorized files.
- [x] .gitignore and .dockerignore exclude reference data and generated/private artifacts.
- [x] No new LICENSE grants rights not established by the project owner.
- [x] README starts with code-only/data-blocked status, unauthenticated shared-history
  limitations, SQLite persistence requirement and unverified Docker status.

## Verification actually performed

Tests ran in a separate temporary copy:
`$env:TEMP/SignCoach-P8-test-1b88165e0474454084ae95fb07f99b07`.
Node dependencies, npm cache and build output exist only in that temporary copy.
No recursive deletion was needed. The delivered snapshot has none of those artifacts.
The Python commands used an existing Python 3.11.14 interpreter read-only; no dependency
was installed into another workspace. Node 24.14.0 / npm 11.9.0 / Vite 5.4.21 were used.

Commands from that temporary root (`python` means the selected Python 3.11 interpreter):

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:MPLCONFIGDIR="$PWD/.test-cache/matplotlib"
python -m unittest discover -s tests -q
Set-Location web-app
$env:PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD='1'
npm ci --cache ../.npm-cache --no-audit --no-fund
npm test
npm run build
npm run test:browser
```

| Check | Result |
| --- | --- |
| Python tests | 59 passed; no restricted reference files required |
| npm ci | 133 packages installed from lock file in temporary copy |
| Frontend tests | 12 passed |
| Production build | 1,580 modules; passed |
| Browser behavior | Fake camera + mocked business responses; all 3 states passed, 37 frames, max in-flight 1; course/reference-link UI passed |
| Missing runtime references | Startup fails with explicit separately-authorized-data message |
| Independent real-asset checker | Explicit read-only check of existing private external 187×22080 assets passed; both supplied SHA256s and 30-word coverage verified; assets were never copied here |
| Independent check without data | Failed explicitly with FileNotFoundError; no silent skip |
| Snapshot scan | All files UTF-8 text/SVG; no prohibited file types, no file above 1 MB; largest package-lock.json 90,455 bytes |
| Secret/path scan | No matches for private keys, GitHub/API/AWS tokens, assigned credentials, credential URLs or personal home-directory paths; pattern scan is not a guarantee of absence |
| Git metadata | No .git anywhere in snapshot, no origin set; no new Git repository initialized |
| Docker | CLI unavailable; build/run/Linux dependency resolution/volume persistence NOT tested |
| Real browser with references | NOT run for this data-free snapshot; synthetic browser checks do not establish real signing effectiveness |

Explicit private-asset command (locations/hash values come from the owner's separate
private asset record, never bundled provenance):

```powershell
python -m scripts.verify_authorized_reference --reference-dir <private-reference-directory> --expected-index-sha256 <trusted-index-sha256> --expected-manifest-sha256 <trusted-manifest-sha256>
# Expected failure with no references in this snapshot:
python -m scripts.verify_authorized_reference --reference-dir deploy/reference --expected-index-sha256 unused --expected-manifest-sha256 unused
```

The one-off scan inspected file extensions, UTF-8 decoding, size, forbidden paths and
credential patterns. It reported only file/category for hits, never secret values.
An initial path-rule hit on web-app/src/data/signContent.js was reviewed as teaching
content, not raw dataset data; the rule was corrected to distinguish the root data directory.
No credential hits occurred. Existing FastAPI/sklearn deprecation warnings did not fail tests.

## Remaining before deployment

- [ ] Confirm code/teaching-content publication rights; no project-wide license was invented.
- [ ] Obtain appropriate data/public-use rights; independently supply authorized reference
  files at /app/deploy/reference before runtime. They remain excluded from Git and image.
- [ ] Verify Docker build/run and persistent SQLite storage in an actual Docker environment.
- [ ] Decide access control before exposing unauthenticated shared history publicly.
- [ ] Check the chosen Render service's private asset provisioning, writable persistent
  storage, 0.0.0.0/PORT and single-worker behavior. These are checks, not validated setup steps.
- [ ] Test real camera permissions, real signing and needed reference-media playback.
- [ ] Initialize a NEW Git repository inside this snapshot before uploading; do not upload
  or force-push the parent repository/history. No GitHub/Render action was performed here.

## Exact delivered file list

60 files; this list includes this checklist. No unlisted data or build products are needed
to run the synthetic tests or compile the frontend.

```text
.dockerignore
.gitattributes
.gitignore
Dockerfile
README.md
RELEASE-CHECKLIST.md
asl_realtime/__init__.py
asl_realtime/api_server.py
asl_realtime/attempt_store.py
asl_realtime/calibration.py
asl_realtime/constants.py
asl_realtime/diagnostics.py
asl_realtime/embedding_encoder.py
asl_realtime/mediapipe_compat.py
asl_realtime/preprocess.py
asl_realtime/reference_index.py
asl_realtime/scoring.py
deploy/reference/README.md
requirements-demo.txt
scripts/evaluate_baseline.py
scripts/export_demo_reference.py
scripts/train_calibrator.py
scripts/verify_authorized_reference.py
signcoach_benchmark/__init__.py
signcoach_benchmark/__main__.py
signcoach_benchmark/cli.py
signcoach_benchmark/config.py
signcoach_benchmark/download.py
signcoach_benchmark/manifest.py
signcoach_benchmark/vocabulary.json
tests/fixtures/README.md
tests/fixtures/baseline_evaluator/keypoints/hello.csv
tests/fixtures/baseline_evaluator/keypoints/no-hands.csv
tests/fixtures/baseline_evaluator/keypoints/please.csv
tests/fixtures/baseline_evaluator/manifest.csv
tests/fixtures/calibration_rows.csv
tests/test_api_contract.py
tests/test_baseline_evaluator.py
tests/test_calibration.py
tests/test_demo_packaging.py
tests/test_popsign_benchmark.py
tests/test_scoring.py
web-app/index.html
web-app/package-lock.json
web-app/package.json
web-app/postcss.config.js
web-app/src/App.jsx
web-app/src/assets/sign-hello.svg
web-app/src/assets/sign-thanks.svg
web-app/src/assets/sign-water.svg
web-app/src/data/signContent.js
web-app/src/index.css
web-app/src/main.jsx
web-app/src/practice/PracticePage.jsx
web-app/src/practice/api.js
web-app/src/practice/recorder.js
web-app/tailwind.config.js
web-app/tests/practice.browser.mjs
web-app/tests/practice.live.browser.mjs
web-app/tests/practice.test.js
```
