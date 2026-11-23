"""Repair add_arm_k42.py's insert in run_vk.py (an LF file): its three new lines were joined with no
separator (the script took the line ending from a CR test that is empty for LF)."""
import pathlib
p = pathlib.Path(__file__).resolve().parents[1] / 'ab2' / 'run_vk.py'
b = p.read_bytes()
bad = (b"RACE_STOP = {a: 75.0 for a in ARMS}LONG_S = float(os.environ.get('RUN_VK_RACE_S') or 0)"
       b"   # Kk42: opt-in long race (race stop, timeout)if LONG_S:    RACE_STOP = {a: LONG_S for a in ARMS}")
good = (b"RACE_STOP = {a: 75.0 for a in ARMS}" + bytes([10]) +
        b"LONG_S = float(os.environ.get('RUN_VK_RACE_S') or 0)   # Kk42: opt-in long race (race stop, timeout)" +
        bytes([10]) + b"if LONG_S:" + bytes([10]) + b"    RACE_STOP = {a: LONG_S for a in ARMS}")
assert b.count(bad) == 1, b.count(bad)
p.write_bytes(b.replace(bad, good))
print('ok')
