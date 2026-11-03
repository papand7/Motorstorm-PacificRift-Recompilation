"""T182: peak working set and private bytes of one bench arm. usage: peak_t182.py <bin> <apart 0|1> KEY=VAL ..."""
import ctypes, ctypes.wintypes as w, os, subprocess, sys
class C(ctypes.Structure):
    _fields_ = [('cb', w.DWORD), ('pf', w.DWORD)] + [(n, ctypes.c_size_t) for n in ('pwss', 'wss', 'ppp', 'pp', 'pnp', 'np', 'pfu', 'ppf')]
b, apart = sys.argv[1], sys.argv[2] == '1'
e = dict(os.environ, BENCH_VTX_GAME='1')
if apart: e['BENCH_QUADS_APART'] = '1'
e.update(kv.split('=', 1) for kv in sys.argv[3:])
e.pop('D3D12_DBG', None)
p = subprocess.Popen([os.path.abspath(f"bin/{b}/bench_draw_path.exe"), '30', '6900', '8', '64', '64', '0'], env=e, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd='.')
p.wait()
c = C(); c.cb = ctypes.sizeof(C)
k = ctypes.WinDLL('psapi'); k.GetProcessMemoryInfo.argtypes = [w.HANDLE, ctypes.POINTER(C), w.DWORD]
k.GetProcessMemoryInfo(int(p._handle), ctypes.byref(c), c.cb)
print(f'rc={p.returncode} peak_ws={c.pwss >> 20} MiB peak_private={c.ppf >> 20} MiB', ' '.join(sys.argv[2:]))
