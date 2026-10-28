"""Temporary, bounded probes in private AOT PPU source; always restore it.

Example: py -3 tools/trace_frontend.py 0x0059F2F8 --seconds 30 --watch-reg r3+4
The tool builds the probe, runs the original game, restores the source, then
rebuilds the ordinary executable. Logs and backup stay under generated/.
"""

import argparse
import hashlib
import os
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "generated/ppu"
LOGS = ROOT / "generated/logs"
ENTRY = b"void func_%08X(ppu_context* ctx) {"


def locate(address):
    marker = ENTRY % address
    for path in sorted(SOURCE.glob("ppu_recomp_*.cpp")):
        data = path.read_bytes()
        if marker in data:
            return path, data
    raise ValueError(f"No generated function at guest 0x{address:08X}")


def watch_expression(value):
    if not value:
        return None
    m = re.fullmatch(r"r([0-9]|[12][0-9]|3[01])\+((?:0x)?[0-9a-fA-F]+)", value)
    if not m:
        raise ValueError("--watch-reg must be rN+offset (N=0..31)")
    register = int(m[1])
    offset = int(m[2], 16 if m[2].lower().startswith("0x") else 10)
    if offset > 0x100000:
        raise ValueError("watch offset too large")
    return f"vm_read32(ctx->gpr[{register}] + 0x{offset:X})"


