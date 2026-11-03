"""T187 (private): attribute the static x64 growth of promote-regs on the hot-function TU.
Variant 'nocold' = promoted source with the spill stores inside the trace-hook cold blocks removed
(static measurement only, not a correct program). Variant 'noreload' additionally drops the reloads
after calls. Compares x64 / memory operands of base, promo, nocold, noreload.
  py -3 generated/analysis/t187/tools/attrib_t187.py <ps3recomp tree> <ms_static dir>"""
import importlib.util, json, os, re, sys
TREE, D = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
spec_t = importlib.util.spec_from_file_location("tpp", os.path.join(TREE, "tools", "test_ppu_promote.py"))
T = importlib.util.module_from_spec(spec_t); spec_t.loader.exec_module(T)
clang = T.find_clang(); objdump = os.path.join(os.path.dirname(clang), "llvm-objdump.exe")
REPO = os.path.dirname(TREE)
STAGE = os.path.join(REPO, "generated", "ppu-t173-staging")
INC = ["-I" + STAGE] + ["-I" + os.path.join(TREE, d) for d in ("include", "runtime/ppu", "runtime/spu", "runtime/memory",
                                                               "runtime/syscalls", "runtime/platform", "libs/video")]
INC.append("-I" + os.path.join(REPO, "port-t185"))
src = open(os.path.join(D, "hot_promo.cpp"), encoding="utf-8", errors="surrogateescape", newline="").read()
COLD = re.compile(r"(if \(__builtin_expect\(g_ppu_trace_mask & \d+u, 0\)\) \{)((?: ctx->(?:gpr\[\d+\]|cr) = _pr(?:\d+|cr);)+)")
nocold = COLD.sub(lambda m: m.group(1), src)
RELOAD = re.compile(r"^\s*_pr(\d+|cr) = ctx->(gpr\[\d+\]|cr);\s*$", re.M)
noreload = RELOAD.sub("", nocold)
out = {}
for tag, text in (("nocold", nocold), ("noreload", noreload)):
    p = os.path.join(D, f"hot_{tag}.cpp")
    open(p, "w", encoding="utf-8", errors="surrogateescape", newline="").write(text)
    obj = os.path.join(D, f"hot_{tag}.obj")
    T.peak_rss_run([clang] + T.FLAGS + INC + [p, "/Fo" + obj])
    out[tag] = T.count_x64(objdump, obj)
ms = json.load(open(os.path.join(D, "ms_static.json")))
res = {}
for h, v in ms["hot"].items():
    k = f"func_{h}"
    res[h] = dict(v, x64_nocold=out["nocold"][k][0], mem_nocold=out["nocold"][k][1],
                  x64_noreload=out["noreload"][k][0], mem_noreload=out["noreload"][k][1])
    r = res[h]
    print(f"{k}: x64 base {r['x64_base']} promo {r['x64_promo']} nocold {r['x64_nocold']} noreload {r['x64_noreload']} | "
          f"mem base {r['mem_base']} promo {r['mem_promo']} nocold {r['mem_nocold']} noreload {r['mem_noreload']}")
tot = {c: sum(r[c] for r in res.values()) for c in ("x64_base", "x64_promo", "x64_nocold", "x64_noreload",
                                                    "mem_base", "mem_promo", "mem_nocold", "mem_noreload")}
print("TOTAL", tot)
json.dump({"hot": res, "total": tot}, open(os.path.join(D, "attrib.json"), "w"), indent=1)
