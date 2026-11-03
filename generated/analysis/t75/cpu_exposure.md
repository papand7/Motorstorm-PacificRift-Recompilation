# T75: how the CPU turns the exposure surface into VP constant c33.x

Static analysis only, with no launch, build or source change. Sources:
- the lifted `generated/ppu/ppu_recomp_010.cpp` (`func_004C3778` at lines 43503–43781, the ctor `func_004C6178` at 45270+);
- Capstone disassembly of `generated/decrypted/EBOOT.elf` (`ppcdis.py`, `elfconst.py`, `dump2.py` in this folder; ctor listing in `ctor_all.txt`).

**TOC (VERIFIED):** `func_004C3778` runs with r2 = `0x010AFBE4`. Stub `0x00754F78` adds `0xFFF4` to the caller's `0x0109FBF0`. The TOC float constants below were read at that base. The values from `0x0109FBF0` are pointers and do not apply here.

## Reconstructed algorithm (VERIFIED from disassembly)

```
lock  = obj->vt[9](obj, &base)                       // 0x4C3808, [[this+0x34]]+0x24
sum   = 0.0                                          // TOC-0x75C0 = 0.0
for p in vector<float2> [this+0x1A4 .. this+0x1A8):  // 8-byte elements
    x = (int)(p.x*16); y = (int)(p.y*16)             // TOC-0x75BC = 16.0, fctiwz (truncate)
    g = half_to_float(*(u16*)(base + y*128 + x*8 + 2))   // 0x4C38A4 lhz +2 = G half; func_00756E08
    sum += log2_approx(g)                            // 0x4C38C8..0x4C3924: exponent bits + poly (1/ln2 = 1.44269)
n     = (end-begin)>>3                               // 0x4C3940
gm    = exp2_approx(sum / n)                         // 0x4C395C..0x4C3A2C: geometric mean
target = clamp(K / gm, Emin, Emax)                   // 0x4C3A50 fdivs, 0x4C3A5C/60 fsel
         K=[this+0xBC], Emin=[this+0xC0], Emax=[this+0xC4]
[ [TOC-0x7610] + 4 ] = target
obj->vt[7](obj)                                      // unlock, 0x4C3A80
s = [this+0x18C]
if (s < target)  s += (target - s) * R               // 0x4C3B54, R=[this+0xD0]
else             s += (target - s) * R * 0.375       // 0x4C3AB0, TOC-0x75B8 = 0.375
[this+0x18C] = s
c = 1 + (s - 1) * S                                  // S=[this+0xB8], 0x4C3AC0 / 0x4C3B64
if (c is NaN) { c = 1.0; [this+0x19D] = 1 }          // 0x4C3B7C (Inf passes)
[this+0x188] = c
stack[0x74] = c; SetVPConstant(33, &stack[0x74])     // 0x4C3AE4 li r4,0x21 → func_00756DF8 → func_007351E0
```

`0x4C3728` (the other c33 writer, at `0x4C3748`) is a small reset routine. It writes `1.0` to `sp+0x70` and sets c33 from it.

`func_007351E0` emits NV4097 method `0x1EFC` with index 33 and 4 words read from `r5[0..15]`.

## Answers

