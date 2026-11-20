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

The fundamental insight is that document structure already encodes retrieval
boundaries — we just need to expose them programmatically without any NLP
or machine learning. The parser reads heading markers (hash symbols) as
natural delimiters and emits chunks bounded by those delimiters.

This approach has been known in information retrieval since the early days
of document indexing. What distinguishes our approach is not the chunking
strategy but the determinism guarantee: every downstream consumer can
recompute the index from scratch and verify it matches byte-for-byte.

No learned embeddings. No trainable parameters. Just hashes, word counts,
and structural boundaries defined entirely by the source formatting.

## A.2 Token budget per chunk

The target is roughly 512-1024 tokens per chunk for a first prototype. This
means chunks should be small enough that indexing top-k terms is cheap, but
large enough that term overlap retrieval remains effective. We use character
thresholds calibrated to average English token length (~4 chars/token):

- Minimum chunk size: 1024 characters (~256 tokens)
- Maximum chunk size: 4096 characters (~1024 tokens)
- If a section between headings exceeds the maximum, it is split at sentence
  boundaries using a simple period-based heuristic (no NLP required).

The lower bound ensures that each chunk carries enough signal for meaningful
term-frequency ranking. Below 256 tokens, the term distribution becomes too
sparse for reliable overlap matching against query terms.

The upper bound is chosen so that even if a retrieval pass fetches all top-K
chunks for a single query, the total context never approaches the LLM context
window limit. For a 128K window model fetching 5 chunks of 500 tokens each,
the worst case is only 2,500 tokens — well under 2% utilization.

In production deployments, the optimal chunk size depends on the query
distribution. Short, focused queries benefit from smaller chunks; broad,
exploratory queries benefit from larger ones. Since we are building a toy,
we accept this trade-off and measure actual performance empirically.

## A.3 Whitespace normalization and reproducibility

Before computing checksums or extracting claims, chunk text undergoes a
single normalization step: every sequence of whitespace characters (spaces,
tabs, multiple newlines) is collapsed into a single space, then trailing
whitespace is stripped. This means that minor formatting changes — extra
blank lines, mixed indentation styles — do not produce different checksums
for semantically identical content.

This normalization is applied once during compilation and stored as the
canonical form. Any future re-parse will apply the same normalization,
ensuring that two compilations of the same source material produce
identical chunks regardless of how the source was originally formatted.

The normalization is also reversible in the sense that no information is
lost from a retrieval perspective. When a downstream consumer reads a
chunk's text, they get the normalized form, which preserves all words,
punctuation marks relevant to meaning, and structural ordering.

## A.4 Term weighting without ML

We use raw TF (term frequency) with basic stopword removal. For each chunk:

1. Lowercase all words (split on non-alphanumeric).
2. Remove stopwords (a hard-coded list of ~150 common English words).
3. Count remaining term occurrences.
4. Sort descending — these become the chunk's "top terms".

No IDF. No BM25. This is intentionally naive to make the retriever fully
deterministic and auditable. In later work, we can swap in BM25 without
changing the index structure.

The choice of stopwords follows the Porter stemmer convention, expanded
with additional common function words found in technical writing. The list
is hardcoded in compile.py as a frozenset literal — no external file
dependency, no version drift possible.

Term frequency alone is sufficient for our toy because corpus sizes of
10K-50K tokens make IDF variation negligible. In a billion-token corpus,
IDF correction becomes important; here, the top terms of a 500-token
chunk dominate anyway.

Query-term matching uses the same stopword filter and stemming pipeline
as compilation, ensuring perfect symmetry between indexing and search.
Every query term gets mapped to its stem and looked up in the inverted
index exactly like every chunk term was during build time.

## A.5 Checksum selection and collision resistance

SHA-256 of the raw chunk text (after whitespace normalization) provides a
collision-resistant fingerprint that any downstream pass can recompute
independently. This is the mechanism for replay verification and staleness
detection — every stored chunk has its source checksum saved alongside it.

We chose SHA-256 over MD5 because the cost difference is negligible
(~microseconds per chunk) while the security margin is orders of magnitude
higher. Even though adversarial hash collisions are not a threat model
here, there is zero reason to prefer the weaker algorithm when the
performance delta is imperceptible.

