"""Log the game process's file read rate (GetProcessIoCounters) once a second while it runs.

usage: py -3 io_rate.py <out.txt> [max_seconds=300]
Lines: seconds since the process appeared, read MB/s, read ops/s, cumulative read MB, write MB/s,
write ops/s."""
import ctypes
import ctypes.wintypes as wt
import subprocess
import sys
import time

EXE = 'MotorStormPacificRiftRecomp.exe'
k32 = ctypes.windll.kernel32


class IO(ctypes.Structure):
    _fields_ = [(n, ctypes.c_ulonglong) for n in ('ReadOps', 'WriteOps', 'OtherOps', 'ReadBytes', 'WriteBytes',
                                                  'OtherBytes')]


def game_pid():
    out = subprocess.run(['tasklist', '/FI', f'IMAGENAME eq {EXE}', '/FO', 'CSV', '/NH'],
                         capture_output=True, text=True).stdout
    for line in out.splitlines():
        p = [x.strip('"') for x in line.split('","')]
        if len(p) > 1 and p[0] == EXE:
            return int(p[1])
    return None


def main():
    out = open(sys.argv[1], 'w')
    limit = float(sys.argv[2]) if len(sys.argv) > 2 else 300
    t0 = time.time()
    pid = None
    while pid is None and time.time() - t0 < 300:
        pid = game_pid()
        time.sleep(0.5)
    if pid is None:
        print('no game process', file=out)
        return 1
    k32.OpenProcess.restype = wt.HANDLE
    h = k32.OpenProcess(0x1000, False, pid)   # PROCESS_QUERY_LIMITED_INFORMATION
    io = IO()
    t1 = time.time()
    last = None
    while time.time() - t1 < limit:
        if not k32.GetProcessIoCounters(h, ctypes.byref(io)):
            break
        cur = (time.time(), io.ReadBytes, io.ReadOps, io.WriteBytes, io.WriteOps)
        if last:
            dt = cur[0] - last[0]
            print(f'{cur[0] - t1:7.1f} {(cur[1] - last[1]) / dt / 1e6:8.2f} MB/s {(cur[2] - last[2]) / dt:8.0f} ops/s '
                  f'{cur[1] / 1e6:9.1f} MB  write {(cur[3] - last[3]) / dt / 1e6:8.2f} MB/s '
                  f'{(cur[4] - last[4]) / dt:6.0f} ops/s', file=out, flush=True)
        last = cur
        time.sleep(1.0)
    return 0


if __name__ == '__main__':
    sys.exit(main())
