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


def reset_all():
    """Hermetic start: wipe shared globals + BOTH files + reseed store."""
    core.BEHAVIOR_FILE.write_text("")
    if core.RULES_FILE.exists():
        core.RULES_FILE.unlink()
    core.init()
    core.PENDING_INJECT = None
    core.LAST_INJECT_TS = 0.0
    core.SESSION_PATHS.clear()
    core.TASK_SEQ.clear()
    core.TASK_DIRECTIONS.clear()
    core.SYNC_JUDGE = True


def test_dream():
    sys.path.insert(0, str(Path(core.__file__).parent.parent / "scripts"))
    import dream  # noqa: F401
    core.SYNC_JUDGE = True
    if core.RULES_FILE.exists():
        core.RULES_FILE.unlink()
    core.init()
    dream.LEDGER.parent.mkdir(parents=True, exist_ok=True)
    dream.LEDGER.write_text("")
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

    # supersession: same session re-providing context x -> dropped, logged
    core.BEHAVIOR_FILE.write_text("")
    core.PENDING_INJECT = None
    core.SESSION_PATHS.clear()
    with mock.patch.object(core, "classify_multi", return_value={
            "notes-routing": (True, 0.95, "yes", "d1-t")}), \
         mock.patch.object(core, "haystack_top",
                           return_value=["a/vpn.md", "a/new.md"]):
        core.choose("where is the vpn note again", cfg, session_id="s1")
        core.choose("where is the vpn note again", cfg, session_id="s1")
    ev = core.behavior_events()
    inj = [e for e in ev if e["kind"] == "inject"]
    check("second injection drops already-provided paths",
          len(inj) == 2 and inj[0]["paths"] == ["a/vpn.md", "a/new.md"]
          and inj[1]["paths"] == [])
    check("superseded event logs the redundant paths",
          any(e["kind"] == "superseded" and e["dropped"] == 2
              and e["paths"] == ["a/vpn.md", "a/new.md"] for e in ev))
    core.SESSION_PATHS.clear()


    # sequence fidelity: genome followed in order -> sequence_match logged
    reset_all()
    core.append_rule({"id": "auto-d0b974f8", "family": "code-change loop",
                      "status": "candidate", "ts": core.time.time()})
    core.BEHAVIOR_FILE.write_text("")
    core.PENDING_INJECT = None
    core.SESSION_PATHS.clear()
    core.TASK_SEQ.clear()
    core.LAST_INJECT_TS = 0.0
    with mock.patch.object(core, "classify_multi", return_value={
            "notes-routing": (False, 0.4, "no", "d1-t"),
            "auto-d0b974f8": (True, 0.90, "yes", "d1-t")}), \
         mock.patch.object(core, "haystack_top", return_value=[]):
        core.choose("refactor the router module", cfg, session_id="s2")
        core.observe_tool("patch", 5.0, "task-x")
        core.observe_tool("terminal", 5.0, "task-x")
    ev = core.behavior_events()
    check("sequence_match logged when genome followed in order",
          any(e["kind"] == "sequence_match" and e["rule"] == "auto-d0b974f8"
              and e["genome"] == ["patch", "terminal"] for e in ev))

    # out-of-order tools -> no match
    core.BEHAVIOR_FILE.write_text("")
    core.PENDING_INJECT = None
    core.TASK_SEQ.clear()
    with mock.patch.object(core, "classify_multi", return_value={
            "notes-routing": (False, 0.4, "no", "d1-t"),
            "auto-d0b974f8": (True, 0.90, "yes", "d1-t")}), \
         mock.patch.object(core, "haystack_top", return_value=[]):
        core.choose("refactor the router module", cfg, session_id="s3")
        core.observe_tool("terminal", 5.0, "task-y")
    ev = core.behavior_events()
    check("no sequence_match before the genome order completes",
          not any(e["kind"] == "sequence_match" for e in ev))
    core.TASK_SEQ.clear()

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



