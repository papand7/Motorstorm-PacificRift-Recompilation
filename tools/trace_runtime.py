"""Bounded original-game probe with the runtime tracer: no source edit, no rebuild.

The hooked build (lifted with --trace-hooks) reads PS3_TRACE at startup; this
wraps tools/probe_first_frame.ps1 with that variable, routes tracer output to
generated/logs/<name>-trace.log and summarizes. Configuration language:
ps3recomp/docs/TRACING.md. trace_frontend.py remains the fallback for points the
hooks do not expose (an exact instruction inside straight-line code).

  py -3 tools/trace_runtime.py "fn=001E8058,00584C20;stall=5000;profile=10" --seconds 60
"""

import argparse
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
LOGS = ROOT / "generated/logs"
HOOKED_EXE = ROOT / "build/motorstorm-trace/MotorStormPacificRiftRecomp.exe"


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("config", help="PS3_TRACE value (';'-separated key=value), or @FILE")
    parser.add_argument("--seconds", type=int, default=60)
    parser.add_argument("--name", default=None)
    parser.add_argument("--focus", help="Guest function for the summary timeline")
    parser.add_argument("--exe", type=Path, default=HOOKED_EXE if HOOKED_EXE.is_file() else None,
                        help="Executable (default: the --trace-hooks build from "
                             "tools/build_trace_port.cmd when present)")
    args = parser.parse_args()
    if not 1 <= args.seconds <= 600:
        parser.error("seconds must be 1..600")
    config = args.config
    if config.startswith("@"):
        config = Path(config[1:]).read_text(encoding="utf-8")
    if "out=" in config:
        parser.error("out= is chosen by this wrapper (<name>-trace.log)")
    name = args.name or f"rtrace-{time.strftime('%Y%m%d-%H%M%S')}"
    LOGS.mkdir(parents=True, exist_ok=True)
    trace = LOGS / f"{name}-trace.log"
    env = os.environ.copy()
    env["PS3_TRACE"] = config.strip().rstrip(";") + f";out={trace}"
    env.pop("PS3_TRACE_FILE", None)
    probe = ["powershell", "-NoProfile", "-File", "tools/probe_first_frame.ps1",
             "-Seconds", str(args.seconds), "-Name", name, "-FirstFrame", "-AudioPolicy", "silent"]
    if args.exe:
        probe += ["-Exe", str(args.exe)]
    with (LOGS / f"{name}-probe.log").open("w", encoding="utf-8") as log:
        result = subprocess.run(probe, cwd=ROOT, env=env, stdout=log,
                                stderr=subprocess.STDOUT, check=False)
    if result.returncode:
        sys.exit(f"probe failed ({result.returncode}); see {LOGS / (name + '-probe.log')}")
    summary = [sys.executable, str(ROOT / "tools/summarize_probe.py"), name, "--trace", str(trace)]
    if args.focus:
        summary += ["--focus", args.focus]
    with (LOGS / f"{name}-summary.txt").open("w", encoding="utf-8") as out:
        subprocess.run(summary, cwd=ROOT, stdout=out, check=True)
    print((LOGS / f"{name}-summary.txt").read_text(encoding="utf-8"), end="")


if __name__ == "__main__":
    main()