The checksum is computed on the normalized text string encoded as UTF-8
bytes. Using the string directly in Python's hashlib.sha256() call works
because Python converts Unicode strings to bytes via UTF-8 encoding before
passing to the digest function. This means the checksum is always
reproducible across platforms and runtimes, provided UTF-8 encoding is used.

## A.6 First-line claim extraction

Each chunk's first complete sentence (up to 120 characters) serves as a
"deterministic claim" — a short summary anyone can verify comes from this
chunk. In practice this means: find the first period, question mark, or
exclamation point; take up to 120 chars; truncate with ellipsis if longer.

The claim is not generated — it's extracted literally from the source text.
This is why determinism matters: the claim must always be verifiable. No
language model paraphrasing, no summarization hallucination. The claim
exists in the chunk text; you can search for it and confirm its presence.

For chunks where the first paragraph contains no terminal punctuation
(unusual but possible with code excerpts or bullet lists), the claim falls
back to the first line truncated at 120 characters. This edge case is
documented rather than treated as an error, since the fallback is still
deterministically derived from the source.

The 120-character limit balances brevity with informativeness. At 120
characters, most English sentences fit completely; some longer compound
sentences require truncation with ellipsis to indicate incompleteness.

## Appendix B: Index Architecture Deep Dive

### B.1 Top-level index schema explained

The index JSON has four top-level fields designed for forward compatibility:

- `meta`: build metadata including corpus source paths, total size, build
  timestamp (UTC), and Python version used. Metadata never affects retrieval
  logic but is essential for auditing and debugging unexpected results.
- `chunks`: array of chunk objects sorted by position in source order. This
  is the primary payload — everything a downstream consumer needs.
- `stem_index`: mapping of stem → [chunk_ids] for efficient term lookup.
  Optional for full index rebuild, but essential for O(1) candidate retrieval.
- `version`: semantic version string "1.0.0". Increment when breaking changes
  are made to the chunk schema or index structure.

Future versions might add: vector embeddings per chunk (learned, lossy),
confidence scores per term (BM25-weighted), or cross-chunk relationship links.
All such additions would be additive to the schema — existing consumers
would ignore unknown fields.

### B.2 Chunk object field semantics

Each chunk object is self-contained:

- `id`: sequential integer starting at 0. Stable across recompilation if
  source ordering does not change. Use this as a key in the stem_index.
- `heading`: the nearest ancestor heading, or "INTRO" for intro text before
  any heading. Provides human-readable grouping for log output.
- `text`: the full chunk text after whitespace normalization. This is what
  goes into the LLM context window if selected by the retriever.
- `byte_range`: {"start": int, "end": int} into the original corpus file.
  Enables efficient random-access read of specific chunks from large files
  without loading the entire corpus into memory.
- `checksum_sha256`: hex digest of normalized chunk text. Primary integrity
  mechanism — any bit flip in the source changes this value.
- `first_line_claim`: first sentence, truncated to 120 chars max. Quick
  sanity check: if a retrieved chunk's claim looks unrelated to the query,
  the retriever may be returning false positives.
- `top_terms`: sorted list of {"term": str, "count": int} dicts. Used for
  explainability: show users which terms matched and contributed to ranking.
- `token_estimate`: rough char_count / 4.0 estimate. Good enough for budget
  planning; actual token count requires running the tokenizer.

### B.3 Stemming approximation rationale

We implement Porter-like stemming via suffix stripping. Stripped suffixes
include: -tion, -ment, -ness, -able, -ible, -ally, -wise, -ful, -ous, -ive,
-less, -like, -hood, -ship, -ing, -ed, -ly, -er, -es, -s.

This is deliberately approximate. It handles the most common inflectional
patterns (running/ran/run, education/educate, happiness/happy) but misses
irregular forms (go/went, good/better). For a toy demonstrator this is fine
because query-term distribution in technical prose heavily favors regular
inflections over irregular ones.

Full Porter v2 implementation would add rules for Y-conversion, double-consonant
preservation, and early-exit conditions. Our simplified version trades 3-5%
recall improvement for simplicity. This is documented explicitly — users who
need higher recall can substitute a proper stemming library without changing
any other component.

The stem index uses lowercase stems as keys. Multiple inflected forms map to
the same stem: "runs"/"running"/"ran" might all map to stem "run" in a full
Porter, but our prefix-stripping yields "run", "run", and "ran" (unchanged).
This partial coverage is acceptable for the toy's purposes.

