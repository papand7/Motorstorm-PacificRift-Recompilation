"""Point run_vk.py's PIN at an exe: copy it to build/motorstorm-vkgame/MotorStormPacificRiftRecomp.exe
(the file `run_vk.py prepare r` copies) and set PIN to its SHA-256. For A/Bs between two links of
the same objects.

usage: py -3 set_pin.py <exe> <note>"""
import hashlib
import pathlib
import re
import shutil
import sys

root = pathlib.Path(__file__).resolve().parents[4]
src = pathlib.Path(sys.argv[1]).resolve()
note = sys.argv[2]
dst = root / 'build' / 'motorstorm-vkgame' / 'MotorStormPacificRiftRecomp.exe'
if src != dst:
    shutil.copyfile(src, dst)
h = hashlib.sha256(dst.read_bytes()).hexdigest()
p = pathlib.Path(__file__).resolve().parents[1] / 'ab2' / 'run_vk.py'
s = p.read_bytes().decode('utf-8')
s2, n = re.subn(r"^PIN = '[0-9a-f]{64}'   # ", "PIN = '%s'   # %s; " % (h, note), s, count=1, flags=re.M)
assert n == 1
p.write_bytes(s2.encode('utf-8'))
print(h)
