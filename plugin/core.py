import hashlib
import json
import re
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from plugins.plugin_storage import plugin_data_dir

DATA = plugin_data_dir("diamondhead")
RULES_FILE = DATA / "rules.jsonl"
BEHAVIOR_FILE = DATA / "behavior.jsonl"

D1_TIMEOUT = 8
HAYSTACK_TIMEOUT = 8
INJECT_TEMPLATE = (
    "[diamondhead route] Load skill notes-router now and answer via it. "
    "Route: project/id question -> `python3 ~/.hermes/scripts/projects.py find <words>`; "
    "anything else -> `python3 ~/.hermes/scripts/haystack.py query <text> -k 5`. "
    "Read the winning note in full before answering."
)


def init():
    if not RULES_FILE.exists():
        seed = {
            "id": "notes-routing",
            "family": "notes/vault question",
            "action": "load notes-router skill + haystack route",
            "status": "hint",
            "evidence_n": 0,
            "source": "user-taught",
            "ts": time.time(),
        }
        RULES_FILE.write_text(json.dumps(seed) + "\n")
    return RULES_FILE


def load_rules():
    rules = []
    if RULES_FILE.exists():
        for line in RULES_FILE.read_text().splitlines():
            if line.strip():
                try:
                    rules.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return rules


def live_rules(rules):
    dead, out = set(), []
    for r in rules:
        rid = r.get("id")
        if not rid or r.get("status") == "retracted":
            if rid:
                dead.add(rid)
                out = [x for x in out if x.get("id") != rid]
            continue
        if rid in dead:
            continue
        cur = next((x for x in out if x.get("id") == rid), None)
        if cur is None:
            out.append(dict(r))
        elif r.get("status") == "enforced":
            cur["status"] = "enforced"
    return out


PROMOTE_MIN_CONSUMED = 0.8
PROMOTE_MIN_AGE_S = 7 * 86400
PROMOTE_MIN_INJ = 5
PROMOTE_MIN_JUDGED = 5


def rule_first_seen(rule_id):
    if RULES_FILE.exists():
        ts_vals = []
        for line in RULES_FILE.read_text().splitlines():
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if r.get("id") == rule_id and isinstance(r.get("ts"), (int, float)) \
                    and r["ts"] > 0:
                ts_vals.append(r["ts"])
        if ts_vals:
            return min(ts_vals)
    return None


def consumed_ratio(rule_id):
    inj = [e for e in behavior_events() if e.get("kind") == "inject"
           and e.get("rule") == rule_id]
    if not inj:
        return 0.0, 0
    inj_ts = {e["ts"] for e in inj}
    cons = [e for e in behavior_events() if e.get("kind") == "consumed"
            and any(0 <= e["ts"] - t <= CONSUME_WINDOW_S for t in inj_ts)]
    return len(cons) / len(inj), len(inj)


def behavior_events():
    try:
        return [json.loads(l) for l in BEHAVIOR_FILE.read_text().splitlines()
                if l.strip()]
    except OSError:
        return []


def judge_ratio(rule_id):
    judged = [e for e in behavior_events() if e.get("kind") == "context_judge"
              and e.get("rule") == rule_id]
    if len(judged) < max(PROMOTE_MIN_JUDGED, 1):
        return None, len(judged)
    return sum(1 for e in judged if e.get("correct")) / len(judged), len(judged)


def enforce_if_ready(rule_id, promote_n):
    n = rule_evidence(rule_id)
    ratio, inj = consumed_ratio(rule_id)
    jr, nj = judge_ratio(rule_id)
    if jr is None:
        return False
    first = rule_first_seen(rule_id)
    if first is None:
        return False
    age = time.time() - first
    if n >= promote_n and inj >= PROMOTE_MIN_INJ and ratio >= PROMOTE_MIN_CONSUMED \
            and jr >= PROMOTE_MIN_CONSUMED and age >= PROMOTE_MIN_AGE_S:
        append_rule({"id": rule_id, "status": "enforced", "ts": time.time(),
                     "evidence_n": n, "consumed_ratio": round(ratio, 3),
                     "injections": inj})
        log_event("promote", rule=rule_id, evidence_n=n,
                  consumed_ratio=round(ratio, 3), injections=inj)
        return True
    return False


def append_rule(rec):
    with open(RULES_FILE, "a") as f:
        f.write(json.dumps(rec) + "\n")


