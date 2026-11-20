# Haystack Crystallization Map

**Purpose:** Audit of `~/Documents/code/haystack` for crystallization potential and NO-LLM compatibility. Every decision classified as **already crystallizable** (deterministic/threshold-driven, ready for a policy crystal) or **NO-LLM gap** (requires model opinion today).

---

## CRYSTALLIZABLE NOW

Decisions currently made by heuristic/threshold/config — they are measurable policies that could become mutation targets for a genetic algorithm or gateable config policy.

### 1. Dense / Lexical Fusion Weight (`wv`)

| Field | Detail |
|---|---|
| **Where** | `haystack.py:rank()` line 646–656 |
| **What** | `dense_weight` default 0.7 from config. Adaptive override: `wv = 1 / (1 + exp(-(mean_df - 3.0)))`, clamped `[0.2, 0.9]`. Rare-term queries lean lexical; common-vocab lean dense. |
| **Evidence stream** | qa_gen.json pairs: run recall@3/MRR per fused weight sweep (grid of 11 values). Pick-encoder already has the harness. Stale pairs auto-excluded by guard. |
| **Crystal genome** | `{dense_weight: float}` + `{adaptive_idf: bool}`. Mutation changes the two floats. No structural mutation needed. This is literally one float parameter. |
| **Gate** | Recall@3 must not regress on the live vault eval set vs incumbent. Measured as +/- delta, not absolute. |

### 2. Learned Pin Boost Strength

| Field | Detail |
|---|---|
| **Where** | `haystack.py:learn_lookup()` line 272 |
| **What** | `strength = 0.10 * sim * min(hits, 3)`. The 0.10 base multiplier, sim multiplication, and cap at hits=3 are all tunable parameters. |
| **Evidence stream** | audit learned corrections pass rate. For each taught correction, measure how many queries reproduce the same pin. Also measure over-pinning: does the pin drown out genuinely semantically better results? |
| **Crystal genome** | `{base_multiplier: float, scale_factor: float, hits_cap: int}`. Three scalar parameters. Mutation alters any subset. |
| **Gate** | audit learned-pass-rate must stay ≥ incumbent OR +0.5pp. Must verify no regression on non-pinned queries. |

### 3. Learned Pin Match Threshold (Pin Firing Rule)

| Field | Detail |
|---|---|
| **Where** | `haystack.py:learn_lookup()` lines 257–270 |
| **What** | A pin fires when `sim > 0.60 AND sim >= corpus_best + 0.01`. The 0.60 floor and the 0.01 margin above corpus-best are configurable heuristics. Scale-free rule (relative to corpus, not absolute), but both threshold values are heuristic. |
| **Evidence stream** | learn_lookup outcomes logged as "pin fired" events. Track precision: of all queries where a pin fired, was the pinned path actually desired? Recall: of all desired-pin queries, did the pin fire? |
| **Crystal genome** | `{floor_threshold: float, margin_above_corpus: float}`. Two floats. Mutation changes both independently or jointly. |
| **Gate** | Precision must not drop below baseline (approx. 0.90+ on lived pins). Recall can trade off freely against precision. |

### 4. Snippet Truncation Length

| Field | Detail |
|---|---|
| **Where** | `haystack.py:query()` line 759 (`[:180]`) |
| **What** | Output snippets cut at 180 chars. Configured nowhere; hardcoded. |
| **Evidence stream** | Human-in-the-loop: show users N-char truncations and ask if the truncated snippet gives sufficient context. Or: ablation where agent reads full snippet vs truncated, measure agent correctness downstream. |
| **Crystal genome** | `{snippet_length: int}`. Single integer. |
| **Gate** | Agent downstream performance on tasks triggered by these snippets doesn't degrade. |

### 5. Chunk Size Window & Step Parameters

