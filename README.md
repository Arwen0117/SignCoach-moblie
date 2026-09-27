# SignCoach — code-only release

**This is publishable application code, not a data-ready website that can be deployed
and used immediately.** No reference index or dataset is included. Startup fails
until separately authorized reference files are supplied. A GitHub/Render connection
alone does not make scoring available. Docker build/run has not been verified.

The current application is a single-user, unauthenticated Demo. Anyone able to access
the service can access its practice history and update feedback. Public deployment
requires an access-control decision before use; the current code does not isolate users.
SQLite requires persistent writable storage to survive container replacement.

## Scope and data permission

The Demo supports 30 ASL product words, four-second recordings, manual-baseline-v1
action similarity, pass/retry/rerecord, up to two diagnostic messages and SQLite feedback.
It does not output calibrated correctness probability. Logistic Regression and PopSign
utilities are offline experiments, never runtime fallback models.

[ASL Citizen's license](https://www.microsoft.com/en-us/research/project/asl-citizen/dataset-license/)
restricts non-commercial research use and prohibits distributing data or modifications.
This snapshot does not establish permission to redistribute references, publish an image
containing them or offer public scoring. Obtain appropriate authorization separately.
No new open-source license is granted for this project by this preparation step.

Before runtime, provide authorized `index.npz` and `manifest.json` independently at
`deploy/reference` locally or `/app/deploy/reference` in the container. Keep these files
out of Git and out of the Docker image. No downloader, secret-transfer mechanism or
synthetic fallback is supplied. See [the reference contract](deploy/reference/README.md).

## Local build and startup

Requirements: Python 3.11 and Node 24. Run from this snapshot root:

```powershell
py -3.11 -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements-demo.txt
Set-Location web-app
npm ci
npm run build
Set-Location ..
```

The build does not require reference data. Before starting the server, supply the
authorized assets and run this explicit check, using trusted SHA256 values supplied
separately with the assets (replace the placeholders):

```powershell
.venv/Scripts/python.exe -m scripts.verify_authorized_reference --reference-dir deploy/reference --expected-index-sha256 <trusted-index-sha256> --expected-manifest-sha256 <trusted-manifest-sha256>
```

It verifies hashes, 187 finite/nonzero vectors of dimension 22080, the exact configured
30-word coverage and portable source identifiers. Missing data or mismatch fails;
it never silently skips validation. The checker was separately tested against private
read-only assets, but none were copied into this snapshot. Unit tests below are synthetic
and cannot establish recognition accuracy.

```powershell
$env:PORT='8000'
$env:SIGNCOACH_DB_PATH="$PWD/data/signcoach-demo.sqlite3"
$env:MPLCONFIGDIR="$PWD/.venv/matplotlib"
.venv/Scripts/python.exe -m asl_realtime.api_server
```

Visit `http://127.0.0.1:8000/`; stop with Ctrl+C. One Python process serves `web-app/build`
and `/api/...`. Default PORT is 8000; default local host is 127.0.0.1. There is no separate
frontend server or API-base configuration. Unknown APIs/assets remain 404. Missing
reference files or frontend build produces a startup error rather than partial service.
Camera frames are handled in memory. Reference video/media links require network access.

## Docker recipe — pending validation

The Dockerfile builds frontend assets with Node 24 and runs Python 3.11 Debian slim.
It intentionally copies only the reference README, never reference data. Building is
independent of reference assets; running still requires them. Neither the Linux dependency
installation nor image/volume behavior has been tested with Docker on this machine.

For an environment with Docker and separately authorized assets, the intended local
verification sequence is:

```powershell
docker build -t signcoach-code:local .
docker volume create signcoach-data
$referenceDir=(Resolve-Path <authorized-reference-directory>).Path
docker run --name signcoach-demo -p 127.0.0.1:8000:8000 -e PORT=8000 --mount "type=bind,source=$referenceDir,target=/app/deploy/reference,readonly" --mount source=signcoach-data,target=/data signcoach-code:local
# In another terminal when finished:
docker stop signcoach-demo
docker rm signcoach-demo
```

The reference mount is read-only; the separate data volume holds SQLite. Retain the volume
to keep practice history. Do not add the references to the image to avoid provisioning
them separately. Use one worker because current attempt sessions are in process memory.

## Tests without restricted assets

```powershell
.venv/Scripts/python.exe -m unittest discover -s tests -q
Set-Location web-app
npm ci
npm test
npm run build
npm run test:browser
```

The browser test needs installed Chrome (or `BROWSER_CHANNEL=msedge`). It uses a fake
camera and intercepted API responses solely to verify UI behavior. No real data is needed.
`tests/practice.live.browser.mjs` is a separate, explicit real-backend test, run only after
authorized data and the service are available; set DEMO_URL to that local origin.
It uses a fake camera without business-response interception. No such real-data test was
run against this data-free release. See [fixture provenance](tests/fixtures/README.md)
and [release verification](RELEASE-CHECKLIST.md).

## Before GitHub / Render

- Upload only this code snapshot. It contains no `.git` and no old history. Initialize
  a new repository in this directory; do not commit or force-push the parent repository.
  A plain Git command before initialization may discover the parent's old repository.
- Confirm rights to publish the project code and third-party teaching assets/links.
  This snapshot does not add a LICENSE or resolve those rights.
- Resolve reference-data permission and a private runtime provisioning method. Connecting
  Render to GitHub does not supply these excluded files; missing data prevents startup.
- Validate Docker build/run on a Docker-capable machine. No claim of container readiness
  or verified Render deployment is made here.
- Check that the chosen service can supply `/app/deploy/reference` independently, bind
  `0.0.0.0` using PORT, and provide persistent writable storage for SIGNCOACH_DB_PATH.
- Address unauthenticated shared history before exposing the service publicly; retain
  one process/worker until session/storage architecture is deliberately changed.
- Manually verify real camera permission, signing behavior and required reference videos.

No GitHub/Render account or repository was accessed or changed, and no push/deployment
is performed by these instructions.