def instrument(data, address, limit, watch=None, exit_label=None, after_call=None,
               include_returns=False, labels=None, sample_power2=False,
               entry_only=False, lr_filter=None):
    marker = ENTRY % address
    if data.count(marker) != 1:
        raise ValueError("Function marker is absent or ambiguous")
    start = data.index(marker)
    next_start = data.find(b"\nvoid func_", start + len(marker))
    if next_start < 0:
        raise ValueError("Function end not found")
    body = data[start:next_start]
    newline = b"\r\n" if b"\r\n" in body[:100] else b"\n"
    if b"[FT]" in body:
        raise ValueError("Existing frontend trace marker found; source must be clean")
    watch_code = watch_expression(watch)
    # The marker sits at function entry. Each return is wrapped as a block so
    # inline `if (...) return;` keeps the same control flow.
    def event(kind):
        fmt = f'[FT] fn={address:08X} {kind} seq=%u'
        args = 'seq'
        if sample_power2:
            fmt += ' hit=%u'
            args += ', hit'
        fmt += ' tid=%u lr=%08X r3=%08X r4=%08X r5=%08X r6=%08X r7=%08X r8=%08X r10=%08X r26=%08X r27=%08X r28=%08X r30=%08X'
        args += (', (unsigned)ctx->thread_id, (unsigned)ctx->lr, '
                '(unsigned)ctx->gpr[3], (unsigned)ctx->gpr[4], '
                '(unsigned)ctx->gpr[5], (unsigned)ctx->gpr[6], '
                '(unsigned)ctx->gpr[7], (unsigned)ctx->gpr[8], '
                '(unsigned)ctx->gpr[10], '
                '(unsigned)ctx->gpr[26], (unsigned)ctx->gpr[27], '
                '(unsigned)ctx->gpr[28], (unsigned)ctx->gpr[30]')
        if watch_code and kind == "entry":
            fmt += ' state=%08X'
            args += f', (unsigned){watch_code}'
        sample = ('static std::atomic<unsigned> frontend_trace_hits{0}; '
                  'unsigned hit = frontend_trace_hits.fetch_add(1, std::memory_order_relaxed); '
                  f'if (hit < {limit}u || (hit && !(hit & (hit - 1u)))) '
                  if sample_power2 else f'if (seq < {limit}u) ')
        condition = 'getenv("FRONTEND_TRACE")'
        if lr_filter is not None:
            condition += f' && (uint32_t)ctx->lr == 0x{lr_filter:08X}u'
        return (f'if ({condition}) {{ unsigned seq = '
                f'frontend_trace_count_{address:08X}.fetch_add(1, std::memory_order_relaxed); '
                f'{sample}fprintf(stderr, "{fmt}\\n", {args}); }}').encode()
    entry_code = newline + b"    " + event("entry") + newline
    body = body.replace(marker, marker + entry_code, 1)
    if entry_only and (exit_label or after_call or include_returns or labels):
        raise ValueError("Entry-only trace cannot include exit or checkpoint points")
    if exit_label and after_call:
        raise ValueError("Select only one targeted trace point")
    if entry_only:
        exit_count = 0
    elif after_call:
        calls = [part.strip() for part in after_call.split(",")]
        if len(set(calls)) != len(calls):
            raise ValueError("Duplicate return callsite")
        for return_address in calls:
            call = re.compile(rb"ctx->lr = 0x" + f"{int(return_address, 16):08X}".encode()
                              + rb"; func_[0-9A-F]{8}\(ctx\); DRAIN_TRAMPOLINE\(ctx\);")
            matches = list(call.finditer(body))
            if len(matches) != 1:
                raise ValueError(f"Return callsite {return_address} absent or ambiguous")
            end = matches[0].end()
            kind = "after-call" if len(calls) == 1 else f"after-{int(return_address, 16):08X}"
            body = body[:end] + newline + b"    " + event(kind) + body[end:]
        exit_count = len(calls)
    elif exit_label:
        label = f"loc_{int(exit_label, 16):08X}:".encode()
        if body.count(label) != 1:
            raise ValueError("Exit label absent or ambiguous in selected function")
        body = body.replace(label, label + newline + b"    " + event("label") + newline, 1)
        exit_count = 1
    else:
        exit_count = body.count(b"return;")
        if not exit_count:
            raise ValueError("No return statements found")
        body = body.replace(b"return;", b"{ " + event("exit") + b" return; }")
    if include_returns and (after_call or exit_label):
        returns = body.count(b"return;")
        body = body.replace(b"return;", b"{ " + event("exit") + b" return; }")
        exit_count += returns
    if labels:
        for label_address in labels:
            label = f"loc_{int(label_address, 16):08X}:".encode()
            if body.count(label) != 1:
                raise ValueError(f"Checkpoint label {label_address} absent or ambiguous")
            body = body.replace(label, label + newline + b"    "
                                + event(f"at-{int(label_address, 16):08X}") + newline, 1)
            exit_count += 1
    if b"#include <atomic>" not in data:
        anchor = b"#include <stdio.h>"
        if data.count(anchor) != 1:
            raise ValueError("stdio include absent or ambiguous")
        data = data.replace(anchor, anchor + newline + b"#include <atomic>", 1)
        # Account for the new include before applying the body splice.
        start += len(newline) + len(b"#include <atomic>")
        next_start += len(newline) + len(b"#include <atomic>")
    counter = (f"static std::atomic<unsigned> frontend_trace_count_{address:08X}{{0}};".encode()
               + newline)
    return data[:start] + counter + body + data[next_start:], exit_count


