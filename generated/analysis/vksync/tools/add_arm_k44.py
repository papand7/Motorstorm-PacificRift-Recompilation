"""Add launch Kk44: the first race at an internal resolution scale (RSX_RES_SCALE=1.5: every target at
1.5x, the display 1920x1080). Kk42's configuration (exe pinned to the res-scale build) with
MSPR_PATCH=drs (no dynamic resolution, so the scene is drawn at full size) instead of vfps. The window
is pictured during the race (Le Office snip_window). Correctness first: no crash, race reached, the
image whole.

usage: py -3 add_arm_k44.py <exe sha256>"""
import pathlib
import sys

pin = sys.argv[1]
assert len(pin) == 64, pin
p = pathlib.Path(__file__).resolve().parents[1] / 'ab2' / 'run_vk.py'
s = p.read_bytes().decode('utf-8')
assert '\r\n' not in s
lines = s.split('\n')
i = [k for k, l in enumerate(lines) if l.startswith("ARMS['K']") and '   # Kk43: ' in l][0]
lines.insert(i + 1, "ARMS['K'] = ('r', {**{k: v for k, v in ARMS['K'][1].items() if k != 'MSPR_PATCH'}, "
                    "'MSPR_PATCH': 'drs', 'RSX_RES_SCALE': '1.5'})"
                    "   # Kk44: exe %s, Kk42 + no dynamic resolution + targets at 1.5x (1080p)" % pin[:8])
s = '\n'.join(lines)


def sub(a, b):
    global s
    assert s.count(a) == 1, (a, s.count(a))
    s = s.replace(a, b)


sub("'Kk42', 'Kk43', 'Yy1']", "'Kk42', 'Kk43', 'Kk44', 'Yy1']")
sub("MAX_LAUNCHES = 90", "MAX_LAUNCHES = 91")
sub("PIN = 'c693e2cb6f61c0bf85e7c95472027e853e46b6d1c75828fe3142b8f366b299cc'   # ",
    "PIN = '%s'   # RSX_RES_SCALE (Kk44); " % pin)
p.write_bytes(s.encode('utf-8'))
print('ok')
