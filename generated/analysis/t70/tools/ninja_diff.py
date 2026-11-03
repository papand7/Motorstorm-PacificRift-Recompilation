MS_ROOT = str(__import__('pathlib').Path(__file__).resolve().parents[4])  # repository root
"""T70: compare the configured AOT build (build/motorstorm-t70-aot) with the T62/T64C build
(build/motorstorm-t62-font-c529ab0), compile entry by compile entry.

For every object: DEFINES, FLAGS and INCLUDES must be identical once ps3recomp-t62 -> ps3recomp-t70,
port -> port-t70 and the build directory name are mapped. Prints objects only in one build and any
entry whose flags differ, then the flags the 32 AOT TUs get. Exit 0 if the only differences are the
expected AOT additions."""
import re, sys

ROOT = MS_ROOT
A = ROOT + "\\build\\motorstorm-t62-font-c529ab0\\build.ninja"
B = ROOT + "\\build\\motorstorm-t70-aot\\build.ninja"


def norm(s):
    s = s.replace("/", "\\")
    for a, b in (("ps3recomp-t62", "ps3recomp-t70"), ("motorstorm-t62-font-c529ab0", "motorstorm-t70-aot"),
                 (ROOT + "\\port\\", ROOT + "\\port-t70\\"), (ROOT + "\\port ", ROOT + "\\port-t70 ")):
        s = s.replace(a, b)
    if s.endswith(ROOT + "\\port"):
        s = s[:-len("port")] + "port-t70"
    return s


def entries(path):
    txt = open(path, encoding="utf-8", errors="replace").read()
    out = {}
    for m in re.finditer(r"^build ([^:]+\.obj): (C|CXX)_COMPILER\S* (\S+)(.*?)(?=^build |\Z)", txt, re.S | re.M):
        obj, body = norm(m.group(1)), m.group(4)
        f = {k: norm(v.strip()) for k, v in re.findall(r"\n  (DEFINES|FLAGS|INCLUDES) = (.*)", body)}
        out[obj] = (norm(m.group(3)), f)
    return out


a, b = entries(A), entries(B)
only_a = sorted(set(a) - set(b))
only_b = sorted(set(b) - set(a))
diff = [o for o in sorted(set(a) & set(b)) if a[o][1] != b[o][1]]
print(f"objects: t62 {len(a)}, t70-aot {len(b)}, common {len(set(a) & set(b))}")
print(f"only in t62 build: {len(only_a)}")
for o in only_a[:20]:
    print("  ", o)
print(f"only in t70-aot build: {len(only_b)}")
aot = [o for o in only_b if "wws_reloc" in b[o][0]]
other = [o for o in only_b if o not in aot]
print(f"  of which WWS AOT TUs (generated/spu_raw/wws_reloc): {len(aot)}")
for o in other:
    print("   unexpected:", o, b[o][0])
print(f"common objects with different DEFINES/FLAGS/INCLUDES: {len(diff)}")
for o in diff[:20]:
    for k in ("DEFINES", "FLAGS", "INCLUDES"):
        if a[o][1].get(k) != b[o][1].get(k):
            print("  ", o, k, "\n     t62:", a[o][1].get(k), "\n     t70:", b[o][1].get(k))
flags = {tuple(sorted(b[o][1].items())) for o in aot}
print(f"distinct flag sets among the AOT TUs: {len(flags)}")
for fs in flags:
    for k, v in fs:
        print(f"   {k} = {v}")
ok = not only_a and not other and not diff and len(aot) == 32 and len(flags) == 1
print("RESULT", "PASS" if ok else "CHECK")
sys.exit(0 if ok else 1)