| Field | Detail |
|---|---|
| **Where** | `haystack.py:chunks_of()` lines 171–177 (long-section sliding window) |
| **What** | `step=800, win=1000`. Sections longer than ~1000 chars get split into overlapping windows of 1000 chars stepped by 800. Minimum segment: 200 chars (line 175). List-heavy files (n_list > 20 AND len > 60): split to ~6-line chunks (line 161). |
| **Evidence stream** | Re-index with different step/win combos. Run eval on qa_gen.json. Measure Recall@3 change per window size. Also: measure token compression ratio (token_metrics.py already measures this for retrieval output; need input-side metric: total indexed tokens vs original file tokens). |
| **Crystal genome** | `{step_size: int, window_size: int, min_segment: int, list_chunk_size: int}`. Four integers. Could also include the list-trigger thresholds `{list_count_threshold: int, file_length_threshold: int}`. |
| **Gate** | Recall@3 and MRR must not degrade. Index build time can improve (larger windows = fewer chunks). Token savings measured via token_metrics.py. |

### 6. Title Mask Boost Factor

| Field | Detail |
|---|---|
| **Where** | `haystack.py:rank()` line 638 |
| **What** | `title_mask = 1.15 if heading in ("(title)", "(top)") else 1.0`. Hardcoded 1.15 factor applied to both dense and lexical ranking streams equally. |
| **Evidence stream** | Sweep the title mask from 1.0 to 2.0 in 0.05 increments on qa_gen.json. Record Recall@3 curve. Check if certain query types benefit more from title boost. |
| **Crystal genome** | `{title_mask_top: float, title_mask_title: float}`. Two floats (separate top/title masks potentially beneficial). |
| **Gate** | MRR must not regress. Top-1 accuracy can be tracked specifically for title-matching queries. |

### 7. Lexical Boost IDF Scaling Constant

| Field | Detail |
|---|---|
| **Where** | `haystack.py:lexical_boost()` lines 559–566 |
| **What** | `idf = 0.25 * min(3.0, log(n/df) + 0.5)` then `boost += idf * tf` then `return 0.10 * boost`. The 0.25 scaling inside IDF, the 3.0 ceiling, the 0.5 offset, and the final 0.10 multiplicative factor. TF capped at 2.0 (line 564). |
| **Evidence stream** | Grid sweep of all five parameters against qa_gen.json. The impact is likely small relative to dense weight, but worth measuring since lexical-only queries go entirely through this path. |
| **Crystal genome** | `{idf_scale: float, idf_ceiling: float, idf_offset: float, boost_scalar: float, tf_cap: int}`. Five parameters. |
| **Gate** | Recall@3 on lexically-dominated queries (those with no dense signal) must not regress. |

### 8. Rare-Token Identifier Bonus

| Field | Detail |
|---|---|
| **Where** | `haystack.py:rank()` lines 661–666 |
| **What** | When a query term appears in ≤ 3 documents (`df <= 3`), those docs get +0.03 bonus. This catches technical identifiers (specific product names, version strings). |
| **Evidence stream** | Count how often df≤3 terms appear in live queries. Track how many queries resolve solely via this bonus. Measure the boundary: what df threshold optimizes precision? (3 seems chosen intuitively.) |
| **Crystal genome** | `{df_threshold: int, bonus_value: float}`. Two params. |
| **Gate** | Don't let rare-token matches displace correct answers in top-1. |

### 9. Filename Segment Completion Bonus

| Field | Detail |
|---|---|
| **Where** | `haystack.py:rank()` lines 672–680 |
| **What** | When query covers ALL segments of a CamelCase filename stem (e.g., "anti skill tree" → AntiSkillTree.md), the file's title chunk gets +0.04. Requires ≥ 2 segments. |
| **Evidence stream** | Catalog filename-style queries in audit logs. How often does this bonus correctly identify the target? How often does it misfire on files sharing substring segments? |
| **Crystal genome** | `{segment_bonus: float, min_segments: int}`. Two params. |
| **Gate** | No misfires on shared-prefix filenames. |

### 10. INDEX.md / Hub Demotion Rules

