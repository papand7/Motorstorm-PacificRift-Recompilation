"""Lift the observed raw Wws_Job policy module for the MotorStorm port."""
import json
import subprocess
import sys
from pathlib import Path

from prepare_wws_pm import main as prepare

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "generated" / "spu_raw"


def main():
    prepare()
    subprocess.run([
        sys.executable, str(ROOT / "ps3recomp" / "tools" / "spu_lifter.py"),
        "--auto-functions", str(DEST / "wws_job_pm.elf"),
        "--output", str(DEST / "wws_job_pm"),
        "--symbol-prefix", "mspr_wws_pm_", "--return-entries",
        "--report", str(DEST / "wws_job_pm_lift.json"),
    ], check=True)
    report = json.loads((DEST / "wws_job_pm_lift.json").read_text())
    if report.get("unsupported"):
        raise RuntimeError(f"Unsupported Wws_Job SPU instructions: {report['unsupported']}")
    for name, old, new in (
        ("spu_recomp.c", '../../runtime/spu/spu_helpers.h', 'spu_helpers.h'),
        ("spu_recomp.h", '../../runtime/spu/spu_context.h', 'spu_context.h'),
    ):
        path = DEST / "wws_job_pm" / name
        source = path.read_text()
        if source.count(old) != 1:
            raise RuntimeError(f"Unexpected generated include in {path}")
        path.write_text(source.replace(old, new))


if __name__ == "__main__":
    main()
