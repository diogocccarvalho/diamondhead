"""Sandboxed simulation of the crystal-router chooser.

Replicates plugin/core.py choose() logic verbatim (hint rule, d1 prompt,
0.85 gate, haystack top-3), hits the REAL d1 (:8080) and haystack (:8083)
endpoints, but writes nothing to the live plugin store. Verdicts + a
promotion simulation land in sim_verdicts.jsonl.
"""
import json
import re
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
OUT = HERE / "sim_verdicts.jsonl"

D1_URL = "http://127.0.0.1:8080/v1/systemone"
MIN_CONF = 0.85
HAYSTACK_URL = "http://127.0.0.1:8083/query"

SKIP_RE = re.compile(r"^\s*/|^(!|hi|hey|ok|thanks|yes|no)\b.{0,12}$", re.I)
MIN_LEN = 12

QUERIES = [
    # ground-truth YES: clear notes questions
    ("yes", "where do I keep the street fighter design notes?"),
    ("yes", "what did we decide about the haystack storage dreams?"),
    ("yes", "search my notes for the guitar practice plan"),
    ("yes", "what's left on the diamondhead backlog?"),
    ("yes", "find the note about the EAI session id for test"),
    ("yes", "which note has the distro speed research?"),
    ("yes", "remind me what the P2 concept was"),
    ("yes", "pull up my work schedule note"),
    # ground-truth YES: fuzzy/colloquial notes questions
    ("yes", "dude where we at with diamondhead"),
    ("yes", "dude what was that thing with the tabs last week"),
    ("yes", "hmm what did I say about the multiplication ladder again"),
    ("yes", "wasnt there a note about the VPN thing"),
    ("yes", "uh the crystal idea, where did we land on that"),
    ("yes", "whats the deal with my meeting notes from friday"),
    ("yes", "check the vault for the resume draft"),
    ("yes", "hey did I write anything about the morning brief"),
    # ground-truth NO: not notes questions
    ("no", "what's the weather in Lisbon tomorrow"),
    ("no", "write a python function to parse csv files"),
    ("no", "how do I reset my bluetooth headphones"),
    ("no", "what time is the meeting today"),
    ("no", "run the tests on the street fighter repo"),
    ("no", "deploy the sql to moscovo04 please"),
    ("no", "hey"),
    ("no", "ok thanks mate that's all"),
]


def plausibly_notes(text):
    t = text.strip()
    return len(t) >= MIN_LEN and not SKIP_RE.match(t)


def classify(text):
    body = {
        "state": "diamondhead routing",
        "questions": {"q": {
            "instructions": (
                "Is this message a question about the user's personal notes, "
                "vault, past sessions, projects, or stored information "
                "(something answered by searching their notes)? "
                "Text: " + text[:400]),
            "type": "choice",
            "criteria": {"yes": "notes/vault question",
                         "no": "not a notes question"},
        }},
    }
    req = urllib.request.Request(
        D1_URL, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=8) as r:
        ans = json.loads(r.read())["answers"]["q"]
    return ans.get("choice"), float(ans.get("confidence", 0.0))


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
        skipped = not plausibly_notes(q)
        choice, conf, ms = None, 0.0, 0.0
        paths = []
        if not skipped:
            try:
                choice, conf = classify(q)
                ms = (time.monotonic() - t0) * 1000
                if choice == "yes" and conf >= MIN_CONF:
                    paths = haystack_top(q)
            except Exception as e:
                results.append({"label": label, "q": q, "error": str(e)[:100],
                                "skipped": skipped})
                continue
        fired = (choice == "yes" and conf >= MIN_CONF) if not skipped else False
        rec = {"label": label, "q": q, "skipped": skipped, "choice": choice,
               "conf": round(conf, 3), "ms": round(ms), "fired": fired,
               "n_paths": len(paths),
               "top_path": paths[0][0] if paths else ""}
        results.append(rec)
        print(f"{label:3s} {'SKIP' if skipped else (str(conf) if choice else '?'):6s} "
              f"{'FIRE ' if fired else '     '} {rec['ms']:5d}ms  {q[:52]}")
        with OUT.open("a") as f:
            f.write(json.dumps(rec) + "\n")

    yes = [r for r in results if r["label"] == "yes"]
    no = [r for r in results if r["label"] == "no"]
    tp = sum(1 for r in yes if r.get("fired"))
    fn = len(yes) - tp
    fp = sum(1 for r in no if r.get("fired"))
    print(f"\nTP {tp}/{len(yes)}  FN {fn}  FP {fp}/{len(no)}")
    print("FN confs:", [(r["q"][:30], r.get("conf")) for r in yes if not r.get("fired")])
    print("FP confs:", [(r["q"][:30], r.get("conf")) for r in no if r.get("fired")])
    allc = [(r.get("conf", 0), 1 if r["label"] == "yes" else 0) for r in results
            if not r.get("skipped")]
    for thr in (0.5, 0.6, 0.7, 0.8, 0.85):
        tp2 = sum(1 for c, y in allc if c >= thr and y)
        fp2 = sum(1 for c, y in allc if c >= thr and not y)
        print(f"threshold {thr}: TP {tp2}/16  FP {fp2}/8")
    print("\n'did it get used' proxy — haystack returned real paths for fired"
          " queries: see top_path in", OUT.name)


if __name__ == "__main__":
    main()
