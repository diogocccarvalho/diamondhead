#!/usr/bin/env python3
"""Deterministic corpus generator (~10k tokens).

Reads existing repo docs, appends a synthetic multi-section appendix,
writes to corpus.md. All content is deterministic — no randomness."""

import os
import sys

DOC_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "docs")
OUTPUT = os.path.join(os.path.dirname(__file__), "corpus.md")


def read_doc(name):
    path = os.path.join(DOC_DIR, name)
    if not os.path.exists(path):
        print(f"WARNING: {path} not found, skipping", file=sys.stderr)
        return ""
    with open(path, encoding="utf-8") as f:
        return f.read()


SYNTHETIC_APPENDIX = """
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
"""


def main():
    # Read existing docs
    design_md = read_doc("design.md")
    impl_md = read_doc("implementation.md")

    # Build corpus: docs + synthetic appendix
    corpus_parts = []
    sources = []

    if design_md:
        corpus_parts.append("# Part 1: Design Specification\n")
        corpus_parts.append(design_md)
        sources.append("design.md")

    if impl_md:
        corpus_parts.append("\n# Part 2: Implementation Plan\n")
        corpus_parts.append(impl_md)
        sources.append("implementation.md")

    # Add synthetic appendix
    corpus_parts.append("\n" + SYNTHETIC_APPENDIX)
    sources.append("synthetic_appendix")

    full_text = "".join(corpus_parts)

    # Token estimate: ~4 chars/token for English
    token_estimate = len(full_text) // 4

    # Write corpus
    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write(full_text)

    byte_size = os.path.getsize(OUTPUT)
    print(f"Corpus written: {OUTPUT}")
    print(f"Bytes: {byte_size}")
    print(f"Token estimate (~char/4): {token_estimate}")
    print(f"Sentence count (approx, period-delimited): {full_text.count('. ') + full_text.count('! ') + full_text.count('? ')}")
    print(f"Sources: {', '.join(sources)}")


if __name__ == "__main__":
    main()
