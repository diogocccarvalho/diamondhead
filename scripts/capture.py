#!/usr/bin/env python3
"""Insight-capture: 'I did this by thinking this way - crystallize this if
possible.' The stated reasoning becomes a candidate crystal (family
'insight', genome = the stated steps); the PROOF obligation is recorded,
not pretended. Proof-tier graduation requires an oracle built over the
stated steps (spike-style: replay + domain-stated); without one the
crystal stays a behavioral hint, honestly labeled capture-only.

Usage:
  python3 scripts/capture.py --steps "step1; step2; step3" [--claim "..."]
Writes: candidate rule + capture event in the live store; PROOF.md note.
"""
import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "plugin"))
import core  # noqa: E402

PROOF_PATH = HERE.parent / "docs" / "captures.md"


def capture(steps_text, claim, oracle_hint="", oracle_name=""):
    steps = [s.strip() for s in steps_text.split(";") if s.strip()]
    genome = steps
    digest = hashlib.sha256(steps_text.encode("utf-8", "replace"))
    rid = "capture-" + digest.hexdigest()[:10]
    known = oracle_name in core.ORACLES if oracle_name else False
    rec = {"id": rid, "family": "insight", "status": "candidate",
           "ts": time.time(), "genome": genome, "origin": "capture",
           "claim": (claim or "")[:300], "oracle_hint": oracle_hint[:200],
           "evidence_tier": "capture-only"}
    if oracle_name:
        rec["oracle_name"] = oracle_name
        rec["evidence_tier"] = "oracle-registered" if known else "oracle-pending"
    core.append_rule(rec)
    core.log_event("capture", rule=rid, steps=len(genome),
                   claim=(claim or "")[:80], oracle=oracle_name or None)
    # proof obligation ledger: what would PROVE this crystal
    entry = {"id": rid, "ts": time.time(), "steps": genome,
             "claim": claim or "", "oracle_hint": oracle_hint or "",
             "oracle_name": oracle_name or None,
             "verdict": ("oracle registered - graduation possible"
                         if known else
                         "unproven - register the oracle in core.ORACLES")}
    PROOF_PATH.parent.mkdir(parents=True, exist_ok=True)
    with PROOF_PATH.open("a") as f:
        f.write(json.dumps(entry) + "\n")
    return rid, genome, known


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--steps", required=True,
                    help="semicolon-separated reasoning steps")
    ap.add_argument("--claim", default="")
    ap.add_argument("--oracle", default="",
                    help="hint at what would prove it (oracle/eval)")
    ap.add_argument("--oracle-name", default="",
                    help="registered oracle in core.ORACLES; enables "
                         "proof_graduate over its stated domain")
    a = ap.parse_args()
    core.init()
    if a.oracle_name and a.oracle_name not in core.ORACLES:
        print(f"oracle '{a.oracle_name}' not in core.ORACLES "
              f"(known: {', '.join(core.ORACLES) or 'none'})")
        print("capturing as oracle-pending; add the oracle spec to "
              "core.ORACLES (fn + expected + domain + probe) then re-capture")
    rid, genome, known = capture(a.steps, a.claim, a.oracle, a.oracle_name)
    print(f"captured {rid}: {len(genome)} steps -> candidate hint")
    print(f"proof obligation logged in {PROOF_PATH.name}")
    if known:
        print(f"oracle {a.oracle_name} registered - graduation possible: "
              f"core.proof_graduate('{rid}', '{a.oracle_name}')")
    print("proof-tier graduation needs an oracle over the stated steps;")


if __name__ == "__main__":
    main()
