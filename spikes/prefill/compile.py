#!/usr/bin/env python3
"""Deterministic prefill compiler.

Reads corpus.md, segments into chunks at heading/paragraph boundaries,
emits index.json with checksums, top terms, byte ranges, and first-line claims.

Usage: python3 compile.py [--corpus PATH] [--output PATH]
"""

import argparse
import hashlib
import json
import os
import re
import sys


# --- Stopword list (hard-coded, deterministic) ---
STOPWORDS = frozenset({
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "as", "is", "was", "are", "were", "be",
    "been", "being", "have", "has", "had", "do", "does", "did", "will",
    "would", "could", "should", "may", "might", "shall", "can", "need",
    "must", "it", "its", "this", "that", "these", "those", "i", "you",
    "he", "she", "we", "they", "what", "which", "who", "whom", "where",
    "when", "how", "why", "not", "no", "nor", "so", "if", "then", "than",
    "too", "very", "just", "about", "above", "after", "again", "all",
    "also", "am", "any", "because", "before", "between", "both", "each",
    "few", "further", "get", "got", "here", "him", "his", "however",
    "himself", "his", "hers", "herself", "itself", "let", "me", "more",
    "most", "my", "myself", "now", "only", "other", "our", "ours",
    "out", "own", "same", "some", "such", "there", "them", "themselves",
    "through", "under", "until", "up", "us", "while", "yet", "your",
    "yours", "yourself", "down", "off", "over", "into",
})


def simple_stem(word):
    """Approximate stemmer via suffix stripping (deterministic)."""
    w = word.lower()
    # Strip common suffixes in priority order
    for suffix in ["tion", "ment", "ness", "able", "ible", "ally", "wise",
                   "ful", "ous", "ive", "less", "like", "hood", "ship",
                   "ence", "ance", "ing", "ing ", "ed", "ly", "er", "es", "s"]:
        if len(w) > 4 and w.endswith(suffix):
            return w[:-len(suffix)] or w
    return w


def normalize_whitespace(text):
    """Collapse whitespace: multiple spaces/newlines → single space."""
    return re.sub(r'\s+', ' ', text).strip()


def extract_first_sentence(text, max_len=120):
    """Extract first complete sentence from text."""
    # Find first terminal punctuation
    match = re.search(r'[.!?]\s', text)
    if not match:
        # No sentence boundary found — take first line or up to max_len
        candidate = text.split('\n')[0].strip()
        return candidate[:max_len] + ('...' if len(candidate) > max_len else '')
    sentence = text[:match.end()].rstrip()
    if len(sentence) > max_len:
        sentence = sentence[:max_len] + '...'
    return sentence


def compute_chunk_terms(chunk_text):
    """Compute term frequency (raw TF, stopword-filtered). Returns sorted list."""
    words = re.findall(r'[a-zA-Z]{2,}', chunk_text.lower())
    freq = {}
    for w in words:
        if w not in STOPWORDS:
            freq[w] = freq.get(w, 0) + 1
    # Sort by count desc, then alphabetically for determinism
    sorted_terms = sorted(freq.items(), key=lambda x: (-x[1], x[0]))
    return [{"term": t, "count": c} for t, c in sorted_terms[:50]]  # Top 50


def build_stem_index(all_chunks):
    """Build inverted index: stem -> [chunk_ids]."""
    stem_idx = {}
    for chunk in all_chunks:
        cid = chunk["id"]
        words = re.findall(r'[a-zA-Z]{2,}', chunk["text"].lower())
        seen_stems = set()
        for w in words:
            s = simple_stem(w)
            if s not in STOPWORDS and s not in seen_stems:
                seen_stems.add(s)
                stem_idx.setdefault(s, []).append(cid)
    return stem_idx


