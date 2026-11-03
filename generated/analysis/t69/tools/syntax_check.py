MS_ROOT = str(__import__('pathlib').Path(__file__).resolve().parents[4])  # repository root
"""T69: clang-cl -fsyntax-only on the original and patched copies of the two
patched files, with the T62 build's flags. Single-file check, no objects, no
link, nothing written outside generated/analysis/t69."""
import os, re, subprocess, sys

ROOT = MS_ROOT
CC = ROOT + "/build/llvm/clang+llvm-23.1.3-x86_64-pc-windows-msvc/bin/clang-cl.exe"
NINJA = ROOT + "/build/motorstorm-t62-font-c529ab0/build.ninja"
WORK = ROOT + "/generated/analysis/t69/patch/work"
FILES = ["libs/spurs/cellSpurs.c", "runtime/spu/spu_channels.c"]

text = open(NINJA, encoding="utf-8", errors="replace").read()
rc_all = 0
for f in FILES:
    obj = f.replace("/", "\\") + ".obj:"
    i = text.find(obj)
    block = text[i:i + 6000]
    flags = re.search(r"\n  FLAGS = (.*)", block).group(1)
    incs = re.search(r"\n  INCLUDES = (.*)", block).group(1)
    defs = re.search(r"\n  DEFINES = (.*)", block)
    args = [CC, "-fsyntax-only"] + flags.split() + incs.split()
    if defs:
        args += defs.group(1).split()
    # the copies only hold the patched file: resolve its relative includes
    # through the original source directory
    args.append("-I" + ROOT + "/ps3recomp-t62/" + os.path.dirname(f))
    for side in ("a", "b"):
        r = subprocess.run(args + [WORK + "/" + side + "/" + f], capture_output=True, text=True)
        errs = r.stdout.count("error:") + r.stderr.count("error:")
        warns = r.stdout.count("warning:") + r.stderr.count("warning:")
        print(f"{side}/{f}: rc={r.returncode} errors={errs} warnings={warns}")
        if side == "b":
            rc_all |= r.returncode
            out = (r.stdout + r.stderr).splitlines()
            print("\n".join(l for l in out if "error" in l)[:4000])
        if side == "a":
            base_warn = warns
    print(f"  new warnings in b: {warns - base_warn}")
sys.exit(rc_all)
