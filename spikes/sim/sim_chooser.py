"""Sandboxed simulation of the multi-crystal chooser (v0.3).

Replicates plugin/core.py choose() logic verbatim (all live crystals, one
multi-question d1 call, 0.80 gate, O(1) hint pre-gate, haystack top-3 for
content crystals), hits the REAL d1 (:8080) and haystack (:8083) endpoints,
but writes nothing to the live plugin store. Verdicts land in sim_verdicts.jsonl.
"""
import json
import re
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
OUT = HERE / "sim_verdicts.jsonl"

D1_URL = "http://127.0.0.1:8080/v1/systemone"
MIN_CONF = 0.80
HAYSTACK_URL = "http://127.0.0.1:8083/query"

SKIP_RE = re.compile(r"^\s*/|^(!|hi|hey|ok|thanks|yes|no)\b[^?]{0,12}$", re.I)
MIN_LEN = 12

# mirrored from plugin/core.py CRYSTAL_SPECS — keep in sync
RULES = [
    {"id": "notes-routing", "family": "notes/vault question",
     "trigger": ("Is this message a question about the user's personal notes, "
                 "vault, past sessions, projects, or stored information "
                 "(something answered by searching their notes)? A question "
                 "naming one of the user's projects, tools or repos by name "
                 "(e.g. diamondhead, haystack, notes-router) counts as yes."),
     "hint_words": [], "content": True},
    {"id": "auto-d0b974f8", "family": "code-change loop",
     "trigger": ("Is this message about editing, fixing, debugging or "
                 "refactoring the user's own code, so the agent should follow "
                 "an edit-then-test-then-commit loop?"),
     "hint_words": ["commit", "refactor", "test suite", "check.sh", "bug"],
     "content": False},
    {"id": "auto-72307acd", "family": "research loop",
     "trigger": ("Is this message a request to search the internet for "
                 "information or news (rather than searching the user's own "
                 "notes)?"),
     "hint_words": ["research", "search", "find out", "look up", "compare",
                    "news"],
     "yes_label": "needs web research", "min_conf": 0.55,
     "content": False},
]

QUERIES = [
    # notes-family ground truth (carried over from the v0.1 sim)
    ("yes-notes", "where do I keep the street fighter design notes?"),
    ("yes-notes", "what did we decide about the haystack storage dreams?"),
    ("yes-notes", "search my notes for the guitar practice plan"),
    ("yes-notes", "what's left on the diamondhead backlog?"),
    ("yes-notes", "find the note about the vpn config details"),
    ("yes-notes", "which note has the distro speed research?"),
    ("yes-notes", "remind me what the P2 concept was"),
    ("yes-notes", "pull up my work schedule note"),
    ("yes-notes", "dude where we at with diamondhead"),
    ("yes-notes", "wasnt there a note about the VPN thing"),
    ("yes-notes", "uh the crystal idea, where did we land on that"),
    ("yes-notes", "check the vault for the resume draft"),
    ("yes-notes", "hey did I write anything about the morning brief"),
    ("no", "what's the weather in Lisbon tomorrow"),
    ("no", "write a python function to parse csv files"),
    ("no", "how do I reset my bluetooth headphones"),
    ("no", "what time is the meeting today"),
    ("no", "run the tests on the street fighter repo"),
    ("no", "deploy the sql to the staging db please"),
    ("no", "hey"),
    ("no", "ok thanks mate that's all"),
    # code-change-loop family
    ("yes-code", "fix the bug in my parser script and commit"),
    ("yes-code", "refactor the router module"),
    ("no", "what did I write about the test suite"),
    # research-loop family
    ("yes-research", "research the best small local models this week"),
    ("yes-research", "look up news about llama.cpp releases"),
    ("no", "search my notes for the llama release checklist"),
]


def plausibly_any(text):
    t = text.strip()
    return len(t) >= MIN_LEN and not SKIP_RE.match(t)


