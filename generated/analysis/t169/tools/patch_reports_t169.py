"""T169: one-shot update of the earlier reports with the D2/F2 results; copies the new tools to the report worktree."""
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
R = ROOT / 'root-t169/generated/analysis/t169'
HERE = Path(__file__).resolve().parent


def edit(name, fn):
    p = R / name
    s = p.read_text(encoding='utf-8').replace('\r\n', '\n')
    p.write_text(fn(s), encoding='utf-8', newline='\n')


def plan(s):
    return '''# T169: game validation plan

## Result of D2 and F2: the corrections ran

**D2 and F2 were both valid, with switches confirmed effective. F2 removed almost all terrain clipping; `RSX_DEPTH_STATE=1` damages vehicles.** Details: `D2_F2_GAME_RESULTS.md`, `VISUAL_CORRECTION_EFFECTIVENESS.md`. All authorised launches are used; any further launch needs new authorisation.

''' + s.split('\n', 2)[2].replace('## Result of the authorised launches (D1, F1): the corrections did not run', '## Earlier launches (D1, F1): the corrections did not run')


def ready(s):
    a = s.index('**Not ready to merge')
    b = s.index('| Item | Value |')
    s = s[:a] + '''**Not ready to merge as a default set. The opt-in plumbing works in the game, but `RSX_DEPTH_STATE=1` damages vehicles (`REMAINING_VISUAL_DEFECTS.md`), and there's no PS3 reference.** No default changed. Nothing was pushed or merged.

''' + s[b:]
    s = s.replace('`agent/t169-visual-fidelity-recovery`, `001a56f`, base `b1eb158` (T165)', '`agent/t169-visual-fidelity-recovery`, `774c81d`, base `b1eb158` (T165)')
    s = s.replace('`766c45916524b85ff5343807c6bd467f8ec0e07097aba9fa9ab37b3d17f70491` (not launched)', '`02b5c83cbb15d61f9cfea46f50868ac4c4c95593fb60976cc862ccf010a23a6f` (launched: D2, F2)')
    s = s.replace('| Change | 5 files, +632, no deletions |', '| Build | Release, clang-cl 23.1.3, `/O2 /Ob2 /DNDEBUG`, `PS3RECOMP_RSX_VULKAN=OFF` |')
    for bit, old, new in (('0x01', 'Needs game arm C and a PS3 reference; changes exposure input 8.5× in B3', 'Active in F2. Needs a single-switch run and a PS3 reference'),
                          ('0x02', 'Needs arm S', 'Active in F2. Needs a single-switch run'),
                          ('0x04', 'Needs arm S; +29.6 % texture bytes in B3', 'Active in F2. Near sand looks soft; check'),
                          ('0x08', 'Needs arm F', 'Active in F2. Effect not separable'),
                          ('0x10', 'Needs arm F', 'Active in F2. Effect not separable'),
                          ('0x20', 'Needs arm F; extra copies, untimed', 'Active in F2. Effect not separable'),
                          ('0x40', 'Needs arm M; memory and copy cost unmeasured', 'Not tested in game'),
                          ('0x80', 'Needs arm D; may expose the `0xBF` velocity misread', '**Not ready: vehicle regression**'),
                          ('0x100', 'Needs arm F', 'Active in F2. Effect not separable')):
        i = s.index(f'| `{bit}` |')
        j = s.index('\n', i)
        assert old in s[i:j], bit
        s = s[:i] + s[i:j].replace(old, new) + s[j:]
    s = s.replace('- Two suite failures predate this work (`REGRESSION_VALIDATION.md`).', '- Two suite failures predate this work, and `test_spurs_kick_wake` now fails on this machine at both commits (`REGRESSION_VALIDATION.md`).')
    s = s.replace('**Windows-specific:** the profile sets unset switches with `_putenv_s` at the top of `d3d12_init`.', '**Windows-specific:** the profile sets unset switches with `_putenv_s` at the top of `rsx_d3d12_backend_init`.')
    return s


