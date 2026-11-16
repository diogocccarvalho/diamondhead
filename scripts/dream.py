"""Dream loop (station 5) — directed mutation of the hottest crystals.

Priority = measured usage (injections + near-misses). Direction = the family's
failure profile (same rules as dogfood.dream_direction). A mutant is appended
to the LIVE store as a candidate hint beside its parent: real-traffic
contention is the arena, consumed/judge/near-miss events are the referee,
and the normal promotion gate decides. The loop never promotes anything.

The loop's own procedure is recorded here as a contract (self-application):
  watch -> pick family by usage -> read failure profile -> emit ONE mutant
  with a fresh variant -> ledger append. Re-runnable; idempotent per variant.
"""
import hashlib
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "plugin"))
import core  # noqa: E402

LEDGER = Path(__file__).parent.parent / "dreams" / "dreams.jsonl"

# stage-1 scaffolding: variant banks are hand-authored; the CONTRACT (which
# variant wins on live traffic) is measured, not authored
PARAPHRASES = {
    "notes/vault question": [
        "Does this message ask about something the user wrote down before "
        "(their notes, records, or saved research)?",
        "Should the answer come from the user's stored notes rather than "
        "general knowledge?",
    ],
    "research loop": [
        "Would answering this need a fresh web search for up-to-date "
        "information?",
        "Is the user asking to find something out online right now?",
    ],
    "code-change loop": [
        "Does this message involve modifying code and verifying the change?",
        "Is the user asking to edit, test or commit their code?",
    ],
}
NARROW = {
    "notes/vault question": " (not general-knowledge or chitchat questions)",
    "research loop": " (the answer is NOT in the user's notes)",
    "code-change loop": " (not running existing tests without edits)",
}
SHARPEN = {
    "notes/vault question": (
        "Load skill notes-router FIRST, before answering. Route: project/id "
        "question -> `python3 ~/.hermes/scripts/projects.py find <words>`; "
        "anything else -> `python3 ~/.hermes/scripts/haystack.py query <text> "
        "-k 5`. Read the winning note in full; never answer from memory."),
    "research loop": (
        "[diamondhead route] Research-loop crystal: fire ALL searches in one "
        "parallel batch, then web_extract every promising hit before writing "
        "a word. Never search sequentially, never answer from one result."),
    "code-change loop": (
        "[diamondhead route] Code-change loop crystal: edit, then run tests, "
        "then the loader gate, then commit — in that order, no skipping."),
}


def failure_profile(events):
    per = {}
    for e in events:
        rid = e.get("rule")
        if not rid:
            continue
        d = per.setdefault(rid, {"inject": 0, "near_miss": 0,
                                 "contention": 0, "deviation": 0})
        if e["kind"] in d:
            d[e["kind"]] += 1
    return per


def pick_family(rules, profile):
    """Priority queue: measured usage IS the dream priority."""
    best, best_score = None, 0
    for r in rules:
        p = profile.get(r["id"], {})
        score = p.get("inject", 0) * 2 + p.get("near_miss", 0)
        if score > best_score:
            best, best_score = r, score
    return best


def direction_for(r, profile):
    p = profile.get(r["id"], {})
    if p.get("deviation", 0) >= max(1, 0.2 * p.get("inject", 0)):
        return "sharpen"
    if p.get("contention", 0) >= p.get("inject", 0):
        return "narrow"
    if p.get("near_miss", 0) > p.get("inject", 0) and p.get("near_miss", 0) >= 3:
        return "paraphrase"
    if p.get("inject", 0) >= 3:
        return "sharpen"
    return None


def mutate(r, direction, idx):
    fam = r.get("family", "")
    mutant = {"id": r["id"] + "-d" + direction[:3] + "-" + hashlib.sha256(
        (r["id"] + direction + str(idx)).encode()).hexdigest()[:6],
        "family": fam, "status": "candidate", "source": "dream",
        "parent": r["id"], "direction": direction, "variant": idx,
        "ts": time.time()}
    if direction == "paraphrase":
        mutant["trigger"] = PARAPHRASES.get(fam, [None])[idx % max(1, len(PARAPHRASES.get(fam, [1])))] or r.get("trigger", "")
        mutant["inject"] = r.get("inject", "")
    elif direction == "narrow":
        mutant["trigger"] = r.get("trigger", "") + NARROW.get(fam, "")
        mutant["inject"] = r.get("inject", "")
    else:  # sharpen: procedure wording, trigger untouched
        mutant["trigger"] = r.get("trigger", "")
        mutant["inject"] = SHARPEN.get(fam, r.get("inject", ""))
    for k in ("hint_words", "yes_label", "min_conf", "content"):
        if k in r:
            mutant[k] = r[k]
    return mutant


def dream():
    events = core.behavior_events()
    rules = [r for r in core.live_rules(core.load_rules())
             if r.get("status") != "enforced"]
    profile = failure_profile(events)
    r = pick_family(rules, profile)
    if r is None:
        if rules:
            return None, (f"{rules[0]['id']}: young — accumulate fires first")
        return None, "no live crystals to dream about"
    r = core.rule_fields(r)
    direction = direction_for(r, profile)
    if direction is None:
        return None, (f"{r['id']}: young (inject {profile.get(r['id'], {}).get('inject', 0)}) "
                      "- accumulate fires first")
    idx = max([x.get("variant", -1) for x in core.load_rules()
               if x.get("parent") == r["id"] and x.get("direction") == direction]
              + [-1]) + 1
    existing_ids = {x.get("id") for x in core.load_rules()}
    mutant = mutate(r, direction, idx)
    if mutant["id"] in existing_ids:
        return None, f"{mutant['id']} already dreamed"
    core.append_rule(mutant)
    core.log_event("dream", parent=r["id"], mutant=mutant["id"],
                   direction=direction, variant=idx)
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a") as f:
        f.write(json.dumps({"ts": time.time(), "parent": r["id"],
                            "mutant": mutant["id"], "direction": direction,
                            "variant": idx}) + "\n")
    return mutant, (f"parent {r['id']} ({direction}, usage "
                    f"{profile.get(r['id'], {})})")


if __name__ == "__main__":
    mutant, why = dream()
    if mutant:
        print(f"DREAMED {mutant['id']}\n  {why}\n  trigger: {mutant['trigger'][:90]}")
    else:
        print(f"no dream: {why}")
