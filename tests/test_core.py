"""diamondhead core tests — offline (mocked HTTP) + live (local services)."""
import io
import json
import sys
import tempfile
import time
import urllib.error
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent.parent / "plugin"))

import core

results = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  [{detail}]"))


def fake_urlopen(payload, fail=False):
    class R:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def read(self):
            if fail:
                raise urllib.error.URLError("down")
            return json.dumps(payload).encode()

    return mock.MagicMock(return_value=R())


def test_dream():
    sys.path.insert(0, str(Path(core.__file__).parent.parent / "scripts"))
    import dream  # noqa: F401
    # refusal: young family dreams nothing
    core.init()
    core.BEHAVIOR_FILE.write_text("")
    m, why = dream.dream()
    check("young family refuses to dream", m is None and "young" in why)

    # usage priority + direction + mutant appended beside parent
    for i in range(4):
        core.log_event("inject", rule="notes-routing", conf=0.9)
    for i in range(2):
        core.log_event("near_miss", rule="notes-routing", conf=0.7, gate=0.8)
    m, why = dream.dream()
    check("hottest family dreams", m is not None and m["parent"] == "notes-routing")
    check("mutation operator is a random draw from the bank",
          m is not None and m["direction"] in
          ("paraphrase", "narrow", "sharpen", "cost"))
    rules = {r["id"]: r for r in core.load_rules()}
    check("mutant beside parent in live store", m["id"] in rules)
    check("mutant is a candidate (never auto-fires enforced)",
          rules[m["id"]]["status"] == "candidate")
    check("mutant carries parent + variant",
          rules[m["id"]].get("parent") == "notes-routing"
          and rules[m["id"]].get("variant") == 0)
    # variant advances on re-run, no duplicate
    m2, _ = dream.dream()
    check("next dream advances variant",
          m2 is None or m2.get("variant", 0) > 0 or m2["id"] != m["id"])
    check("dream ledger line appended", dream.LEDGER.exists())


def test_task_direction():
    # distilled once per session; raw text memory-only
    core.TASK_DIRECTIONS.clear()
    core.BEHAVIOR_FILE.write_text("")
    t = core.set_task_direction("sess-abc-123", "refactor the router and   "
                                "make sure the tests pass afterwards, then "
                                "commit everything  ")
    check("direction distilled (whitespace normalized, truncated)",
          t == "refactor the router and make sure the tests pass afterwards,"
               " then commit everything"[:300]
          or t.startswith("refactor the router and make sure the tests"))
    ev = core.behavior_events()
    check("direction_set logs hash only, never raw text",
          any(e["kind"] == "direction_set" for e in ev)
          and "refactor" not in open(core.BEHAVIOR_FILE).read())
    # compass injects each turn
    line = core.task_direction_inject("sess-abc-123")
    check("compass injects with reasoning scaffold",
          line is not None and line.startswith("Main task:")
          and "checkpoints" in line)
    # other sessions get nothing
    check("no compass for unknown session",
          core.task_direction_inject("other") is None)
    # re-set overwrites (same session, corrected task)
    core.set_task_direction("sess-abc-123", "actually the task is X instead")
    check("re-distill overwrites", len(core.TASK_DIRECTIONS) == 1)


def test_dimensions():
    cfg = {"d1_url": "http://x", "haystack_url": "http://y",
           "min_confidence": 0.80, "promote_n": 20}

    # contention: two crystals above gate -> winner higher conf
    core.init()
    core.append_rule({"id": "auto-72307acd", "family": "research loop",
                      "status": "candidate", "ts": time.time()})
    core.BEHAVIOR_FILE.write_text("")
    core.PENDING_INJECT = None
    with mock.patch.object(core, "classify_multi", return_value={
            "notes-routing": (True, 0.95, "yes", "d1-t"),
            "auto-72307acd": (True, 0.90, "yes", "d1-t")}), \
         mock.patch.object(core, "haystack_top", return_value=[]):
        core.choose("search my notes for the llama release checklist", cfg)
    ev = core.behavior_events()
    check("contention logged with both rules",
          any(e["kind"] == "contention" and e["winner"] == "notes-routing"
              and e["runner_up"] == "auto-72307acd" for e in ev))

    # near_miss: yes choice below gate -> logged with conf + gate, no inject
    core.BEHAVIOR_FILE.write_text("")
    core.PENDING_INJECT = None
    with mock.patch.object(core, "classify_multi", return_value={
            "notes-routing": (False, 0.72, "yes", "d1-t")}), \
         mock.patch.object(core, "haystack_top", return_value=[]):
        core.choose("where is the VPN note", cfg)
    ev = core.behavior_events()
    check("near_miss logged when yes under gate",
          any(e["kind"] == "near_miss" and e["rule"] == "notes-routing"
              and e["conf"] == 0.72 and e["gate"] == cfg["min_confidence"]
              for e in ev))
    check("no inject on near miss", not any(e["kind"] == "inject" for e in ev))