def regress(s):
    head = '''# T169: regression validation

**Result: no new failure traces to T169 code. `test_spurs_kick_wake` is new on this machine but also fails on the earlier commit that passed it, so it isn't this change.** Rendering results: `D2_F2_GAME_RESULTS.md`.

## Preflight for D2 and F2 (ps3recomp `774c81d`)

Logs: `logs/preflight2/`, not committed.

| Check | Result | Label |
|---|---|---|
| Build | rc 0; Release, clang-cl 23.1.3, `/O2 /Ob2 /DNDEBUG`; exe sha256 `02b5c83c…a23a6f` | VERIFIED |
| `test_t169_profile` with negative control | 0 failed | VERIFIED |
| `test_t169_visual` and WARP D3D12 fixtures | rc 0; 0 failed | VERIFIED |
| Full suite, 166 entries | PASS 120, FAIL 3, SKIP 43, TIMEOUT 0 | PARTIAL |
| `audit_public.py --tree` on the changed ps3recomp files | Passed | VERIFIED |
| Runner dry run, D and F | Hash OK; switches as requested; only the known `SRC_EXE` name hit | VERIFIED |

**Suite failures:**
- `test_rt_pool_srv_layout` ("pool evicts only surfaces unused this frame"): inherited, same on `b1eb158`.
- `test_vpc_watch` ("the environment is read once", and its fixture lacks `<time.h>`): inherited, same on `b1eb158`.
- `test_spurs_kick_wake`: new in this suite. It fails 3 of 3 alone on `774c81d`, and 1 of 1 alone on `001a56f`, which passed it earlier today. No file it builds differs between those commits.

**Why the SPURS failure didn't block launches:** the test asserts that wake-on halves the median of wake-off. Wake-on is unchanged (53 → 56 µs), but the wake-off median fell from 8,550 to 53 µs, with the p90 still near 16 ms. So the machine's baseline changed. Why it changed is unknown (HYPOTHESIS: timer resolution held by another process). The test itself remains failing, not fixed.

## Earlier validation (`001a56f`)

'''
    return head + s.split('\n', 4)[4]