1. **G or R: G (VERIFIED).** `lhz r10, 2(r8)` at `0x4C38A4` reads the second big-endian half, so the CPU never reads R (the GPU's E).
2. **How the samples are combined: geometric mean (VERIFIED).**
   - The function averages log2 over all points, then applies exp2.
   - The points are a `std::vector<float2>` of normalised (x, y) at `[this+0x1A4]` (begin) and `[this+0x1A8]` (end), with `this+0x1A0` as the vector base. The ctor at `0x4C63CC` zeroes it.
   - The count is (end−begin)/8 and is data-driven. The run-time count is 5.
   - The coordinates are multiplied by 16 and truncated. Who fills the vector is not traced (PARTIAL).
3. **Invalid samples (VERIFIED).**
   - **No clamp:** the CPU never applies the 0.006/3 limits to the samples.
   - **Zero:** the log2 approximation gives 0.0 → −127 exactly (exponent field 0), so one zero among five pulls the average down by ≈25.4. gm is then ≲1e-8 and K/gm hits Emax. With all samples zero, gm = 0.0, K/0 = +Inf, and the result is Emax.
   - **Inf:** log2 gives ≈+128, which drives the target to Emin.
   - **NaN:** gives ≈+128 as well. If gm itself is NaN, `fsel` picks Emax.
   - **Negative:** the sign bit is ignored by the exponent extract and corrupts the polynomial input, so the result is garbage.
   - **Output guard:** only a NaN result for c33.x is replaced by 1.0.
4. **Temporal smoothing: IIR with a fixed rate per call (VERIFIED).**
   - There is no dt in this function. It rises at R = `[this+0xD0]` and falls at 0.375·R.
   - The ctor default is R = 0.1 (TOC-0x7590), but the data overrides it (see 6).
   - The two call sites (`0x34CF30` and `0x34F954`) are mutually exclusive branches (`beq 0x34F928` at `0x34CEF0`), so there is one call per post-process invocation.
5. **Formula: c33.x = 1 + S·(s − 1)**, where s is the IIR state tracking clamp(K / geomean(G), Emin, Emax) (VERIFIED structure).
   - **Ctor defaults (VERIFIED, `0x4C62B8–0x4C6348`):** S = 0, K = 0.5, Emin = 0.5, Emax = 2.0, [+0xC8] = 8.0, [+0xCC] = 3.0, R = 0.1, s0 = 1.0. These defaults would give c33 = 1, so the parameters are loaded later from data. No setter was found, and no float 35.3 exists in the ELF.
   - **Inferred run-time parameters (HYPOTHESIS, strong):** K = 0.3, S = 0.7, Emax = 50 (= 0.3/0.006), Emin = 0.1 (= 0.3/3).
   - With these, the CPU formula is identical to the GPU FP's E = 1 + 0.7·(clamp(0.3/G, 0.1, 50) − 1), and c33∞ = 1 + 0.7·49 = **35.3**, the observed maximum. 35.3 is therefore the *CPU* clamp Emax, not the GPU per-pixel value.
   - **c33.y/z/w:** never written in `func_004C3778`. Only `sp+0x74` is stored, while `func_007351E0` reads `sp+0x74..0x83`, so `y`, `z` and `w` are stale stack bytes (VERIFIED).
   - That `w = 50` equals Emax is a HYPOTHESIS: a leftover from an earlier frame at the same depth. Garage first frame w = 0 is consistent with stack garbage.
6. **Consistency (PARTIAL).** All-zero samples give target = Emax and c33 → 35.3 asymptotically ✓.
   - The garage first frame from s0 = 1 gives c = 1 + 34.3·R = 3.401, so **R = 0.0700** (exact to 4 digits).
   - Fitting the T71 and T72 increments gives r ≈ 0.085 and 0.082 per captured frame. T72's increment is 10× smaller at 1/10 the distance from 35.3, so the exponential approach to C = 35.30 is confirmed.
   - The ~20 % gap between 0.07 and 0.085 is unexplained. Possible causes: the rate is data-driven per scene, or `[this+0xD0]` is rewritten elsewhere (for example dt-scaled), or there are occasional extra calls per flip.
7. **Predictions (VERIFIED arithmetic, given the HYPOTHESIS parameters).**
   - **(0.67, 0, 0, 0, 0):** gm = 2.4e-31 and K/gm = 1.2e30, clamped to 50, so **c33 → 35.3**, the same as all zero. Even (0.67 ×4, 0) gives gm = 1.6e-8, which also pins to 35.3.
   - **All five ≈ 0.67:** target = 0.448, so **c33 → 0.613**. This matches the GPU's E = 0.611 at G = 0.674. It falls at 0.375·R ≈ 0.026–0.032 per frame, which takes about 200–300 frames to settle. The loop is closed through G = sqrt(lum/c33_prev), so the final value shifts.
   - **Yes:** restoring lower-screen luminance should lower exposure from 35.3 to about 0.6. It is necessary that **every** sample point is non-zero, because the geometric mean makes a single zero sample pin the target to Emax.
