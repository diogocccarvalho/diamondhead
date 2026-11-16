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

## Novelty verdict (subagent's, pending citation verification)
"Online crystallization of verified sub-procedures" — a procedure starting as a scored
candidate, accumulating verified-use evidence in an append-only ledger, and transitioning at
a threshold (~20 verified executions over a week) from scored selection to deterministic
auto-fire — is NOT published in this combination. The two separately-published halves:
procedure extraction + verification-gated admission (Voyager/Zep/SCBT line), and
deterministic runtime artifacts (SCBT). Nobody does the online PROMOTION transition —
the move from "needs scoring" to "bypasses scoring" on live traffic.

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
