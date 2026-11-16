"""Crystallization progress check — run at every diamondhead session.

Reads the LIVE plugin store (no writes). Reports: rule status, evidence
vs promotion threshold, injections, consumptions, corrections, and any
NEW candidate rules (crystallization events) since the marker file.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "plugin"))
import core  # noqa: E402

MARKER = Path.home() / ".hermes" / "plugin-data" / "diamondhead" / ".dogfood-ts"


def main():
    rules = core.load_rules()
    print("== crystallization state ==")
    for r in rules:
        if r.get("status") in ("candidate", "validated", "retracted", "hint"):
            print(f"  {r['id']}: {r.get('status')} "
                  f"(evidence {core.rule_evidence(r['id'])}/20)")
    ev = [json.loads(l) for l in core.BEHAVIOR_FILE.read_text().splitlines()
          if l.strip()]
    counts = {}
    for e in ev:
        counts[e["kind"]] = counts.get(e["kind"], 0) + 1
    print("  event counts:", counts)
    if MARKER.exists():
        since = float(MARKER.read_text().strip())
        fresh = [e for e in ev if e["ts"] > since and e["kind"] in
                 ("inject", "consumed", "correction", "chooser_crash")]
        print(f"== since last check ({len(fresh)} new) ==")
        for e in fresh[-10:]:
            print(f"  {e['kind']:14s} {json.dumps({k: v for k, v in e.items()
                  if k not in ('ts', 'kind')})[:140]}")
    MARKER.write_text(str(ev[-1]["ts"] if ev else 0))


if __name__ == "__main__":
    main()
