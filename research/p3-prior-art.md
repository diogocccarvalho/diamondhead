# P3 (query-formation pass) — prior-art sweep, 2026-11-17

Two parallel sweeps (academic + engineering). Full transcripts in
`~/.hermes/cache/delegation/live/deleg_09ee578f/`. Verdict below governs how
the novelty claim is worded; the steal-list governs what the prototype takes.

## Novelty verdict (what we may claim)

INVALID individually (do not claim): operator-based query rewriting, sub-query
decomposition, fitness-driven rewriter optimization, adaptive operator
selection, multilingual query normalization — all established.

SURVIVES as the narrow claim: **a deterministic, no-LLM, GA-evolved operator
chain applied live as a uniform gate before heterogeneous semantic callees
(retriever + binary classifier + LLM), one frozen chain per callee, with a
precision-gated apply/suggest decision.** Load-bearing differentiators:
(1) no-LLM/no-RL — discrete genetic search over a fixed operator inventory
(the RL-rewriter family uses gradient policies + LLM rewriters);
(2) per-callee universality across heterogeneous callees — the classifier-callee
angle (TP/FP fitness) has NO counterpart in anything surfaced;
(3) the apply-vs-suggest two-tier gate keyed on outcome variance.

MUST-CITE + DIFFERENTIATE (highest pressure):
- mRewriter-R1 (arXiv:2610.04899) — agentic RL selecting among discrete rewriting
  operators (language/structural/semantic); their taxonomy maps ~1:1 onto our
  genome axes. Our delta: one frozen genome per callee, zero runtime LLM/planner.
  Their own finding ("no single operator fits all queries") is our supporting
  evidence.
- Multi-step operator-space rewriter (arXiv:2610.10955) — typed rewriting ops
  with retrieval reward; closest structural relative of the genome.
- OATS (arXiv:2603.13426) — per-tool, no-LLM, learned from outcomes, zero
  serving cost. Selection signal only (which tool), not query formation; no
  operator grammar. Erodes any broader "learned per-tool optimization" claim.
- LearnedRewrite (Zhou et al. 2021, SQL) — MCTS over rule application, fully
  non-LLM; single-callee (DBMS). Best non-LLM precedent for crystallized chains.
- SkillQR (arXiv:2610.33768) — "optimal rewriting strategy depends on the
  retrieval target, not the model": direct empirical support for the per-callee
  premise; but routes to LLM strategies at inference.
- RL rewriter family: DeepRetrieval (2503.00223), LeReT (2410.23214),
  RLQR-MiniELM (2501.18056), learning-to-coordinate reformulators (1809.10658),
  leToR (2019). Frame: "we replace RL policy learning with discrete genetic
  search — no gradients, no LLM, no training data."
- Google US8521764B2 — deterministic log-derived rewrite tables (auto-rewrite
  vs suggest-only keyed on click peakedness). Frame: generalization from table
  lookup to GA-evolved operator composition.

## Ranked steal-list (what the prototype takes)

1. **Typed operator taxonomy** (mRewriter-R1, 2610.10955) — organize the genome
   into language / structural / semantic axes.
2. **GEPA survivorship** (arXiv:2507.19457) — Pareto-per-instance selection:
   keep any chain that wins on ≥1 eval instance; prune only strictly dominated;
   minibatch-then-full-eval promotion. Better than global-best elitism.
3. **Tag-not-rewrite** (Grammarly GEC stack / GECToR) — emit localized edits,
   never full rewrites; KEEP-bias + probability threshold as the gate's
   precision dials (a wrong rewrite is worse than no rewrite).
4. **Confidence-gated trigger** ("Better Together", arXiv:2609.05637) — fire
   rewrites only when the baseline's top-1 signal is weak; ~half the gain on
   <40% of queries; blind application HURTS (−2.4 on some sets). Justifies a
   per-query accept/reject gate instead of always-apply.
5. **Never discard the original** (Query2doc 2303.07678, MultiQuery) — keep
   literal, add variants; RRF-merge multi-form results.
