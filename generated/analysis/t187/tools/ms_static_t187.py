"""T187 (private: reads MotorStorm's lifted PPU code): apply tools/ppu_promote.py to existing lifted sources
and compare the compiled x64 with the default lowering -- same compiler, flags and includes as the game build.
  py -3 generated/analysis/t187/tools/ms_static_t187.py <ps3recomp tree> <out dir> [max regs]
1. chunk ppu_recomp_006.cpp whole: promote stats, compile time, peak memory, .text, x64 per function;
2. a TU of the T185 hot functions (from their chunks) with the chunk preamble: x64 and memory operands each.
No game launch, nothing executed."""
import importlib.util, json, os, re, subprocess, sys, time
TREE, OUT = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
os.makedirs(OUT, exist_ok=True)
REPO = os.path.dirname(TREE)                              # the ps3recomp tree is a sibling of generated/
STAGE = os.path.join(REPO, "generated", "ppu-t173-staging")
sys.path.insert(0, os.path.join(TREE, "tools"))
import ppu_promote as P                                   # noqa: E402
if len(sys.argv) > 3:                                     # optional: --promote-max-regs N
    P.MAX_REGS = int(sys.argv[3])
spec = importlib.util.spec_from_file_location("tpp", os.path.join(TREE, "tools", "test_ppu_promote.py"))
T = importlib.util.module_from_spec(spec); spec.loader.exec_module(T)
clang = T.find_clang(); objdump = os.path.join(os.path.dirname(clang), "llvm-objdump.exe")
INC = ["-I" + STAGE] + ["-I" + os.path.join(TREE, d) for d in ("include", "runtime/ppu", "runtime/spu", "runtime/memory",
                                                               "runtime/syscalls", "runtime/platform", "libs/video")]
INC.append("-I" + os.path.join(REPO, "port-t185"))


def build(src, tag):
    obj = os.path.join(OUT, tag + ".obj")
    dt, peak = T.peak_rss_run([clang] + T.FLAGS + INC + [src, "/Fo" + obj])
    return {"compile_s": round(dt, 1), "peak_mb": round(peak / 2**20) if peak else None,
            "text_bytes": T.text_bytes(objdump, obj), "src_bytes": os.path.getsize(src)}, T.count_x64(objdump, obj)


def split(path):
    s = open(path, encoding="utf-8", errors="surrogateescape", newline="").read()
    i = s.find("\nvoid func_")
    return s, s[:i + 1]


res = {}
# 1. whole chunk
c006 = os.path.join(STAGE, "ppu_recomp_006.cpp")
s, _ = split(c006)
P.PROMOTE_STATS.update({"functions": 0, "promoted": 0, "skipped": {}})
t0 = time.perf_counter(); ps = P.promote_source(s); pass_s = time.perf_counter() - t0
pfile = os.path.join(OUT, "p006.cpp"); open(pfile, "w", encoding="utf-8", errors="surrogateescape", newline="").write(ps)
res["chunk006_pass"] = {"stats": P.stats_line(), "pass_s": round(pass_s, 2)}
b, xb = build(c006, "b006"); p, xp = build(pfile, "p006")
fn = [k for k in xb if k.startswith("func_") and k in xp]
res["chunk006"] = {"base": b, "promo": p, "functions": len(fn), "x64_base": sum(xb[k][0] for k in fn),
                   "x64_promo": sum(xp[k][0] for k in fn), "mem_base": sum(xb[k][1] for k in fn),
                   "mem_promo": sum(xp[k][1] for k in fn)}
gi = {}
for m in re.finditer(r"PPU_TR_BB\(ctx, 0x([0-9A-F]{8})u\)", s):
    pass
# guest size per function from the staging table is not in the chunk; use the address gap to the next function
addrs = sorted(int(k[5:], 16) for k in fn)
sizes = {f"func_{a:08X}": (addrs[i + 1] - a) // 4 for i, a in enumerate(addrs[:-1]) if addrs[i + 1] - a < 0x10000}
gsum = sum(sizes[k] for k in sizes)
res["chunk006"]["guest_insns_est"] = gsum
res["chunk006"]["x64_per_guest_base"] = round(sum(xb[k][0] for k in sizes) / gsum, 2)
res["chunk006"]["x64_per_guest_promo"] = round(sum(xp[k][0] for k in sizes) / gsum, 2)
# 2. hot functions
HOT = ["0002FB60", "00030594", "004B63F0", "00B500A0", "00BCACE8", "008CE850", "0070D1C8", "00A482D0", "00A499F8",
       "00A48A18", "006F69E0", "0050C818", "00BAD240"]
bodies, pre = {}, None
for f in sorted(os.listdir(STAGE)):
    if not re.fullmatch(r"ppu_recomp_\d+\.cpp", f):
        continue
    s, p0 = split(os.path.join(STAGE, f))
    pre = pre or p0
    for h in HOT:
        if h in bodies:
            continue
        m = re.search(r"^void func_%s\(ppu_context\* ctx\) \{.*?\n\}\r?\n" % h, s, re.M | re.S)
        if m:
            bodies[h] = m.group(0)
tb = os.path.join(OUT, "hot_base.cpp"); tp = os.path.join(OUT, "hot_promo.cpp")
open(tb, "w", encoding="utf-8", errors="surrogateescape", newline="").write(pre + "".join(bodies[h] for h in HOT if h in bodies))
open(tp, "w", encoding="utf-8", errors="surrogateescape", newline="").write(P.promote_source(open(tb, encoding="utf-8", errors="surrogateescape", newline="").read()))
_, hb = build(tb, "hot_base"); _, hp = build(tp, "hot_promo")
res["hot"] = {h: {"x64_base": hb[f"func_{h}"][0], "x64_promo": hp[f"func_{h}"][0], "mem_base": hb[f"func_{h}"][1],
                  "mem_promo": hp[f"func_{h}"][1], "lifted_lines": bodies[h].count("\n")} for h in HOT if f"func_{h}" in hb and f"func_{h}" in hp}
json.dump(res, open(os.path.join(OUT, "ms_static.json"), "w"), indent=1)
print(json.dumps({k: v for k, v in res.items() if k != "hot"}, indent=1))
for h, v in res["hot"].items():
    print(f"func_{h}: x64 {v['x64_base']} -> {v['x64_promo']} ({v['x64_promo'] / v['x64_base'] - 1:+.0%}), "
          f"memory operands {v['mem_base']} -> {v['mem_promo']} ({v['mem_promo'] / max(1, v['mem_base']) - 1:+.0%})")
