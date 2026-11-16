"""Genetic dreaming for the addition spike — REAL structural mutation.

Genome: an executable op-sequence computing a + b starting from r = a.
Primitives (the only legal moves; genome may NOT reference the oracle):
  ["add", k]          r += k
  ["addifbit", i, k]  r += k if b has bit i set
Mutation: uniform structural operators on the sequence (flip constant, flip
bit index, duplicate, delete, swap, truncate, append, point-type flip).
Fitness axis (--fitness): latency (min-of-3 weighted hot/cold wall time)
or space (serialized genome bytes). The axis is the ONLY human choice.
Selection: replay equality (proof) + domain probe (proof) + cheaper than
oracle under the axis (measurement). Provenance audit before the gate.
Every verdict lands in the append-only ledger (shared with spike.py).
"""
import argparse
import hashlib
import json
import random
import time
from pathlib import Path

HERE = Path(__file__).parent
LEDGER = HERE / "ledger.jsonl"

import sys
sys.path.insert(0, str(HERE))
from spike import build_workload, run_min, domain_probe, log, replay_ledger  # noqa: E402
from spike import naive_add  # noqa: E402  (oracle: frozen, gate-side only)

CONST_ALPHABET = [1, 2, 4, 8, 16, 32, 64, -1, -2, -4]
# correctness over the WORKLOAD selects the bit range: cold b reaches 5000,
# so genomes need bits up to 13 — the gates force representational adequacy
MAX_BITS = 13
MAX_OPS = 14
HOT_SHARE = 0.7


# ---- genome <-> executable ----
def interpret(genome, a, b):
    r = a
    for op in genome:
        kind = op[0]
        if kind == "add":
            r += op[1]
        elif kind == "addifbit":
            if b & (1 << op[1]):
                r += op[2]
        else:
            raise ValueError(f"illegal op {kind}")
    return r


def genome_bytes(genome):
    return len(json.dumps(genome, sort_keys=True).encode())


# ---- mutation: structural operators, uniform draw ----
def mutate(genome, rng):
    g = [list(op) for op in genome]
    if not g:
        g = [["add", rng.choice(CONST_ALPHABET)]]
    op = rng.randrange(len(g))
    kind = rng.choice(["flip_const", "flip_bit", "duplicate", "delete",
                       "swap", "truncate", "append", "point_flip"])
    if kind == "flip_const":
        g[op][1 if g[op][0] == "add" else 2] = rng.choice(CONST_ALPHABET)
    elif kind == "flip_bit" and g[op][0] == "addifbit":
        g[op][1] = rng.randrange(MAX_BITS)
    elif kind == "duplicate":
        g.insert(op, list(g[op]))
    elif kind == "delete" and len(g) > 1:
        del g[op]
    elif kind == "swap" and len(g) > 1:
        j = rng.randrange(len(g))
        g[op], g[j] = g[j], g[op]
    elif kind == "truncate" and len(g) > 1:
        g = g[:op]
    elif kind == "append":
        if rng.random() < 0.5:
            g.append(["add", rng.choice(CONST_ALPHABET)])
        else:
            g.append(["addifbit", rng.randrange(MAX_BITS),
                      rng.choice(CONST_ALPHABET)])
    elif kind == "point_flip":
        g[op] = (["addifbit", rng.randrange(MAX_BITS), rng.choice(CONST_ALPHABET)]
                 if g[op][0] == "add"
                 else ["add", rng.choice(CONST_ALPHABET)])
    return g[:MAX_OPS + 2]


def seed_population(rng, size):
    pop = []
    # one seed per known structure (prior art as founder, not as bank):
    pop.append([["addifbit", i, 1 << i] for i in range(MAX_BITS)])  # double_add
    while len(pop) < size:
        n = rng.randrange(1, 6)
        pop.append([(["add", rng.choice(CONST_ALPHABET)] if rng.random() < 0.5
                     else ["addifbit", rng.randrange(MAX_BITS),
                           rng.choice(CONST_ALPHABET)])
                    for _ in range(n)])
    return pop


# ---- selection ----
def audit(genome):
    """Provenance: genome text may not reference the oracle — by construction
    ops are primitives, but the check stays (it caught a cheat once)."""
    txt = json.dumps(genome)
    for bad in ("naive", "oracle", "inspect", "eval", "exec"):
        if bad in txt:
            return False
    return all(op[0] in ("add", "addifbit") for op in genome)


