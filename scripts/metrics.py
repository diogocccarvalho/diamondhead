"""Token-cost dimension: crystal path vs no-crystal path.

Measured columns come from the behavior log (injected chars/latency, consumed
rate, judge rate). The counterfactual (tokens the turn would have cost without
the crystal) is NOT directly observable — the no-crystal column is a SIMULATED
estimate: what the naive path costs when the skill was actually needed (grep +
read winning note in full), taken from sim runs. Emit markdown + CSV.

Usage: python3 scripts/metrics.py [--out FILE.md]
"""
import argparse
import csv
import json
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "plugin"))
import core  # noqa: E402

CHARS_PER_TOKEN = 4.0
SIM_NO_CRYSTAL_TOKENS = 2500  # grep + read winning note in full (sim estimate)
SIM_NO_CRYSTAL_TURNS_FRACTION = 1.0


def est_tokens(chars):
    return int(chars / CHARS_PER_TOKEN)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    ev = core.behavior_events()
    turns = [e for e in ev if e.get("kind") == "turn"]
    inj = [e for e in ev if e.get("kind") == "inject"]
    cons = [e for e in ev if e.get("kind") == "consumed"]
    dev = [e for e in ev if e.get("kind") == "deviation"]
    judges = [e for e in ev if e.get("kind") == "context_judge"]
    evals = [e for e in ev if e.get("kind") == "chooser_no"]

    inj_tokens = [est_tokens(e.get("chars", 0)) for e in inj]
    eval_ms = [e["ms"] for e in evals if e.get("ms")]
    skip_ms = [e["ms"] for e in turns if e.get("ms") == 0]

    # rot curve: context the crystals did NOT add. Dedup dropped = paths
    # already in conversation history; superseded = paths a crystal already
    # provided this session. Naive baseline = re-injecting everything.
    sup = [e for e in ev if e.get("kind") == "superseded"]
    dedup = [e for e in ev if e.get("kind") == "context_dedup"]
    rot_saved = len(sup) * 60 + len(dedup) * 60  # ~1 path line = ~60 tok
    naive_reinject = sum(inj_tokens) + rot_saved

    closed = len(cons) + len(dev)
    consumed_rate = len(cons) / closed if closed else 0.0
    judged_correct = (sum(1 for e in judges if e.get("correct")) / len(judges)
                      if judges else 0.0)

    # counterfactual (simulated): consumed injections replace the naive path
    saved = int(len(cons) * SIM_NO_CRYSTAL_TOKENS)
    spent = sum(inj_tokens)
    net = saved - spent

    rows = [
        ("turns observed", len(turns), "measured"),
        ("injections fired", len(inj), "measured"),
        ("tokens injected (total)", sum(inj_tokens), "measured (chars/4)"),
        ("tokens injected (mean/injection)",
         int(st.mean(inj_tokens)) if inj_tokens else 0, "measured (chars/4)"),
        ("chooser p50 / p99 latency ms",
         f"{sorted(eval_ms)[len(eval_ms)//2] if eval_ms else 0}/"
         f"{sorted(eval_ms)[int(len(eval_ms)*.99)] if eval_ms else 0}", "measured"),
        ("skip-gate 0ms turns", len(skip_ms), "measured"),
        ("consumed rate", f"{consumed_rate:.0%} ({len(cons)}/{closed})",
         "measured"),
        ("judge-correct rate", f"{judged_correct:.0%} ({len(judges)} judged)",
         "measured"),
        ("no-crystal cost per naive turn (tokens)", SIM_NO_CRYSTAL_TOKENS,
         "SIMULATED"),
        ("net tokens (simulated savings - injected)", net,
         "SIMULATED: consumed injections x naive cost"),
        ("rot: re-injections dropped (dedup + superseded)",
         f"{len(dedup)} + {len(sup)}", "measured"),
        ("rot: tokens NOT re-added (est)", rot_saved, "measured (~60/path)"),
        ("rot: naive reinject vs actual",
         f"{naive_reinject} vs {sum(inj_tokens)}", "measured+est"),
    ]
    print("| metric | value | source |")
    print("|---|---|---|")
    for name, val, src in rows:
        print(f"| {name} | {val} | {src} |")

    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        with open(args.out, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["metric", "value", "source"])
            for name, val, src in rows:
                w.writerow([name, val, src])
        print(f"csv -> {args.out}")


if __name__ == "__main__":
    main()
