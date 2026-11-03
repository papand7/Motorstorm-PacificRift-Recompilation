"""T101: pin the backend rules that test_t101_offscreen_replay.c models.

If one of these lines changes, the model in that test no longer describes the
backend and must be revisited. Run from the repo root: python tools/test_t101_pins.py
"""
import pathlib
import re
import sys

SRC = pathlib.Path(__file__).resolve().parents[4] / "ps3recomp-t100/libs/video/rsx_d3d12_backend.c"
text = SRC.read_text(encoding="utf-8", errors="replace")

PINS = [
    # VP-path uploads reject a draw when attribute 0's array is off (6 sites).
    ("attr0 gate x6",
     lambda t: len(re.findall(r"if \(!state->vertex_attribs\[0\]\.enabled\) \{ da_fail\(DA_R_POSITION_ATTRIB_DISABLED\); return 0; \}", t)) == 6),
    # Every replay resets the offscreen pool's `used` marks...
    ("pool used reset per replay",
     lambda t: "for (int _i = 0; _i < MAX_OFF_RTS; _i++) s_d3d.off_rt[_i].used = 0;" in t),
    # ...and a new target evicts a slot not used in this replay.
    ("evict !used",
     lambda t: "if (slot < 0) {   /* evict an entry not used this frame */" in t
     and "if (!s_d3d.off_rt[i].used) { slot = i; break; }" in t),
    # Host clear of the backbuffer and shared depth only without keep_targets.
    ("keep_targets guards entry clear",
     lambda t: re.search(r"if \(!keep_targets\) \{\s*s_d3d\.cmd_list->lpVtbl->ClearRenderTargetView\(", t) is not None),
    # The flip presents only with a display draw, counting early-replayed ones.
    ("flip display gate",
     lambda t: "int flip_has_display = (s_d3d.draw_count == 0);" in t
     and "if (s_vpf.flushed_display) flip_has_display = 1;" in t),
    # vp_flush replays without a Present.
    ("early replay no present",
     lambda t: re.search(r"const int keep = s_present_this_frame;\s*s_present_this_frame = 0;\s*render_frame\(\);", t) is not None),
    # The frame dump is not gated on s_present_this_frame (it also samples
    # early replays and offscreen-only batches).
    ("dump not present-gated",
     lambda t: "int dumping = (s_d3d.dump_frames_left > 0 && s_d3d.readback_buf\n                   && s_d3d.dump_skip_left == 0);" in t),
]

bad = 0
for name, ok in PINS:
    r = ok(text)
    print(("ok   " if r else "FAIL ") + name)
    bad += not r
print(f"{'PASS' if not bad else 'FAIL'}: {len(PINS) - bad}/{len(PINS)} pins")
sys.exit(1 if bad else 0)