def classify_one(text, rule, min_conf):
    min_conf = rule.get("min_conf") or min_conf
    body = {
        "state": "diamondhead routing",
        "questions": {"q": {
            "instructions": rule["trigger"] + " Text: " + text[:400],
            "type": "choice",
            "criteria": {"yes": rule.get("yes_label") or rule["family"], "no": "not this"},
        }},
    }
    req = urllib.request.Request(
        D1_URL, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=8) as r:
        ans = json.loads(r.read())["answers"]["q"]
    choice = str(ans.get("choice", "")).strip().lower()
    return choice, float(ans.get("confidence", 0.0))


def classify_multi(text, rules):
    # one single-question call per crystal, concurrent (mirrors core.py)
    from concurrent.futures import ThreadPoolExecutor
    out = {}
    with ThreadPoolExecutor(max_workers=len(rules)) as ex:
        futs = {r["id"]: ex.submit(classify_one, text, r, MIN_CONF) for r in rules}
        for rid, fut in futs.items():
            out[rid] = fut.result()
    return out


def haystack_top(text, k=3):
    body = {"q": text[:300], "k": k}
    req = urllib.request.Request(
        HAYSTACK_URL, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=8) as r:
        d = json.loads(r.read())
    rows = d if isinstance(d, list) else (d.get("results") or d.get("chunks") or [])
    return [(row.get("path", ""), row.get("heading", "")) for row in rows[:k]]


def main():
    results = []
    for label, q in QUERIES:
        t0 = time.monotonic()
        skipped = not plausibly_any(q)
        cand = []
        if not skipped:
            cand = [r for r in RULES
                    if not r["hint_words"]
                    or any(w in q.lower() for w in r["hint_words"])]
        rule_id = None
        conf = 0.0
        paths = []
        if cand:
            try:
                res = classify_multi(q, cand)
            except Exception as e:
                results.append({"label": label, "q": q, "error": str(e)[:100]})
                print(f"ERR {q[:50]}  {str(e)[:60]}")
                continue
            hits = [(r, res[r["id"]]) for r in cand
                    if res[r["id"]][0] == "yes"
                    and res[r["id"]][1] >= (r.get("min_conf") or MIN_CONF)]
            ms = (time.monotonic() - t0) * 1000
            if hits:
                rule, (_, conf) = max(hits, key=lambda x: x[1][1])
                rule_id = rule["id"]
                if rule.get("content"):
                    paths = haystack_top(q)
            rec = {"label": label, "q": q, "skipped": skipped,
                   "n_d1_questions": len(cand),
                   "res": {k: list(v) for k, v in res.items()},
                   "fired_rule": rule_id, "conf": round(conf, 3),
                   "ms": round(ms), "n_paths": len(paths),
                   "top_path": paths[0][0] if paths else ""}
        else:
            rec = {"label": label, "q": q, "skipped": True, "fired_rule": None,
                   "ms": 0}
        results.append(rec)
        state = "SKIP" if rec.get("skipped") else (rule_id or "no")
        print(f"{label:13s} {state:16s} {rec.get('conf', 0):.3f} "
              f"{rec.get('ms', 0):5d}ms  {q[:48]}")
        with OUT.open("a") as f:
            f.write(json.dumps(rec) + "\n")

    print("\n-- per family --")
    for fam in ("yes-notes", "yes-code", "yes-research"):
        rows = [r for r in results if r["label"] == fam]
        tp = sum(1 for r in rows if r.get("fired_rule"))
        print(f"{fam}: TP {tp}/{len(rows)}  "
              f"FN: {[r['q'][:32] for r in rows if not r.get('fired_rule')]}")
    no = [r for r in results if r["label"] == "no"]
    fp = [(r["q"][:32], r.get("fired_rule")) for r in no if r.get("fired_rule")]
    print(f"no-family: FP {len(fp)}/{len(no)}  {fp}")
    lat = sorted(r["ms"] for r in results if not r.get("skipped"))
    if lat:
        print(f"d1 latency ms p50 {lat[len(lat)//2]} p100 {lat[-1]}")


if __name__ == "__main__":
    main()
