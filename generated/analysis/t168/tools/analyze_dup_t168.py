#!/usr/bin/env python3
"""T168: group draws in existing RSXI captures and classify repetition. Reads files only.

A libgcm DRAW_INDEX_ARRAY packet holds many (first, count) words, so one FIFO packet gives many
draw records. Records are first collapsed into packets: an unbroken run with one cmd_offset.

  replay   a cmd_offset that appears in two separate runs, or a CALL return site in two runs
  tail     a run whose counts are not 256,...,256,n<=256: not the shape of a libgcm split
  A        same mesh proxy (per-batch counts and expanded vertices) in another target
  B        same mesh proxy and target, different vertex constants
  suspect  same target, program, state, textures, constants and mesh proxy at a different address

The capture records neither the vertex array addresses nor `first`, nor constants above c[63], so
a suspect is not a confirmed duplicate. Offsets and hashes only: no asset data is written.
"""
import collections
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from rsxi_load import events, manifest

ROOT = Path(__file__).resolve().parents[4]
CAPS = sys.argv[1:] or [
    "generated/analysis/t145/ab/runtime-A1-20261028-181934/rsxi",
    "generated/analysis/t145/ab/runtime-B1-20261028-182350/rsxi",
    "generated/analysis/t145/ab/runtime-D1-20261028-183730/rsxi",
    "generated/analysis/t113/runtime-F-20261027-180148/rsxi",
    "generated/analysis/t113/runtime-G-20261027-181504/rsxi",
    "generated/analysis/t113/runtime-H-20261027-182143/rsxi",
    "generated/analysis/t113/runtime-I-20261027-182926/rsxi",
    "generated/runs/20261027-010225-t84d-pb-trace/rsxi",
]
STATE = ("rt", "mrt", "zeta", "fp", "vs_hash", "depth", "stencil", "blend", "blend_key", "cmask", "cull", "alpha",
         "viewport", "scissor", "ds_key", "raster", "mrt_regs", "prim", "indexed")


def h(obj):
    return hashlib.blake2b(json.dumps(obj, sort_keys=True).encode(), digest_size=8).hexdigest()


def rec(e):
    g, n = e["guest"], e.get("native", {})
    tex = [(t.get("unit"), t.get("req", {}).get("addr"), t.get("req", {}).get("fmt"), t.get("native", {}).get("csum"))
           for t in e.get("tex", [])]
    return {"op": e["op"], "off": g.get("cmd_offset"), "ret": g.get("call_ret"), "rt": g.get("rt"), "state": h({k: g.get(k) for k in STATE}),
            "tex": h(tex), "cons": h([g.get("vp_consts"), g.get("fp_consts")]), "count": g.get("count"),
            "verts": n.get("vertices", 0), "fp": g.get("fp"), "blend": g.get("blend"), "dw": (g.get("depth") or {}).get("write"),
            "prim": g.get("prim")}


def packets(dr):
    out = []
    for x in dr:
        if out and out[-1][0]["off"] == x["off"]:
            out[-1].append(x)
        else:
            out.append([x])
    return out


