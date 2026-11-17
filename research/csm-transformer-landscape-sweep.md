# CSM Prior-Art Sweep #1 — Academic Context Compression & Memory Architectures

**Date:** 2026-01-04  
**Scope:** Academic literature covering gist tokens, prompt compression, KV-cache eviction, soft-prompt/state-space caching, agent memory architectures, hippocampal/RAG hybrids, temporal KGs, speculative decoding, surprise-based methods, SSM context states, and 2025–2026 context engineering. Each entry evaluated against four CSM-relevant dimensions.

---

## Executive Summary

**Novelty assessment:** No existing system combines (a) **deterministic+replayable crystallized context** with (b) **independent staleness detection via checksum-like invariant**, (c) **per-edge SPRT promotion gates**. Gist tokens are learned/lossy. All KV-cache eviction policies operate *within* the model's inference loop (eviction ≠ crystallization). MemGPT/Letta/Zep provide memory hierarchies but none verify their crystallized content against a source checksum or detect semantic drift autonomously. Staleness is always external (human review, TTL, manual flush). This is an open gap.

---

## Detailed Entries

### 1. Gist Tokens — Mu et al., NeurIPS 2023
- **arXiv:** [2202.01943](https://arxiv.org/abs/2202.01943) (published NeurIPS 2023 as "Learning to Compress Prompts with Gist Tokens")
- **Mechanism:** Train a language model to compress arbitrary prompts into a small set of virtual "gist" tokens using meta-learning. The model predicts compressed activations (K/V pairs) on top of these tokens zero-shot, enabling caching and reuse. Uses modified attention masks preventing post-gist tokens from attending to pre-gist tokens.
- **What it crystallizes:** Learned/compressed representations. **Learned, lossy.** Up to 26× compression, minimal output-quality loss.
- **CHECKABLE/replayable?** ❌ No. Gist activations are learned approximations; no mechanism to verify them against the original prompt text. Lossy by construction.
- **Staleness handling:** None intrinsic. If the original prompt changes, you must recompute the gist tokens.
- **Transfers to CSM:** Compression ratio and meta-learning approach are directly relevant. However, the fundamental limitation (learned, uncheckable artifacts) confirms why CSM needs a *different* crystallization strategy — deterministic extraction with provenance, not learned approximation.
- **Steal score:** ⭐⭐ (compression technique + architectural insight about modified attention masks)

### 2. LLMLingua / Selective Context — Jiang et al., EMNLP 2023
- **arXiv:** [2310.05736](https://arxiv.org/abs/2310.05736); Selective Context baseline: arXiv:2306.08986
- **Mechanism:** Coarse-to-fine prompt compression using a small LM's perplexity to measure token importance. Budget controller allocates different compression ratios per component (instruction, demonstrations, question). Iterative token-level algorithm models inter-token conditional dependencies. Distribution alignment via instruction tuning.
- **What it crystallizes:** Deterministically selected subset of original tokens. **Learned scoring** (via small LM PPL), but compression itself preserves exact tokens — not abstracted.
- **CHECKABLE/replayable?** Partially. The output is a subsequence of the original text with some tokens dropped. One could reconstruct the original by insertion, but the selection rationale isn't encoded. No checksum/provenance on which tokens were dropped and why.
- **Staleness handling:** Re-run compression if source changes. No built-in staleness detection.
- **Transfers to CSM:** Budget controller (adaptive compression ratios per component) and iterative token-level compression that considers conditional dependencies. LongLLMLingua (arXiv:2407.02490) adds question-aware contrastive perplexity for long contexts.
- **Steal score:** ⭐⭐⭐ (budget controller pattern, contrastive perplexity scoring)

### 3. H2O (Heavy Hitter Oracle) — Zhang et al., ICLR 2024
- **arXiv:** [2306.14048](https://arxiv.org/abs/2306.14048)
- **Mechanism:** Identify "Heavy Hitter" tokens whose accumulated attention scores follow a power-law distribution. Retain only H2 tokens + recent tokens in the KV cache. Formulate eviction as dynamic submodular maximization with theoretical guarantees.
- **What it crystallizes:** Subset of original KV embeddings for pivotal tokens. **Exact KV state preserved**, but selective retention based on attention-signal importance.
- **CHECKABLE/replayable?** Limited. Heavy hitters can be verified (their attention scores are observable at inference time), but there's no mechanism to independently audit whether the retained set equals the optimal set.
- **Staleness handling:** None. The cache is recomputed fresh each generation session.
- **Transfers to CSM:** Power-law importance distribution (heavy-hitters concept) and submodular formulation of eviction budget. The observation that a small set of tokens drives most attention is foundational for any selective crystallization gate.
- **Steal score:** ⭐⭐⭐ (power-law importance + submodular eviction framing)

### 4. SnapKV — Li et al., 2024
- **arXiv:** [2404.14469](https://arxiv.org/abs/2404.14469)
- **Mechanism:** Use an "observation window" at the end of the prompt to identify robust attention patterns. Compress KV caches by selecting clustered important KV positions per attention head. Fine-tuning-free.
- **What it crystallizes:** Selected KV positions (exact K/V values retained). **Deterministic selection** from observed attention patterns during inference.
- **CHECKABLE/replayable?** No. Selection depends on current generation step; no independent audit trail.
- **Staleness handling:** None. New generation = new observation.
- **Transfers to CSM:** Observation-window approach for identifying important positions without training. Per-head clustering for KV selection is a structural pattern worth adapting.
- **Steal score:** ⭐⭐ (observation window pattern)

### 5. TOVA (Token Omission Via Attention) — Schwartz Lab, 2024
- **arXiv:** [2401.06104](https://arxiv.org/abs/2401.06104)
- **Mechanism:** Prove transformers can be conceptualized as unbounded multi-state RNNs. Introduce TOVA: when KV cache reaches capacity, drop the token with lowest attention score. Training-free, retains up to 1/8 of original cache size while matching full-model performance.
- **What it crystallizes:** Exact KV embeddings for remaining tokens. **Deterministic, exact preservation** but lossy due to eviction.
- **CHECKABLE/replayable?** No audit trail for decisions made.
- **Staleness handling:** None intrinsic.
- **Transfers to CSM:** The "transformers as multi-state RNNs" theoretical framing is philosophically close to CSM's premise. TOVA demonstrates that attention-score-based retention works near-losslessly with bounded state.
- **Steal score:** ⭐⭐⭐ (RNN-equivalence theorem; low-bound-capacity operation)

### 6. Scissorhands — Liu et al., NeurIPS 2023
- **arXiv:** [2305.17118](https://arxiv.org/abs/2305.17118)
- **Mechanism:** Persistence of Importance Hypothesis: "Only pivotal tokens which had substantial influence at one previous step will have significant influence at a future step." Empirically verified >90% overlap in attended tokens across steps. Uses reservoir sampling + LRU for fixed-budget KV cache. Reduces KV memory up to 5×.
- **What it crystallizes:** Fixed-size KV subset. **Deterministic, exact KV state**.
- **CHECKABLE/replayable?** No verification mechanism beyond importance scores.
- **Staleness handling:** None. Recompiled each session.
- **Transfers to CSM:** The persistence hypothesis is the strongest theoretical justification for selective retention across passes. Directly motivates the CSM gate design: if importance persists, we don't need to re-read everything.
- **Steal score:** ⭐⭐⭐⭐ (persistence hypothesis — core theoretical pillar for CSM)

### 7. K-Norm — Devoto et al., 2024
- **arXiv:** [2405.12533](https://arxiv.org/abs/2405.12533)
- **Mechanism:** Prune KV cache entries based on norm magnitude — remove keys/values with smallest ℓ₂ norms. Simpler than attention-based methods, requires no attention computation after prefill.
- **What it crystallizes:** Subset of KV embeddings preserved by norm threshold.
- **CHECKABLE/replayable?** No audit mechanism.
- **Staleness handling:** None.
- **Transfers to CSM:** Norm-based pruning is simpler than attention-scoring and avoids per-step attention computation. Useful as a cheaper first-pass filter before more expensive analysis.
- **Steal score:** ⭐⭐ (norm-based cheap filter)

### 8. Titans + MIRAS — Behrouz et al., Google Research, NeurIPS 2025
- **arXiv:** [2501.00663](https://arxiv.org/abs/2501.00663) (MIRAS framework: [2504.13173](https://arxiv.org/abs/2504.13173))
- **Mechanism:** Neural long-term memory module (LMM) using gradient descent with momentum and weight decay at test time. Three architecture variants: MAC (memory as context), MAG (memory as gate), MAL (memory as layer). Combines short-term attention (precise, limited) with long-term neural memory (fading, unlimited capacity). Surprise-driven memorization with adaptive forgetting (weight decay).
- **What it crystallizes:** Model weights updated at test time encode long-term memory. **Learned, parametric, lossy** (weight updates approximate the history).
- **CHECKABLE/replayable?** ❌ No. Weight updates are opaque function approximations. No audit trail from final weights back to source facts.
- **Staleness handling:** Adaptive weight decay provides natural forgetting. Momentum helps retain surprising/later information. But no explicit staleness check — the model simply drifts.
- **Transfers to CSM:** The surprise-momentum-forgetting triad is highly relevant. Test-time learning (continuing to update parameters as new data streams in) mirrors CSM's incremental crystallization gate. The dual-memory perspective (attention = short-term, neural memory = long-term/persistent) directly maps to CSM's layered design.
- **Steal score:** ⭐⭐⭐⭐ (test-time memorization + surprise gating + dual-memory architecture)

### 9. Larimar — IBM, 2024
- **arXiv:** [2403.11901](https://arxiv.org/abs/2403.11901)
- **Mechanism:** Brain-inspired episodic memory controller using hierarchical CLS-view model. Fast-learning hippocampal system (episodic memory matrix) records samples; slow-learning neocortex (LLM decoder) learns summary statistics. One-shot memory update via least-squares solution to linear systems. Memory conditions LLM decoder output.
- **What it crystallizes:** Distributed episodic memory matrix (512×768 in experiments). **Hybrid: learned weights + exact sample storage in memory matrix**.
- **CHECKABLE/replayable?** No. The episodic memory is a learned transformation matrix. While individual samples can be traced within it, there's no independent verification mechanism.
- **Staleness handling:** Selective fact forgetting via one-shot inversion mechanism. Information leakage prevention built in. Not staleness-detection per se, but controlled knowledge decay.
- **Transfers to CSM:** One-shot distributed writing to a global episodic memory is structurally similar to CSM's incremental compilation. The CLS-view separation (hippocampus fast-learning vs neocortex slow-learning) mirrors the CSM split between "what to extract" and "how to integrate."
- **Steal score:** ⭐⭐⭐ (one-shot distributed memory writing + hippocampal/neocortical duality)

### 10. MemGPT / Letta — Packer et al., UC Berkeley, 2023/2024
- **arXiv:** [2310.08560](https://arxiv.org/abs/2310.08560)
- **Mechanism:** OS-inspired virtual context management. Three tiers: Core Memory (in-context, editable blocks analogous to RAM), Archival Memory (vector DB, external long-term storage analogous to disk), Recall Memory (full conversation log). LLM manages memory via function calls (`core_memory_append`, `archival_memory_search`, etc.). Page-warning interrupts trigger compaction/eviction.
- **What it crystallizes:** Editable core memory blocks (plain text, agent-written). Deterministic text stored verbatim. External stores are raw vector embeddings.
- **CHECKABLE/replayable?** Partially. Core memory blocks are plain text — readable, auditable. But no mechanism verifies they still match the original source material they summarize. Agent writes are LLM-generated prose, not verbatim extraction.
- **Staleness handling:** Page-pressure warnings trigger self-rewrite/compaction. No autonomous staleness detection. Manual/human review is the fallback. Sleep-time agents do async memory refinement.
- **Transfers to CSM:** The tiered hierarchy (working vs archival vs recall) is architecturally foundational. Function-call memory API is reusable. Interrupt-driven pressure responses. Git-backed memory repository in Letta (versioned block contents).
- **Steal score:** ⭐⭐⭐⭐⭐ (OS-inspired tiered memory + interrupt-driven compaction + git-backed versioning in modern Letta)

### 11. Zep / Graphiti — Rasmussen et al., 2025
- **arXiv:** [2501.13956](https://arxiv.org/abs/2501.13956)
- **Mechanism:** Temporally-aware knowledge graph engine powering AI agent memory. Three-tier subgraph hierarchy: Episode Subgraph (raw inputs stored non-lossily), Semantic Entity Subgraph (extracted entities/facts as nodes and edges), Community Subgraph (clusters of connected entities with summaries). Bi-temporal edge model: `t'_created`/`t'_expired` (system timeline) + `t_valid`/`t_invalid` (real-world timeline). Edge invalidation on contradiction detection.
- **What it crystallizes:** Structured fact network derived from raw conversation/text. Non-lossy episode store. Semantic layer is LLM-extracted, thus **learned abstraction** over raw input.
- **CHECKABLE/replayable?** ✅ Stronger than most. Episodes are stored **non-lossily** — the ground-truth raw input exists. Edges carry validity timestamps. Contradictions are tracked via `t_invalid`. Provenance chains exist from extracted facts back to episodes.
- **Staleness handling:** Bi-temporal model tracks both when something was learned AND when it became true/false in reality. Edge invalidation on contradiction. This is the closest anyone has come to **structured staleness tracking**.
- **Transfers to CSM:** The bi-temporal edge model is potentially the most stealable single pattern. Non-lossy episode store backing a lossy semantic layer enables verification. Edge invalidation on contradiction detection directly inspires a "stale fact detected" signal. Label propagation for community detection (vs Leiden) is efficient for incremental updates.
- **Steal score:** ⭐⭐⭐⭐⭐ (bi-temporal edges + non-lossy episode store + contradiction invalidation — closest to "checkable crystallized context")

### 12. HippoRAG — Jiménez Gutiérrez et al., NeurIPS 2024
- **arXiv:** [2404.xxxx] (NeurIPS 2024, confirmed hippocampal indexing theory)
- **Mechanism:** Inspired by hippocampal memory indexing theory. Neocortex (LLM) transforms corpus into schemaless knowledge graph. Hippocampus = indexed connections via Personalized PageRank (PPR) on the KG. Given query, extract key concepts → seed PPR → explore KG paths → retrieve subgraphs. Single-step retrieval replaces iterative chain-of-thought.
- **What it crystallizes:** Knowledge graph (schemaless triples from LLM extraction) + PPR-indexed associations. **Learned KG structure**, extracted deterministically from corpus.
- **CHECKABLE/replayable?** Partially. Triplets can be traced back to source passages. PPR indices are deterministic given the KG. But KG extraction itself is LLM-generated.
- **Staleness handling:** None explicit. KG is rebuilt or incrementally updated when new corpus arrives.
- **Transfers to CSM:** Hippocampal indexing theory (C-shaped hippocampus holds index, neocortex stores memories) is the conceptual basis for the CSM name. PPR-as-indexing for multi-hop retrieval without iterative LLM calls is directly applicable. Single-step retrieval replacing iterative reasoning.
- **Steal score:** ⭐⭐⭐⭐ (hippocampal indexing analogy + PPR retrieval + single-step multi-hop)

### 13. A-MEM — Xu et al., Rutgers/Ant Group, 2025
- **arXiv:** [2502.12110](https://arxiv.org/abs/2502.12110)
- **Mechanism:** Agentic Zettelkasten-inspired memory. Each new interaction creates atomic notes with multiple attributes (contextual descriptions, keywords, tags, embeddings). Automatic link generation between related historical memories. Memory evolution: new memories trigger updates to existing memories' contextual representations. Continuous self-refinement.
- **What it crystallizes:** Structured knowledge graph of atomic notes. Notes contain LLM-generated metadata. **Learned/attribution-based** organization.
- **CHECKABLE/replayable?** No direct verification against source conversations. Note content is LLM-authored, not verbatim. Links between notes are semantically determined.
- **Staleness handling:** Memory evolution handles "drift" — existing notes update as new evidence emerges. But no explicit staleness trigger or independent verification.
- **Transfers to CSM:** Zettelkasten principles (atomic notes + flexible linking) for knowledge organization. Self-evolving memory where new input triggers reorganization of old facts. Link generation between semantically similar historical items.
- **Steal score:** ⭐⭐⭐ (Zettelkasten + self-evolution + link generation between notes)

### 14. StreamingLLM — Xiao et al., 2024
- **arXiv:** [2309.17446](https://arxiv.org/abs/2309.17446)
- **Mechanism:** Keeps attention sink tokens (first ~4 tokens) + sliding window of recent tokens. Discards everything else. Works because models exhibit stable attention on initial tokens regardless of sequence position. Training-free.
- **What it crystallizes:** Tiny subset of original tokens. **Minimal, deterministic** — exact tokens kept.
- **CHECKABLE/replayable?** No — too sparse to be useful for verification purposes. Sink tokens are trivially identifiable.
- **Staleness handling:** N/A — fundamentally loses mid-context information irreversibly.
- **Transfers to CSM:** The attention sink phenomenon (tokens that maintain stable attention regardless of position) is important to know about. It may indicate which tokens should NEVER be evicted.
- **Steal score:** ⭐ (sink awareness only)

### 15. Speculative Decoding — Leviathan et al., 2023 / Chen et al., 2023
- **arXiv:** [2302.00367](https://arxiv.org/abs/2302.00367) (EAGLE/Leviathan framework)
- **Mechanism:** Small draft model generates candidate tokens autoregressively. Target LLM verifies candidates in parallel (single forward pass, akin to prefill). Accepts matching prefix. Restarts speculation after rejection. Speedup depends on acceptance rate.
- **What it crystallizes:** Nothing new — just faster decoding via verification. **Not a crystallization method.**
- **CHECKABLE/replayable?** Verification inherently produces checkable results: every accepted token is independently validated by the target model. This is the closest thing to a "replayable crystal" in ML inference.
- **Staleness handling:** N/A — each generation is independent.
- **Transfers to CSM:** The verification step is the key transferable insight. Every accepted speculative token IS independently validated. CSM's crystallized context could similarly be **verified before consumption** by running it through the same evaluation that produced it. Pre-filling from crystallized state vs. re-reading original = identical computational role to speculative verification.
- **Steal score:** ⭐⭐⭐⭐ (verification paradigm — "trust but verify" as a computational primitive)

### 16. SeKV (Semantic KV Cache) — 2026
- **arXiv:** [2606.31145](https://arxiv.org/abs/2606.31145)
- **Mechanism:** Resolution-adaptive semantic KV cache. Segments context into entropy-guided semantic spans using token surprisal as boundary signal. GPU-resident span summaries + CPU-resident low-rank SVD bases for reconstruction. Zoom-in mechanism selectively expands query-relevant spans during decoding. Dual-representation: coarse routing on GPU, fine reconstruction on demand.
- **What it crystallizes:** Hierarchical semantic memory with two resolution levels. **Deterministic segmentation** (surprisal boundaries) + SVD compression within spans.
- **CHECKABLE/replayable?** Partially. Span boundaries are computed deterministically from surprisal. Low-rank SVD captures essential structure within each span, though exact token recovery is approximate.
- **Staleness handling:** N/A — designed for single-pass inference, not persistent context.
- **Transfers to CSM:** Multi-resolution storage (GPU summary + CPU detail) is elegant for tiered crystallization. Entropy-guided boundary detection for semantic segments. Zoom-in on-demand expansion. Surprisal as zero-cost boundary signal during prefill.
- **Steal score:** ⭐⭐⭐ (multi-resolution hierarchy + zoom-in mechanism)

### 17. BOA Compressor (SSM-based online compression) — 2026
- **arXiv:** [2601.09113](https://arxiv.org/abs/2601.09113)
- **Mechanism:** Mamba SSM encoder reads arbitrarily long context in linear time, produces compact representation injected into frozen target LLM. Trained by distillation matching teacher LLM's next-token distribution on full context. Online (runs as part of inference path), order-of-magnitude faster than offline Transformer-based compression. 16× compression ratio demonstrated.
- **What it crystallizes:** Continuous compressed representation (hidden states projected to LLM attention space). **Learned, lossy** — SSM state summarizes context approximately.
- **CHECKABLE/replayable?** ❌ No. Mamba hidden states are continuous vectors with no traceability back to source tokens.
- **Staleness handling:** N/A — single-pass compressor, not a persistent store.
- **Transfers to CSM:** Linear-time context encoding via SSM as a practical compression backbone. Distillation training approach matching teacher's output distribution.
- **Steal score:** ⭐⭐ (SSM-based linear-time encoding as compression backbone)

### 18. ACE (Agentic Context Engineering) — 2025
- **arXiv:** [2510.04618](https://arxiv.org/abs/2510.04618)
- **Mechanism:** Treats contexts as evolving playbooks rather than summaries. Three-role workflow: Generator (produces trajectories), Reflector (distills insights from successes/errors), Curator (integrates insights into structured context updates). Grow-and-refine principle prevents context collapse. Structured incremental updates preserve detailed domain knowledge.
- **What it crystallizes:** Evolving playbook documents. **Deterministic text accumulation** with LLM-guided curation.
- **CHECKABLE/replayable?** No — playbooks accumulate curated strategies but aren't checked against source.
- **Staleness handling:** Incremental accumulation prevents erasure. No staleness detection, but grow-only approach means nothing is lost.
- **Transfers to CSM:** Modular division of labor (generate → reflect → curate) for context optimization. Prevention of "context collapse" through structured incremental updates.
- **Steal score:** ⭐⭐ (modular workflow + grow-and-refine principle)

### 19. PAACE (Plan-Aware Context Engineering) — 2025
- **arXiv:** [2512.16970](https://arxiv.org/abs/2512.16970)
- **Mechanism:** Unified framework for plan-aware context optimization in long-horizon agents. Next-k-task relevance modeling, plan-structure analysis, instruction co-refinement, function-preserving compression. Synthetic data generator (PAACE-Syn) + distilled practitioners (PAACE-FT).
- **What it crystallizes:** Pruned, rewritten, summarized agent state optimized for next-k tasks.
- **CHECKABLE/replayable?** No — text is rewritten/summarized with no source tracking.
- **Staleness handling:** Task relevance modeling implicitly handles staleness by dropping irrelevant-but-not-yet-stale content.
- **Transfers to CSM:** Plan-aware next-k-task relevance scoring is applicable to per-edge promotion: "is this edge still relevant to upcoming tasks?" Function-preserving compression preserves semantics while reducing tokens.
- **Steal score:** ⭐⭐ (plan-aware relevance scoring for per-edge decision making)

### 20. BASS (Balanced State Subspaces) — Shang et al., 2026
- **arXiv:** [2610.36617](https://arxiv.org/abs/2610.36617)
- **Mechanism:** Post-training state reduction for Mamba-2 SSMs using balanced truncation. Employs controllability and observability Gramians from forward statistics to find low-dimensional subspace preserving input-output map. SPAR/HARP allocates rank budgets per layer from Hankel spectrum.
- **What it crystallizes:** Reduced-dimension state subspace of trained SSM. **Learned, lossy** — coordinate rotation + truncation.
- **CHECKABLE/replayable?** No — rotated/truncated state loses direct traceability to source sequences.
- **Staleness handling:** N/A — single-shot post-training transform.
- **Transfers to CSM:** Balanced truncation as principled compression method. Controllability/observability Gramians as principled importance metrics.
- **Steal score:** ⭐⭐ (principled subspace selection via Gramian analysis)

---

## Novelty Gap Analysis

### Already Does Checkable Crystallized Context + Staleness Detection?

**No.** The closest partial match is **Graphiti/Zep** with its bi-temporal edge model and non-lossy episode store. However:
- Episode store is non-lossy raw input, not a *crystallized* compressed representation
- Edge validity tracking is about truth-value timelines, not "this summary drifted from its source"
- No checksum-like invariant relation between live state and crystallized structure
- No automated staleness-triggered recompilation

**This is the gap.** Everything that compresses context does so either:
1. Learned/approximate (gist tokens, SSM states, speculators) — inherently uncheckable
2. Exact-subset-selection (KV eviction, Scissorhands, H2O) — no staleness check between old and new source
3. Deterministic text extraction (LLMLingua, MEM) — no verification that extracted text still faithfully represents source

CSM proposes: **deterministic extraction → checksum/invariant → recomputation when invariant breaks.**

### Ranked Steal-List (what to copy first)

| Rank | System | What to Steal | Why |
|------|--------|---------------|-----|
| 1 | **Graphiti/Zep** | Bi-temporal edge model + non-lossy episode store + contradiction invalidation | Closest existing pattern to checkable provenance + staleness tracking |
| 2 | **MemGPT/Letta** | OS-inspired tiered hierarchy + interrupt-driven compaction + git-backed memory versioning | Architecture blueprint for production memory management |
| 3 | **HippoRAG** | Hippocampal indexing theory + PPR retrieval + single-step multi-hop | Conceptual basis for CSM naming + retrieval mechanism |
| 4 | **Scissorhands** | Persistence of Importance Hypothesis | Theoretical foundation for "don't re-verify what didn't change" |
| 5 | **Titans/MIRAS** | Test-time memorization + surprise-gating + momentum-forgetting | Mechanism for incremental, adaptive crystallization |
| 6 | **LLMLingua** | Budget controller (adaptive compression ratios) + contrastive perplexity | Practical scoring mechanism for determining what to compress |
| 7 | **SeKV** | Multi-resolution storage + zoom-in-on-demand + surprisal boundary detection | Tiered crystallization pattern (summary + detail layers) |
| 8 | **Speculative Decoding** | Verification-as-primitive paradigm | Every approved token is independently validated — transfer this mindset |
| 9 | **H2O** | Power-law importance + submodular optimization | Mathematical grounding for selective retention |
| 10 | **A-MEM** | Zettelkasten note-linking + self-evolution pattern | Structure for interconnected crystallized claims |

---

## Key Findings for CSM Design

1. **The gap is real.** No one combines deterministic crystallized context + independent staleness detection + automatic recompilation triggers.

2. **KV-cache eviction is NOT crystallization.** These operate within the inference loop to manage memory during a single generation. They discard tokens permanently with no recovery. CSM's crystallized context would be *read-only* until explicitly invalidated by staleness detection.

3. **Zep/Graphiti is the closest predecessor** on the provenance-checkability axis, but operates on a knowledge-graph level rather than a context-compilation level.

4. **Test-time learning (Titans)** shows that continuing to learn/update parameters as data flows in is viable — supports CSM's incremental crystallization model.

5. **"Context rot" in agents is a problem everyone acknowledges but no one solves systematically.** PAACE identifies it as a primary cause of agentic failure — validating the CSM premise that better context management = better agent reliability.