| Field | Detail |
|---|---|
| **Where** | `haystack.py:rank()` lines 695–711 |
| **What** | Two-tier rule: (a) superseded files get ×0.40 multiplier. (b) hub files (INDEX.md) get ×0.92 ONLY when a content chunk is within 0.92× the hub's score (tie-breaker, not elimination). Dominant hubs survive. |
| **Evidence stream** | Query INDEX.md-targeting queries: do dominant hubs correctly surface? Do competitive content chunks correctly suppress the hub? Review eval misses involving INDEX.md. |
| **Crystal genome** | `{superseded_multiplier: float, hub_demote_factor: float, hub_competitiveness_ratio: float}`. Three floats. |
| **Gate** | Content notes outrank INDEX.md for substantive queries; INDEX.md ranks first for meta-queries about the vault structure. |

### 11. Temporal Boost Weights

| Field | Detail |
|---|---|
| **Where** | `haystack.py:temporal_boost()` line 334–335; config `config.toml` lines 37–42 |
| **What** | `weight=0.008` (file mtime recency boost), `asked_weight=0.004` (previously-queried-path boost). Both additive on fused score. Already partially crystallized in config, but values are heuristic defaults. |
| **Evidence stream** | Review temporal query volume. Measure the impact of these weights on relevant queries vs side-effects on non-temporal queries (should be zero by construction, but verify). Compare different weight ratios. |
| **Crystal genome** | `{recency_weight: float, asked_weight: float}`. Two floats. |
| **Gate** | Temporal queries should prefer recent answers; non-temporal queries unchanged by construction. |

### 12. Embed Resilience Strategy

| Field | Detail |
|---|---|
| **Where** | `haystack.py:embed_resilient()` lines 84–99 |
| **What** | On HTTPError (chunk exceeds context): single-chunk case → skip + log. Multi-chunk case → binary split recursively. This is a deterministic fault-handling policy. |
| **Evidence stream** | Track "embed-skip" events in logs. Rate of skipped chunks per corpus. Does skipping hurt recall? (It shouldn't matter much — the skipped chunk is too big for ANY model.) |
| **Crystal genome** | N/A — this is already a robust deterministic strategy. Not really a crystal candidate (it works correctly; the question is whether we even need resilience when embeddings are eliminated from stage 2). |

### 13. Cluster Enablement Gate

| Field | Detail |
|---|---|
| **Where** | `haystack.py:cluster_boost()` lines 572–573; config `config.toml` line 48 |
| **What** | Clusters are enabled=false because content-derived clusters scored NEGATIVELY (-1pp MRR at every tested weight). The gate itself is a measured crystallized decision. But if clusters ever come from USAGE patterns (not text), the weight and margin thresholds would be new crystals. Current: `{enable: false}` is the crystal. |
| **Crystal genome** | `{enable: bool}`. Already frozen. |
| **Gate** | Would reopen when usage-based clustering is implemented. |

### 14. Reindex Trigger Logic

| Field | Detail |
|---|---|
| **Where** | `haystack.py:reindex()` lines 411–459 |
| **What** | Mtime + SHA-256 hash comparison drives incremental reindex. Files with unchanged hash are skipped. Deleted files are removed from index. If n_new > 0 AND n_del > 0 → reanchor stale pins (content-hash match first, semantic-fallback second). |
| **Evidence stream** | How often is the semantic-reanchor used? What fraction of pins need reanchor? Is semantic matching accurate enough? Hash-only reanchor should handle 99%+ of cases (renames); semantic is fallback for edits. |
| **Crystal genome** | `{semantic_reanchor_margin: float, semantic_reanchor_floor: float}` — the same thresholds from reanchor(). These ARE already crystallized in the code (lines 398–399). The reindex trigger itself is event-driven (user invocation), not a continuous policy. |

### 15. Alias Mining Thresholds

| Field | Detail |
|---|---|
| **Where** | `haystack.py:mine_aliases()` lines 1288–1316; `config.toml` not present (hardcoded: `min_folder_df=2`, `max_corpus_df=3`) |
| **What** | Tokens frequent inside a folder (≥ 2 times) and rare outside (≤ 3 times total) are nickname candidates. Nothing auto-taught — offered to user for `learn`. |
| **Evidence stream** | Of alias candidates presented, how many did the user actually adopt via `learn`? Track adoption rate per threshold combo. |
| **Crystal genome** | `{min_folder_frequency: int, max_corpus_frequency: int}`. Two integers. |
| **Gate** | High adoption rate (> 30% of candidates adopted). Low false-positive rate (candidates that were NOT nicknames). |

---

## NO-LLM GAPS / ISSUES FOR STAGE 2

Everything that would break or degrade if NO model whatsoever runs at query time.

### 1. EMBEDDINGS: THE MODEL THAT IS ALSO AN LLM PROXY

| Gap | Detail |
|---|---|
| **File/Line** | `haystack.py:embed()` lines 73–81 |
| **Reality** | Every query goes through `embed([text])` → HTTP POST to an OpenAI-compatible `/v1/embeddings` endpoint. In the reference setup: llama.cpp serving bge-small-en GGUF or granite-97m on :8082. |
| **Law violation?** | This IS a model — just not a *generative* LLM. It's a 384-dim embedding model (~35 MB for BGE, ~98 MB for Granite). Cosine similarity computation depends on these vectors being meaningful. For a "no LLM at runtime" architecture, embeddings either: (a) stay (embedding models are fundamentally different from LLMs — they don't reason, hallucinate, or cost per-token at inference time), or (b) require a purely deterministic matcher. |
| **Verdict** | **Flagged as unresolved.** The stage 2 architect must decide: is an embedding model acceptable under "no LLM"? If yes, it becomes the "matcher" layer. If no, semantic matching must be replaced by deterministic string/structure-based approaches (BM25-like keyword matching with dictionary lookups). The hybrid dense+lexical architecture would collapse to lexical-only unless replacement semantics exist. |
| **Impact on architecture** | Without embeddings: lose paraphrase matching, synonym understanding, cross-language retrieval. Keep: exact-match keywords, prefix matching, structured field matching (title vs body vs date). The entire RRF fusion with dense component vanishes. The learned-correction pin system loses its core mechanism (cosine similarity against pin vectors). |