# contract versioning: a crystal's operative fields hash into contract_sha;
# changes require a version record; rollback restores the previous snapshot
CONTRACT_FIELDS = ("trigger", "inject", "hint_words", "yes_label",
                   "min_conf", "genome")


def contract_sha(rule):
    blob = json.dumps({k: rule.get(k) for k in CONTRACT_FIELDS},
                      sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()[:12]


def bump_version(rule_id, fields):
    """Append a new contract version (fields = full operative snapshot)."""
    n = max((r.get("version", 0) for r in load_rules()
             if r.get("id") == rule_id and r.get("version")), default=0) + 1
    rec = {"id": rule_id, "status": "version", "version": n,
           "contract_sha": contract_sha(fields), "ts": time.time()}
    rec.update({k: fields.get(k) for k in CONTRACT_FIELDS})
    append_rule(rec)
    log_event("contract_version", rule=rule_id, version=n,
              contract_sha=rec["contract_sha"])
    return n


def rollback_version(rule_id, to_version=None):
    """Append-only rollback: restore the given (or previous) version's
    fields as a NEW record. Replay stays lossless - rollbacks are history."""
    recs = [r for r in load_rules() if r.get("id") == rule_id
            and r.get("status") == "version"]
    if not recs:
        return None
    recs.sort(key=lambda r: r["version"])
    if to_version is None:
        to_version = max(r["version"] for r in recs) - 1
    snap = next((r for r in recs if r["version"] == to_version), None)
    if snap is None:
        return None
    rec = {"id": rule_id, "status": "rollback", "to_version": to_version,
           "contract_sha": snap["contract_sha"], "ts": time.time()}
    rec.update({k: snap.get(k) for k in CONTRACT_FIELDS})
    append_rule(rec)
    log_event("contract_rollback", rule=rule_id, to_version=to_version)
    return rec


def replay_rules():
    state = {}
    versions = {}
    for line in RULES_FILE.read_text().splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        rid = r.get("id")
        if not rid:
            continue
        if r.get("status") == "evidence":
            st = state.setdefault(rid, {"evidence_n": 0, "status": "hint"})
            st["evidence_n"] += r.get("n", 1)
        elif r.get("status") == "retracted":
            state[rid] = {"status": "retracted", "evidence_n": 0}
        elif r.get("status") == "version":
            versions[rid] = dict(r)
            cur = state.setdefault(rid, {"evidence_n": 0})
            cur.update({k: r.get(k) for k in CONTRACT_FIELDS})
            cur["contract_sha"] = r.get("contract_sha")
            cur["version"] = r.get("version")
        elif r.get("status") == "rollback":
            cur = state.setdefault(rid, {"evidence_n": 0})
            cur.update({k: r.get(k) for k in CONTRACT_FIELDS})
            cur["contract_sha"] = r.get("contract_sha")
            cur["version"] = r.get("to_version")
        else:
            cur = state.setdefault(rid, {"evidence_n": 0})
            cur["status"] = r.get("status", cur.get("status", "hint"))
    return state


def audit_contracts():
    """Provenance pass for the store: flag rules whose operative fields
    changed without a version/rollback record carrying the new sha."""
    problems = []
    live = {}
    for line in RULES_FILE.read_text().splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        rid = r.get("id")
        if not rid or r.get("status") in ("evidence", "promote"):
            continue
        if r.get("status") in ("version", "rollback"):
            live[rid] = {k: r.get(k) for k in CONTRACT_FIELDS}
        elif r.get("status") not in ("retracted",):
            merged = dict(live.get(rid, {}))
            merged.update({k: r[k] for k in CONTRACT_FIELDS if k in r})
            if merged != live.get(rid) and rid in live:
                problems.append({"id": rid, "kind": r.get("status"),
                                 "unversioned_field_change": True})
            live[rid] = merged
    return problems


def bump_evidence(rule_id, n=1):
    rec = {"id": rule_id, "status": "evidence", "n": n, "ts": time.time()}
    with open(RULES_FILE, "a") as f:
        f.write(json.dumps(rec) + "\n")


def rule_evidence(rule_id):
    n = 0
    if RULES_FILE.exists():
        for line in RULES_FILE.read_text().splitlines():
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if r.get("id") == rule_id and r.get("status") == "evidence":
                n += r.get("n", 1)
            if r.get("id") == rule_id and r.get("status") == "retracted":
                n = 0
    return n


SKIP_RE = re.compile(r"^\s*/|^(!|hi|hey|ok|thanks|yes|no)\b[^?]{0,12}$", re.I)
MIN_LEN = 12


CORRECTION_POS = re.compile(
    r"\b(use|load|check|try|consult)\s+(the\s+)?(notes[-\s]?router|haystack)\b", re.I)
CORRECTION_NEG = re.compile(
    r"\b(wrong|incorrect|bad|don'?t|stop|no,)\b.{0,40}?\b(skill|route|routing|rule|that)\b", re.I)
CORRECTION_FAMILY = "notes-routing"


def note_correction(text):
    if CORRECTION_POS.search(text):
        return {"kind": "positive", "target": CORRECTION_FAMILY}
    if CORRECTION_NEG.search(text):
        return {"kind": "negative", "target": None}
    return None


def record_correction(corr, mh=""):
    log_event("correction", corr_kind=corr["kind"], target=corr["target"], mh=mh)
    if corr["kind"] == "positive" and corr["target"]:
        bump_evidence(corr["target"])


def plausibly_notes(text):
    t = text.strip()
    return len(t) >= MIN_LEN and not SKIP_RE.match(t)


def classify(text, url, min_conf):
    body = {
        "state": "diamondhead routing",
        "questions": {
            "q": {
                "instructions": (
                    "Is this message a question about the user's personal notes, "
                    "vault, past sessions, projects, or stored information "
                    "(something answered by searching their notes)? A question "
                    "naming one of the user's projects, tools or repos by name "
                    "(e.g. diamondhead, haystack, notes-router) counts as yes. "
                    "Text: " + text[:400]
                ),
                "type": "choice",
                "criteria": {
                    "yes": "notes/vault question",
                    "no": "not a notes question",
                },
            }
        },
    }
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=D1_TIMEOUT) as r:
        payload = json.loads(r.read())
    ans = payload["answers"]["q"]
    choice = str(ans.get("choice", "")).strip().lower()
    conf = float(ans.get("confidence", 0.0))
    model = payload.get("model") or ans.get("model") or ""
    return choice == "yes" and conf >= min_conf, conf, model


