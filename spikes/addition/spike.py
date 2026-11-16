"""Spike: proof-gated crystallization of addition.

Frozen naive adder = the oracle (ground truth, never mutated).
Mutants are dreamed at random from a grammar of additions; the replay gate
(byte-identical over the workload distribution + measured cheaper) decides
promotion. Append-only ledger records every verdict.
"""
import hashlib
import inspect
import json
import random
import time
from pathlib import Path

HERE = Path(__file__).parent
LEDGER = HERE / "ledger.jsonl"
DISTRIBUTION_FILE = HERE / "workload.json"


# ---- oracle: frozen, never mutated ----
def naive_add(a, b):
    r = a
    for _ in range(b):
        r += 1
    return r


# ---- dreaming grammar: random leaf mutants over (a, b) ----
def mut_double_add(a, b):
    r, addend = a, 1
    base = 1
    while addend <= b:
        if b & addend:
            r = r + base
        base = base + base
        addend <<= 1
    return r


def mut_chunk4(a, b):
    r = a
    while b >= 4:
        r = r + 2
        r = r + 2
        b -= 4
    while b > 0:
        r += 1
        b -= 1
    return r


def mut_hot_lookup(a, b):
    table, r = {}, 0
    for i in range(16):
        table[i] = r
        r += 1
    if 0 <= b < 16:
        return a + table[b]
    r = a
    while b >= 16:
        r = r + 16
        b -= 16
    while b > 0:
        r += 1
        b -= 1
    return r


MUTANTS = {"double_add": mut_double_add, "chunk4": mut_chunk4, "hot_lookup": mut_hot_lookup}


# ---- workload: the distribution is the only legitimate constraint ----
def build_workload(n=4000):
    rng = random.Random(20261116)
    cases = []
    for _ in range(n):
        if rng.random() < 0.7:
            cases.append((rng.randrange(0, 64), rng.randrange(0, 32)))
        else:
            cases.append((rng.randrange(0, 10**6), rng.randrange(0, 5000)))
    return cases


def run(fn, cases):
    out = []
    t0 = time.perf_counter()
    for a, b in cases:
        out.append(fn(a, b))
    return out, (time.perf_counter() - t0)


def run_min(fn, cases, reps=3):
    outputs = None
    best = None
    for _ in range(reps):
        out, t = run(fn, cases)
        outputs = out
        best = t if best is None or t < best else best
    return outputs, best


PROBE_CASES = ((0, 0), (5, 0), (0, 7), (-5, 3), (5, -3), (-5, -3), (3, 10**6))


def domain_probe(fn):
    for a, b in PROBE_CASES:
        try:
            fn(a, b)
        except Exception as e:
            return {"fn": fn.__name__, "crash": f"{type(e).__name__}: {e}",
                    "input": [a, b]}
    return {"fn": fn.__name__, "crash": None}


def log(event):
    with LEDGER.open("a") as f:
        f.write(json.dumps(event, sort_keys=True) + "\n")


def replay_ledger():
    events = [json.loads(l) for l in LEDGER.read_text().splitlines() if l.strip()]
    latest = {}
    for e in events:
        if e["kind"] in ("verdict", "demote"):
            latest[e["mutant"]] = e
    return {
        "events": len(events),
        "demoted": sorted(m for m, e in latest.items() if e["kind"] == "demote"),
        "promoted": sorted(m for m, e in latest.items()
                           if e["kind"] == "verdict" and e["promoted"]),
        "rejected": sorted(m for m, e in latest.items()
                           if e["kind"] == "verdict" and e["status"] == "rejected"),
        "lossless": all(e.get("outputs_sha") for e in events if e["kind"] == "verdict"),
    }


def main():
    cases = build_workload()
    if not DISTRIBUTION_FILE.exists():
        DISTRIBUTION_FILE.write_text(json.dumps({"n": len(cases), "seed": 20261116}))

    base_out, base_t = run_min(naive_add, cases)

    probes = {}
    for name, fn in MUTANTS.items():
        probes[name] = domain_probe(fn)
        log({"kind": "domain_probe", "mutant": name, **probes[name]})
        if probes[name]["crash"]:
            print(f"DOMAIN PROBE {name}: CRASH {probes[name]['crash']} "
                  f"on {probes[name]['input']}")

    hot = [c for c in cases if c[0] < 64 and c[1] < 32]
    cold = [c for c in cases if c not in hot]

    for name, fn in MUTANTS.items():
        out, t = run_min(fn, cases)
        _, t_hot = run_min(fn, hot)
        _, t_cold = run_min(fn, cold)
        _, b_hot = run_min(naive_add, hot)
        _, b_cold = run_min(naive_add, cold)
        size = len(inspect.getsource(fn).encode())
        weighted = 0.7 * t_hot + 0.3 * t_cold
        weighted_base = 0.7 * b_hot + 0.3 * b_cold
        identical = out == base_out
        cheaper = weighted < weighted_base
        usage_weighted = True
        crash = probes[name]["crash"]
        promoted = identical and cheaper and not crash
        dream_judge = {
            "hot_cheaper": t_hot < b_hot,
            "cold_cheaper": t_cold < b_cold,
            "hot_share": 0.7,
            "weighted_faster": cheaper,
            "size_bytes": size,
            "size_per_hot_call": round(size / max(len(hot), 1), 2),
            "footprint_note": (
                "hot crystal: speed is what matters; cold crystal: only its "
                "size matters, so a big cold crystal is a compaction target"),
        }
        log({
            "kind": "verdict",
            "mutant": name,
            "dream_judge": dream_judge,
            "code_sha": __import__("hashlib").sha256(
                inspect.getsource(fn).encode()).hexdigest()[:12],
            "outputs_sha": __import__("hashlib").sha256(
                repr(out).encode()).hexdigest()[:12],
            "oracle_sha": __import__("hashlib").sha256(
                repr(base_out).encode()).hexdigest()[:12],
            "identical": identical,
            "t_mut_ms": round(t * 1000, 2),
            "t_oracle_ms": round(base_t * 1000, 2),
            "promoted": promoted,
            "status": "promoted" if promoted else "rejected",
        })

    for e in (json.loads(l) for l in LEDGER.read_text().splitlines() if l.strip()):
        if e["kind"] == "verdict":
            print(f"{e['mutant']:12s} identical={e['identical']} "
                  f"t={e['t_mut_ms']}ms vs oracle {e['t_oracle_ms']}ms "
                  f"-> {e['status'].upper()}")
    print("replay:", replay_ledger())


if __name__ == "__main__":
    main()
