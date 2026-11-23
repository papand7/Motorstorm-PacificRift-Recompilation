r"""run_vk.py: RUN_VK_PLAY=1, a play session. The game's GPU watchdog line (GcKernel::Present() Timeout) is
noted but no longer stops the run (the game runs its own timeout callback and goes on); Kk91/Kk92 were
stopped on it while the user drove. usage: py -3 play_mode.py"""
import pathlib

p = pathlib.Path(__file__).resolve().parents[1] / 'ab2' / 'run_vk.py'
s = p.read_text(encoding='utf-8')
if 'RUN_VK_PLAY' in s:
    print('already edited'); raise SystemExit


def rep(old, new):
    global s
    assert s.count(old) == 1, old
    s = s.replace(old, new)


rep("LONG_S = float(os.environ.get('RUN_VK_RACE_S') or 0)",
    "PLAY = os.environ.get('RUN_VK_PLAY') == '1'   # Kk93: play session, the GPU watchdog line does not stop it\n"
    "LONG_S = float(os.environ.get('RUN_VK_RACE_S') or 0)")
rep("""            self.note('serious', line=line[:240])
            self.finish('serious error: ' + line[:80])
            return""",
    """            self.note('serious', line=line[:240])
            if PLAY and 'Present() Timeout' in line:
                return
            self.finish('serious error: ' + line[:80])
            return""")
rep("""        while '--target' in a:   # T98""",
    """        if PLAY and '--stop-on-line' in a:
            j = a.index('--stop-on-line'); del a[j:j + 2]
        while '--target' in a:   # T98""")
p.write_text(s, encoding='utf-8', newline='\n')
print('edited', p.name)