def test_contracts():
    core.init()
    reset_all()
    check("contract sha changes when operative fields change",
          core.contract_sha({"inject": "a"}) != core.contract_sha({"inject": "b"})
          and core.contract_sha({"inject": "a", "genome": ["x"]})
          != core.contract_sha({"inject": "a", "genome": ["y"]}))

    # bump -> rollback -> replay restores previous fields
    reset_all()
    n = core.bump_version("notes-routing", {"inject": "v1 template",
                                            "genome": ["patch", "terminal"]})
    core.bump_version("notes-routing", {"inject": "v2 template",
                                        "genome": ["patch", "terminal"]})
    check("version counter advances", n == 2)
    core.rollback_version("notes-routing")
    st = core.replay_rules()["notes-routing"]
    check("rollback restores previous version fields in replay",
          st.get("inject") == "v1 template" and st.get("version") == 1)

    # audit flags unversioned operative change
    core.append_rule({"id": "notes-routing", "status": "hint",
                      "inject": "sneaky unversioned change", "ts": core.time.time()})
    problems = core.audit_contracts()
    check("audit flags unversioned field change",
          any(p["id"] == "notes-routing" for p in problems))


def test_sequential_gate():
    core.init()
    reset_all()
    cfg = {"d1_url": "http://x", "haystack_url": "http://y",
           "min_confidence": 0.80, "promote_n": 20}
    # burn-in: no verdict below 8 uses
    check("no verdict before burn-in",
          core.sequential_verdict("notes-routing", cfg)[0] is None)
    # 8 all-success injections + judge-correct -> promote
    for i in range(8):
        core.log_event("inject", rule="notes-routing", conf=0.9,
                       mh="mh%d" % i)
        core.log_event("consumed", tool="haystack_top", mh="mh%d" % i)
        core.log_event("context_judge", rule="notes-routing", correct=True,
                       conf=0.9, mh="mh%d" % i)
    v, llr, n = core.sequential_verdict("notes-routing", cfg)
    check("8 clean uses promote", v == "promote" and n == 8)
    # futility: failures drive demote fast
    reset_all()
    for i in range(8):
        core.log_event("inject", rule="notes-routing", conf=0.9,
                       mh="f%d" % i)
    v, llr, n = core.sequential_verdict("notes-routing", cfg)
    check("8 unconsumed injections demote", v == "demote" and n == 8)
    # enforce_if_ready wires the verdict to the store
    reset_all()
    core.append_rule({"id": "auto-d0b974f8", "family": "code-change loop",
                      "status": "hint", "ts": core.time.time()})
    for i in range(8):
        core.log_event("inject", rule="auto-d0b974f8", conf=0.9,
                       mh="p%d" % i)
        core.log_event("consumed", tool="patch", mh="p%d" % i)
        core.log_event("context_judge", rule="auto-d0b974f8", correct=True,
                       conf=0.9, mh="p%d" % i)
    ok = core.enforce_if_ready("auto-d0b974f8", 20, cfg)
    st = core.replay_rules()["auto-d0b974f8"]
    check("per-use promotion binds enforced + version",
          ok and st.get("status") == "enforced" and st.get("contract_sha"))


CHAMPION = [["while_chunk", k] for k in (512, 256, 128, 64, 32, 16, 8, 4, 2, 1)]