def main():
    tmp = tempfile.mkdtemp(prefix="dh-test-")
    core.DATA = Path(tmp)
    core.RULES_FILE = core.DATA / "rules.jsonl"
    core.BEHAVIOR_FILE = core.DATA / "behavior.jsonl"
    core.init()

    # skip gate
    check("slash command skipped", not core.plausibly_notes("/new"))
    check("greeting skipped", not core.plausibly_notes("hey"))
    check("short skipped", not core.plausibly_notes("ok thanks"))
    check("greeting with question NOT skipped",
          core.plausibly_notes("no, actually where are my VPN notes from last tuesday?"))
    check("real question passes", core.plausibly_notes("where did I put the VPN note"))

    # rules store
    rules = core.load_rules()
    check("seed rule present", rules and rules[0]["id"] == "notes-routing")
    check("live rules keep hint", core.live_rules(rules)[0]["status"] == "hint")

    # evidence counting + retraction supersede
    core.bump_evidence("notes-routing")
    core.bump_evidence("notes-routing")
    check("evidence accumulates", core.rule_evidence("notes-routing") == 2)
    with open(core.RULES_FILE, "a") as f:
        f.write(json.dumps({"id": "notes-routing", "status": "retracted"}) + "\n")
    check("retraction resets evidence", core.rule_evidence("notes-routing") == 0)
    check("retracted rule not live", not core.live_rules(core.load_rules()))
    core.RULES_FILE.unlink()
    core.init()
    check("re-init reseeds after wipe", core.load_rules()[0]["id"] == "notes-routing")

    # chooser: classifier no
    cfg = {"d1_url": "http://x", "haystack_url": "http://y", "min_confidence": 0.85}
    with mock.patch.object(core, "classify_multi", return_value={"notes-routing": (False, 0.4, "no", "")}):
        text, conf, ms = core.choose("what did I do Friday", cfg)
    check("classifier-no returns None", text is None)

    # chooser: hit with haystack paths
    with mock.patch.object(core, "classify_multi", return_value={"notes-routing": (True, 0.95, "yes", "d1-test")}), \
         mock.patch.object(core, "haystack_top", return_value=["notes/vpn.md"]):
        text, conf, ms = core.choose("where is the VPN note", cfg)
    check("hit returns injection", text is not None and "notes-router" in text)
    check("hit includes paths", "notes/vpn.md" in text)
    ev = [json.loads(l) for l in core.BEHAVIOR_FILE.read_text().splitlines()]
    check("inject logged with hash not raw",
          any(e["kind"] == "inject" for e in ev)
          and not any("VPN note" in json.dumps(e) for e in ev))

    # chooser: service down degrades to None
    with mock.patch.object(core, "classify_multi",
                           side_effect=urllib.error.URLError("down")):
        text, conf, ms = core.choose("where is the VPN note", cfg)
    check("classifier-down fail-open None", text is None)

    # haystack list-shaped response (real /query shape)
    class FakeResp:
        def __init__(self, payload):
            self.payload = payload

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def read(self):
            return json.dumps(self.payload).encode()

    with mock.patch.object(core.urllib.request, "urlopen",
                           return_value=FakeResp([{"path": "a/b.md", "heading": "(title)"}])):
        check("haystack list response parsed", core.haystack_top("q", "http://y") == ["a/b.md"])

    # haystack down still injects route
    with mock.patch.object(core, "classify_multi", return_value={"notes-routing": (True, 0.95, "yes", "d1-test")}), \
         mock.patch.object(core, "haystack_top",
                           side_effect=urllib.error.URLError("down")):
        text, conf, ms = core.choose("where is the VPN note", cfg)
    check("haystack-down still injects", text is not None and "notes-router" in text)

    # promotion lifecycle (v0.2)
    cfg2 = dict(cfg, promote_n=3)
    core.BEHAVIOR_FILE.write_text("")
    with mock.patch.object(core, "classify_multi", return_value={"notes-routing": (True, 0.95, "yes", "d1-t")}), \
         mock.patch.object(core, "haystack_top", return_value=[]):
        for _ in range(5):
            core.choose("where is the VPN note", cfg2)
    ev = [json.loads(l) for l in core.BEHAVIOR_FILE.read_text().splitlines()]
    check("no promote below age gate",
          not any(e["kind"] == "promote" for e in ev))
    rules_now = core.load_rules()
    check("rule still hint before age/consume gates",
          core.live_rules(rules_now)[0]["status"] == "hint")
    # simulate age + consumed history -> promote
    for i, e in enumerate(ev):
        if e["kind"] == "inject":
            cons = {"ts": e["ts"] + 10, "kind": "consumed",
                    "tool": "skill_view", "task": f"c{i}"}
            core.BEHAVIOR_FILE.open("a").write(json.dumps(cons) + "\n")
    with mock.patch.object(core, "classify_multi", return_value={"notes-routing": (True, 0.95, "yes", "d1-t")}), \
         mock.patch.object(core, "haystack_top", return_value=[]), \
         mock.patch.object(core, "PROMOTE_MIN_AGE_S", 0), \
         mock.patch.object(core, "PROMOTE_MIN_INJ", 3), \
         mock.patch.object(core, "PROMOTE_MIN_JUDGED", 0):
        core.RULES_FILE.parent.joinpath("behavior.jsonl").open("a").write(
            json.dumps({"ts": time.time(), "kind": "context_judge",
                        "rule": "notes-routing", "correct": True,
                        "conf": 0.9, "model": "d1-t", "mh": "x"}) + "\n")
        core.choose("where is the VPN note", cfg2)
    ev = [json.loads(l) for l in core.BEHAVIOR_FILE.read_text().splitlines()]
    check("promote event fired", any(e["kind"] == "promote" for e in ev))
    st = core.replay_rules()["notes-routing"]
    check("replay shows enforced", st["status"] == "enforced")
    with mock.patch.object(core, "haystack_top", return_value=[]):
        text, conf, ms = core.choose("where is the VPN note", cfg2)
    check("enforced rule bypasses classifier (0ms, no d1 call)",
          text is not None and ms == 0.0)
    ev = [json.loads(l) for l in core.BEHAVIOR_FILE.read_text().splitlines()]
    check("enforced_fire logged", any(e["kind"] == "enforced_fire" for e in ev))
    # retraction supersedes enforcement
    with open(core.RULES_FILE, "a") as f:
        f.write(json.dumps({"id": "notes-routing", "status": "retracted"}) + "\n")
    check("retraction kills enforced rule", not core.live_rules(core.load_rules()))
    check("replay after retraction is clean", 
          core.replay_rules()["notes-routing"]["status"] == "retracted")

    # deviation instrument
    core.RULES_FILE.unlink()
    core.init()
    core.PENDING_INJECT = None
    core.BEHAVIOR_FILE.write_text("")
    with mock.patch.object(core, "classify_multi", return_value={"notes-routing": (True, 0.95, "yes", "d1-t")}), \
         mock.patch.object(core, "haystack_top", return_value=[]):
        core.choose("where is the VPN note", cfg)
        check("pending inject open, no deviation yet",
              core.PENDING_INJECT is not None and not core.PENDING_INJECT["consumed"])
        core.choose("where is the VPN note", cfg)
    ev = [json.loads(l) for l in core.BEHAVIOR_FILE.read_text().splitlines()]
    check("unconsumed inject closed as deviation",
          sum(1 for e in ev if e["kind"] == "deviation") == 1)
    core.PENDING_INJECT = None
    core.BEHAVIOR_FILE.write_text("")
    with mock.patch.object(core, "classify_multi", return_value={"notes-routing": (True, 0.95, "yes", "d1-t")}), \
         mock.patch.object(core, "haystack_top", return_value=[]):
        core.choose("where is the VPN note", cfg)
        core.observe_tool("skill_view", 5.0, "t9")
        check("consumed marks pending", core.PENDING_INJECT["consumed"] is True)
        core.choose("where is the VPN note", cfg)
    ev = [json.loads(l) for l in core.BEHAVIOR_FILE.read_text().splitlines()]
    check("consumed inject not a deviation",
          not any(e["kind"] == "deviation" for e in ev),
          json.dumps([e["kind"] for e in ev]))

    # context judge (second semantic dimension)
    core.RULES_FILE.unlink()
    core.init()
    core.PENDING_INJECT = None
    core.BEHAVIOR_FILE.write_text("")
    with mock.patch.object(core, "classify_multi", return_value={"notes-routing": (True, 0.95, "yes", "d1-t")}), \
         mock.patch.object(core, "haystack_top", return_value=[]), \
         mock.patch.object(core, "judge_context", return_value=(True, 0.9, "d1-t")):
        core.choose("where is the VPN note", cfg)
        core.close_pending_inject(cfg)
    ev = [json.loads(l) for l in core.BEHAVIOR_FILE.read_text().splitlines()]
    check("context_judge logged with verdict",
          any(e["kind"] == "context_judge" and e.get("correct") is True for e in ev))
    check("raw message text never in log",
          not any("VPN note" in json.dumps(e) for e in ev))
    # wrong-context judge blocks promotion
    core.BEHAVIOR_FILE.write_text("")
    core.RULES_FILE.unlink()
    core.init()
    for _ in range(6):
        with mock.patch.object(core, "classify_multi", return_value={"notes-routing": (True, 0.95, "yes", "d1-t")}), \
             mock.patch.object(core, "haystack_top", return_value=[]), \
             mock.patch.object(core, "judge_context", return_value=(False, 0.9, "d1-t")), \
             mock.patch.object(core, "PROMOTE_MIN_AGE_S", 0):
            core.choose("where is the VPN note", cfg)
            core.observe_tool("skill_view", 5.0, "tk")
            core.close_pending_inject(cfg)
    ev = [json.loads(l) for l in core.BEHAVIOR_FILE.read_text().splitlines()]
    check("wrong-context judges logged",
          sum(1 for e in ev if e["kind"] == "context_judge") >= 5)
    check("wrong context blocks promotion",
          not any(e["kind"] == "promote" for e in ev)
          and core.live_rules(core.load_rules())[0]["status"] == "hint")
    # context-dedup: paths already in history are not re-injected
    core.RULES_FILE.unlink()
    core.init()
    core.BEHAVIOR_FILE.write_text("")
    core.PENDING_INJECT = None
    with mock.patch.object(core, "classify_multi", return_value={"notes-routing": (True, 0.95, "yes", "d1-t")}), \
         mock.patch.object(core, "haystack_top",
                           return_value=["a/dup.md", "a/fresh.md"]):
        text, conf, ms = core.choose("where is the VPN note", cfg,
                                     history="earlier context quoted a/dup.md here")
    check("dedup drops path already in history",
          "a/dup.md" not in (text or "") and "a/fresh.md" in (text or ""))
    ev = [json.loads(l) for l in core.BEHAVIOR_FILE.read_text().splitlines()]
    check("context_dedup logged",
          any(e["kind"] == "context_dedup" and e.get("dropped") == 1 for e in ev))

    # corrections ingest
    check("positive correction detected",
          core.note_correction("hey use notes-router for that") ==
          {"kind": "positive", "target": "notes-routing"})
    check("negative correction detected",
          (core.note_correction("wrong skill, stop that") or {}).get("kind") == "negative")
    check("plain question not a correction", core.note_correction("where is the VPN note") is None)
    n0 = core.rule_evidence("notes-routing")
    core.record_correction({"kind": "positive", "target": "notes-routing"})
    check("positive correction bumps evidence",
          core.rule_evidence("notes-routing") == n0 + 1)
    ev = [json.loads(l) for l in core.BEHAVIOR_FILE.read_text().splitlines()]
    check("correction logged",
          any(e.get("corr_kind") == "positive" for e in ev if e["kind"] == "correction"))

    # observe_tool + consumption
    core.LAST_INJECT_TS = 0.0
    core.observe_tool("skill_view", 12.3, "t1")
    core.observe_tool("terminal", 100.0, "t3", args={"command": "ls"})
    core.LAST_INJECT_TS = time.time()
    core.observe_tool("terminal", 50.0, "t2",
                      args={"command": "python3 ~/.hermes/scripts/haystack.py query x"})
    ev = [json.loads(l) for l in core.BEHAVIOR_FILE.read_text().splitlines()]
    by_task = {e["task"]: e for e in ev if e["kind"] == "tool"}
    check("tool log flags skill loads",
          by_task["t1"]["skill"] is True and by_task["t3"]["skill"] is False)
    check("no consumed outside inject window",
          not by_task["t1"].get("consumed") and not by_task["t3"].get("consumed"))
    check("haystack use within window consumed",
          any(e["kind"] == "consumed" for e in ev)
          and by_task["t2"].get("used") is True
          and by_task["t2"].get("consumed") is True)

    n_fail = sum(1 for _, ok, _ in results if not ok)
    test_dimensions()
    test_dream()
    test_task_direction()
    print(f"{len(results) - n_fail}/{len(results)} passed")
    sys.exit(1 if n_fail else 0)


if __name__ == "__main__":
    main()
