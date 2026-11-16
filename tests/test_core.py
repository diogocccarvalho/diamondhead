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
    with mock.patch.object(core, "classify", return_value=(False, 0.4)):
        text, conf, ms = core.choose("what did I do Friday", cfg)
    check("classifier-no returns None", text is None)

    # chooser: hit with haystack paths
    with mock.patch.object(core, "classify", return_value=(True, 0.95)), \
         mock.patch.object(core, "haystack_top", return_value=["notes/vpn.md"]):
        text, conf, ms = core.choose("where is the VPN note", cfg)
    check("hit returns injection", text is not None and "notes-router" in text)
    check("hit includes paths", "notes/vpn.md" in text)
    ev = [json.loads(l) for l in core.BEHAVIOR_FILE.read_text().splitlines()]
    check("inject logged with hash not raw",
          any(e["kind"] == "inject" for e in ev)
          and not any("VPN note" in json.dumps(e) for e in ev))

    # chooser: service down degrades to None
    with mock.patch.object(core, "classify",
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
    with mock.patch.object(core, "classify", return_value=(True, 0.95)), \
         mock.patch.object(core, "haystack_top",
                           side_effect=urllib.error.URLError("down")):
        text, conf, ms = core.choose("where is the VPN note", cfg)
    check("haystack-down still injects", text is not None and "notes-router" in text)

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
    core.observe_tool("terminal", 100.0, "t1", args={"command": "ls"})
    core.LAST_INJECT_TS = time.time()
    core.observe_tool("terminal", 50.0, "t2",
                      args={"command": "python3 ~/.hermes/scripts/haystack.py query x"})
    ev = [json.loads(l) for l in core.BEHAVIOR_FILE.read_text().splitlines()]
    tools = [e for e in ev if e["kind"] == "tool"]
    check("tool log flags skill loads", tools[0]["skill"] is True and tools[1]["skill"] is False)
    check("no consumed outside inject window", not any(e["kind"] == "consumed" for e in ev[:2]))
    check("haystack use within window consumed",
          any(e["kind"] == "consumed" for e in ev)
          and any(e.get("used") for e in tools))

    n_fail = sum(1 for _, ok, _ in results if not ok)
    print(f"{len(results) - n_fail}/{len(results)} passed")
    sys.exit(1 if n_fail else 0)


if __name__ == "__main__":
    main()
