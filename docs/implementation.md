# implementation.md — P2: crystallization as a Hermes plugin (researched 2026-11-13)

Question: how do we implement crystallization as a plugin for the agent, so
repeated behavior fires automatically — no thinking, no user asking (the
notes-router case). Sources: Hermes Agent docs (developer-guide/plugins,
developer-guide/middleware, user-guide/features/hooks, cost-control), read
2026-11-13. Everything below is from the docs, not guesses.

## 0. The evidence this is needed (measured, not vibes)

Auto skill discovery is relevance-driven and weak: measured ~1 skill load
across ~190 messages on one install (hermes-agent cost-control doc). The
routing today is a SOUL.md rule — still a soft prior the model can miss
(exactly the failure Diogo names: "I'm always telling you to use the
notes-router"). A plugin hook is deterministic: code fires every turn.

## 1. The mechanism map (Hermes surfaces, most reliable first)

1. **Plugin middleware** (`ctx.register_middleware`, from `register(ctx)`):
   `llm_request` / `tool_request` / `llm_execution` / `tool_execution`.
   Rewrites args/requests before guardrails and approvals run, or wraps the
   execution callback. Deterministic, model-independent — this is the
   invariant layer. Caveat below in §4 (fail-open tension).
2. **Plugin hooks** (`ctx.register_hook`), the two that matter for P2:
   - `pre_llm_call(session_id, user_message, conversation_history, ...) ->
     injected text`: fires ONCE PER TURN, and the return value is injected
     into the current user message. This is the auto-router mechanism: cheap
     code decides "this is a notes question" and injects the routing line
     (skill name + candidate paths). The model receives it as given, not as
     a suggestion.
   - `post_tool_call(tool_name, args, result, duration_ms)`: fires once per
     tool call. This is the observation layer — the behavior log.
3. **Shell hooks / gateway event hooks** (`hooks:` in config.yaml;
   HOOK.yaml+handler.py in ~/.hermes/hooks/, trusted-by-placement): the
   trigger layer — condition→action, event-driven (agent:start, session:*,
   command:*, wildcards). Matches the event-driven-triggers preference.
4. **SOUL.md routing rule** (~60 tokens): the soft fallback. Keep it — the
   plugin can be down; the rule is the degraded-mode path (D2: degradation
   must never lose the constraint).

## 2. The crystallization loop (P2's actual design, haystack's pattern applied to behavior)

Stage        | Mechanism                                    | Design rule
observe      | post_tool_call + observer hooks → behavior log (which skill/tool fired per turn; misses = Diogo corrections) | D6: log granularity, not just names
learn        | recurring pattern → candidate crystallization rule (when X, do Y) appended to the plugin's store        | D4: append-only, survives plugin updates (plugin_db()/plugin_data_dir())
enforce      | the rule becomes code: pre_llm_call injection or tool_request rewrite — no model vote                    | D7: think-budget zero for the crystallized step
validate     | a rule is only ENFORCED after it has fired and been validated N times; before that it is injected as a hint  | D1: user-taught > learned-by-use > model opinion
unlearn      | retraction records supersede rules; store is replayable                                                   | D4 supersession (Reglos evidence)

The promotion gate IS the validator loop from the thesis: a behavior is
crystallized when its cheap path (code) has demonstrably matched or beaten the
model's judgment on the observed distribution — measured, one variable at a
time, same discipline as haystack's RESEARCH.md.

## 3. First experiment: `crystal-router` plugin (the notes-router case)

Scope (one variable, measurable):
- pre_llm_call: gate on a cheap classifier (the d1 :8080 endpoint is already
  running) → "is this a notes/vault question?" If yes, inject: "Load skill
  notes-router now; route via haystack.py (project question → projects.py
  find, anything else → query)." Also inject top-3 haystack paths when the
  question names a topic.
- post_tool_call: log every skill_view/tool call per turn to plugin_db;
  a turn where the user had to correct the route = a missed crystallization
  candidate (becomes a learn entry, same loop as haystack learn).
- Metrics: skill-load count per 100 messages (hermes insights) before vs
  after; injection precision (turns injected where no notes question existed
  = false positives, measured from the log); latency added per turn
  (classifier is ~ms-scale, well under D3's 1s budget).
- Gates: pass = 100% skill load on notes questions with <1% false-positive
  injection rate, measured over a week of real traffic (Telegram included).
  Compare against the SOUL.md-rule baseline first.

## 4. Open tension to resolve in design (do not hand-wave)

Middleware and hook callbacks are FAIL-OPEN: "middleware failures are
fail-open — Hermes logs a warning and continues with the base runtime path."
That directly collides with D2 (graceful degradation must degrade capability,
never constraints) and D1 (hard layer). Resolution options, to decide at
build time:
(a) accept fail-open for the router (worst case = the current status quo,
    a missed skill load) and use fail-closed shell `pre_tool_call` hooks only
    for true invariants (blocking ops);
(b) pair every middleware rule with a shell pre_tool_call hook that fails
    closed — belt and suspenders, more complexity.
Recommendation: (a) for P2 — crystallized ROUTING is an optimization, not a
safety invariant; save fail-closed enforcement for the P4 architecture'
invariant blocks.

## 5. Mapping to the thesis (why this is a P2 experiment, not just a feature)

- "judge once, remember the verdict" (D3): the learned rule store remembers
  the classifier/teach verdict; per-turn cost drops to O(1) string injection.
- "crystallize repeated sub-problems into deterministic checkable components"
  (thesis): the router IS that component, at software scale, running inside a
  live agent — the behavior log and promotion gates make it checkable.
- Staggered crystallization (wall 3): only one behavior class crystallizes at
  a time (notes routing first); the SOUL.md rule stays as the frozen judge
  relative to what's being tested.

## Sources

- https://hermes-agent.nousresearch.com/docs/developer-guide/plugins
- https://hermes-agent.nousresearch.com/docs/developer-guide/middleware
- https://hermes-agent.nousresearch.com/docs/user-guide/features/hooks
- https://hermes-agent.nousresearch.com/docs/user-guide/features/built-in-plugins
- cost-control reference (auto-discovery measurement, insights verification recipe)