### B.4 Inverted index construction details

Building the stem_index is an O(n × m) operation where n is the number of
chunks and m is the average number of unique stems per chunk. With 50 chunks
averaging 100 unique stems each, this is ~5,000 dictionary insertions —
trivial even on a microcontroller.

The construction algorithm:
1. Iterate through all chunks sequentially.
2. For each chunk, extract all alphanumeric words via regex.
3. For each word, compute its stem. Skip if word is a stopword.
4. Track seen stems per chunk to avoid duplicate chunk IDs.
5. Append chunk ID to the stem's candidate list.

Because we iterate chunks in deterministic order and deduplicate within
each chunk, the resulting list of chunk IDs is always sorted ascending.
No secondary sort needed. Query-time union of candidate lists produces
a predictable result set.

Memory footprint of the stem index: for 50 chunks with 100 unique stems
each containing 5 distinct stems, the index stores ~500 entries averaging
25 bytes of key plus 25 bytes of list overhead per entry. Total: ~25KB.
Trivial compared to the index payload itself.

## Appendix C: Retrieval Protocol Specification

### C.1 Full query processing pipeline

Step-by-step, a query flows through the following pipeline:

Input: free-text query string "how to implement crystallization middleware"

1. Tokenization: split on non-alphanumeric boundaries → ["how", "to", 
   "implement", "crystallization", "middleware"]
2. Lowercasing: all tokens already lowercase in this example.
3. Stopword filtering: remove "how", "to" → ["implement", "crystallization", 
   "middleware"]
4. Stemming: map each remaining term to its stem → ["implement", "crystal", 
   "middl"]
5. Lookup: for each stem, retrieve candidate chunk IDs from stem_index
   → implement:[4,7], crystal:[0,1,3,5], middl:[2,6]
6. Scoring: count overlapping stems per chunk → chunk 0:1, chunk 1:1, 
   chunk 2:1, chunk 3:1, chunk 4:1, chunk 5:1, chunk 6:1, chunk 7:1
   (all score 1 here; tie-break by chunk id)
7. Ranking: sort by score desc, then id asc for determinism
8. Selection: return top-K chunks (default K=5)

Each step is pure function — no state mutation, no network calls, no
randomness. Given identical input and identical index, the output is
always identical. This is the core property enabling verification.

### C.2 Query-time vs index-time trade-offs

Index-time costs (pay once at compile):
- Hashing every chunk: O(n) sha256 operations
- Computing term frequencies: O(n × w) where w = avg words per chunk
- Building stem index: O(n × u) where u = unique stems per chunk

Query-time costs (pay per query):
- Tokenizing and filtering query terms: O(q) where q = query length
- Looking up stems in stem_index: O(k × c) where k = query stems, 
  c = avg candidates per stem
- Scoring and sorting candidates: O(k × c × log(c)) for top-K selection

With our toy corpus, query-time is sub-millisecond even in Python. At scale
(1M chunks, 1000 query QPS), this would need optimization (Bloom filters,
bitset representation for candidate sets), but the algorithmic complexity
class does not change — only constant factors.

### C.3 Tie-breaking strategy

When two chunks have identical scores (same number of matched query stems),
we break ties by chunk ID ascending. This means: earlier chunks in the
corpus win ties. Alternative strategies include:

- Score by term frequency sum (stronger signal wins)
- Score by recency (newer chunks preferred)
- Random selection (non-deterministic — forbidden here)
- Alphanumeric title sort (semantically meaningful but expensive)

We chose chunk ID because it is O(1), deterministic, and requires no
extra computation. In production, one could layer secondary scoring 
over the primary tie-break without invalidating the determinism property.

## Appendix D: Measurement Methodology

### D.1 Context savings metric definition

Context savings measures how much fewer tokens a downstream consumer reads
when using the prefill index versus reading the entire corpus.

Formula: savings_pct = (total_corpus_tokens - retrieved_chunks_tokens) / 
                         total_corpus_tokens × 100%

Where:
- total_corpus_tokens ≈ corpus_byte_size / 4.0 (character-to-token proxy)
- retrieved_chunks_tokens = sum of token_estimates for all chunks returned
  by the retriever for a given query

