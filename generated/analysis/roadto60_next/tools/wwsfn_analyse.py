"""roadto60_next: compare base vs fast Wws lifts on the FNREC replay (wwsfn run output), and summarise bench output.

usage:
  py -3 wwsfn_analyse.py compare <run_base.txt> <run_fast.txt>     bit-exact fingerprint comparison
  py -3 wwsfn_analyse.py bench <bench_base.txt> <bench_fast.txt>   per-module lifted-time ratio (factors)
Output: a short text report (stdout) and, with --json <file>, the same numbers as JSON.
Labels: the comparison is VERIFIED for the snapshots it covers; timing is MEASURED (function level) and
any whole-job or frame number derived from it is MODELLED."""
import collections
import json
import statistics as st
import sys


def parse_run(path):
    rows = {}
    for line in open(path, encoding="utf-8", errors="replace"):
        line = line.strip()
        if not line or line.startswith("[rtk]"):
            continue
        parts = line.split()
        name = parts[0]
        if parts[0] == "TIMEOUT":
            name = parts[1]
            rows[name] = ("TIMEOUT", line)
        elif parts[0] in ("NOENTRY", "BADFILE", "NOTHREAD"):
            rows[parts[1]] = (parts[0], line)
        elif "halted=" in line:
            rows[name] = ("OK", line)
    return rows


def compare(a_path, b_path):
    a, b = parse_run(a_path), parse_run(b_path)
    common = sorted(set(a) & set(b))
    only_a = sorted(set(a) - set(b))
    only_b = sorted(set(b) - set(a))
    same = 0
    diff = []
    cls = collections.Counter()
    for k in common:
        ka, la = a[k]
        kb, lb = b[k]
        cls[(ka, kb)] += 1
        if ka == kb == "OK":
            if la.split(" ", 1)[1] == lb.split(" ", 1)[1]:
                same += 1
            else:
                diff.append((k, la, lb))
        elif ka == kb:
            same += 1
        else:
            diff.append((k, la, lb))
    rep = {"snapshots_compared": len(common), "identical": same, "different": len(diff),
           "only_in_base": len(only_a), "only_in_fast": len(only_b),
           "classes": {f"{x}/{y}": n for (x, y), n in cls.items()},
           "first_differences": [{"file": k, "base": x, "fast": y} for k, x, y in diff[:10]]}
    return rep


def bench(a_paths, b_paths):
    """a_paths / b_paths: the interleaved bench rounds of each variant (same ordered snapshot list). Per snapshot the
    minimum over rounds is kept (min is the least noisy estimator of a fixed-work run); rounds must agree in length."""
    def load(p):
        rows = []
        for line in open(p, encoding="utf-8", errors="replace"):
            if line.startswith("bench "):
                f = line.split()
                d = dict(x.split("=", 1) for x in f[2:] if "=" in x)
                rows.append((int(d["img"]), d["addr"], int(d["run_ns"]), int(d["restore_ns"]), int(d["steps"])))
        return rows

    def merge(paths):
        rounds = [load(p) for p in paths]
        n = len(rounds[0])
        assert all(len(r) == n for r in rounds), "bench rounds differ in length"
        out = []
        for i in range(n):
            cand = [r[i] for r in rounds]
            best = min(cand, key=lambda x: x[2])
            out.append((best[0], best[1], best[2], min(c[3] for c in cand), best[4]))
        return out
    a, b = merge(a_paths), merge(b_paths)
    assert len(a) == len(b), "variants differ in length"
    per_img = collections.defaultdict(list)
    for ra_row, rb_row in zip(a, b):
        ia, addr, ra, ca, sa = ra_row
        ib, _, rb, cb, sb = rb_row
        if ra <= 0 or rb <= 0:
            continue
        per_img[ia].append((addr, ra, rb, ca, sa, sb))
    rep = {}
    for img, rows in per_img.items():
        ra = sum(r[1] for r in rows)
        rb = sum(r[2] for r in rows)
        rep[str(img)] = {"snapshots": len(rows), "base_run_us_total": round(ra / 1e3, 1),
                         "fast_run_us_total": round(rb / 1e3, 1),
                         "ratio_fast_over_base_sum": round(rb / ra, 4) if ra else None,
                         "ratio_median_per_snapshot": round(st.median(r[2] / r[1] for r in rows if r[1]), 4),
                         "copy_us_mean": round(st.mean(r[3] for r in rows) / 1e3, 2),
                         "base_mean_run_us": round(ra / len(rows) / 1e3, 2),
                         "steps_equal": all(r[4] == r[5] for r in rows)}
    return rep


if __name__ == "__main__":
    mode = sys.argv[1]
    out = None
    args = sys.argv[2:]
    if "--json" in args:
        i = args.index("--json")
        out = args[i + 1]
        args = args[:i] + args[i + 2:]
    if mode == "compare":
        rep = compare(*args)
    else:   # bench <base round files, comma-separated> <fast round files, comma-separated>
        rep = bench(args[0].split(","), args[1].split(","))
    print(json.dumps(rep, indent=1))
    if out:
        open(out, "w", encoding="utf-8").write(json.dumps(rep, indent=1))
