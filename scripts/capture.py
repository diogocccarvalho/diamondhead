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


def capture(steps_text, claim, oracle_hint=""):
    steps = [s.strip() for s in steps_text.split(";") if s.strip()]
    genome = steps
    digest = hashlib.sha256(steps_text.encode("utf-8", "replace"))
    rid = "capture-" + digest.hexdigest()[:10]
    rec = {"id": rid, "family": "insight", "status": "candidate",
           "ts": time.time(), "genome": genome, "origin": "capture",
           "claim": (claim or "")[:300], "oracle_hint": oracle_hint[:200],
           "evidence_tier": "capture-only"}
    core.append_rule(rec)
    core.log_event("capture", rule=rid, steps=len(genome),
                   claim=(claim or "")[:80])
    # proof obligation ledger: what would PROVE this crystal
    entry = {"id": rid, "ts": time.time(), "steps": genome,
             "claim": claim or "", "oracle_hint": oracle_hint or "",
             "verdict": "unproven - no oracle yet"}
    PROOF_PATH.parent.mkdir(parents=True, exist_ok=True)
    with PROOF_PATH.open("a") as f:
        f.write(json.dumps(entry) + "\n")
    return rid, genome


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--steps", required=True,
                    help="semicolon-separated reasoning steps")
    ap.add_argument("--claim", default="")
    ap.add_argument("--oracle", default="",
                    help="hint at what would prove it (oracle/eval)")
    a = ap.parse_args()
    core.init()
    rid, genome = capture(a.steps, a.claim, a.oracle)
    print(f"captured {rid}: {len(genome)} steps -> candidate hint")
    print(f"proof obligation logged in {PROOF_PATH.name}")
    print("proof-tier graduation needs an oracle over the stated steps;")


if __name__ == "__main__":
    main()