### 2. CROSS-ENCODER RERANKER

| Gap | Detail |
|---|---|
| **File/Line** | `haystack.py:rerank()` lines 721–753 |
| **Reality** | Optional (url empty → disabled). When enabled: posts {query, documents[:max_chars]} to `url/rerank`. Default: ms-marco-MiniLM-L12-v2 on :8084. Latency ~450ms-1.5s depending on `top` setting. |
| **Law violation?** | Violates **D3** (relevance judgment at query time is the bottleneck). A NO-LLM architecture would need relevance to be O(1)-ish or pre-computed. |
| **Verdict** | **Eliminatable.** The reranker provides +2.9pp Recall@3 (RESEARCH.md P1 addendum 2) but costs 450ms+. A deterministic alternative would be: pre-rank during indexing (annotate chunks with metadata tags, topic labels derived from structure), then use pre-computed metadata to order candidates. Or: skip reranking entirely and accept the ~2.9pp difference. The teacher-beats-model invariant (D1) already pins learned corrections ahead of rerank, making the reranker's effect bounded. |
| **Crystal candidate** | `{rerank_enabled: bool, rerank_quality_threshold: float}` — whether rerank quality gain justifies the latency budget. Currently answered empirically (+2.9pp ≈ keep it). Stage 2: answer differently (latency budget → 0ms → disable). |

### 3. EVAL-GEN: SYNTHETIC QA GENERATION VIA LLM

