"""T169: count D3D12 debug-layer messages from OutputDebugString, without touching the game or its exe.
The backend's D3D12_IQ stops at 80 messages, which CreateGraphicsPipelineState warnings use up before the race,
so race-time errors would go unseen. Keeps one count and one sample per severity + message id. Runs until <stop file> exists.
  py -3 dbwin_d3d12_t169.py <out.json> <stop file>"""
import ctypes as C, ctypes.wintypes as W, json, re, sys, time
from pathlib import Path

k = C.WinDLL('kernel32', use_last_error=True)
k.CreateFileMappingW.restype = W.HANDLE
k.CreateFileMappingW.argtypes = [W.HANDLE, C.c_void_p, W.DWORD, W.DWORD, W.DWORD, W.LPCWSTR]
k.MapViewOfFile.restype = C.c_void_p
k.MapViewOfFile.argtypes = [W.HANDLE, W.DWORD, W.DWORD, W.DWORD, C.c_size_t]
k.CreateEventW.restype = W.HANDLE
k.CreateEventW.argtypes = [C.c_void_p, W.BOOL, W.BOOL, W.LPCWSTR]
k.SetEvent.argtypes = [W.HANDLE]
k.WaitForSingleObject.argtypes = [W.HANDLE, W.DWORD]
k.WaitForSingleObject.restype = W.DWORD

RX = re.compile(r'^D3D12 (ERROR|WARNING|CORRUPTION|MESSAGE|INFO): (.*?)(?:\[ .*? #(\d+): .*?\])?\s*$', re.S)
out, stop = Path(sys.argv[1]), Path(sys.argv[2])
ready = k.CreateEventW(None, False, False, 'DBWIN_BUFFER_READY')
data = k.CreateEventW(None, False, False, 'DBWIN_DATA_READY')
mapping = k.CreateFileMappingW(W.HANDLE(-1), None, 4, 0, 4096, 'DBWIN_BUFFER')
view = k.MapViewOfFile(mapping, 4, 0, 0, 4096)
if not (ready and data and mapping and view):
    raise SystemExit(f'DBWIN setup failed, error {C.get_last_error()}')
if C.get_last_error() == 183:
    print('note: DBWIN_BUFFER already existed; another listener may be sharing it', flush=True)
seen, other, t0, last = {}, 0, time.time(), 0.0


def save():
    out.write_text(json.dumps({'seconds': round(time.time() - t0, 1), 'other_ods_lines': other,
                               'messages': sorted(seen.values(), key=lambda r: -r['n'])}, indent=1), encoding='utf-8')


k.SetEvent(ready)
print('listening', flush=True)
while True:
    if k.WaitForSingleObject(data, 200) == 0:
        pid = C.c_uint32.from_address(view).value
        text = C.string_at(view + 4).decode('utf-8', 'replace')
        k.SetEvent(ready)
        m = RX.match(text)
        if m:
            key = (m.group(1), m.group(3) or m.group(2)[:60])
            r = seen.setdefault(key, {'severity': m.group(1), 'id': m.group(3), 'n': 0, 'pid': pid,
                                      'first_s': round(time.time() - t0, 2), 'sample': text[:400]})
            r['n'] += 1
            r['last_s'] = round(time.time() - t0, 2)
        else:
            other += 1
    if time.time() - last > 5:
        last = time.time()
        save()
    if stop.exists():
        save()
        break
print('stopped', flush=True)
