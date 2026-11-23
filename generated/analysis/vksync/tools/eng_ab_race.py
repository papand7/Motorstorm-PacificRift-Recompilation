"""Race-only [eng-ab] comparison: difference the cumulative on/off sums between
consecutive [eng-ab] lines and keep the windows where both sides drew a race
(more than MIN_DRAWS draws a present). Usage: eng_ab_race.py <stderr.log> [min_draws]"""
import re
import sys

PAT = re.compile(r'\[eng-ab\] on: ([\d.]+) Mcycles ([\d.]+) ms (\d+) draws a present \((\d+)\) \| '
                 r'off: ([\d.]+) Mcycles ([\d.]+) ms (\d+) draws \((\d+)\)')


def sums(m):
    out = []
    for side in (0, 4):
        cyc, ms, dr, n = float(m[side]), float(m[side + 1]), float(m[side + 2]), int(m[side + 3])
        out.append((cyc * n, ms * n, dr * n, n))
    return out


def main():
    path = sys.argv[1]
    min_draws = float(sys.argv[2]) if len(sys.argv) > 2 else 1000.0
    rows = [sums(m) for m in PAT.findall(open(path, errors='ignore').read())]
    tot = [[0.0, 0.0, 0.0, 0], [0.0, 0.0, 0.0, 0]]
    kept = 0
    for a, b in zip(rows, rows[1:]):
        d = [[b[s][k] - a[s][k] for k in range(4)] for s in (0, 1)]
        if d[0][3] <= 0 or d[1][3] <= 0:
            continue
        if d[0][2] / d[0][3] < min_draws or d[1][2] / d[1][3] < min_draws:
            continue
        kept += 1
        for s in (0, 1):
            for k in range(4):
                tot[s][k] += d[s][k]
    print(f'race windows {kept} (of {max(len(rows) - 1, 0)})')
    for name, t in (('on ', tot[0]), ('off', tot[1])):
        if t[3]:
            print(f'{name}: {t[1] / t[3]:.2f} ms a present ({1000 * t[3] / t[1]:.1f} fps), '
                  f'RSX thread {t[0] / t[3]:.1f} Mcycles, {t[2] / t[3]:.0f} draws, {t[3]} presents')


main()
