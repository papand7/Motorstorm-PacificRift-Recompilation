"""T170 baseline crash isolation: arm A of ab/run_t170.py with the T169 exe (ps3recomp 542420e, T170's parent), pinned.
Other differences: stops about 3 s after an unresolved indirect call or a guest null write, so the crash dump reaches the log.
  py -3 generated/analysis/t170/tools/make_runner_base_t170.py
  py -3 generated/analysis/t170/base169/run_base.py prepare r ; dryrun A ; launch A B1"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
AB = HERE.parent / 'ab'
OUT = HERE.parent / 'base169'
src = (AB / 'run_t170.py').read_text(encoding='utf-8')
PIN = '59019e06b9a39074ea2d47e90dd3c41f0299d73463e610db2ce8fa030011ba08'


def sub(old, new):
    global src
    assert src.count(old) == 1, (old[:80], src.count(old))
    src = src.replace(old, new)


sub("'motorstorm-t170'", "'motorstorm-t169'")
sub("PIN = 'f46eb9910d7eb01974fbe43d33b2ad163bd5811eae29a7e60c1c96e1aa80d9c1'", f"PIN = '{PIN}'")
sub("ARM, RUN_NAME = arm, f't170-{arm}{tag}'", "ARM, RUN_NAME = arm, f't170base-{arm}{tag}'")
sub("""        if RX_SERIOUS.search(line):
""", """        if getattr(self, 'crash_t', None) is None and ('unresolved indirect call' in line or line.startswith('[null-write]')):
            self.crash_t = now
            self.note('crash', line=line[:240])
        if RX_SERIOUS.search(line):
""")
sub("""        if (self.rt / 'STOP').exists():
""", """        if getattr(self, 'crash_t', None) is not None and self.now() - self.crash_t >= 3.0:
            self.finish('guest crash')
            return True
        if (self.rt / 'STOP').exists():
""")
OUT.mkdir(exist_ok=True)
(OUT / 'cpath_sites.cfg').write_bytes((AB / 'cpath_sites.cfg').read_bytes())
(OUT / 'run_base.py').write_text(src, encoding='utf-8')
print('wrote', OUT / 'run_base.py')