def test_proof_station():
    reset_all()
    rid = "add-champion"
    core.append_rule({"id": rid, "status": "candidate", "family": "addition",
                      "genome": CHAMPION, "ts": core.time.time()})
    ok, detail = core.proof_graduate(rid, "naive_add", b_max=255)
    check("proof graduation passes on champion genome",
          ok and detail["n_cases"] == 256,
          str(detail) if not ok else "")
    st = core.replay_rules()[rid]
    check("proven record lands in replay state", st.get("status") == "proven")
    live = [r for r in core.live_rules(core.load_rules())
            if r.get("id") == rid][0]
    check("live path agrees with replay on proven status",
          live.get("status") == "proven")

    # proven rule fires O(1), proof-tagged
    reset_all()
    core.append_rule({"id": rid, "status": "proven", "family": "addition",
                      "genome": CHAMPION, "ts": core.time.time()})
    cfg = {"d1_url": "http://127.0.0.1:8080/v1/systemone",
           "haystack_url": "http://127.0.0.1:8083/query",
           "min_confidence": 0.8, "inject_enabled": True, "promote_n": 20}
    out = core.choose("notes question about haystack please", cfg)
    ev = [e for e in core.behavior_events() if e.get("kind") == "enforced_fire"]
    check("proven crystal fires O(1) with proof tag",
          out[0] is not None and ev and ev[-1].get("proof") is True)

    # broken genome fails replay
    reset_all()
    core.append_rule({"id": "add-broken", "status": "candidate",
                      "genome": CHAMPION[:-1], "ts": core.time.time()})
    ok, detail = core.proof_graduate("add-broken", "naive_add", b_max=16)
    check("replay mismatch blocks graduation",
          not ok and "mismatch" in detail["reason"])

    # oracle-reference genome fails provenance audit
    reset_all()
    core.append_rule({"id": "add-cheat", "status": "candidate",
                      "genome": CHAMPION + [["naive_add", 1]],
                      "ts": core.time.time()})
    ok, detail = core.proof_graduate("add-cheat", "naive_add", b_max=8)
    check("provenance audit blocks oracle-referencing genome",
          not ok and "audit" in detail["reason"])

    # vacuous oracle (constant truth) is refused before any verdict
    reset_all()
    core.ORACLES["const_add"] = {"fn": core._oracle_naive_add,
                                 "expected": lambda a, b: 0,
                                 "domain": lambda: ((0, b) for b in range(3)),
                                 "probe": [(0, -1)],
                                 "domain_text": "a=0, b in [0,2]"}
    core.append_rule({"id": "add-const", "status": "candidate",
                      "genome": CHAMPION, "ts": core.time.time()})
    ok, detail = core.proof_graduate("add-const", "const_add")
    check("vacuous oracle refused", not ok and "vacuous" in detail["reason"])
    del core.ORACLES["const_add"]

    # off-domain crash probe blocks graduation
    reset_all()
    core.append_rule({"id": "add-crash", "status": "candidate",
                      "genome": CHAMPION + [["badop", 1]],
                      "ts": core.time.time()})
    ok, detail = core.proof_graduate("add-crash", "naive_add", b_max=4)
    check("off-domain crash blocks graduation",
          not ok and "crash" in detail["reason"])

    # unknown oracle refused
    ok, detail = core.proof_graduate("add-champion", "nonexistent_oracle")
    check("unknown oracle refused", not ok)



def main():
    core.SYNC_JUDGE = True
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
    # clean per-use outcomes -> sequential gate promotes (no age gate)
    inj = [e for e in ev if e["kind"] == "inject"]
    for i, e in enumerate(inj):
        core.BEHAVIOR_FILE.open("a").write(json.dumps(
            {"ts": e["ts"] + 10, "kind": "consumed",
             "tool": "skill_view", "task": f"c{i}", "mh": e["mh"]}) + "\n")
        core.BEHAVIOR_FILE.open("a").write(json.dumps(
            {"ts": e["ts"] + 11, "kind": "context_judge",
             "rule": "notes-routing", "correct": True, "conf": 0.9,
             "model": "d1-t", "mh": e["mh"]}) + "\n")
    while len(core.injection_outcomes("notes-routing", cfg2)) < 8:
        with mock.patch.object(core, "classify_multi", return_value={"notes-routing": (True, 0.95, "yes", "d1-t")}), \
             mock.patch.object(core, "haystack_top", return_value=[]):
            core.choose("where is the VPN note", cfg2)
        ev2 = [json.loads(l) for l in core.BEHAVIOR_FILE.read_text().splitlines()]
        last = [e for e in ev2 if e["kind"] == "inject"][-1]
        n_inj = len(core.injection_outcomes("notes-routing", cfg2))
        core.BEHAVIOR_FILE.open("a").write(json.dumps(
            {"ts": last["ts"] + 10, "kind": "consumed",
             "tool": "skill_view", "task": "c", "mh": last["mh"]}) + "\n")
        core.BEHAVIOR_FILE.open("a").write(json.dumps(
            {"ts": last["ts"] + 11, "kind": "context_judge",
             "rule": "notes-routing", "correct": True, "conf": 0.9,
             "model": "d1-t", "mh": last["mh"]}) + "\n")
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
    reset_all()
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
    test_contracts()
    test_sequential_gate()
    test_proof_station()


    # golden replay: what works today must not silently change
    import subprocess
    g = subprocess.run([sys.executable, str(Path(__file__).parent /
                                            "make_golden.py")],
                       capture_output=True, text=True, timeout=60)
    check("golden behavior replay matches blessed fixture",
          "MATCH" in g.stdout, g.stdout[-200:] + g.stderr[-200:])

    print(f"{len(results) - n_fail}/{len(results)} passed")
    sys.exit(1 if n_fail else 0)


if __name__ == "__main__":
    main()