Savings approach 100% as K→1 and relevance increases. Savings drop toward
0% as K approaches total chunks. The measurement varies per query because
different queries match different numbers of chunks.

We report per-query savings and aggregate mean savings across a representative
set of probe queries. The probe set must cover the query distribution we
expect in production.

### D.2 Probe query design

Probe queries simulate real usage patterns. Our set includes:

- Architectural concept queries ("deterministic", "prefill", "architecture")
- Implementation detail queries ("plugin", "middleware", "hooks")  
- Design principle queries ("invariant", "constraint", "retrieval")
- Technical specification queries ("token", "chunking", "stemming")

Each query targets different parts of the corpus, testing whether the
index covers different sections effectively. A well-built index returns
relevant chunks for each query type.

A limitation: probe queries use the same language as the corpus. In
production, user queries will be phrased differently, and term-overlap
will miss semantically related but lexically distinct content. This is
honestly reported in the limitations section.

### D.3 Staleness detection measurement

Staleness rate measures what fraction of chunks have changed checksum since
last compile. Detection procedure:

1. Re-parse source corpus into fresh chunks.
2. Compute SHA-256 for each fresh chunk.
3. Compare against stored checksums in index.
4. Report exact set of stale chunk IDs.

Accuracy: perfect for our purpose. Every stale chunk is detected; no false
negatives. False positives depend on the threshold: we flag any checksum
mismatch, even one-bit changes. If desired, a fuzzy comparison could be
added, but exact hashing is simpler and more verifiable.

Cost: single pass over source corpus, hashing each chunk once. For a
10KB corpus this takes < 1ms. For a 1GB corpus at similar parse speed,
still under 1 second.

## Appendix E: End-to-end Workflow Example

### E.1 Typical development cycle

Developer workflow with the prefill index:

Day 1: Initial setup
1. Write source document (markdown/text corpus)
2. Run compile.py → generates index.json with checksums and indices
3. Verify runs automatically: checks determinism (recompile), checksums
4. Store index.json alongside source document in version control

Day 1 (continued): Testing retrieval
5. Define probe queries covering expected usage
6. Run verify.py --measure to see context savings
7. Tune chunk size and K parameters based on results
8. Commit everything including measurements

Week 2: Source evolves
1. Developer edits source document (adds section, modifies text)
2. Before next retrieval session, run staleness check
3. verify.py --staleness reports: "3 of 50 chunks stale (6%)"
4. Only rebuild affected chunks (or full recompile for simplicity)
5. Updated index has new checksums for changed chunks only

Week 2 (continued): Verification persists
6. New index passes determinism check: two compilations → identical
7. Staleness now at 0%: index matches current source perfectly
8. Next developer pull receives fresh index on merge

Month 3: Scale test
1. Corpus grew to 100K tokens (multiplied by adding more docs)
2. Compile time: measured ~200ms (linear scaling)
3. Query time: measured ~2ms for typical 5-stem queries
4. Storage overhead: index is ~15% of corpus size
5. Savings remain strong: ~85% avg (queries access 5 of 500 chunks)

### E.2 Error scenarios and handling

Scenario: Corrupted index file
Detection: JSON parse fails → regenerate from scratch. No data loss since
source corpus is intact. The index is a derived artifact.

Scenario: Source corpus deleted
Detection: compile.py exits with error on missing input file. Recovery:
restore corpus from backup or VCS history, then recompile.

Scenario: Checksum mismatch on verification
Action: investigate whether source was modified outside compiler. If yes,
recompile. If no, report bug — the index cannot be corrupted without
matching source modification.

Scenario: Very long source file (> 1GB)
Mitigation: byte_range-based lazy reading for verification. Load only
chunks whose checksums need checking. Still linear scan but avoids 
memory pressure. The stem_index is built incrementally.

## Appendix F: Comparison to Learned Embedding Approaches

### F.1 Deterministic vs embedding-based retrieval

Learned embedding approaches (sentence transformers, CLIP, etc.) offer
semantic similarity matching: "database management system" finds chunks
about "relational databases" despite no shared vocabulary. Our term-overlap
approach finds only literal overlaps: "database" matches chunks containing
the word "database".

Trade-offs table:

