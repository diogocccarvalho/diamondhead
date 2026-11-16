"""Candidate mining from the behavior log — the first self-generated crystals.

Groups tool events by task, counts tool 3-grams (the repeated shapes of the
agent's own work), and appends CANDIDATE rules to the store. Candidates never
fire (live_rules skips them) — they are data awaiting promotion machinery.
Usage count IS the dream priority queue: hottest pattern mined first.
"""
import hashlib
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "plugin"))
import core  # noqa: E402

MIN_OCCURRENCES = 5
FAMILY_ACTIONS = {
    ("patch", "terminal"): ("code-change loop",
                            "after editing a file, run the test suite, then the "
                            "loader gate, then commit"),
    ("web_search", "web_search"): ("research loop",
                                   "batch parallel searches, then extract pages"),
}


def mine():
    seqs = defaultdict(list)
    for e in core.behavior_events():
        if e.get("kind") == "tool":
            seqs[e.get("task", "")].append(e["tool"])
    grams = Counter()
    for s in seqs.values():
        for i in range(len(s) - 1):
            pair = (s[i], s[i + 1])
            if pair in FAMILY_ACTIONS:
                grams[pair] += 1
    made = []
    for pair, n in grams.most_common():
        if n < MIN_OCCURRENCES:
            break
        family, action = FAMILY_ACTIONS[pair]
        rid = "auto-" + hashlib.sha256(
            ("->".join(pair) + "|" + family).encode()).hexdigest()[:8]
        if any(r.get("id") == rid for r in core.load_rules()):
            continue
        spec = core.CRYSTAL_SPECS.get(family, {})
        rec = {"id": rid, "family": family, "action": action,
               "status": "candidate", "evidence_n": n,
               "source": "mined", "pattern": "->".join(pair),
               "ts": time.time()}
        for k in ("trigger", "inject", "hint_words", "content"):
            if k in spec:
                rec[k] = spec[k]
        core.append_rule(rec)
        core.log_event("crystal_candidate", rule=rid, pattern=rec["pattern"],
                       evidence_n=n)
        made.append(rec)
    return made


if __name__ == "__main__":
    new = mine()
    for r in new:
        print(f"CANDIDATE {r['id']}  {r['pattern']}  x{r['evidence_n']}  {r['family']}")
    if not new:
        print("no new candidates (already mined or below threshold)")
