import hashlib
import json
import re
import time
import urllib.error
import urllib.request
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
        if r.get("status") == "retracted":
            dead.add(rid)
            out = [x for x in out if x.get("id") != rid]
            continue
        if rid in dead or r.get("status") == "candidate":
            continue
        if any(x.get("id") == rid for x in out):
            continue
        out.append(r)
    return out


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
    choice = ans.get("choice")
    conf = float(ans.get("confidence", 0.0))
    model = payload.get("model") or ans.get("model") or ""
    return choice == "yes" and conf >= min_conf, conf, model


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


def log_event(kind, **fields):
    rec = {"ts": time.time(), "kind": kind, **fields}
    try:
        with open(BEHAVIOR_FILE, "a") as f:
            f.write(json.dumps(rec) + "\n")
    except OSError:
        pass


def mhash(text):
    return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()[:12]


def choose(user_message, cfg):
    rules = live_rules(load_rules())
    if not rules or not plausibly_notes(user_message):
        return None, 0.0, 0.0
    t0 = time.monotonic()
    try:
        hit, conf, model = classify(user_message, cfg["d1_url"], cfg["min_confidence"])
    except (urllib.error.URLError, TimeoutError, OSError, KeyError, ValueError) as e:
        log_event("chooser_error", err=str(e)[:120], mh=mhash(user_message))
        return None, 0.0, (time.monotonic() - t0) * 1000
    dt = (time.monotonic() - t0) * 1000
    rule = rules[0]
    if not hit:
        log_event("chooser_no", conf=round(conf, 3), ms=round(dt),
                  model=model[:60], mh=mhash(user_message))
        return None, conf, dt
    paths = []
    try:
        paths = haystack_top(user_message, cfg["haystack_url"])
    except (urllib.error.URLError, TimeoutError, OSError, KeyError, ValueError) as e:
        log_event("haystack_error", err=str(e)[:120], mh=mhash(user_message))
    bump_evidence(rule["id"])
    global LAST_INJECT_TS
    LAST_INJECT_TS = time.time()
    log_event("inject", rule=rule["id"], conf=round(conf, 3),
              ms=round(dt), chars=len(INJECT_TEMPLATE) + sum(len(p) for p in paths),
              paths=paths, mh=mhash(user_message))
    text = INJECT_TEMPLATE
    if paths:
        text += "\nTop matching notes:\n" + "\n".join(f"- {p}" for p in paths)
    return text, conf, dt


ROUTE_TOOLS = ("haystack.py", "projects.py")
SKILL_TOOLS = ("skill_view", "skills_list")


def observe_tool(tool_name, duration_ms, task_id="", args=None):
    used = tool_name in SKILL_TOOLS or (
        tool_name == "terminal"
        and args is not None and any(t in str(args) for t in ROUTE_TOOLS))
    consumed = used and (time.time() - LAST_INJECT_TS) <= CONSUME_WINDOW_S
    if consumed:
        log_event("consumed", tool=tool_name,
                  since_inject_s=round(time.time() - LAST_INJECT_TS),
                  task=task_id)
    log_event("tool", tool=tool_name, ms=round(duration_ms or 0), task=task_id,
              skill=tool_name in SKILL_TOOLS, used=used, consumed=consumed)