def corr(s):
    head = '''# T169: rendering and performance correlation

## D2 and F2 in game

**Result: the F2 set costs about 6–7 % on normal race frames and about 54 % more PSO-miss time. The draw load matches, and no correction saved host work. T167's slow mode and fence waits weren't involved.**

Same exe, local session, debug layer on in both, so absolute figures are pessimistic. Frames are aligned to the first race frame. Times in ms.

| Window | n | FPS | p50 | p95 | p99 | Draws | Record | PSO | Cmd | Wait | PSO miss ms |
|---|---|---|---|---|---|---|---|---|---|---|---|
| D2 race | 501 | 10.6 | 94.0 | 135.1 | 201.5 | 4,496 | 47.8 | 11.5 | 33.5 | 0.1 | 3,868 |
| F2 race | 457 | 9.6 | 98.4 | 145.7 | 245.7 | 4,549 | 58.0 | 17.5 | 37.1 | 0.1 | 5,951 |
| D2 700–2000 draws | 151 | 16.4 | 44.9 | 50.4 | 201.5 | 1,821 | 23.9 | 10.5 | 12.1 | 0.0 | 1,435 |
| F2 700–2000 draws | 150 | 15.6 | 45.1 | 51.9 | 225.7 | 1,823 | 28.7 | 13.4 | 13.8 | 0.0 | 1,832 |
| D2 3500–5000 | 123 | 10.5 | 95.1 | 100.3 | 102.4 | 4,549 | 49.6 | 5.1 | 41.9 | 0.1 | 41 |
| F2 3500–5000 | 81 | 9.9 | 100.6 | 107.6 | 174.8 | 4,643 | 55.3 | 6.2 | 45.8 | 0.1 | 30 |
| D2 5000–7000 | 124 | 8.4 | 108.1 | 128.8 | 150.8 | 5,582 | 62.9 | 11.9 | 46.9 | 0.1 | 743 |
| F2 5000–7000 | 125 | 7.6 | 114.8 | 136.9 | 185.7 | 5,585 | 75.1 | 17.1 | 52.8 | 0.1 | 1,254 |
| D2 7000+ | 43 | 7.3 | 134.3 | 145.4 | 218.8 | 7,312 | 71.6 | 8.7 | 58.2 | 0.1 | 55 |
| F2 7000+ | 43 | 6.7 | 143.9 | 176.0 | 245.7 | 7,314 | 83.2 | 11.4 | 66.3 | 0.1 | 112 |

| Correlation | D2 | F2 | Reading |
|---|---|---|---|
| Guest draw counts | Median per bin matches F2 within 1 outside the 3500–5000 bin (shift of F2's cut-off window) | Correlation 0.976 by frame; 173 of 457 identical | Same work; timing offsets explain the rest. `RSX_DEPTH_STATE` adds no draws |
| PSO misses | 128 | 129 | Same count; cost per miss up about 50 % (HYPOTHESIS: larger compile from the sRGB rewrite plus the sampler root signature) |
| Shader compiles in the diagnostic window | 2 | 2 | No difference there |
| Samplers | 0 new, 0 binds | 19 new, 490,454 binds (`[vis-work]`) | Bind work; `cmd` rises about 4–8 ms |
| Uploads in the window | 1,073; 450.5 MB | 1,079; 469.9 MB | +4.3 % bytes |
| RT transitions, copies | 0 feedback copies | 5,152 feedback copies | Extra GPU copies; GPU time not measured |
| GPU | No timestamps | No timestamps | **Inconclusive**. `wait` about 0.1 ms means the frame doesn't block on the fence |
| Fence waits | 0 frames at `wait_ms`≈84 | 0 frames | T167's slow mode absent |
| Memory (sampled) | 687 MB | 703 MB | +2.3 %, one sample each |

**T168 distinction:** this is draw-record CPU cost, not duplicate draws. Packet-level duplicates weren't measured here. **Baseline caution:** D1 and F1 ended on the RSXI timeout at about 272–288 frames and never reached the 5,000+ draw scenes, so they can't be compared overall. Their p50 near 50 ms matches D2's first 100 frames (45.3). Scene-matched per-switch cost is **inconclusive** because F2 changes 8 switches.

'''
    return head + '## Offline analysis, before D2 and F2\n\n' + s.split('\n', 4)[4]


edit('GAME_VALIDATION_PLAN.md', plan)
edit('INTEGRATION_READINESS.md', ready)
edit('REGRESSION_VALIDATION.md', regress)
edit('RENDERING_PERFORMANCE_CORRELATION.md', corr)
edit('VISUAL_DEFECT_MATRIX.md', lambda s: s.replace('**Update (runtime):** D1 and F1 ran with no correction active, because `RSX_VISUAL_PROFILE` never reaches the game\'s D3D12 path. See `GAME_VALIDATION_PLAN.md`. Runtime status here stays unverified.',
     '**Update (runtime):** D2 and F2 ran the corrections. The patch-and-depth-state link below did not hold, and depth state damages vehicles. See `VISUAL_CORRECTION_EFFECTIVENESS.md`.'))
for f in ('make_runner_t169.py', 'patch_profile_t169.py', 'patch_profile2_t169.py', 'patch_profile3_t169.py', 'patch_runner_t169.py', 'run_preflight2_t169.cmd', 'd2f2_analysis_t169.py', 'd2f2_crops_t169.py', 'patch_reports_t169.py', 'runtime_summary_t169.py', 'dbwin_d3d12_t169.py'):
    shutil.copy2(HERE / f, R / 'tools' / f)
