"""Offline reranker evaluation over an eval run's candidate pool (synthetic dataset only).

Usage (any venv with sentence-transformers + CUDA, HF_HUB_OFFLINE=1): python -I rr_score.py <eval_dir> <pool.json> <out.json>
Scores each (question, candidate item) with a local cross-encoder (bge-reranker-v2-m3,
HF cache, offline), then applies cut policies and recomputes the eval's micro P/R.
"""
import hashlib
import json
import sys
import time

eval_dir, pool_path, out_path = sys.argv[1:4]
Q = json.load(open(f"{eval_dir}/questions.json"))["questions"]
D = json.load(open(f"{eval_dir}/dataset.json"))
text = {}
for m in D["memories"]:
    text[m["key"]] = m["content"]
for d in D["decisions"]:
    text[d["key"]] = f"Decision: {d['title']}. {d.get('reasoning') or ''}".strip()
for i in D["intentions"]:
    text[i["key"]] = f"Intention: {i['content']}"
pool = json.load(open(pool_path))["arms"]["bge-m3"]["per_question"]
split = {q["id"]: ("tune", "test")[hashlib.sha256(q["id"].encode()).digest()[0] % 2] for q in Q}

from sentence_transformers import CrossEncoder  # noqa: E402

model = CrossEncoder("BAAI/bge-reranker-v2-m3", max_length=512, device="cuda")
model.model.half()


def score_all():
    out, ms = {}, []
    for q in Q:
        log = pool[q["id"]]["item_log"]
        keys = [e["key"] for e in log if e["key"] in text]
        t0 = time.perf_counter()
        s = model.predict([(q["query"], text[k]) for k in keys], batch_size=32, activation_fn=None) if keys else []
        ms.append((time.perf_counter() - t0) * 1000)
        out[q["id"]] = {k: float(v) for k, v in zip(keys, s)}
    return out, ms


import torch  # noqa: E402

sig = lambda x: x  # CrossEncoder already returns sigmoid probabilities  # noqa: E731
s1, ms = score_all()
s2, _ = score_all()
maxdiff = max(abs(s1[q][k] - s2[q][k]) for q in s1 for k in s1[q]) if s1 else 0.0
standing_of = {q["id"]: {e["key"] for e in pool[q["id"]]["item_log"] if e.get("block") != "search"} for q in Q}


def evaluate(policy, ids):
    tot = {"items": 0, "ok": 0, "req": 0, "found": 0, "forb": 0}
    per = {}
    for q in Q:
        if q["id"] not in ids:
            continue
        p = pool[q["id"]]
        keys_all = [e["key"] for e in p["item_log"]]
        sc = s1[q["id"]]
        kept = policy(q, keys_all, sc)
        req, ok = set(q.get("required", [])), set(q.get("required", [])) | set(q.get("acceptable", []))
        forb_pool = set(p["forbidden_as_current"])
        tot["items"] += len(kept)
        tot["ok"] += len(set(kept) & ok)
        tot["req"] += len(req)
        tot["found"] += len(set(kept) & req)
        tot["forb"] += len(set(kept) & forb_pool)
        per[q["id"]] = sorted(req - set(kept))
    r = lambda a, b: round(a / b, 3) if b else None  # noqa: E731
    return {"P": r(tot["ok"], tot["items"]), "R": r(tot["found"], tot["req"]),
            "items_per_q": r(tot["items"], len(per)), "forbidden_as_current": tot["forb"],
            "missed": {k: v for k, v in per.items() if v}}


def absolute(t, keep=3, exempt_standing=False):
    def f(q, keys, sc):
        ranked = sorted(keys, key=lambda k: -sc.get(k, -99))
        kept = [k for i, k in enumerate(ranked) if i < keep or sig(sc.get(k, -99)) >= t
                or (exempt_standing and k in standing_of[q["id"]])]
        return kept
    return f


def none(q, keys, sc):
    return keys


ids = {"tune": {q for q, s in split.items() if s == "tune"}, "test": {q for q, s in split.items() if s == "test"},
       "all": set(split), "O": {q["id"] for q in Q if q["category"] == "O"}}
res = {"determinism_max_abs_logit_diff": maxdiff, "rerank_ms_p50": sorted(ms)[len(ms) // 2],
       "rerank_ms_p95": sorted(ms)[int(len(ms) * 0.95)], "gpu": torch.cuda.get_device_name(0), "policies": {}}
import math  # noqa: E402

lg = lambda p: math.log(max(p, 1e-9) / max(1 - p, 1e-9))  # noqa: E731


def topk_rr(k):
    return lambda q, keys, sc: sorted(keys, key=lambda x: -sc.get(x, -99))[:k]


def topk_cos(k):
    def f(q, keys, sc):
        sco = {e["key"]: e.get("score") or 0 for e in pool[q["id"]]["item_log"]}
        return sorted(keys, key=lambda x: -sco.get(x, 0))[:k]
    return f


def rel_logit(delta, keep=3):
    def f(q, keys, sc):
        ranked = sorted(keys, key=lambda x: -sc.get(x, -99))
        if not ranked:
            return []
        top = lg(sc.get(ranked[0], 0))
        return [x for i, x in enumerate(ranked) if i < keep or lg(sc.get(x, 0)) >= top - delta]
    return f


pols = {"pool(no cut)": none}
for k in (4, 5, 6, 7, 8, 9):
    pols[f"top{k} reranker"] = topk_rr(k)
    pols[f"top{k} cosine"] = topk_cos(k)
for d in (2, 3, 4, 5, 6, 8):
    for k in (3, 5):
        pols[f"rel logit d={d} keep={k}"] = rel_logit(d, k)
for name, pol in pols.items():
    res["policies"][name] = {s: evaluate(pol, i) for s, i in ids.items()}
json.dump(res, open(out_path, "w"), indent=1)
print("determinism max |logit diff|", maxdiff, "ms p50/p95", res["rerank_ms_p50"], res["rerank_ms_p95"])
for name, r in res["policies"].items():
    print(f"{name:22s} " + "  ".join(f"{s}: P {r[s]['P']} R {r[s]['R']} n {r[s]['items_per_q']} f {r[s]['forbidden_as_current']}" for s in ("tune", "test", "all", "O")))
