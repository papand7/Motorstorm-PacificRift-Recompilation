# Thermal guard: runtime validation and decision (2026-10-23)

## Decision

Software thermal monitoring is **optional and off by default** in `tools/fast_startup.py`.
Ordinary temperature protection is left to the PC's hardware, firmware and Windows
thermal management, which act whether or not a run is being supervised. That does not
mean every possible shutdown is prevented: the earlier unexplained host power losses
during garage workloads are not explained by this decision, and extended garage
execution stays opt-in (`--allow-extended`).

The runner and wrapper handle what software can control: execution limits and software
failures. These are mandatory and do not depend on thermal monitoring:

| Safeguard | Where |
|---|---|
| 210 s cap: `--timeout` defaults to 210 s, and a higher value is refused | `fast_startup.apply_safe_stop` |
| Hard deadline: the process tree is killed at timeout + 15 s even if the runner loop is stuck | `fast_startup.main` (timer) |
| Stop at the first `GcKernel::Present() Timeout` line (the GPU watchdog), independent of the milestone config | runner `--stop-on-line`, always passed by the wrapper |
| Process-tree kill on stop (`taskkill /PID /T /F`), then a kill by image name after every run | `startup_runner.run`, `fast_startup.kill_tree_by_name` |
| Default stop at `garage_resources_requested`; later targets need `--allow-extended` | `fast_startup.apply_safe_stop` |
| No retries: `--retries` and `--retry-before` are refused | `fast_startup.apply_safe_stop` |
| Evidence is kept: no run directory, log or cache is deleted; the stop reason goes to `manifest.json` and `safeguards.json` | runner and wrapper |

## Optional monitor

`--thermal-guard` runs guard v3 (`generated/profile/thermal_guard_v3.ps1`) through
`tools/thermal_supervisor.py`. The flag is consumed by the wrapper and never passed to the
runner. Without the flag, `thermal_supervisor` is not imported and no sensor is polled.

Once enabled, the monitor fails closed:
- it refuses to launch the game without a first reading;
- it kills the target at 363 K, on a rise of at least 8 K within 12 s, on two missed
  readings, or when the guard dies or goes stale.

The wrapper prints `thermal monitor: ON|off`, and `safeguards.json` records the state.
v1 and v2 guards are rejected; there is no automatic fallback to them.

## Sensor (read-only findings)

- **Only one temperature is readable:** ACPI `\_TZ.TZ01`, in 1 K steps, via
  `Win32_PerfRawData_Counters_ThermalZoneInformation` (~30 ms per read).
- **TZ01 is not identified as a CPU or GPU sensor.** It is a firmware zone. It is not
  Tctl and not a GPU hotspot.
- **The other sources fail:** `MSAcpi_ThermalZoneTemperature` is access-denied, and
  `root/Hardware` reports a generic failure. GPD's service exposes nothing.
- **Freshness cannot be proven.** The counter's timestamp is the query time.
- **Readings seen:** idle 348–356 K, and a decay from 355 to 348 K within 20 s, so the
  zone responds.
- **Limit of the optional monitor:** it is a coarse diagnostic, not comprehensive hardware
  protection.

## Tests (dummy processes only)

- `tools/test_fast_startup_safety.py`, 19/19. Covers:
  - thermal monitoring off by default, with no import and no polling;
  - a missing sensor does not block a default run;
  - the explicit opt-in, and that an enabled guard which fails launches nothing;
  - the 210 s cap and the hard deadline;
  - the GPU-watchdog stop line, with benign lines not matching;
  - extended targets need opt-in, and retries are refused;
  - real-runner runs of a renamed `cmd.exe` with a `PING` child: the stop line and the
    timeout each kill the whole tree with no orphan, and the hard deadline kills a hung
    runner's target.
- `ps3recomp-int/tools/test_startup_runner.py`, 22/22. Includes `--stop-on-line` without
  a fatal config, and a timeout that kills a child process.
- `tools/test_thermal_supervisor.py`, 11/11, and `generated/profile/test_thermal_guard.ps1`
  (v2), all pass. Both are kept for the optional monitor.
