"""Provenance audit for dreamed mutants (invariant block, not signature-chasing).

Rule: a mutant must not reference the oracle (or anything that references
the oracle). Cheating is impossible BY CONSTRUCTION, not detected by
behavior. Runs on source text + call graph, offline.
"""
import inspect
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import spike

ORACLE_NAMES = {"naive_add", "ORACLE"}


def oracle_refs(fn) -> list:
    src = inspect.getsource(fn)
    refs = []
    for name in ORACLE_NAMES:
        for m in re.finditer(rf"\b{name}\b", src):
            refs.append(m.group(0))
    seen = set()
    for callee_name in re.findall(r"(\w+)\s*\(", src):
        callee = globals().get(callee_name) or getattr(spike, callee_name, None)
        if callee is not None and callee is not fn and callable(callee):
            for ref in oracle_refs(callee):
                if ref not in seen:
                    seen.add(ref)
    return refs + sorted(seen)


def audit(fn) -> dict:
    refs = oracle_refs(fn)
    return {"mutant": fn.__name__, "clean": not refs, "oracle_refs": refs}


def main():
    verdicts = []
    print(f"{'mutant':12s} {'clean':6s} oracle_refs")
    for name, fn in vars(spike).items():
        if name.startswith("mut_") and callable(fn):
            a = audit(fn)
            print(f"{a['mutant']:12s} {str(a['clean']):6s} {a['oracle_refs']}")
            verdicts.append(a)
    bad = [a for a in verdicts if not a["clean"]]
    print(f"\n{len(verdicts) - len(bad)}/{len(verdicts)} clean;"
          f" {len(bad)} CHEATING (must be demoted, gate result void)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