# per-family crystal spec: the d1 trigger question, the injected procedure,
# the O(1) hint pre-gate words and whether the crystal carries haystack content
CRYSTAL_SPECS = {
    "notes/vault question": {
        "trigger": (
            "Is this message a question about the user's personal notes, "
            "vault, past sessions, projects, or stored information "
            "(something answered by searching their notes)? A question "
            "naming one of the user's projects, tools or repos by name "
            "(e.g. diamondhead, haystack, notes-router) counts as yes."),
        "inject": INJECT_TEMPLATE,
        "hint_words": [],
        "compass_words": ["note", "notes", "vault", "haystack", "schedule",
                          "backlog", "research", "project"],
        "content": True,
    },
    "code-change loop": {
        "trigger": (
            "Is this message about editing, fixing, debugging or refactoring "
            "the user's own code, so the agent should follow an edit-then-"
            "test-then-commit loop?"),
        "inject": (
            "[diamondhead route] Code-change loop crystal: make the edit, "
            "then run the test suite, then the loader gate, then commit. "
            "One loop, in that order, every time."),
        "hint_words": ["commit", "refactor", "test suite", "check.sh", "bug"],
        "genome": ["patch", "terminal"],
        "content": False,
    },
    "research loop": {
        "trigger": (
            "Is this message a request to search the internet for "
            "information or news (rather than searching the user's own "
            "notes)?"),
        "inject": (
            "[diamondhead route] Research-loop crystal: batch parallel web "
            "searches first, then extract the promising pages with "
            "web_extract. Do not search one at a time."),
        "hint_words": ["research", "search", "find out", "look up", "compare", "news"],
        "yes_label": "needs web research",
        "min_conf": 0.55,
        "genome": ["web_search", "web_extract"],
        "content": False,
    },
}


def rule_fields(rule):
    spec = CRYSTAL_SPECS.get(rule.get("family"), {})
    out = dict(rule)
    for k in ("trigger", "inject", "hint_words", "compass_words", "content",
              "genome"):
        out.setdefault(k, spec.get(k, [] if k in ("hint_words", "compass_words")
                                   else ("" if k != "content" else False)))
    return out


