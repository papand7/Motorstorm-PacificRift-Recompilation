"""Summarize a bounded native startup probe without printing poll spam.

Accepts the probe name or a stderr log path. All output remains local.
"""

import argparse
from collections import Counter, deque
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
LOGS = ROOT / "generated/logs"
INTERESTING = re.compile(
    r"\[FT\]|\[FDTRANS\]|\[FDS16\]|\[CALL\]|\[RSX\]|\[fs\]|"
    r"\[evt\]|\[SCREENTEX\]|\[spurs-lfq\]|assert|error|fail|unsupported|"
    r"shader|pipeline|draw|present|flip|callback|mainmenu|title",
    re.IGNORECASE,
)
ERROR = re.compile(r"assert|error|fail|unsupported|NOSYS|0x80070057", re.IGNORECASE)
TRANSITION = re.compile(r"\[FT\]|\[FDTRANS\]|\[FDS16\]|\[CALL\]")
DRAW = re.compile(r"draw|present|flip|pipeline", re.IGNORECASE)
RESOURCE = re.compile(r"\[fs\]|PSARC|resource|archive", re.IGNORECASE)
WAIT = re.compile(r"\[WAIT\]|WAIT_SIGNAL|event.*wait", re.IGNORECASE)
TAG = re.compile(r"^\[([^]]+)\]")


PT_FIELD = re.compile(r"(\w+)=(\S+)")
MEM_WRITES = {"ppu-write", "atomic", "hle-write", "spu-put"}


def summarize_runtime_trace(events, limit=8):
    """Sections for ps3recomp runtime tracer lines ([PT], see ps3recomp
    docs/TRACING.md); `events` are (line number, field dict, text)."""
    out = []
    def section(title, rows):
        out.append(title)
        out.extend(f"  {row}" for row in rows) if rows else out.append("  none observed")
    config = [text for _, f, text in events if f.get("ev") in ("config", "config-error", "budget")]
    section("runtime trace configuration:", config[:limit])

    entries, exits, unwound, last_enter = Counter(), Counter(), Counter(), {}
    fnstat = {}
    for n, f, text in events:
        ev = f.get("ev")
        if ev == "enter":
            entries[f.get("pc")] += 1
            last_enter[f.get("pc")] = (n, text)
        elif ev == "exit":
            (unwound if f.get("how") == "unwound" else exits)[f.get("fn")] += 1
        elif ev == "fnstat":
            fnstat[f.get("fn")] = f   # the last report wins
    rows = []
    for fn in sorted(set(entries) | set(fnstat)):
        st = fnstat.get(fn)
        if st:
            rows.append(f"{fn}: entries={st.get('entries')} returns={st.get('returns')} open={st.get('open')} "
                        f"total_us={st.get('total_us')} max_us={st.get('max_us')}")
        else:
            rows.append(f"{fn}: entries>={entries[fn]} returns>={exits[fn]} unwound>={unwound[fn]} (sampled)")
    section("function entry/exit pairs:", rows[:limit * 2])
    open_fns = [fn for fn in sorted(set(entries) | set(fnstat))
                if (fnstat.get(fn) and fnstat[fn].get("open", "0") not in ("0", "-0"))
                or (fn not in fnstat and entries[fn] > exits[fn] + unwound[fn])]
    section("unmatched calls (entered, not returned):",
            [f"{fn}: last entry line {last_enter[fn][0]}: {last_enter[fn][1][:200]}"
             if fn in last_enter else f"{fn}: open per fnstat" for fn in open_fns][:limit])
    section("stalls:", [f"{n}: {text[:300]}" for n, f, text in events if f.get("ev") == "stall"][-limit:])

    waits = {}
    for _, f, _ in events:
        if f.get("ev") in ("sc", "hle"):
            key = (f["ev"], f.get("num") or f.get("nid"), f.get("tid"))
            dur = int(f.get("dur_us", "0"))
            count, total, longest = waits.get(key, (0, 0, 0))
            waits[key] = (count + 1, total + dur, max(longest, dur))
    section("repeated waits (syscalls and imports, by total time):",
            [f"{kind} {ident} tid={tid}: calls={c} total_ms={t / 1000:.1f} max_ms={m / 1000:.1f}"
             for (kind, ident, tid), (c, t, m) in sorted(waits.items(), key=lambda kv: -kv[1][1])[:limit]])

    hot = [(f, text) for _, f, text in events if f.get("ev") == "hot"]
    latest = max((int(f.get("t", "0")) for f, _ in hot), default=0)
    rows, shown = [], Counter()
    for f, text in hot:   # reports are cumulative: the last one is enough
        key = (f.get("tid"), f.get("what"))
        if int(f.get("t", "0")) == latest and shown[key] < 3:
            shown[key] += 1
            rows.append(f"tid={f.get('tid')} " + text[text.index("what="):][:150])
    section("hotspots (latest profile report, top 3 per thread and kind):", rows[:limit * 4])

    by_addr = {}
    for _, f, _ in events:
        if f.get("ev") == "mem":
            by_addr.setdefault(f.get("addr"), []).append(f)
    rows = []
    for addr, hits in sorted(by_addr.items()):
        producers = Counter(f"{h.get('kind')}@{h.get('fn') if h.get('fn') != '00000000' else h.get('hostfn')}"
                            for h in hits if h.get("kind") in MEM_WRITES)
        consumers = Counter(f"{h.get('kind')}@{h.get('fn') if h.get('fn') != '00000000' else h.get('hostfn')}"
                            for h in hits if h.get("kind") not in MEM_WRITES)
        values, last = [], None
        for h in hits:
            if h.get("kind") in MEM_WRITES and h.get("val") != last:
                values.append(f"{h.get('val')}<-{h.get('fn')}/t{h.get('tid')}")
                last = h.get("val")
        rows.append(f"{addr}: producers={dict(producers.most_common(4))} consumers={dict(consumers.most_common(4))}")
        if values:
            rows.append(f"{addr}: value transitions " + " ".join(values[:10])
                        + (" ..." if len(values) > 10 else ""))
    section("memory producers, consumers and state transitions:", rows[:limit * 2])
    return out