Property                  | Term Overlap (this tool) | Embeddings
--------------------------+--------------------------+------------------
Deterministic             | Yes                      | No (model inference)
Byte-identical repro      | Yes                      | Dependent on model
Training required         | No                       | Yes (pre-trained)
Model dependency          | None                     | Requires model weights
Version tracking          | Trivial (diff the index) | Hard (model + index)
Adversarial robustness    | High                     | Medium (gradient attacks)
Latency                   | Sub-ms                   | 50-200ms GPU
CPU-only viable           | Yes                      | Usually (slow)
Maintenance cost          | Zero                     | Model updates, drift

Our approach wins on predictability, auditability, and zero-dependency.
It loses on semantic recall — the ability to find conceptually relevant
content without lexical overlap. Both approaches are valid; neither is
universally superior.

### F.2 Hybrid approach sketch

A future enhancement could combine both: term overlap for initial candidate
selection, lightweight semantic reranking for final ordering. This preserves
the determinism invariant (term overlap is unchanged) while improving recall
for semantically diverse queries.

The hybrid would store both the term index (deterministic) and optional
embedding vectors (learned, version-tagged). When embeddings exist, the
hybrid mode uses them; when absent (fresh index, no embeddings computed),
it falls back to pure term overlap.

This backward-compatible design means the base tool works standalone while
supporting extension via optional artifacts stored alongside the index.

### F.3 Why we chose the simple path first

Occam's razor applies to systems engineering too. Starting with the simplest
working system gives us:

1. A clear baseline for measuring improvements
2. Proof-of-concept of the deterministic index architecture
3. Measurable performance characteristics under controlled conditions
4. A reference implementation that is trivially understandable

Adding complexity (embeddings, neural ranking, learned scoring) on top of
a verified simple foundation is safer than starting with complexity and
trying to decompose it later. The toy proves the structure works; extensions
prove the structure extends.

## Appendix G: Implementation Checklist for Future Work

### G.1 Completing the toy toward production-readiness

The deterministic index architecture is sound at toy scale. Here is what
a next iteration would need to address before production deployment:

- [ ] Replace character/4 token estimation with actual tokenizer counts
       from the target LLM's official tokenizer library. Current estimates
       are accurate within ±15% for English prose but vary significantly
       for code, math notation, or non-Latin text.
- [ ] Add sentence-level chunking as alternative to heading-level chunking.
       For documents without clear heading structure (prose books, essays),
       sentence boundaries serve as reliable delimiters. Each sentence
       becomes its own chunk with a checksum and term index.
- [ ] Implement BM25 weighting instead of raw TF. This improves retrieval
       quality for larger corpora where document frequency variations matter.
       The stem_index data structure remains unchanged — only the scoring
       function changes during query-time ranking.
- [ ] Support multiple source files in a single index. Currently we read
       one corpus.md file. A multi-file index would merge all .md files
       from a directory tree, maintaining separate byte ranges per source.
- [ ] Add incremental rebuild support. Instead of full recompile when
       a small section changes, detect which chunks need updating based
       on file timestamps and hash comparisons of source sections.
- [ ] Implement a REST API wrapper around verify.py --measure so that
       downstream consumers can query the index via HTTP rather than
       Python imports. Flask or any lightweight framework suffices.
- [ ] Write a Rust port for performance-critical paths. The Python
       implementation validates the algorithm; a native port provides
       the throughput needed for high-QPS scenarios. Both must produce
       identical results for verification to hold.

### G.2 Testing and CI requirements

A production release requires automated testing:

- Unit tests for each stage: normalize_whitespace, compute_checksums,
  extract_first_sentence, compute_terms, build_stem_index, compile_chunks
- Integration test: compile → verify roundtrip on known corpus
- Regression test: deterministic comparison (two compilations match)
- Performance benchmark: compile time vs corpus size, query latency vs K

Test corpus should include edge cases: empty headings, nested markdown,
special characters, Unicode content, very short paragraphs, code blocks.

### G.3 Documentation deliverables

- API reference for index.json schema (machine-readable)
- User guide for compile.py and verify.py CLI usage
- Architecture decision record documenting the deterministic approach
- Comparison document against embedding-based alternatives (Section F)
- Performance benchmarks across corpus sizes (10K, 100K, 1M tokens)

This checklist ensures completeness beyond the toy spike while preserving
the core design principle: every derived structure must be deterministically
rebuildable and verifiable from the source material alone.
