# next-steps.md — what can be implemented NOW in P2 (crystal-router)
Researched 2026-11-13. Sources: design.md (D1-D8), implementation.md (mechanism map,
verified against Hermes docs 2026-11-13), vault research/papers.md, p3-core.md.
No code here — each item is scoped enough to build directly.

## (a) Ranked components for the crystal-router plugin

1. **Behavior log (observe) — `post_tool_call` hook + gateway `agent:step` hook.**
   Does: append one JSON line per turn/step to plugin_data_dir(): which skill/tool
   fired, session/platform, user-message hash, duration. Misses are captured when
   Diogo corrects routing in a later message (tagged correction events).
   Serves: D4 (this log is the substrate; everything below rebuilds from it), D6
   (log at turn + tool + correction granularity, not just tool names).
   Implement: `ctx.register_hook("post_tool_call", ...)`; write to
   `plugin_data_dir()` (survives plugin updates); never raises (hooks are
   fail-open by design — that's correct here, it's telemetry).
   Measure: log completeness (100% of turns logged vs `hermes insights` counts);
   fraction of routing decisions derivable from the log alone.

2. **Auto-router injection — `pre_llm_call` hook.**
   Does: fires once per turn; cheap classifier (d1 :8080 endpoint, ~ms) answers
   "is this a notes/vault question?"; if yes, inject the routing line (skill
   name + haystack.py route) and top-3 haystack paths. The injected text arrives
   as given, not as a suggestion — code, not model opinion.
   Serves: D7 (zero think-budget for the crystallized step), D3 (judge once:
   the classifier verdict is O(1)-ish, well under a 1s budget), D1 (injection is
   deterministic code — learned-by-use layer sits above model opinion).
   Implement: `ctx.register_hook("pre_llm_call", cb)` with signature
   `(session_id, user_message, conversation_history, is_first_turn, model,
   platform, **kwargs)`; return injection text or None. Keep the SOUL.md rule
   as the fail-open fallback (D2: degrade capability, never the constraint).
   Measure: skill-load count per 100 messages before/after (baseline = current
   ~1/190-message measured rate); injection precision over a week of real
   traffic incl. Telegram. Gate: 100% skill load on notes questions, <1% FP.

