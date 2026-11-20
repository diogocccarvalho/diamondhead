# Part 1: Design Specification
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

# Part 2: Implementation Plan
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
(the recurring failure: "I'm always telling you to use the
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
observe      | post_tool_call + observer hooks → behavior log (which skill/tool fired per turn; misses = user corrections) | D6: log granularity, not just names
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


# Appendix A: Deterministic Chunking Theory

## A.1 Why chunk by headings?

Headings provide an intrinsic boundary structure in markdown documents.
Unlike naive fixed-size splits, heading-aware chunking preserves semantic
coherence within each chunk while making the boundaries easily verifiable.

A heading defines both a topic label (the heading text itself) and a scope
(all content until the next heading at the same or higher level). This maps
directly to the prefill-replacement problem: each chunk becomes independently
checksummed, indexed, and staleness-checkable.

## A.2 Token budget per chunk

The target is roughly 512-1024 tokens per chunk for a first prototype. This
means chunks should be small enough that indexing top-k terms is cheap, but
large enough that term overlap retrieval remains effective. We use character
thresholds calibrated to average English token length (~4 chars/token):

- Minimum chunk size: 1024 characters (~256 tokens)
- Maximum chunk size: 4096 characters (~1024 tokens)
- If a section between headings exceeds the maximum, it is split at sentence
  boundaries using a simple period-based heuristic (no NLP required).

## A.3 Term weighting without ML

We use raw TF (term frequency) with basic stopword removal. For each chunk:

1. Lowercase all words (split on non-alphanumeric).
2. Remove stopwords (a hard-coded list of ~150 common English words).
3. Count remaining term occurrences.
4. Sort descending — these become the chunk's "top terms".

No IDF. No BM25. This is intentionally naive to make the retriever fully
deterministic and auditable. In later work, we can swap in BM25 without
changing the index structure.

## A.4 Checksum selection

SHA-256 of the raw chunk text (after whitespace normalization) provides a
collision-resistant fingerprint that any downstream pass can recompute
independently. This is the mechanism for replay verification and staleness
detection — every stored chunk has its source checksum saved alongside it.

If a chunk's source changes, its SHA-256 diverges. The staleness detector
compares stored checksums against freshly computed ones and flags exactly
which chunks need rebuilding.

## A.5 First-line claims

Each chunk's first complete sentence (up to 120 characters) serves as a
"deterministic claim" — a short summary anyone can verify comes from this
chunk. In practice this means: find the first period, question mark, or
exclamation point; take up to 120 chars; truncate with ellipsis if longer.

The claim is not generated — it's extracted literally from the source text.
This is why determinism matters: the claim must always be verifiable.

## Appendix B: Index Architecture Details

### B.1 Top-level index schema

The index JSON has four top-level fields:

- `meta`: build metadata including corpus source paths, total size, build
  timestamp (UTC), and Python version used.
- `chunks`: array of chunk objects (sorted by position in source).
- `stem_index`: mapping of stem → [chunk_ids] for basic search.
- `version`: semantic version string "1.0.0".

### B.2 Chunk object fields

Each chunk contains:

- `id`: sequential integer starting at 0.
- `heading`: the nearest ancestor heading, or "INTRO" for intro text before
  any heading.
- `text`: the full chunk text (whitespace-normalized).
- `byte_range`: {"start": int, "end": int} into the original corpus file.
- `checksum_sha256`: hex digest of normalized chunk text.
- `first_line_claim`: first sentence, truncated to 120 chars max.
- `top_terms`: sorted list of {"term": str, "count": int} dicts.
- `token_estimate`: rough char_count / 4.0 estimate.

### B.3 Stem index

We implement Porter-like stemming via prefix matching on word roots. For
simplicity, we strip common suffixes (-ing, -ed, -tion, -ment, -s, -y→ie)
and lowercase. This is a proxy for full stemming — sufficient for the toy
but documented as approximate.

The stem_index maps each stem value to a list of chunk IDs that contain
that stem. It enables O(1) lookup of candidates for a given query term.

## Appendix C: Retrieval Protocol

### C.1 Query processing

1. Parse query: split on spaces, lowercase, remove stopwords.
2. For each query term, look up stems in stem_index.
3. Union of candidate chunk IDs from all terms.
4. Rank chunks by total term-overlap count.
5. Return top-K chunks (default K=5).

### C.2 Savings calculation

For each probe query, measure:

- INDEX_READ: sum of token_estimates of retrieved chunks from the index.
- FULL_READ: total token count of the entire corpus.
- SAVINGS_PCT: (FULL_READ - INDEX_READ) / FULL_READ × 100%.

With ~10K tokens total and 5 chunks averaging 500 tokens each reading ~200
tokens of context, expected savings are around 75-80%.

### C.3 Staleness detection protocol

1. Recompute SHA-256 for every chunk from current source.
2. Compare each checksum against the stored value.
3. Report exact set of stale chunk IDs.
4. Cost: O(n) single-pass over corpus, hashing each chunk.
5. Rebuild cost (if fixing): only affected chunks, not the whole corpus.

This gives us a precise staleness score: number_of_stale_chunks / total_chunks.
In normal operation (minor edits), expect 1-5% staleness rate. After major
restructuring, expect 50%+ until recompilation.