def task_families(session_id, rules):
    """Which crystal families serve the session's task direction: the task
    steers DiamondHead's own machinery (dream priority, arbitration notes),
    not just the LLM call."""
    d = TASK_DIRECTIONS.get(session_id)
    if not d:
        return set()
    t = d["text"].lower()
    fams = set()
    for r in rules:
        words = r.get("compass_words") or r.get("hint_words") or []
        if any(w in t for w in words):
            fams.add(r.get("family"))
    return {f for f in fams if f}


def _classify_one(text, rule, url, min_conf):
    min_conf = rule.get("min_conf") or min_conf
    body = {
        "state": "diamondhead routing",
        "questions": {"q": {
            "instructions": rule["trigger"] + " Text: " + text[:400],
            "type": "choice",
            "criteria": {"yes": rule.get("yes_label") or rule.get("family", "match"),
                         "no": "not this"},
        }},
    }
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=D1_TIMEOUT) as r:
        payload = json.loads(r.read())
    ans = payload["answers"]["q"]
    choice = str(ans.get("choice", "")).strip().lower()
    conf = float(ans.get("confidence", 0.0))
    model = payload.get("model") or ans.get("model") or ""
    return choice == "yes" and conf >= min_conf, conf, choice, model


def classify_multi(text, rules, url, min_conf):
    # one single-question call per crystal, concurrent: multi-question calls
    # measured uncalibrated (yes-conf collapses); parallel keeps latency flat
    out = {}
    with ThreadPoolExecutor(max_workers=len(rules)) as ex:
        futs = {r["id"]: ex.submit(_classify_one, text, r, url, min_conf)
                for r in rules}
        for rid, fut in futs.items():
            out[rid] = fut.result()
    return out


def haystack_top(text, url, k=3):
    body = {"q": text[:300], "k": k}
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=HAYSTACK_TIMEOUT) as r:
        d = json.loads(r.read())
    rows = d if isinstance(d, list) else (d.get("results") or d.get("chunks") or [])
    out = []
    for row in rows[:k]:
        p = row.get("path", "")
        h = row.get("heading", "")
        out.append(f"{p}#{h}" if h and h != "(title)" else p)
    return out


LAST_INJECT_TS = 0.0
CONSUME_WINDOW_S = 300.0
PENDING_INJECT = None

# crystal supersession: paths any crystal already provided this session.
# A crystal re-providing context x is redundant - x is not needed again.
SESSION_PATHS = {}
# sequence fidelity: tools observed per task since its last injection
TASK_SEQ = {}

# task direction: the distilled main task kept in memory as a semantic
# compass. Raw text is MEMORY-ONLY (privacy law); the log keeps hashes.
TASK_DIRECTIONS = {}
DIRECTION_MIN_LEN = 30
# works WITH the reasoning chain, not in front of it: checkpoints the
# model's own thinking walks through, not commands it must obey
DIRECTION_INJECT = (
    "[reasoning scaffold] As you reason, carry these checkpoints: "
    "(1) split the main task into parts that don't depend on each other "
    "and run those in parallel; (2) at each decision, name which part it "
    "serves; (3) if a step stops serving the main task, drop it; "
    "(4) before finishing, re-check every part was done, not just attempted.")


def set_task_direction(session_id, text):
    t = " ".join(text.split())[:300]
    TASK_DIRECTIONS[session_id] = {"text": t, "ts": time.time(),
                                   "mh": mhash(text)}
    log_event("direction_set", session=session_id[-8:], chars=len(t),
              mh=mhash(text))
    return t


def task_direction_inject(session_id):
    d = TASK_DIRECTIONS.get(session_id)
    if not d:
        return None
    log_event("direction_inject", session=session_id[-8:], mh=d["mh"])
    return f"Main task: {d['text']}\n{DIRECTION_INJECT}"


def judge_context(text, url):
    """Second semantic dimension: was the crystal's trigger context correct?"""
    body = {
        "state": "diamondhead context judge",
        "questions": {"q": {
            "instructions": (
                "The assistant answered this user message by loading its "
                "personal-notes search skill and searching the user's notes. "
                "Was that the correct response to the message? "
                "Text: " + text[:400]),
            "type": "choice",
            "criteria": {"yes": "correct context", "no": "wrong context"},
        }},
    }
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=D1_TIMEOUT) as r:
        payload = json.loads(r.read())
    ans = payload["answers"]["q"]
    return (ans.get("choice") == "yes",
            float(ans.get("confidence", 0.0)),
            (payload.get("model") or ""))