6. **Conservative expansion** (PRF/RM3 lineage) — topic-drift is the known
   failure of expansion; constraint-addition over synonym-spam; per-callee
   rewrite-strength gene (RM3's λ, generalized).
7. **Two-tier auto-vs-suggest** (Google patent) — auto-apply when historical
   outcome variance is low, propose-only when high; mine behavior logs as
   fitness data.
8. **Ensemble-over-single** (NCHS name-matching study) — combination of
   matchers beats any single; nickname tables are crystallizable lookup
   operators; Soundex→Jaro-Winkler→COMPGED cascade = cheap-then-expensive
   blocking for fitness evaluation at scale.
9. **Question-type lexical features** (arXiv:2604.03455) — citable support for
   hand-crafted routing signals; cheap trigger for decomposition-vs-passthrough.
10. **Eval discipline** (Better Together budget-matched controls) — prove gains
    aren't "more retrieval"; matched-budget ablation is mandatory in the GA eval.

## Cautions (eval traps + hot-path prohibitions)

- "Sample More, Reflect Less" (arXiv:2607.28576): at equal token cost NO
  self-inspection method beats repeated sampling; Self-Refine/Reflexion are
  negative at small scale. Use as justification for the deterministic gate, and
  as an eval trap: the GA must not evolve a "skip everything" degenerate chain
  that looks cheap.
- OPRO's length-bias artifact: rewriters drift verbose; add a length penalty
  gene or the GA will exploit evaluator quirks.
- DSPy (2406.11695) lifecycle pattern = compile-time-optimize → save frozen
  artifact → run — ours matches; cite as the prompt-space analog (per-module
  optimization is their nearest "per-callee" precedent).
- APE (2211.01910) sampled-subset scoring keeps GA generations cheap.

## Prototype implications (the first experiment)

Target: distro-cluster nickname failure (haystack A1), held-out hard-pairs gate.
- Genome axes: language (PT<->EN, nickname table), structural (sub-query split,
  constraint-add), semantic (synonym union, abstraction).
- Gate: tag-style localized edits + KEEP-bias; confidence-triggered apply;
  original query always in the result set.
- Selection: Pareto-per-instance survivorship, minibatch-then-full promotion,
  matched-budget control, length penalty.
- Success = chain beats frozen normalize_query + hand rules on held-out pairs;
  else P3 collapses to inline fixes (documented kill test, ROADMAP §E).

---

# ADDENDUM — semantic-only redesign (2026-11-17, Diogo's principle)

Principle: EVERYTHING is semantic, NOTHING is hand-authored. Hardcoded
artifacts (thresholds, maps, filler lists) are not written by humans — they are
DISCOVERED from data (vault co-occurrence, call logs, correction tables) and
then CRYSTALLIZED via DiamondHead's per-use SPRT promotion. Full sweep:
[research/p3-semantic-sweep.md](research/p3-semantic-sweep.md).

Key findings:
- ReFormeR mines compact reformulation pattern libraries from query pairs —
  rule discovery from data, not authorship.
- LOOComp/EnComp: leave-one-out token saliency = semantic filler detection
  (delete token, measure answerability drop, auto-threshold via gap detection)
  — replaces hand filler lists.
- DC-PRF "Safety Anchor": residual interpolation toward the original query
  bounds drift — the semantic version of the strength dial.
- Conformal-RAG: split-conformal order-statistic thresholds for accept/reject
  — threshold calibration from data, with coverage guarantees.
- CoRe: two-family automated promotion gate (reward-like + stability) at
  production scale — closest overlap with DiamondHead's crystallization angle;
  cite and differentiate (they retrain models weekly; we promote individual
  rules via per-use SPRT).
- Oracle ceiling analysis (arXiv:2603.13301): selective rewriting maxes at
  ~+3pp — expectation-setter for the whole experiment.

Novelty gap (survives the second sweep too): no prior work combines
data-discovered operations + embedding-space execution + per-operation SPRT
crystallization + conformal threshold calibration + selective preserve
decisions. CoRe promotes whole models; WeTune verifies via SMT; Google/Bing
serve mined tables by lookup. Per-operation statistical promotion in IR
rewriting: unclaimed — that is DiamondHead's angle.
