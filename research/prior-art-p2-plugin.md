# Prior-art pass — P2 crystallization-as-plugin (semantic function chooser + online promotion)
Compiled 2026-11-16 by research subagent. Claims are LEADS from literature search —
verify citations at the implementation gate, same rule as every adopted change.
Some arXiv IDs were not re-verified by the maintainer.

## Closest works (ranked by proximity)

1. **SCBT — Self-Crystallizing Behavior Trees** (Oct 2026, drone control). LLM proposes
   subtree patches on failure; three-stage admission; once LLM-call rate decays below a
   threshold, patches are CRYSTALLIZED into a deterministic BT running with zero LLM calls,
   with exact-reproducibility on log re-ticks. Same word, same "compiler not runtime" idea —
   but robotics, reactive compile-on-failure, call-rate trigger (not verified-execution count),
   no semantic memory feeding it.
2. **Zep Agent Skills** (Nov 2026, production). Trace→Skill compiler: Capture → Compile →
   Curate → Admit → Serve; separate proposer/checker; evidence-cited claims; admission gates;
   verified outcomes change search rank. Production-grade version of our reviewer — but batch/
   scheduled, selection stays search-based forever, no transition to deterministic firing.
3. **Voyager** (2023). The existence proof: frozen model, environment-verified skills, stored
   executable, composed. But selection is always vector retrieval; no promotion to auto-fire.
4. **MACLA** (AAMAS 2026). Frozen LLM + external procedural memory, Bayesian reliability
   tracking, expected-utility selection. Still scores every call; never stops needing the router.
5. **SkillRouter / RouteLLM / xRouter / MARS / RouteFM** (2024–2026). The routing family:
   learned routers between models or skills. ALL keep a scorer on the critical path forever —
   none crystallize a mature route past scoring.
6. **Trace compilers (batch)**: Trace2Skill (EMNLP 2026), SKILL-DISCO, TraceCompiler,
   AnyThing2Skill, SPEM, PLVR. Extract procedures from traces into executable/portable
   artifacts, verification-gated — but offline/batch, artifacts stay under retrieval.

7. **RSPM — Recursive Self-Pruning Memory** (arXiv:2610.25561, Oct 2026). Constraint
   promotion instance→category→universal after holding in 3-5 contexts; offline sleep
   cycles only.
8. **WikiSkill** (arXiv:2608.27454, Aug 2026). Raw→wiki→skills workspace; proposal gated
   by R > R_best with rollback; offline, held-out tasks.
9. **AutoSkill / SkillEvo** (github ECNU-ICALK/AutoSkill, Mar 2026). Replay-driven
   mutation; five-gate AND promotion vs champion (quality/trigger/cost/latency/regression);
   offline replay pool.

## Novelty verdict (RE-VERIFIED 2026-11-16, second research pass — claim NARROWED)
First pass said "promotion past scoring is unclaimed". Second pass (2026-11-16) found
threshold promotion IS now published, offline: Zep Agent Skills is a full paper
(arXiv:2611.01386) with gated auto-admission; RSPM (arXiv:2610.25561) promotes constraints
instance→category→universal after 3-5 contexts; WikiSkill (arXiv:2608.27454) gates proposals
with R > R_best + rollback; AutoSkill/SkillEvo (github ECNU-ICALK) promotes on a five-gate
AND (quality/trigger/cost/latency/regression) vs champion — ALL offline (sleep cycles,
replay pools, held-out evals, scheduled compilation).

SURVIVING CLAIM (narrow): procedure-level capture→compile→threshold→promotion DRIVEN BY
LIVE INFERENCE TRAFFIC in a single closed loop — the runtime watches its own traces and
deterministically auto-fires a newly-promoted crystal onto the active execution path. No
surveyed work (incl. Microsoft Foundry canary/promotion and agent-canary, which are
whole-agent versioning, not learned-procedure promotion) does this. Batch threshold
admission is no longer ours. Every writeup must say "live-traffic promotion", never
bare "online promotion".

Notable inversion: SCBT is compile-on-failure; DiamondHead is compile-on-success.

## What stays ours after prior art
- The promotion gate itself (streak-of-verified-executions → deterministic injection).
- Append-only replayable state coupled to promotion (retraction = demotion, not deletion).
- Haystack-as-inputs: the chosen function's context served by the same engine family
  that learns the routing pins (semantic memory feeding the chooser; ERSkill is the nearest
  neighbor and still doesn't promote).
- Design laws preserved as differentiators: external frozen referee, judge-once,
  staggered crystallization.

## Consequence for the build
The plugin loop (next-steps.md #1-#6) is unclaimed territory; the differentiating component
is #3+#4 (candidate rule store + promotion gate) — everything else exists in pieces. Re-check
novelty again before any public claim (last: 2026-11-16).