def close_pending_inject(cfg=None):
    global PENDING_INJECT
    if not PENDING_INJECT:
        return
    if not PENDING_INJECT.get("consumed"):
        log_event("deviation", rule=PENDING_INJECT["rule"],
                  enforced=PENDING_INJECT.get("enforced", False),
                  waited_s=round(time.time() - PENDING_INJECT["ts"]),
                  mh=PENDING_INJECT["mh"])
    text = PENDING_INJECT.get("text")
    pend = dict(PENDING_INJECT)
    PENDING_INJECT = None
    if text and cfg:
        # judge OFF the turn's critical path: runs concurrently with the turn
        def _judge():
            try:
                correct, conf, model = judge_context(text, cfg["d1_url"])
                log_event("context_judge", rule=pend["rule"],
                          correct=correct, conf=round(conf, 3),
                          model=model[:60], mh=pend["mh"])
            except (urllib.error.URLError, TimeoutError, OSError,
                    KeyError, ValueError):
                log_event("context_judge_error", rule=pend["rule"],
                          mh=pend["mh"])
        threading.Thread(target=_judge, daemon=True).start()


def open_pending_inject(rule_id, mh, enforced, text=""):
    global PENDING_INJECT
    close_pending_inject()
    PENDING_INJECT = {"ts": time.time(), "rule": rule_id, "mh": mh,
                      "enforced": enforced, "consumed": False,
                      "text": text}


def log_event(kind, **fields):
    rec = {"ts": time.time(), "kind": kind, **fields}
    try:
        with open(BEHAVIOR_FILE, "a") as f:
            f.write(json.dumps(rec) + "\n")
    except OSError:
        pass


def mhash(text):
    return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()[:12]


def choose(user_message, cfg, history="", session_id=""):
    rules = live_rules(load_rules())
    if not rules or not plausibly_notes(user_message):
        return None, 0.0, 0.0
    rules = [rule_fields(r) for r in rules]
    task_fams = task_families(session_id, rules)
    cand, skipped = [], []
    for r in rules:
        words = r.get("hint_words") or []
        if words and not any(w in user_message.lower() for w in words):
            skipped.append(r["id"])
        else:
            cand.append(r)
    if skipped:
        log_event("chooser_skip", rules=skipped, mh=mhash(user_message))
    if not cand:
        return None, 0.0, 0.0
    enforced = [r for r in cand if r.get("status") == "enforced"]
    if enforced:
        rule = enforced[0]
        log_event("enforced_fire", rule=rule["id"], mh=mhash(user_message))
        return inject_for(rule, user_message, cfg, conf=1.0, dt=0.0,
                          history=history)
    t0 = time.monotonic()
    try:
        results = classify_multi(user_message, cand, cfg["d1_url"],
                                 cfg["min_confidence"])
    except (urllib.error.URLError, TimeoutError, OSError, KeyError, ValueError) as e:
        log_event("chooser_error", err=str(e)[:120], mh=mhash(user_message))
        return None, 0.0, (time.monotonic() - t0) * 1000
    dt = (time.monotonic() - t0) * 1000
    hits = [(r, results[r["id"]]) for r in cand if results[r["id"]][0]]
    for r in cand:
        _hit, _conf, _choice, _model = results[r["id"]]
        if _choice == "yes" and not results[r["id"]][0]:
            log_event("near_miss", rule=r["id"], conf=round(_conf, 3),
                      gate=r.get("min_conf") or cfg["min_confidence"],
                      mh=mhash(user_message))
    if not hits:
        log_event("chooser_no",
                  confs={r["id"]: round(results[r["id"]][1], 3) for r in cand},
                  choices={r["id"]: results[r["id"]][2] for r in cand},
                  ms=round(dt), mh=mhash(user_message))
        return None, 0.0, dt
    rule, (hit, conf, choice, model) = max(hits, key=lambda x: x[1][1])
    if len(hits) > 1:
        loser = max((h for h in hits if h[0]["id"] != rule["id"]),
                    key=lambda x: x[1][1])
        log_event("contention", winner=rule["id"], runner_up=loser[0]["id"],
                  confs={h[0]["id"]: round(h[1][1], 3) for h in hits},
                  task_winner=rule.get("family") in task_fams,
                  task_fams=sorted(task_fams), mh=mhash(user_message))
    return inject_for(rule, user_message, cfg, conf, dt, history=history,
                      session_id=session_id)


