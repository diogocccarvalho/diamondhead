# CSM (Crystallized Semantic Model) — prior-art synthesis, 2026-11-17

Three sweeps, one architecture question. CSM = P4, from scratch: NO LLM, NO
transformer core. Reasoning = the semantic router itself — a from-scratch
decision-maker selecting links (inject-from-memory vs call-a-proven-block);
training becomes link-selection, not next-token prediction; creativity lives
in selection, correctness lives in the blocks.

Sweeps:
1. `research/csm-transformer-landscape-sweep.md` — the learned-native answers
   to the same cost problem (APPENDIX: what CSM replaces/out-argues).
2. `research/csm-posttransformer-sweep.md` — the post-transformer families
   (CORE: prior art for a from-scratch router).
3. This file — synthesis, novelty wording, the open research hole.

## What prior art says about the router (our research hole)

The router must decide, deterministically, with no learned core:
- ACT-R's conflict resolution is the closest existing from-scratch
  decision-maker (buffer matches + utility values over productions).
  Utility values there are learned — CSM's replacement candidate: DH-promoted
  weights (SPRT-frozen) + semantic distance as the selection signal.
- SOAR chunks on impasse: compile when stuck. Our inversion (compile on
  SUCCESS, gate by proof) is the differentiator; their chunk degeneracy
  (over-general rules) is the failure our Lean-gate prevents.
- VSA/HD binding is the best candidate interlingua: deterministic, invertible,
  one-shot composition — every hypervector unbinds to its construction, so
  THE ROUTING DECISION ITSELF IS REPLAYABLE. Cleanup memory = concept index.
- KG span-grounded triples (triple, span, extractor-version) = the memory
  artifact schema with built-in replayability.
- RETRO's 25x parameter reduction = precedent that competence != core size.
- NeSyPr proceduralizes reasoning into symbol procedures (LLM as compiler) —
  nearest prior art, but UNVERIFIED compilation. WALL-E 2.0 extracts replayable
  rules from interaction. The CSM niche — verified proceduralization with no
  learned core — is EMPTY as of this sweep.

## Novelty wording (narrow, defensible)

CSM = verified proceduralization of reasoning over a from-scratch router:
deterministic link-selection over proven blocks + span-grounded replayable
memory, with per-block SPRT promotion and impasse-driven retreat. No surveyed
system combines (a) no learned core, (b) checkable/replayable decisions,
(c) statistical per-block promotion. CoALA concedes the shape but fills the
center with an LLM; NeSyPr keeps an unverified LLM compiler; ACT-R/SOAR
compile unverified rules.

## The case against CSM (must be answered in the design doc)

1. PERCEPTION IS THE WALL. Every dead architecture died at recognition:
   concepts presuppose learned feature extraction. CSM must declare an
   explicit perception frontier — where does a raw utterance become concepts?
   (Our pragmatic answer: the encoder forward for grasping semantics —
   p4-core already concedes encoders at the edge, "orders of magnitude
   cheaper than an LLM pass" — but the design doc must OWN this: CSM is
   no-LLM, not no-neural.)
2. APPLICABILITY vs CORRECTNESS. A verifier certifies a block on its
   instance, not its applicability to future instances (Soar chunk
   degeneracy, resurrected). Needed: verified applicability preconditions +
   impasse retreat (fall back to re-derivation instead of trusting a block).
3. LINK-SELECTION IS STILL PREDICTION. Every retrieval-centric system
   (kNN-LM, RETRO, DNC) kept an opaque controller because deterministic
   selection didn't generalize. CSM's bet: post-hoc route checking + impasse
   retreat + DH-gated selection weights contain the brittleness. This is THE
   research risk — the thing to falsify first, cheaply.

## First falsification experiment (cheap, next session)

Take the d1-classifier routing problem (verdicts flip on wording — measured)
and try to build the router's selection signal from scratch: candidate signals
= embedding distance to crystal trigger phrases, DH-promoted weights, and
memory-access patterns. If NO from-scratch selection signal separates
should-fire from should-not-fire better than the frozen hand rule, the router
problem is evidence of where determinism fails — record it, and CSM's scope
shrinks honestly.