def run_command(command, log, env=None):
    with log.open("w", encoding="utf-8", errors="replace") as output:
        result = subprocess.run(command, cwd=ROOT, env=env, stdout=output,
                                stderr=subprocess.STDOUT, check=False)
    if result.returncode:
        raise RuntimeError(f"exit {result.returncode}: {command[0]} (see {log})")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("address", type=lambda s: int(s, 0))
    parser.add_argument("--seconds", type=int, default=30)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--watch-reg", help="Optional 32-bit guest state, e.g. r3+4")
    parser.add_argument("--exit-label", help="Trace this guest label instead of every return")
    parser.add_argument("--after-call", help="Trace after a call with this guest return address")
    parser.add_argument("--include-returns", action="store_true",
                        help="Also trace function returns with --after-call or --exit-label")
    parser.add_argument("--labels", help="Comma-separated guest labels inside the primary function")
    parser.add_argument("--sample-power2", action="store_true",
                        help="After the per-site limit, log only power-of-two visit counts")
    parser.add_argument("--entry-only", action="store_true",
                        help="Trace only the primary function entry (useful for large trampolines)")
    parser.add_argument("--lr-filter", type=lambda s: int(s, 0),
                        help="Record the primary function only when its guest LR matches")
    parser.add_argument("--also", action="append", default=[],
                        help="Additional function: ADDRESS[%%rN+offset][@CALL_RETURN]")
    parser.add_argument("--name", default=None)
    args = parser.parse_args()
    if not 1 <= args.seconds <= 600 or not 1 <= args.limit <= 10000:
        parser.error("seconds must be 1..600 and limit 1..10000")
    if not 0 <= args.address <= 0xFFFFFFFF:
        parser.error("guest address must be 32-bit")
    if args.lr_filter is not None and not 0 <= args.lr_filter <= 0xFFFFFFFF:
        parser.error("guest LR filter must be 32-bit")
    labels = args.labels.split(",") if args.labels else None
    specs = [(args.address, args.watch_reg, args.exit_label,
              args.after_call, args.include_returns, labels, args.sample_power2,
              args.entry_only, args.lr_filter)]
    for item in args.also:
        head, separator, after = item.partition("@")
        address_text, watch_separator, watch = head.partition("%")
        specs.append((int(address_text, 0), watch if watch_separator else None,
                      None, after if separator else None, False, None, False,
                      False, None))
    if len({item[0] for item in specs}) != len(specs):
        parser.error("Each guest function may be traced only once")
    originals = {}
    modified = {}
    points = 0
    for address, watch, label, after, returns, checkpoints, power2, entry_only, lr_filter in specs:
        path, data = locate(address)
        if path not in originals:
            originals[path] = data
            modified[path] = data
        modified[path], count = instrument(modified[path], address, args.limit,
                                           watch, label, after, returns, checkpoints,
                                           power2, entry_only, lr_filter)
        points += count
    LOGS.mkdir(parents=True, exist_ok=True)
    name = args.name or f"frontend-{args.address:08X}-{time.strftime('%Y%m%d-%H%M%S')}"
    backups = {path: LOGS / f"{name}-{path.name}.original" for path in originals}
    for backup in backups.values():
        if backup.exists():
            raise RuntimeError(f"Backup already exists: {backup}")
    for path, backup in backups.items():
        backup.write_bytes(originals[path])
    print(f"trace functions={len(specs)} chunks={len(originals)} points={points}", flush=True)
    installed = []
    try:
        for path, data in modified.items():
            path.write_bytes(data)
            installed.append(path)
        run_command(["cmd", "/c", "tools\\build_incremental.cmd"], LOGS / f"{name}-build.log")
        env = os.environ.copy()
        env["FRONTEND_TRACE"] = "1"
        run_command(["powershell", "-NoProfile", "-File", "tools/probe_first_frame.ps1",
                     "-Seconds", str(args.seconds), "-Name", name,
                     "-FirstFrame", "-AudioPolicy", "silent"],
                    LOGS / f"{name}-probe.log", env=env)
        run_command([sys.executable, "tools/summarize_probe.py", name,
                     "--focus", f"{args.address:08X}"],
                    LOGS / f"{name}-summary.txt")
        print((LOGS / f"{name}-summary.txt").read_text(encoding="utf-8"), flush=True)
    finally:
        if installed:
            for path in installed:
                if path.read_bytes() != modified[path]:
                    raise RuntimeError(f"Generated source changed during trace; backup retained at {backups[path]}")
            for path in installed:
                path.write_bytes(originals[path])
                assert hashlib.sha256(path.read_bytes()).digest() == hashlib.sha256(originals[path]).digest()
            print("private generated source restored", flush=True)
            run_command(["cmd", "/c", "tools\\build_incremental.cmd"],
                        LOGS / f"{name}-clean-build.log")
            print("ordinary native executable rebuilt", flush=True)


if __name__ == "__main__":
    main()
