"""T70: check generated/spu_raw/wws_reloc against the original retail EBOOT.

usage: py -3 -I verify_wws_reloc.py <EBOOT.elf> <retail_jobs.json> <wws_reloc dir> <modules dir>

For every spu_reloc_register_module(...) call in wws_reloc_register.c, it checks,
independently of lift_wws_reloc.py:
  - the module is one of the 31 retail images at its EBOOT file offset (header magic);
  - the registered span equals the image size and the bytes there are the
    module file byte for byte, and its sha256 matches the file name;
  - sig = EBOOT bytes +0x00..+0x10, entry16 = bytes at +entry_off, entry_off = header
    +0x10, link base = header +0x28;
  - body hash = spu_reloc_body_hash (re-implemented here from spu_reloc.h) of the span;
  - image ids are unique and the manifest agrees with the registration;
  - the PM registration is image 1297305682, code-base word 0x1320, return 0x3214.
Exit 0 only if every check passes."""
import hashlib, json, os, re, struct, sys

M64 = (1 << 64) - 1


def body_hash(p):
    n = len(p)
    h = (0x9E3779B97F4A7C15 ^ n) & M64
    for i in range(0, n, 8):
        w = 0
        for k in range(8):
            w = (w << 8) | (p[i + k] if i + k < n else 0)
        h ^= w
        h = (h * 0xFF51AFD7ED558CCD) & M64
        h ^= h >> 32
    return h


eboot = open(sys.argv[1], "rb").read()
jobs = json.load(open(sys.argv[2]))
out, mods = sys.argv[3], sys.argv[4]
reg = open(os.path.join(out, "wws_reloc_register.c")).read()
man = {m["file"]: m for m in json.load(open(os.path.join(out, "wws_reloc_manifest.json")))}

fails = 0
def check(ok, what):
    global fails
    if not ok:
        fails += 1
        print("  FAIL", what)

pm = re.findall(r"spu_wws_register_pm\((\d+), 0x([0-9A-F]+)u, 0x([0-9A-F]+)u\)", reg)
check(pm == [("1297305682", "1320", "3214")], f"PM registration {pm}")

blocks = re.findall(r"sig\[16\] = \{([^}]*)\};\s*static const uint8_t ent\[16\] = \{([^}]*)\};\s*"
                    r"spu_begin_image\((\d+)\); (wr_(ms_[0-9a-f]+_e[0-9A-F]+)_)spu_recomp_register\(\);\s*"
                    r"spu_reloc_register_module\(sig, ent, 0x([0-9A-F]+)u, 0x([0-9A-F]+)u, 0x([0-9A-F]+)u, "
                    r"0x([0-9A-F]+)ull, (\d+)\);", reg)
print(f"registrations: {len(blocks)}")
check(len(blocks) == 31, "31 registrations")
ids = set()
by_sha12 = {j["sha256"][:12]: j for j in jobs}
for sig, ent, img0, prefix, stem, lb, eo, span, h, img in blocks:
    sig = bytes(int(x, 16) for x in sig.split(","))
    ent = bytes(int(x, 16) for x in ent.split(","))
    lb, eo, span, h, img = int(lb, 16), int(eo, 16), int(span, 16), int(h, 16), int(img)
    j = by_sha12.get(stem[3:15])
    fails0 = fails
    check(j is not None, f"{stem}: not a retail image")
    if j is None:
        continue
    off = j["file_off"]
    img_bytes = eboot[off:off + span]
    f = open(os.path.join(mods, stem + ".bin"), "rb").read()
    check(span == j["size"] == len(f), f"{stem}: span {span:#x} vs size {j['size']:#x}/{len(f):#x}")
    check(img_bytes == f, f"{stem}: EBOOT bytes != module file")
    check(hashlib.sha256(f).hexdigest() == j["sha256"], f"{stem}: sha256")
    check(img_bytes[0x20:0x24] == b"\xc0\xde\xc0\xde", f"{stem}: magic")
    check(sig == img_bytes[:16], f"{stem}: sig")
    check(eo == struct.unpack(">I", img_bytes[0x10:0x14])[0] == j["entry_off"], f"{stem}: entry_off")
    check(ent == img_bytes[eo:eo + 16], f"{stem}: entry16")
    check(lb == struct.unpack(">I", img_bytes[0x28:0x2C])[0] == 0x4000, f"{stem}: link base")
    check(h == body_hash(img_bytes), f"{stem}: body hash")
    check(img == int(img0) and img not in ids, f"{stem}: image id {img}")
    ids.add(img)
    m = man.get(stem + ".bin", {})
    check(m.get("registered") and m.get("entry_off") == eo and m.get("size") == span
          and int(m.get("body_hash", "0"), 16) == h and m.get("image_id") == img, f"{stem}: manifest")
    check(os.path.isfile(os.path.join(out, stem, "spu_recomp.c")), f"{stem}: lifted TU")
    print(f"  {'OK  ' if fails == fails0 else 'FAIL'} {j['name']:<42} off=0x{off:07X} span=0x{span:05X} entry=+0x{eo:X} hash={h:016X}")
print("RESULT", "PASS" if fails == 0 else f"FAIL ({fails})")
sys.exit(1 if fails else 0)