def summarize(lines, focus=None):
    counts = Counter()
    runtime_trace = []
    transitions = deque(maxlen=12)
    errors = deque(maxlen=12)
    graphics = deque(maxlen=8)
    resources = deque(maxlen=8)
    waits = Counter()
    trace = deque(maxlen=8)
    trace_counts = Counter()
    before_focus = deque(maxlen=8)
    focus_timeline = []
    focus_seen = False
    total = 0
    for line in lines:
        total += 1
        line = line.rstrip("\r\n")
        tag = TAG.match(line)
        if tag:
            counts[tag[1]] += 1
        if line.startswith("[PT] "):
            runtime_trace.append((total, dict(PT_FIELD.findall(line)), line))
            continue
        if WAIT.search(line):
            waits[line[:140]] += 1
        if not INTERESTING.search(line):
            continue
        if ERROR.search(line):
            errors.append((total, line[:240]))
        if TRANSITION.search(line):
            transitions.append((total, line[:240]))
            if focus and not focus_seen:
                before_focus.append((total, line[:240]))
            elif focus and focus_seen and len(focus_timeline) < 40:
                focus_timeline.append((total, line[:240]))
        if "[FT]" in line:
            trace.append((total, line[:240]))
            function = re.search(r"fn=([0-9A-Fa-f]{8})", line)
            if function:
                trace_counts[function[1].upper()] += 1
            if focus and not focus_seen and f"fn={focus.upper()} entry" in line:
                focus_timeline = list(before_focus)
                focus_seen = True
        if DRAW.search(line):
            graphics.append((total, line[:240]))
        if RESOURCE.search(line):
            resources.append((total, line[:240]))
    def section(title, entries):
        return [title] + ([f"  {n}: {value}" for n, value in entries] if entries else ["  none observed"])
    output = [f"lines={total}",
              "tags=" + " ".join(f"{tag}:{count}" for tag, count in counts.most_common(18))]
    if trace_counts:
        output.append("trace functions=" + " ".join(f"{fn}:{count}" for fn, count in trace_counts.items()))
    if focus:
        output += section(f"frontend handoff near {focus.upper()}:", focus_timeline)
    output += section("last frontend transitions:", transitions)
    output += section("last targeted trace events:", trace)
    output += section("last errors:", errors)
    output += section("last graphics events:", graphics)
    output += section("last resource events:", resources)
    output += section("most repeated waits:", [(count, line) for line, count in waits.most_common(5)])
    if runtime_trace:
        output += summarize_runtime_trace(runtime_trace)
    return "\n".join(output) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("probe", help="Probe name or stderr log path")
    parser.add_argument("--focus", help="Guest function address for a compact transition timeline")
    parser.add_argument("--trace", help="Runtime tracer output written with out= "
                                        "(default: <probe>-trace.log when present)")
    args = parser.parse_args()
    path = Path(args.probe)
    if not path.is_file():
        path = LOGS / f"{args.probe}-stderr.log"
    if not path.is_file():
        parser.error(f"Probe stderr log not found: {path}")
    trace = Path(args.trace) if args.trace else LOGS / f"{args.probe}-trace.log"
    with path.open(encoding="utf-8", errors="replace") as stream:
        lines = list(stream)
    if trace.is_file():
        with trace.open(encoding="utf-8", errors="replace") as stream:
            lines += list(stream)
    print(summarize(lines, args.focus.removeprefix("0x") if args.focus else None), end="")


if __name__ == "__main__":
    main()
