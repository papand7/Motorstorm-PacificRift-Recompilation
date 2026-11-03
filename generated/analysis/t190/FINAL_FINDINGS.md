# T190 final findings

## Decision: **INCONCLUSIVE** (no in-game evidence; preflight BLOCKED)

- **Launches:** 0 of 4. Preflight failed:
  - the session is RDP (`rdp-tcp#0`), not the console the established runs used;
  - Godot was running.
  The brief requires stopping before launch. All 4 authorized launches remain unused.
- **Measured FPS difference:** none. No in-game FPS claim is made.
- **Ready to run:**
  - one exe, `9e77bd4b…8453`, from T189 `a26240c5` and the existing lift (not relifted), with inline stores compiled in;
  - the runner `generated/analysis/t190/ab/run_t190.py`: P = T184 arm P, B = P + `PS3_VM_STORE_INLINE=1`, with order, cap and no-retry enforced;
  - the analysis `generated/analysis/t190/tools/analyze_t190.py`, which reproduces T184 P exactly.
- **Wider integration of T189 inline stores:** not yet. They stay opt-in.
  - Offline evidence (1.48× on one real store-heavy function; neutral to −5 % on short fixture paths) does not justify a default.
  - The in-game P/B/P/B remains the gate.

## Acceptance (to apply after the runs)

ACCEPT only if all of the following hold:
- Bb1 and Bb2 reach the race;
- no new serious-error or reservation-anomaly lines;
- the `[vm-gates]` banner is present in B;
- P1→B1 and P2→B2 move the same way;
- pooled B frame time is below P by more than the P1–P2 drift.

Otherwise:
- **REJECT** if B is no better or is worse;
- **INCONCLUSIVE** if the pairs disagree or Δ ≤ drift.

If `after` falls but `havok`/`spin` absorb it, report the PPU saving and the flat frame time separately.

## Next generic milestone (only if ACCEPT)

1. Correct SPU indirect-branch fast dispatch: a cached resolver with an eligibility word and generation invalidation (T189 S1).
2. SPU register promotion on an SPU differential test.
3. Atomic-wait improvements: parking same-line reservation spinners.

## Reproduce

```
py -3 generated/analysis/t190/tools/make_t190_staging.py
generated\analysis\t190\tools\build_t190.cmd
py -3 generated/analysis/t190/tools/make_runner_t190.py 9e77bd4b12d2ea66f6bd35d16018d07e2fbd71593a4cce30efd15892ba1f8453
py -3 generated/analysis/t190/ab/run_t190.py prepare r ; envcheck ; dryrun P p1
```

Then follow `PREFLIGHT.md` § "What the user does to run it".
