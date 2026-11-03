MS_ROOT = str(__import__('pathlib').Path(__file__).resolve().parents[4])  # repository root
"""T70: compile-only check (no link, no game build) of every TU the AOT build
adds or changes, with the exact flags the T62/T64C build used
(build/motorstorm-t62-font-c529ab0/build.ninja), re-pointed from ps3recomp-t62
to ps3recomp-t70.

  - SPU group: the 31 lifted modules + wws_reloc_register.c, with the flags of
    a lifted SPU TU in that build (-DSPU_USE_DISPATCH_MT, -fwrapv, -O2 -msse4.1),
    which is what port/CMakeLists.txt applies to everything in SPU_SOURCES;
  - runtime group: the runtime files the series and the T69 commit touch, with
    their own entries' flags.
Objects go to a temp dir and are deleted. Exit 0 only if every TU compiles."""
import os, re, subprocess, sys, tempfile, glob

ROOT = MS_ROOT
CC = ROOT + "/build/llvm/clang+llvm-23.1.3-x86_64-pc-windows-msvc/bin/clang-cl.exe"
NINJA = open(ROOT + "/build/motorstorm-t62-font-c529ab0/build.ninja", encoding="utf-8", errors="replace").read()
LIFT = ROOT + "/generated/spu_raw/wws_reloc"
OLD, NEW = "ps3recomp-t62", "ps3recomp-t70"


def entry_flags(obj_suffix):
    i = NINJA.find(obj_suffix)
    if i < 0:
        sys.exit("no build.ninja entry for " + obj_suffix)
    blk = NINJA[i:i + 8000]
    get = lambda k: (re.search(r"\n  " + k + r" = (.*)", blk) or [None, ""])[1]
    return [a.replace(OLD, NEW) for a in (get("DEFINES") + " " + get("FLAGS") + " " + get("INCLUDES")).split()]


spu = entry_flags("spu_recomp.c.obj:")          # first lifted SPU TU of the target
assert "-DSPU_USE_DISPATCH_MT" in spu and "-fwrapv" in spu, spu
groups = [("spu", spu, sorted(glob.glob(LIFT + "/*/spu_recomp.c")) + [LIFT + "/wws_reloc_register.c"])]
for f in ["runtime/spu/spu_channels.c", "runtime/spu/spu_drain.c", "runtime/spu/spu_interp.c",
          "libs/spurs/cellSpurs.c"]:
    groups.append(("runtime", entry_flags(f.replace("/", "\\") + ".obj:"), [ROOT + "/" + NEW + "/" + f]))

bad = 0
with tempfile.TemporaryDirectory() as tmp:
    for name, flags, srcs in groups:
        for k, src in enumerate(srcs):
            obj = os.path.join(tmp, f"{name}_{k}.obj")
            r = subprocess.run([CC] + flags + ["-c", src, "/Fo" + obj], capture_output=True, text=True)
            ok = r.returncode == 0 and os.path.isfile(obj)
            out = r.stdout + r.stderr
            errs = out.count(": error")
            rel = src.replace(ROOT + "/", "")
            print(f"{'OK  ' if ok else 'FAIL'} [{name}] {rel} errors={errs} warnings={out.count(': warning')}")
            if not ok:
                bad += 1
                print("\n".join(l for l in out.splitlines() if ": error" in l)[:3000])
print("RESULT", "PASS" if not bad else f"FAIL ({bad})")
sys.exit(1 if bad else 0)