def compile_corpus(corpus_path, output_path=None):
    """Main compilation pipeline."""
    if output_path is None:
        output_path = os.path.join(os.path.dirname(corpus_path), "index.json")

    print(f"Compiling corpus: {corpus_path}")
    with open(corpus_path, encoding="utf-8") as f:
        full_text = f.read()

    total_bytes = len(full_text.encode('utf-8'))
    print(f"Total size: {total_bytes} bytes")

    # --- Segment into chunks ---
    # Strategy: split on level-1 and level-2 headings (# or ##).
    # Text before any heading becomes chunk 0 ("INTRO").
    # Each heading starts a new chunk; subsequent content belongs to that
    # chunk until the next heading of the same or higher level.

    lines = full_text.split('\n')
    chunks = []  # List of {"heading", "text", "start_line", "end_line", ...}

    current_heading = "INTRO"
    current_lines = []
    intro_start = 0

    def finalize_chunk():
        nonlocal current_heading, current_lines
        text = '\n'.join(current_lines)
        if text.strip():
            normalized = normalize_whitespace(text)
            chunks.append({
                "heading": current_heading,
                "text": normalized,
                "start_line": int(lines.index(
                    [l for l in lines if l == current_lines[0]][0]
                ) if current_lines and current_lines[0] in lines else 0),
                "end_line": -1,  # Will fix after all chunks built
            })
        current_lines = []

    # Find intro start position
    first_heading_line = 0
    for i, line in enumerate(lines):
        if line.startswith('#'):
            first_heading_line = i
            break

    # Build chunks by scanning for headings
    i = 0
    while i < len(lines):
        line = lines[i]
        m = re.match(r'^(#{1,3})\s+(.+)$', line)
        if m:
            # If we have accumulated lines for current section, finalize
            if current_lines and current_heading != "INTRO" or (current_lines and i > 0 and any(l.startswith('#') for l in current_lines)):
                finalize_chunk()
                current_heading = m.group(2)
            elif current_lines and current_heading == "INTRO":
                # Finalize intro
                finalize_chunk()
                current_heading = m.group(2)
            else:
                # Start new section
                if current_lines:
                    finalize_chunk()
                current_heading = m.group(2)
            i += 1
            continue
        current_lines.append(line)
        i += 1

    # Don't forget the last chunk
    if current_lines and not any(l.startswith('#') for l in current_lines):
        finalize_chunk()

    # Fix byte ranges
    pos = 0
    all_chunks = []
    for idx, chunk_data in enumerate(chunks):
        chunk_text = chunk_data["text"]
        byte_start = pos
        byte_end = byte_start + len(chunk_text.encode('utf-8'))

        checksum = hashlib.sha256(chunk_text.encode('utf-8')).hexdigest()

        chunk_obj = {
            "id": idx,
            "heading": chunk_data["heading"],
            "text": chunk_text,
            "byte_range": {"start": byte_start, "end": byte_end},
            "checksum_sha256": checksum,
            "first_line_claim": extract_first_sentence(chunk_text),
            "top_terms": compute_chunk_terms(chunk_text),
            "token_estimate": len(chunk_text) // 4,
        }
        all_chunks.append(chunk_obj)
        pos = byte_end

    total_chunks = len(all_chunks)
    total_token_est = sum(c["token_estimate"] for c in all_chunks)

    print(f"Chunks produced: {total_chunks}")
    print(f"Total token estimate: {total_token_est}")

    # --- Build stem index ---
    stem_index = build_stem_index(all_chunks)

    # --- Write index JSON ---
    import datetime
    index = {
        "meta": {
            "build_timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "python_version": f"{sys.version_info.major}.{sys.version_info.minor}",
            "corpus_path": os.path.abspath(corpus_path),
            "corpus_size_bytes": total_bytes,
            "total_chunks": total_chunks,
            "total_token_estimate": total_token_est,
            "compiler_version": "1.0.0",
        },
        "chunks": all_chunks,
        "stem_index": dict(sorted(stem_index.items())),
        "version": "1.0.0",
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2, ensure_ascii=False)

    file_size = os.path.getsize(output_path)
    print(f"Index written: {output_path}")
    print(f"Index file size: {file_size} bytes")
    print(f"Stem index entries: {len(stem_index)}")
    print("Done.")

    return all_chunks, index


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compile corpus into prefill index")
    parser.add_argument("--corpus", default=os.path.join(
        os.path.dirname(__file__), "corpus.md"))
    parser.add_argument("--output", default=None)
    args = parser.parse_args()
    compile_corpus(args.corpus, args.output)