def inject_for(rule, user_message, cfg, conf, dt, history="", session_id=""):
    paths = []
    if rule.get("content"):
        try:
            paths = haystack_top(user_message, cfg["haystack_url"])
        except (urllib.error.URLError, TimeoutError, OSError, KeyError, ValueError) as e:
            log_event("haystack_error", err=str(e)[:120], mh=mhash(user_message))
        paths = [str(p) for p in paths]
        # context-dedup vs conversation history: already-present x is redundant
        fresh = [p for p in paths if p and p not in history]
        deduped = len(paths) - len(fresh)
        if deduped:
            log_event("context_dedup", rule=rule["id"], dropped=deduped,
                      kept=len(fresh), mh=mhash(user_message))
        # crystal supersession vs this session's prior injections: context x
        # provided once is not needed again (the crystal replaces the context)
        seen = SESSION_PATHS.setdefault(session_id, set())
        ss = [p for p in fresh if p in seen]
        fresh = [p for p in fresh if p not in seen]
        if ss:
            log_event("superseded", rule=rule["id"], dropped=len(ss),
                      paths=ss, mh=mhash(user_message))
        seen.update(fresh)
        paths = fresh
    bump_evidence(rule["id"])
    global LAST_INJECT_TS
    LAST_INJECT_TS = time.time()
    template = rule.get("inject") or INJECT_TEMPLATE
    log_event("inject", rule=rule["id"], conf=round(conf, 3),
              ms=round(dt), chars=len(template) + sum(len(p) for p in paths),
              paths=paths, mh=mhash(user_message))
    open_pending_inject(rule["id"], mhash(user_message),
                        rule.get("status") == "enforced", user_message)
    if rule.get("genome") and rule.get("status") in ("hint", "candidate"):
        PENDING_INJECT["genome"] = list(rule["genome"])
        PENDING_INJECT["task"] = None  # task id arrives with the first tool
    if rule.get("status") in ("hint", "candidate"):
        enforce_if_ready(rule["id"], cfg.get("promote_n", 20))
    text = template
    if paths:
        text += "\nTop matching notes:\n" + "\n".join(f"- {p}" for p in paths)
    return text, conf, dt


ROUTE_TOOLS = ("haystack.py", "projects.py")
SKILL_TOOLS = ("skill_view", "skills_list")


def observe_tool(tool_name, duration_ms=0, task_id="", args=None):
    used = tool_name in SKILL_TOOLS or (
        tool_name == "terminal"
        and args is not None and any(t in str(args) for t in ROUTE_TOOLS))
    consumed = used and (time.time() - LAST_INJECT_TS) <= CONSUME_WINDOW_S
    if consumed:
        global PENDING_INJECT
        if PENDING_INJECT and not PENDING_INJECT["consumed"]:
            PENDING_INJECT["consumed"] = True
        log_event("consumed", tool=tool_name,
                  since_inject_s=round(time.time() - LAST_INJECT_TS),
                  task=task_id)
    # sequence-crystal fidelity: tools since the injection, per task, checked
    # against the crystal's genome (the recorded order of the proven loop)
    if task_id:
        p = PENDING_INJECT
        if p and p.get("genome") and p.get("task") is None:
            p["task"] = task_id  # bind the pending genome to its first tool
        seq = TASK_SEQ.setdefault(task_id, [])
        seq.append(tool_name)
        if p and p.get("genome") and p.get("task") == task_id \
                and not p.get("seq_done"):
            genome = p["genome"]
            if _is_subsequence(genome, seq) and len(seq) >= len(genome):
                p["seq_done"] = True
                log_event("sequence_match", rule=p["rule"], matched=True,
                          genome=genome, observed=seq[-len(genome) - 2:],
                          task=task_id)
    log_event("tool", tool=tool_name, ms=round(duration_ms or 0), task=task_id,
              skill=tool_name in SKILL_TOOLS, used=used, consumed=consumed)


def _is_subsequence(needle, hay):
    it = iter(hay)
    return all(t in it for t in needle)
