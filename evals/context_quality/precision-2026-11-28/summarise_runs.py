"""Summarise eval_context_quality report JSONs (bge-m3 arm): micro precision/recall, per category, safety."""
import json, sys
from pathlib import Path

def pick(q, *names, default=0):
    for n in names:
        if n in q:
            v = q[n]
            return len(v) if isinstance(v, (list, dict, set)) else v
    return default

def summ(path):
    r = json.loads(Path(path).read_text(encoding="utf-8"))
    a = r["arms"]["bge-m3"]
    pq = a["per_question"]
    rows = pq.items() if isinstance(pq, dict) else [(q.get("id"), q) for q in pq]
    tot = {"items": 0, "ok": 0, "req": 0, "found": 0, "items_ns": 0, "ok_ns": 0}
    cat = {}
    for qid, q in rows:
        items = pick(q, "items"); ok = pick(q, "ok_items"); req = pick(q, "required"); found = pick(q, "found_required")
        st = pick(q, "standing_items"); okst = pick(q, "ok_standing")
        c = (qid or "?")[0]
        d = cat.setdefault(c, {"items": 0, "ok": 0, "req": 0, "found": 0, "n": 0})
        for k, v in (("items", items), ("ok", ok), ("req", req), ("found", found)):
            d[k] += v; tot[k] += v
        d["n"] += 1
        tot["items_ns"] += items - st; tot["ok_ns"] += ok - okst
    zt = a.get("zero_tolerance", {}); lat = a.get("latency_ms", {})
    P = tot["ok"] / tot["items"] if tot["items"] else 0; R = tot["found"] / tot["req"] if tot["req"] else 0
    Pns = tot["ok_ns"] / tot["items_ns"] if tot["items_ns"] else 0
    cats = " ".join(f"{c}:{d['ok']/d['items'] if d['items'] else 0:.2f}/{d['found']/d['req'] if d['req'] else 1:.2f}" for c, d in sorted(cat.items()))
    n = sum(d["n"] for d in cat.values())
    return (f"{Path(path).stem:<16} n={n:<2} P={P:.3f} R={R:.3f} P_nostand={Pns:.3f} items/q={tot['items']/max(n,1):.1f} "
            f"forb={zt.get('forbidden_as_current')} leaks={zt.get('cross_tenant_leaks')} cloud={zt.get('cloud_model_calls')} "
            f"p50={lat.get('p50')} p95={lat.get('p95')} | {cats}")

for p in sys.argv[1:]:
    try: print(summ(p))
    except Exception as e: print(Path(p).stem, "ERR", type(e).__name__, e)