def main():
    res = []
    for cap in CAPS:
        capd = ROOT / cap
        prev_offs = None
        for fr in manifest(capd)["frames"]:
            ev = events(capd / fr["dir"] / "events.jsonl")
            dr = [rec(e) for e in ev if e["e"] == "draw" and "guest" in e]
            pk = packets(dr)
            offs = collections.Counter(p[0]["off"] for p in pk)
            rets = []
            for p in pk:
                if not rets or rets[-1] != p[0]["ret"]:
                    rets.append(p[0]["ret"])
            ret_runs = collections.Counter(r for r in rets if r != "0x00000000")
            bad_tail = sum(1 for p in pk if len(p) > 1 and (any(x["count"] != 256 for x in p[:-1]) or p[-1]["count"] > 256))
            sig = lambda p: h([[x["count"], x["verts"]] for x in p])
            groups = collections.defaultdict(list)
            for p in pk:
                groups[sig(p)].append(p)
            by_site = collections.defaultdict(list)
            for p in pk:
                by_site[p[0]["ret"]].append(h([p[0]["rt"], p[0]["state"], p[0]["tex"], p[0]["cons"], sig(p)]))
            site_seq = collections.Counter(h(v) for k, v in by_site.items() if k != "0x00000000" and len(v) > 1)
            dup_sites = sum(v - 1 for v in site_seq.values())
            susp_rt = collections.Counter()
            a = b = suspect = suspect_draws = suspect_blend = suspect_opaque = suspect_same_ret = 0
            examples = []
            for g in groups.values():
                if len(g) < 2:
                    continue
                if len({p[0]["rt"] for p in g}) > 1:
                    a += 1
                seen = collections.defaultdict(list)
                for p in g:
                    seen[(p[0]["rt"], p[0]["state"], p[0]["tex"])].append(p)
                for same in seen.values():
                    if len(same) < 2:
                        continue
                    cons = collections.defaultdict(list)
                    for p in same:
                        cons[p[0]["cons"]].append(p)
                    if len(cons) > 1:
                        b += 1
                    for c in cons.values():
                        if len(c) > 1:
                            n = len(c) - 1
                            suspect += n
                            susp_rt[c[0][0]["rt"]] += n
                            suspect_draws += n * len(c[0])
                            if c[0][0]["blend"]:
                                suspect_blend += n
                            elif c[0][0]["dw"]:
                                suspect_opaque += n
                            if len(examples) < 12:
                                examples.append({"n": len(c), "rt": c[0][0]["rt"], "fp": c[0][0]["fp"], "batches": len(c[0]),
                                                 "verts": sum(x["verts"] for x in c[0]), "blend": c[0][0]["blend"], "dw": c[0][0]["dw"],
                                                 "offs": [p[0]["off"] for p in c][:4], "ops": [p[0]["op"] for p in c][:4],
                                                 "rets": [p[0]["ret"] for p in c][:4]})
            row = {"cap": cap, "pass": fr["frame"], "unparsed": sum(e["e"] == "unparsed" for e in ev),
                   "draw_records": len(dr), "packets": len(pk), "records_from_splits": len(dr) - len(pk),
                   "replayed_packets": sum(v - 1 for v in offs.values()), "repeated_call_runs": sum(v - 1 for v in ret_runs.values()),
                   "call_sites": len(ret_runs), "bad_split_shape": bad_tail, "A_mesh_in_targets": a, "B_instanced_groups": b,
                   "suspect_packets": suspect, "suspect_records": suspect_draws, "suspect_blend": suspect_blend,
                   "suspect_opaque_depthwrite": suspect_opaque, "targets": dict(collections.Counter(x["rt"] for x in dr)), "suspect_by_target": dict(susp_rt), "identical_call_sites": dup_sites,
                   "shared_offs_prev_capture": len(prev_offs & set(offs)) if prev_offs else None, "examples": examples}
            prev_offs = set(offs)
            res.append(row)
    out = ROOT / "generated/analysis/t168/logs"
    out.mkdir(exist_ok=True)
    (out / "dup_offline.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    for r in res:
        print(r["cap"].split("/")[-2][:14], r["pass"], "rec", r["draw_records"], "pk", r["packets"], "REPLAY", r["replayed_packets"], "CALLREP", r["repeated_call_runs"],
              "sites", r["call_sites"], "shape", r["bad_split_shape"], "A", r["A_mesh_in_targets"], "B", r["B_instanced_groups"], "susp", r["suspect_packets"],
              "rec", r["suspect_records"], "bl", r["suspect_blend"], "op", r["suspect_opaque_depthwrite"], "prevshare", r["shared_offs_prev_capture"], "dupsites", r["identical_call_sites"], r["suspect_by_target"])


main()