3. **Candidate rule store (learn) — append-only rules in plugin_db().**
   Does: patterns from the log (e.g. "corrections mention Jira after deploy
   questions") become candidate `when X → do Y` rules, appended with evidence
   counts; retraction records supersede; store is replayable to rebuild
   everything derived (classifiers, caches).
   Serves: D4 (append-only storage law + supersession), D6 (rules record
   granularity: which question family, not just keywords).
   Implement: plugin_db()/plugin_data_dir(); one JSONL table, rules carry
   {pattern, action, evidence_n, status: candidate|validated|retracted}.
   Measure: replay test — delete all derived state, rebuild from store, verify
   router behavior identical (D4 holds iff replay is lossless).

4. **Promotion gate (validate) — hint → enforced, staged.**
   Does: a candidate rule is injected as a HINT until its cheap path (code) has
   matched-or-beaten the model/user judgment on observed traffic N times
   (suggest N≥20 + one full week); only then does it become enforced injection
   (or `tool_request` rewrite). This is the validator loop from the thesis,
   at software scale.
   Serves: D1 (user-taught > learned-by-use > model opinion — the ordering is
   the gate), D7 (enforced rules never think), staggered crystallization (wall
   3): one behavior class crystallizes at a time; the SOUL.md rule stays the
   frozen judge relative to what's being tested.
   Implement: status field in the store; enforcement path is the same
   pre_llm_call hook reading status. Enforced set is tiny and auditable by eye.
   Measure: promotion precision — enforced rules later retracted = 0 (target);
   time-to-promotion and retraction rate per rule.

5. **Corrections ingest (set-valued unlearn) — user message watcher.**
   Does: explicit Diogo corrections ("use notes-router", "wrong skill") become
   the highest-priority teaching signal, recorded at family granularity
   (D6), superseding conflicting learned rules immediately (D1).
   Implement: gateway/command hook or a lightweight check inside pre_llm_call
   on the raw message; corrections write supersede-records, not edits.
   Measure: correction-to-fix latency (how many turns until the corrected
   route fires automatically), correction recall in the log.

6. **Latency + cost envelope (cross-cutting, build with #2).**
   Does: measure ms added per turn by classifier + injection; log token delta
   from injections. Serves D3/D7 empirically. Measure: p50/p99 added latency
   (<10ms p99 target); injected tokens/turn; net token cost incl. avoided
   re-explanations.

## (b) Best practices from the papers, per component

- Scale-free pinning / relative-not-absolute matching (haystack pin rule; the
  hint p3-core.md adopts for the router's "grasp"): candidate-rule patterns
  should match by relative similarity on the question family, not exact tokens
  or absolute thresholds. Keeps the router portable across phrasings and is
  the current best answer to "what is grasp without an encoder".
- Append-only learned state (D4; Reglos-style supersession, also Gist [30]'s
  opposite — learned+lossy — as the anti-example): every rule store write is
  an append; corrections supersede; caches/indexes are always rebuildable.
  Deterministic + replayable is the differentiator vs gist tokens.
- Validator-gated crystallization (Gödel Machine [21]: proof system frozen;
  AlphaProof [31]: external checker as reward): promotion happens only behind
  a frozen gate — the gate's criteria don't change while a candidate is being
  evaluated, and the SOUL.md baseline stays frozen relative to the test.
- Reward-hacking is an equilibrium, not a bug [26]: never let the component
  that produces candidates also score them. The behavior log scores; the
  rules store proposes; the promotion gate (external, frozen) decides. Avoid
  DGM-style objective-hacking [19] by keeping the referee outside the loop.
- Staggered crystallization (wall 3 / component 5 of the architecture): only
  ONE behavior class crystallizes at a time (notes routing first). Simultaneous
  self-modification is the failure mode; the P2 gate schedule enforces it.
- Judge once, remember the verdict (D3; Memory Layers [3] as the KV-lookup
  shape): the classifier/teach verdict is stored; per-turn cost drops to
  O(1) injection. Do not re-judge the same question shape every turn.
- Induction heads [14] as the monolith analog: the LLM already self-organizes
  repeated behavior into circuits; P2 moves that self-organization OUT of the
  weights into inspectable, re-derivable code — the log tells you which moves.

## (c) Risks / open questions

- Fail-open enforcement (implementation.md §4): middleware/hooks are fail-open
  by Hermes design, colliding with D1/D2. Recommended resolution (a): accept
  fail-open for routing (worst case = status quo); reserve fail-closed shell
  `pre_tool_call` hooks for true invariants. Do not hand-wave; decide at build.
- Injection is soft-after-all: the model receives injected text but can still
  ignore it. The measured claim is "code decides + fires every turn", not
  "model can't deviate". Track deviation rate explicitly in the log.
- Classifier drift vs the frozen gate: the d1 :8080 endpoint will improve
  during a measurement week, contaminating before/after comparisons. Pin the
  classifier version per measurement window (staggered crystallization applied
  to the experiment itself).
- Base-rate poverty: notes questions may be too rare for 20-sample gates on a
  weekly cadence. Open question: promote on pooled distribution across
  question families, or wait longer for the single class? (Lean to pooled
  evidence, per-class enforcement.)
- Multi-class generalization: success on notes-routing doesn't prove the loop
  generalizes (candidate #2: a second family, e.g. EAI/Jira deploy routing).
  Plan the second class as the real test of D6 granularity.
- Novelty re-check: search again for published "online crystallization of
  verified sub-procedures" before claiming anything (last checked 2026-11-06).
- Privacy of the log: behavior log captures user-message hashes and tool args
  from Telegram traffic. Keep only hashes + patterns in the append-only store;
  raw text stays out of plugin_db.
