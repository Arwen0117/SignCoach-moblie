"""Train one local calibrator from P2 sample_results.csv (never raw feature CSVs)."""
import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from asl_realtime.calibration import run_calibration  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--features", type=Path, required=True, help="P2 sample_results.csv")
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--report-dir", type=Path, required=True)
    parser.add_argument("--model-version", required=True)
    parser.add_argument("--synthetic-smoke", action="store_true")
    args = parser.parse_args()
    metadata = run_calibration(args.features, args.artifact, args.report_dir,
                               args.model_version, args.synthetic_smoke)
    print(json.dumps(metadata, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