def fitness(genome, cases, hot, cold, oracle_hot_t, oracle_cold_t,
            oracle_genome_bytes, axis, reps=3):
    probe = domain_probe(lambda a, b: interpret(genome, a, b))
    if probe["crash"]:
        return None, {"crash": probe["crash"]}
    out, t = run_min(lambda a, b: interpret(genome, a, b), cases, reps)
    if axis == "latency":
        _, t_hot = run_min(lambda a, b: interpret(genome, a, b), hot, reps)
        _, t_cold = run_min(lambda a, b: interpret(genome, a, b), cold, reps)
        score = HOT_SHARE * t_hot + (1 - HOT_SHARE) * t_cold
        base = HOT_SHARE * oracle_hot_t + (1 - HOT_SHARE) * oracle_cold_t
    else:  # space
        score = genome_bytes(genome)
        base = oracle_genome_bytes
    return (score, out), {"score": score, "base": base}


def run_ga(fitness_axis="latency", generations=6, population=8, seed=20261116):
    rng = random.Random(seed)
    cases = build_workload()
    hot = [c for c in cases if c[0] < 64 and c[1] < 32]
    cold = [c for c in cases if c not in hot]
    base_out, base_t = run_min(naive_add, cases)
    _, oh = run_min(naive_add, hot)
    _, oc = run_min(naive_add, cold)
    # space baseline: the bytes of the smallest KNOWN-correct structure (the
    # double_add seed) — a genome must compact against the best prior art
    space_base = genome_bytes([["addifbit", i, 1 << i]
                               for i in range(MAX_BITS)])
    pop = seed_population(rng, population)
    champion, champion_fit, champion_out = None, None, None
    for gen in range(generations):
        scored = []
        for g in pop:
            if not audit(g):
                log({"kind": "audit_fail", "gen": gen,
                     "genome_sha": hashlib.sha256(
                         json.dumps(g).encode()).hexdigest()[:12]})
                continue
            res, meta = fitness(g, cases, hot, cold, oh, oc, space_base,
                                fitness_axis)
            if res is None:
                log({"kind": "domain_probe", "gen": gen, "crash": meta["crash"]})
                continue
            score, out = res
            identical = out == base_out
            cheaper = meta["score"] < meta["base"]
            promoted = identical and cheaper
            log({"kind": "verdict", "mutant": "ga-" + hashlib.sha256(
                    json.dumps(g, sort_keys=True).encode()).hexdigest()[:8],
                "gen": gen, "axis": fitness_axis, "ops": g,
                "identical": identical, "cheaper": cheaper,
                "score": round(meta["score"], 6),
                "base": round(meta["base"], 6),
                "promoted": promoted,
                "status": "promoted" if promoted else "rejected",
                "outputs_sha": hashlib.sha256(
                    repr(out).encode()).hexdigest()[:12]})
            scored.append((score, identical, cheaper, g, out))
            if identical and cheaper and (champion is None or score < champion_fit):
                champion, champion_fit, champion_out = g, score, out
        # generational selection: keep the correct-and-cheaper half, mutate on
        survivors = [g for s, i, c, g, _ in sorted(scored) if i and c]
        pop = [mutate(rng.choice(survivors), rng) for _ in range(population)] \
            if survivors else seed_population(rng, population)
    return champion, champion_fit, champion_out, base_out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fitness", choices=["latency", "space"],
                    default="latency")
    ap.add_argument("--generations", type=int, default=6)
    ap.add_argument("--population", type=int, default=8)
    args = ap.parse_args()
    t0 = time.perf_counter()
    champion, fit, out, base_out = run_ga(args.fitness, args.generations,
                                          args.population)
    if champion is None:
        print("no champion: every genome failed the gates")
    else:
        print(f"CHAMPION ({args.fitness}): {json.dumps(champion)}")
        print(f"  fitness {fit:.6f}  identical={out == base_out} "
              f"(replay-proven)")
    print(f"  {args.generations} generations in "
          f"{time.perf_counter() - t0:.1f}s")
    print("replay:", replay_ledger())


if __name__ == "__main__":
    main()
