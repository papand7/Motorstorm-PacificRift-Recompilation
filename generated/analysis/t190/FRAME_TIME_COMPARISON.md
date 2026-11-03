# T190 frame-time comparison

**No in-game data: 0 launches** (preflight failed; `PREFLIGHT.md`). Nothing here measures inline stores.

**Reference only.** T184 arm P (exe `c32cd09d…`, run `20261103-061935-t183-Pp1`), re-derived with `analyze_t190.py Pp1 t183`:

| Metric | T184 P |
|---|---:|
| Frames in window | 802 |
| Mean / median | 68.51 / 68.14 ms |
| p5 / p95 / p99 / max | 63.13 / 74.71 / 82.16 / 104.34 ms |
| SD (cv) | 4.09 ms (6.0 %) |
| FPS | 14.60 |
| Histogram (<60, 60–65 … ≥85 ms) | 0, 140, 420, 203, 28, 5, 4, 2 |

**Noise:**
- One run's standard error of the mean is about 0.14 ms.
- Same-config run-to-run drift has never been measured on this line; P1 vs P2 would be the first estimate.

**Prepared analysis.** `py -3 generated/analysis/t190/tools/analyze_t190.py` gives:
- per run: mean, median, p5–p99, max, SD, cv, FPS and a histogram;
- for P1→B1, P2→B2, pooled P→B, P1→P2 (drift) and B1→B2 (repeatability): Δ ms, Δ %, a bootstrap 95 % CI of the mean difference, and the Δ of the medians, for the frame and every phase.
