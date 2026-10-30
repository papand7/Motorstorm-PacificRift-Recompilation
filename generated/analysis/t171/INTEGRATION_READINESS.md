# T171: integration readiness

**Not ready to merge as a confirmed visual fix.** Cause and offline behaviour are verified; the in-game picture is not.

- Commit: ps3recomp `b282e26` on `agent/t171-tire-track-depth-fix`, on top of `542420e` (T169 head). Not pushed or merged.
- Exe: `build/motorstorm-t171/MotorStormPacificRiftRecomp.exe`, SHA-256 `4450EA1FA8D31BCFD6F24CA9B6018459331DAD96D6E4D14989B9511D6D12A8BE`, built with port-t161. Never launched.
- Rollback: `RSX_SHADER_WINDOW=0`.

## Risks

1. Water and surf (`0x07200641`, `0x070B0701`) also change. This is guest-correct, but the shoreline is unverified.
2. VB's blocky patches may have a different cause and survive the fix.
3. The fix leaves the depth-write, RT-feedback and window mismatches in place, and these may still affect track edges.
4. Vehicle speckle: T171 leaves depth state and vehicle programs unchanged, so no new risk is expected. The capture checks this.

## Gate

Run `GAME_CAPTURE_REQUEST.md` once authorized; merge only if its expected evidence holds.