| Gap | Detail |
|---|---|
| **File/Line** | `haystack.py:_llm()` lines 1063–1089; `eval_gen()` lines 1092–1133 |
| **Reality** | Uses the chat completions endpoint (`url/v1/chat/completions`) to generate synthetic owner-style queries for notes, creating the ground truth for large-scale evaluation. Default endpoint: `http://127.0.0.1:8081` (LFM3 1.7B reasoning model). |
| **Law violation?** | Uses LLM for query generation (synthetic data creation). Not a runtime retrieval operation, but part of the evaluation infrastructure. |
| **Verdict** | **Not a runtime gap**, but means stage 2 cannot validate itself using the existing eval-gen pipeline. Alternative: human-curated eval sets (like the current 8 hand pairs), or template-based query generation (fill-in-the-blank patterns derived from note structure). |

### 4. CONFLICTS --VERIFY: CONTRADICTION JUDGMENT VIA LLM

| Gap | Detail |
|---|---|
| **File/Line** | `haystack.py:conflicts()` lines 781–829, especially `_llm()` call at lines 822–829 |
| **Reality** | The `--verify` flag sends excerpts of high-similarity cross-file pairs to an LLM to judge CONTRADICT/DUPLICATE/NEUTRAL. Comment explicitly says "UNSCORED until the judge is benchmarked." |
| **Law violation?** | Uses LLM for contradiction detection. Ship-and-forget mode (without --verify) works fine (report-only). |
| **Verdict** | **Non-critical.** The core conflict scan (cosine pre-filter, 0.80-0.97 range, report-only candidates) is fully deterministic. The LLM verify is optional and unscored. For stage 2, contradiction detection would need a different approach entirely: compare semantic topics of conflicting passages, or rely on the `superseded_by` frontmatter convention (which is already deterministic). |

### 5. TOKEN COUNTING: CHARS/4 HEURISTIC VS REAL TOKENIZER

| Gap | Detail |
|---|---|
| **Files/Lines** | `scripts/token_metrics.py` line 20: `CHARS_PER_TOKEN = 4.0`; `haystack.py` snippet formatting uses char counts (180 chars at line 759, 1000 at line 187, 600 at line 732) |
| **Reality** | Token metrics estimates tokens as `len(text) / 4.0` — a 4.0 chars-per-token heuristic appropriate for English prose. Actual tokenizer behavior varies: Chinese/technical text may be closer to 2 chars/token; pure ASCII code closer to 3.5. |
| **Law violation?** | Directly violates **D8** (only the tokenizer can validate length). The comment at line 189 says "BGE ctx=512 tok" — assumes 1000 chars ≈ 512 tokens, which aligns roughly with 4.0 char/token. |
| **Verdict** | **Known approximation.** Token_metrics.py explicitly states it's a rough estimate. For stage 2, a real tokenizer (sentence-transformers' tokenizer for BGE, or tiktoken/bpe for multilingual) would be needed for accurate token accounting. The 4.0 heuristic is fine for comparative ratios but wrong for absolute budgets. |

### 6. CHUNKING CONTEXT WINDOW ASSUMPTION: 1000 CHARS

