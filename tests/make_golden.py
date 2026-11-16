"""Generate the golden behavioral fixture: what WORKS today, frozen.

Runs a scripted set of scenarios through the real chooser (mocked d1/haystack)
in a sandboxed store and records the event stream (ts stripped). Any change
that alters this stream must re-bless deliberately:  python3 tests/make_golden.py --bless
and say why in the commit message. The golden test fails otherwise.
"""
import hashlib
import json
import sys
import tempfile
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent.parent / "plugin"))
import core  # noqa: E402

HERE = Path(__file__).parent
GOLDEN = HERE / "golden.json"


def scenarios(cfg):
    """Each scenario: (name, classify response, haystack paths, message, history)."""
    return [
        ("notes_hit", {"notes-routing": (True, 0.94, "yes", "d1-t")},
         ["a/vpn.md", "a/distro.md"], "where is the VPN note", ""),
        ("notes_no", {"notes-routing": (False, 0.40, "no", "d1-t")}, [],
         "what's the weather in Lisbon", ""),
        ("near_miss", {"notes-routing": (False, 0.72, "yes", "d1-t")}, [],
         "remind me about the vpn config", ""),
        ("contention", {
            "notes-routing": (True, 0.95, "yes", "d1-t"),
            "auto-72307acd": (True, 0.90, "yes", "d1-t")}, [],
         "search my notes for the llama release checklist", ""),
        ("dedup_hit", {"notes-routing": (True, 0.91, "yes", "d1-t")},
         ["a/dup.md", "a/fresh.md"], "where did we land on the distro thing",
         "earlier context quoted a/dup.md here"),
        ("haystack_down", {"notes-routing": (True, 0.93, "yes", "d1-t")},
         "URLError", "find the note about the resume", ""),
    ]


def run_all():
    tmp = tempfile.mkdtemp(prefix="dh-golden-")
    core.DATA = Path(tmp)
    core.RULES_FILE = core.DATA / "rules.jsonl"
    core.BEHAVIOR_FILE = core.DATA / "behavior.jsonl"
    core.TASK_DIRECTIONS.clear()
    core.init()
    core.append_rule({"id": "auto-72307acd", "family": "research loop",
                      "status": "candidate", "ts": core.time.time()})
    cfg = {"d1_url": "http://x", "haystack_url": "http://y",
           "min_confidence": 0.80, "promote_n": 20}
    out = []
    for name, cres, hpaths, msg, history in scenarios(cfg):
        core.BEHAVIOR_FILE.write_text("")
        core.PENDING_INJECT = None
        core.LAST_INJECT_TS = 0.0

        def fake_haystack(text, url, k=3, _p=hpaths):
            if isinstance(_p, str) and _p == "URLError":
                raise __import__("urllib.error", fromlist=["x"]).URLError("down")
            return list(_p)

        with mock.patch.object(core, "classify_multi", return_value=cres), \
             mock.patch.object(core, "haystack_top", side_effect=fake_haystack):
            text, conf, ms = core.choose(msg, cfg, history=history,
                                         session_id="sess-golden")
        evs = [json.loads(l) for l in
               core.BEHAVIOR_FILE.read_text().splitlines() if l.strip()]
        out.append({
            "scenario": name,
            "returned": None if text is None else hashlib.sha256(
                text.encode()).hexdigest()[:12],
            "conf": round(conf, 3),
            "events": [{k: v for k, v in e.items() if k not in ("ts",)}
                       for e in evs],
        })
    return out


def main():
    data = run_all()
    if "--bless" in sys.argv:
        GOLDEN.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n")
        print(f"blessed {GOLDEN} ({len(data)} scenarios)")
    else:
        golden = json.loads(GOLDEN.read_text())
        print("MATCH — behavior identical to the blessed fixture"
              if golden == data else "DIFF — behavior changed from golden")


if __name__ == "__main__":
    main()
