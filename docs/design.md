# design.md — spec lines harvested from production (haystack failure catalog)

Every line here is an architectural implication distilled from a live failure in
the haystack retrieval tool (see haystack docs/SHORTCOMINGS.md for what failed,
why, and how it was patched). These are the design rules for the from-scratch
architecture; the patches in haystack were mortise wood, these are the joints.

- D1 — User-acquired constraints must be a HARD layer, not a soft score any
  learned component can override. "What the user taught" is an invariant block
  (non-learned), not a prior. Selection order: invariant > learned-by-use >
  model opinion.
- D2 — Graceful degradation must degrade the CAPABILITY (skip reordering), never
  the CONSTRAINTS (ordering rules). Layers must be composable in any availability
  state. A "just do" step (crystallized op) can't depend on which optional
  components happen to be alive.
- D3 — Relevance judgment at query time is the bottleneck of retrieval-augmented
  everything. The endgame (no encoders, crystallized selection) must make "is
  this context good" O(1)-ish or make the judgment incremental (judge once,
  remember the verdict), not re-judge every candidate on every query.
- D4 — Crystallized knowledge (verified ops, taught mappings) must be an
  append-only substrate that all derived structures (indexes, caches, weights)
  are REBUILDABLE FROM. Cache may die; crystal may not. This is the storage law.
- D5 — Navigational artifacts and content artifacts need different retrieval
  classes. Index the graph (structure) separately from the text (content) and
  rank content first by default — "pointers serve, never replace."
- D6 — Correctness of retrieval is often set-valued, not scalar. A learning
  signal that can't represent "this family, any member" chases noise. Learned
  corrections record granularity (file / folder / family), not just a path.
- D7 — "Think then do" is the wrong shape for bounded tasks — the thinking cost
  exceeds the task. Crystallized steps have a think-budget of ZERO by default
  and earn thinking only when a validator says the cheap path failed.
- D8 — Any "context window" assumption must be enforced at the boundary
  (token-count check before ingest), not tuned per-corpus by character
  heuristics. Length is a property of the TOKENIZER, not the text; only the
  tokenizer can validate it.