| Gap | Detail |
|---|---|
| **File/Line** | `haystack.py:chunks_of()` line 187: `txt = (ctx + "\n" + txt)[:1000]` |
| **Reality** | Non-title chunks truncated to 1000 chars. The comment says "BGE ctx=512 tok" implying 1000 chars ≈ fits in context. This assumes char/token ratio of ~2 for the embedder's tokenizer. |
| **Law violation?** | Another D8 violation: assuming context window capacity based on character count. Different embedders have different tokenizers with different vocabularies and thus different char→token ratios. |
| **Verdict** | **Needs real tokenizer integration** for stage 2. Until then: documented assumption (current embedders tolerate up to 1000 chars; oversized chunks hit llama.cpp's 500 error → handled by `embed_resilient`). |

### 7. CLUSTER K SELECTION

| Gap | Detail |
|---|---|
| **File/Line** | `haystack.py:cluster()` line 494 |
| **What** | `k = int(config.get("clusters.k", 0)) or max(4, round(sqrt(num_files)))`. When unset, auto-selects k = √(file count), floored at 4. |
| **Current state** | Cluster boosting is experimentally dead (enable=false after -1pp MRR testing). The k-selection formula is a heuristic but irrelevant until clusters are revived. |
| **Future crystal** | If clusters revive (from usage patterns instead of content), k would need elbow-method or silhouette-score measurement. Auto-k via √N is heuristic. |

### 8. SNIPPET TRUNCATION: 180 CHAR HARDCODE

| Gap | Detail |
|---|---|
| **File/Line** | `haystack.py:query()` line 759: `texts[i][:180]`; also `server.py` line 71: same |
| **Reality** | Output snippets are hard-truncated at 180 chars. No newline handling, no word-boundary awareness. Can produce half-word fragments. |
| **Impact** | Pure display concern. Doesn't affect retrieval quality. But for "is this the BEST organization" question: does 180 chars give users enough context to decide if they want to open the file? Empirically unknown. |
| **Crystal candidate** | `{snippet_length: int}` — already listed in section 4 above. |

### 9. LEARNED PIN BOOST SCALING: `min(hits, 3)` SOFT CAP

| Gap | Detail |
|---|---|
| **File/Line** | `haystack.py:learn_lookup()` line 272: `strength = 0.10 * sim * min(row["hits"], 3)` |
| **Reality** | Each learning interaction increases `hits` counter (capped at 3). The hard cap at 3 means repeated corrections beyond 3 learnings provide no additional signal. Is 3 the right cap? Maybe 5 or 7 would capture stronger preferences. |
| **Crystal candidate** | `{hits_max: int}` — already listed in section 2 above. |

### 10. TEMPORAL WINDOW PARSING: FIXED TIME SPANS

| Gap | Detail |
|---|---|
| **File/Line** | `haystack.py:parse_when()` lines 306–327 |
| **Reality** | Recognized expressions: "last N day(s)/week(s)/month(s)", "N day(s)/week(s)/month(s) ago", "yesterday", "today/morning/night/later today", "this week", "last week", "this month". Month = 30 days, week = 7 days. Midnight defined as `now - now % day - timezone`. |
| **Gap** | No "next week/month", no specific dates ("on November 15"), no relative expressions ("two months ago"). Fixed calendar assumptions (day always 86400s regardless of DST). Week starts Monday implicitly (via midnight calculation). |
| **Verdict** | Partial coverage is acceptable as a start. For stage 2: same regex-based parsing is already deterministic — no LLM needed. The gaps are feature completeness, not architecture violations. |

---

## VAULT-ORGANIZATION QUESTION

**"Is this the BEST organization?"** — what would need measured:

1. **Depth vs breadth**: Average subdirectory depth of notes vs recall rate. Deeper hierarchies → lower recall? Evidence: measure query paths through directory tree vs flat structure.

2. **Naming consistency**: Are synonyms/referents for the same concept grouped? Evidence: mine aliases (`mine_aliases()`) and check if distinct folders reference the same concept. This requires cross-folder token analysis (the existing function does folder-level only).

3. **Cluster validity**: Are existing manual folder structures aligned with emergent semantic clusters? Evidence: compare manual folder assignments against k-means cluster assignments (Jaccard overlap). Currently disabled (enable=false) but the methodology exists in `cluster()`.

4. **Hub-vs-content separation**: Are INDEX.md files doing useful routing or causing confusion? Evidence: measure queries where INDEX.md ranked #1 vs queries where it blocked content.

5. **Temporal decay**: Do old notes accumulate without being superseded? Evidence: track mtime distribution vs superseded_by count. Notes older than X months without supersede or query hits = staleness signal.

---

## TOP-5 CRYSTALLIZATIONS TO IMPLEMENT NEXT

Ranked by: measurability × impact × simplicity (can be done as a single float/int parameter change with clear gates).

### #1: Adaptive Fusion Weight (`dense_weight`)

- **Why**: Biggest lever with smallest risk. The logistic-sigmoid adaptive IDF already exists (line 647–656) but uses a hard-coded mean_df=3.0 pivot. Sweeping this pivot value and the base weight simultaneously would optimize per-query routing. Current empirical result: RRF fusion alone (no rerank) achieves 0.971 Recall@3; rerank adds +2.9pp. Better adaptive fusion could narrow that gap to near-zero, making rerank dispensable.
- **Mutation space**: `{dense_weight_base: float ∈ [0.3, 0.9], adaptive_pivot_df: float ∈ [1.0, 5.0], adaptive_clamp_lo: float ∈ [0.1, 0.5], adaptive_clamp_hi: float ∈ [0.7, 0.95]}` — 4 floats.
- **Gate**: Recall@3 must not regress on qa_gen (55 pairs). MRR can trade off.
- **Effort**: ~2 hours (existing code, just parameterize and sweep).

### #2: Learn Lookup Threshold Tuning

- **Why**: Pins are haystack's primary "teacher beats model" invariant. If pin thresholds are mis-calibrated, the teacher signal gets drowned (granite showed this: wrong pin firing on sim 0.206 destroyed top-3). The current scale-free rule (beats corpus best by 0.01) is clever but the floor (0.60) and margin (0.01) are unconstrained guesses.
- **Mutation space**: `{floor_threshold: float ∈ [0.40, 0.80], margin_above_corpus: float ∈ [0.001, 0.05]}` — 2 floats. Plus `base_multiplier` (0.10 → sweep 0.05 to 0.20).
- **Gate**: Learned correction audit pass rate ≥ 0.95. No new incorrect pins introduced.
- **Effort**: ~1 hour (measure pin activations, sweep thresholds).

### #3: Chunk Window Optimization

- **Why**: Chunk size directly impacts token investment, retrieval granularity, and index rebuild speed. Larger windows = fewer chunks = cheaper indexing but potentially diluted semantic signal. Smaller windows = richer semantics but more embed calls. Current values (win=1000, step=800) came from intuition about BGE context window.
- **Mutation space**: `{window_size: int ∈ [500, 1500], step_size: int ∈ [200, 1200], list_chunk_size: int ∈ [3, 10]}` — 3 integers.
- **Gate**: Recall@3/MRR stable ±0.5pp. Total indexed tokens decrease (check token_metrics.py ratios).
- **Effort**: ~3 hours (re-index multiple configs, evaluate).

### #4: Superseded Demotion Multiplier

- **Why**: The 0.40 ×0 multiplier for superseded notes is a strong demotion but arguably arbitrary. Should it be 0.30 (stronger tombstoning) or 0.60 (gentler, allows accidental supersede reversibility)? The multiplier controls the "one-truth-per-fact" enforcement level.
- **Mutation space**: `{superseded_multiplier: float ∈ [0.20, 0.70]}` — 1 float.
- **Gate**: No superseded note returns as top-1 for any query where the replacement note exists. Replacement note must beat supersedes on related queries.
- **Effort**: ~1 hour (swap multiplier, run eval).

### #5: Alias Mining Frequency Thresholds

- **Why**: Alias mining produces candidates that can seed `learn` entries. Currently: ≥ 2 intra-folder appearances AND ≤ 3 corpus-wide appearances. Tightening these thresholds would reduce false positives (common words masquerading as project nicknames) but increase missed nicknames.
- **Mutation space**: `{min_folder_freq: int ∈ [1, 5], max_corpus_freq: int ∈ [1, 5]}` — 2 integers.
- **Gate**: Adoption rate (fraction of candidates actually used via learn) ≥ 25%. False positive rate ≤ 10% (candidates that aren't actual nicknames).
- **Effort**: ~2 hours (run mine_aliases, survey candidates, measure adoption).

---

*Generated by subagent reconnaissance. All findings derived from static code analysis of haystack.py v1.x (1398 lines), config.toml, SHORTCOMINGS.md, RESEARCH.md, and diamondhead/design.md (D1-D8). No code was modified.*
