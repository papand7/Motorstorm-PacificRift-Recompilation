"""T163: find candidate VEC->SCA same-instruction hazards in translated RSX
vertex programs. rsx_vp_decompiler.c emits the VEC store of an instruction
before evaluating its SCA operand, so an SCA op whose source temp is the VEC
destination would read the new value. Only blocks that can only be SCA ops
(rcp/rsq/exp2/log2/sin/cos/LIT) are checked; the preceding block must be a
VEC block writing an overlapping temp component. A hit is a candidate (the
HLSL alone cannot show both blocks came from one instruction).

Usage: python scan_vp_dualissue_t163.py <root> [...]
"""
import hashlib
import os
import re
import sys

BLOCK = re.compile(r"\{ float4 _v = \(float4\)\((.*?)\);(?: _v = saturate\(_v\);)?\n"
                   r"((?:        (?:if \(cc\[\d\]\.[xyzw] [^)]*\) )?[or]\[\d+\]\.[xyzw]+ = _v\.[xyzw]+;\n)+)"
                   r"    \}", re.S)
STORE = re.compile(r"([or])\[(\d+)\]\.([xyzw]+) = ")
SCA = re.compile(r"^(?:\(1\.0/|clamp\(1\.0/|rsqrt\(|exp2\(|log2\(|sin\(|cos\(|float4\(1\.0, max\()")
READ = re.compile(r"r\[(\d+)\]\)\.([xyzw]{4})\)?\.x|r\[(\d+)\]\)\.([xyzw]{4})")


def blocks(src):
    for m in BLOCK.finditer(src):
        writes = [(k, int(i), set(c)) for k, i, c in STORE.findall(m.group(2))]
        yield m.group(1), writes


def main():
    seen = set()
    hits = 0
    n = 0
    for root in sys.argv[1:]:
        for dp, _, fns in os.walk(root):
            for fn in fns:
                if not (fn.startswith("vp_") and fn.endswith(".hlsl")):
                    continue
                s = open(os.path.join(dp, fn), encoding="utf-8", errors="replace").read()
                h = hashlib.sha1(s.encode()).hexdigest()
                if h in seen:
                    continue
                seen.add(h)
                n += 1
                prev = None
                for rhs, writes in blocks(s):
                    if prev and SCA.match(rhs):
                        # scalar ops read component .x of their swizzled source
                        for m in re.finditer(r"r\[(\d+)\]\)\.([xyzw])[xyzw]{3}\)\.x", rhs):
                            reg, comp = int(m.group(1)), m.group(2)
                            for k, i, cs in prev:
                                if k == "r" and i == reg and comp in cs:
                                    hits += 1
                                    print(f"{fn}: SCA '{rhs[:60]}' reads r[{reg}].{comp} "
                                          f"written by preceding VEC block")
                    prev = None if SCA.match(rhs) else writes
    print(f"unique VPs: {n}, candidate hazards: {hits}")


if __name__ == "__main__":
    main()
