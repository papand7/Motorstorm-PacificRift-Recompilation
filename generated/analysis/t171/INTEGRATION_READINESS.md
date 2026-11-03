# T171: integration readiness

**Correction is correct and low-risk, and has one visible in-game improvement. It does not resolve the blocky patches, and its FPS cost is unmeasured.** Not pushed or merged.

- Commit: ps3recomp `b282e26` on `agent/t171-tire-track-depth-fix`, on top of `542420e`.
- Exe SHA-256: `4450EA1FA8D31BCFD6F24CA9B6018459331DAD96D6E4D14989B9511D6D12A8BE`. Two authorized launches, both complete.
- Rollback: `RSX_SHADER_WINDOW=0`.

## Open

1. Rectangular patches remain with the fix on and need their own investigation. Candidate draws, unproven: fp `0x022C20C1` boxes and stale `0x0243AB00` content.
2. No close-up tracks, and no arm B RSXI frame with a WPOS draw. Sky-and-trees removal rests on the mechanism, the fixture and the fragment comparison.
3. FPS comparison contaminated by T170's suite during arm B. A clean comparison needs a new authorization and an idle machine.
4. Depth-write and RT-feedback mismatches remain; `RSX_DEPTH_STATE` stays off.
5. No PS3 reference exists.

## Decision

The arm A/B evidence supports keeping the default-on correction. The patch defect should stay open as a separate item.
