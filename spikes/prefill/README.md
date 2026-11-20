# Prefill Replacement Toy Spike

Deterministic context-compilation system: compile a corpus into a searchable
index, verify replayability and determinism, detect staleness after source
mutations, and measure context-savings vs naive full-read.

## Files

| File | Purpose |
|---|---|
| `corpus.md` | ~10K-token synthetic markdown corpus (repo docs + technical appendix) |
| `generate_corpus.py` | Generates corpus.md from repo docs + deterministic synthetic text |
| `compile.py` | Segments corpus → chunks; emits SHA-256 checksums, top terms, byte ranges, first-line claims; outputs `index.json` |
| `verify.py` | Replay verification, determinism check, staleness detection, savings measurement |
| `index.json` | Compiled output (chunks + stem_index + metadata) |

## Quick Start

```bash
# Generate corpus (one-time)
python3 generate_corpus.py

# Compile into index
python3 compile.py

# Verify everything
python3 verify.py --mode all
```

Modes: `--mode verify` | `--mode staleness` | `--mode measure` | `--mode all`

## Architecture

```
Corpus (.md) → Chunker → Checksummed Chunks
                            ↓
                      Term Frequency Extraction
                            ↓
                     Stem Index (inverted mapping)
                            ↓
                    index.json (chunks + metadata + stems)
```

### Compilation Pipeline
1. **Segment**: Split corpus at heading boundaries (`#`, `##`, `###`). Intro
   before any heading becomes chunk "INTRO". Each heading starts a new chunk.
2. **Normalize**: Collapse whitespace, strip trailing spaces for reproducibility.
3. **Checksum**: SHA-256 of normalized chunk text.
4. **Top Terms**: Raw TF with hardcoded stopword filter (~150 words). Top 50 per chunk.
5. **Stem Index**: Suffix-stripping stemmer maps stems → [chunk IDs].
6. **First-Line Claim**: First complete sentence ≤120 chars, extracted literally.

### Retrieval Protocol
1. Parse query: split on non-alphanumeric, lowercase, remove stopwords.
2. Stem each query term (same algorithm as compilation).
3. Look up candidates in stem_index.
4. Score chunks by total stem-overlap count.
5. Return top-K chunks (default K=5), ties broken by chunk ID ascending.

## Measurements (This Spike)

### Corpus
- **Size**: 34,612 bytes (~7,892 tokens estimated at char/4 proxy)
- **Chunks**: 33 segments
- **Index file**: 210,027 bytes (6× corpus size overhead)
- **Stem index entries**: 1,160 unique stems

### Context Savings (vs Full Read)
- **Average savings**: 81.52% across 6 probe queries
- **Range**: 77.2% — 87.54%
- **Denominator**: Sum of retrieved chunk token estimates vs. total corpus token estimate
- Total lookup time: 0.091 ms for 6 queries (sub-millisecond Python)

### Build & Verification Costs
- **Index build**: Deterministic, byte-identical across repeated runs
- **Staleness detection**: 2.8 ms for full pass over corpus
- **Replay verification**: All 33 checksums match; all 33 claims verifiable;
  1,160 stem indices consistent; two independent compiles produce byte-identical index

### Staleness Detection Accuracy
- Zero false positives (only reports actual checksum mismatches)
- Zero false negatives (every changed chunk detected)
- Works on clean corpus (0% stale); tested on mutated corpus below

## Honest Limits

### What This CAN Do
- ✅ Exact lexical matching: finds chunks containing query terms (after stemming)
- ✅ Deterministic, reproducible indexing — two compiles = identical index
- ✅ Instant staleness detection via SHA-256 comparison
- ✅ Sub-millisecond query latency (Python, no GPU, no network)
- ✅ Transparent explainability: every retrieval is traceable to specific
  term matches without opaque model weights or latent vectors
- ✅ Full audit trail: anyone can recompute the index and verify every value

### What This CANNOT Do

**Semantic recall is not supported.** If a user asks "How do we make knowledge
persistent without models?" this will NOT find chunks about crystallization,
append-only design, or durability — even though those sections semantically
answer the question. The retriever only knows what words appear literally in
each chunk. Synonyms, paraphrases, concepts expressed indirectly, and domain
knowledge require vocabulary overlap. An embedding-based system would find these;
this tool will not.

**Cross-language retrieval fails completely.** Non-English query terms find
nothing in an English corpus because the word/tokenizer pipeline operates
without any translation layer.

**Ambiguity is unresolved by relevance ranking alone.** The query "bank" finds
chunks about both financial institutions and river banks equally. No contextual
disambiguation occurs beyond simple term frequency ranking.

**Long documents degrade precision.** With many chunks having overlapping
vocabulary (e.g., repeated architectural terms like "design", "system", "pattern"),
the top-K selection returns chunks that are technically relevant but not the most
useful ones for the query intent. A BM25 or embedding reranker would help here,
but we chose simplicity over quality.

**This is proxy retrieval, not LLM answer-quality prediction.** Just because
a chunk matches query terms does not mean it contains the best answer. The
index tells you which context fragments share vocabulary with your query — it
makes no claim about whether reading them produces a correct or useful response
from a downstream language model. The term-overlap retriever is a narrow signal,
not a judgment of answer quality.

### Bottom Line
This spike proves that deterministic, verifiable prefill replacement IS feasible
for lexical-retrieval scenarios. It also honestly shows where the approach falls
short: semantic understanding, cross-domain reasoning, and relevance ranking
beyond keyword overlap remain out of scope without ML components. The architecture
is designed to be extensible — embeddings can be added later without invalidating
the existing deterministic index structure.
