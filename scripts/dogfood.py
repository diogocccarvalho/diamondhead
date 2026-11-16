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


def conf_stats(events, rid):
    vals = [e["conf"] for e in events
            if e.get("rule") == rid and isinstance(e.get("conf"), (int, float))]
    if not vals:
        return None
    n = len(vals)
    mean = sum(vals) / n
    std = (sum((v - mean) ** 2 for v in vals) / n) ** 0.5
    return mean, std, n


def dream_direction(rid, stats, counts, rule_events):
    """Selection signal per concept. Mutation is RANDOM — this failure
    profile is what the SELECTION gates will judge mutants against, never
    a steering wheel for the generator."""
    near = rule_events.get(("near_miss", rid), 0)
    inj = rule_events.get(("inject", rid), 0)
    cont = rule_events.get(("contention", rid), 0)
    dev = rule_events.get(("deviation", rid), 0)
    sig = []
    if dev:
        sig.append(f"deviation {dev}")
    if cont:
        sig.append(f"contention {cont}")
    if near:
        sig.append(f"near_miss {near}")
    if stats and stats[1] >= 0.15:
        sig.append(f"wobble std {stats[1]:.2f}")
    prof = ("; ".join(sig) or "no failures yet")
    if inj < 3:
        return f"young (inj {inj}) — selection signal: {prof}"
    return f"selection signal: {prof} — gates will judge random mutants on this"


def main():
    rules = core.live_rules(core.load_rules())
    print("== crystallization state ==")
    for r in rules:
        if r.get("status") in ("candidate", "validated", "retracted", "hint",
                               "enforced"):
            rid = r["id"]
            ratio, inj = core.consumed_ratio(rid)
            ratio = min(1.0, ratio)
            first = core.rule_first_seen(rid)
            age_d = f"{(core.time.time() - first) / 86400:.1f}" if first else "0 (no ts)"
            ev_n = core.rule_evidence(rid) or r.get("evidence_n", 0)
            print(f"  {rid}: {r.get('status')} "
                  f"(evidence {ev_n}/20, "
                  f"injections {inj}/{core.PROMOTE_MIN_INJ}, "
                  f"consumed {ratio:.0%} vs >=80%, age {age_d}d vs >=7d)")
    ev = [json.loads(l) for l in core.BEHAVIOR_FILE.read_text().splitlines()
          if l.strip()]
    counts = {}
    for e in ev:
        counts[e["kind"]] = counts.get(e["kind"], 0) + 1
    print("  event counts:", counts)
    dev = counts.get("deviation", 0)
    cons = counts.get("consumed", 0)
    closed = dev + cons
    if closed:
        print(f"  obedience: {cons}/{closed} injections consumed, "
              f"deviation rate {dev / closed:.0%}")
    # dynamic dimension report: per-rule stability, misses, contention,
    # and the dream direction each family's failure profile implies
    rule_events = {}
    for e in ev:
        k = (e["kind"], e.get("rule"))
        if k[1]:
            rule_events[k] = rule_events.get(k, 0) + 1
    print("== dimensions per crystal ==")
    for r in rules:
        rid = r["id"]
        stats = conf_stats(ev, rid)
        st = (f"conf mean {stats[0]:.2f} std {stats[1]:.2f} n{stats[2]}"
              if stats else "conf: no data")
        nm = rule_events.get(("near_miss", rid), 0)
        ct = rule_events.get(("contention", rid), 0)
        judged = [x for x in ev if x.get("kind") == "context_judge"
                  and x.get("rule") == rid]
        jok = (f"judge {sum(1 for x in judged if x.get('correct'))}/{len(judged)}"
               if judged else "judge: none")
        print(f"  {rid}: {st}, near_miss {nm}, contention {ct}, {jok}")
        print(f"    dream: {dream_direction(rid, stats, counts, rule_events)}")
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
