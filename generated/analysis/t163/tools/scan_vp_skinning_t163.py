"""T163: scan translated RSX vertex programs (captured HLSL) for GPU-skinning
signatures: ARL (address register load) and relative constant reads
(vp_c[(N + aK.c) & 511u]). Prints per-shader counts and a dedup summary.

Usage: python scan_vp_skinning_t163.py <root> [<root> ...]
"""
import hashlib
import os
import re
import sys

REL = re.compile(r"vp_c\[\((\d+)u \+ a(\d)\.([xyzw])\) & 511u\]")
ARL = re.compile(r"\{ int4 _a = \(int4\)floor\((.*?)\); a(\d)\.")
VS = re.compile(r"VSOutput main\(VSInput input\)")


def scan(roots):
    seen = {}
    total = 0
    for root in roots:
        for dp, _, fns in os.walk(root):
            for fn in fns:
                if not fn.endswith(".hlsl"):
                    continue
                p = os.path.join(dp, fn)
                try:
                    s = open(p, encoding="utf-8", errors="replace").read()
                except OSError:
                    continue
                if not VS.search(s):
                    continue
                total += 1
                h = hashlib.sha1(s.encode()).hexdigest()[:12]
                if h in seen:
                    seen[h]["n"] += 1
                    continue
                rel = REL.findall(s)
                arl = ARL.findall(s)
                seen[h] = {"n": 1, "path": p, "rel": rel, "arl": arl,
                           "inputs": sorted(set(re.findall(r"input\.a(\d+)", s)), key=int)}
    return total, seen


def main():
    total, seen = scan(sys.argv[1:])
    skin = {h: v for h, v in seen.items() if v["rel"] or v["arl"]}
    print(f"vertex shaders: {total} files, {len(seen)} unique, "
          f"{len(skin)} unique with ARL/relative constants")
    for h, v in sorted(skin.items(), key=lambda kv: -kv[1]["n"]):
        bases = sorted({int(b) for b, _, _ in v["rel"]})
        arl_src = sorted({a for a, _ in v["arl"]})
        print(f"{h} x{v['n']} inputs={','.join(v['inputs'])} rel_reads={len(v['rel'])} "
              f"bases={bases[:8]} arl_src={arl_src[:4]}\n    {v['path']}")


if __name__ == "__main__":
    main()
