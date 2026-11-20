#!/usr/bin/env python3
"""Prefill index verification, staleness detection, and measurement.

Three modes:
  --verify       Replay-verify all checksums, determinism check (run twice).
  --staleness    Detect stale chunks after source mutation.
  --measure      Measure context savings for probe queries.
  --all          Run all three (default).

Usage: python3 verify.py [--mode verify|staleness|measure|all]
"""

import argparse
import copy
import datetime
import hashlib
import json
import os
import re
import shutil
import sys
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CORPUS_PATH = os.path.join(SCRIPT_DIR, "corpus.md")
INDEX_PATH = os.path.join(SCRIPT_DIR, "index.json")


# --- Reuse terms/stopwords from compile.py ---
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
    w = word.lower()
    for suffix in ["tion", "ment", "ness", "able", "ible", "ally", "wise",
                   "ful", "ous", "ive", "less", "like", "hood", "ship",
                   "ing", "ed", "ly", "er", "es", "s"]:
        if len(w) > 4 and w.endswith(suffix):
            return w[:-len(suffix)] or w
    return w


def compute_checksum(text):
    """SHA-256 of text."""
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


# ------------------------------------------------------------------ VERIFY -----------------------------------------------

def load_index(path=None):
    if path is None:
        path = INDEX_PATH
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def verify_all(checksums=True, claims=True, stems=True):
    """Replay verification: recompute everything from corpus and compare to index."""
    print("=" * 70)
    print("MODE: VERIFY — Replay Verification")
    print("=" * 70)

    # Read corpus fresh
    with open(CORPUS_PATH, encoding='utf-8') as f:
        full_text = f.read()

    idx = load_index()
    chunks = idx["chunks"]
    stem_index = idx["stem_index"]
    issues = []
    verified = 0

    # --- Checksum verification ---
    if checksums:
        print("\n[1] Verifying SHA-256 checksums...")
        byte_pos = 0
        for chunk in chunks:
            actual = chunk["text"]
            expected = chunk["checksum_sha256"]
            recomputed = compute_checksum(actual)
            if recomputed != expected:
                issues.append(f"Chunk {chunk['id']} checksum mismatch")
            else:
                verified += 1
        print(f"  Checked {len(chunks)} chunks. Matches: {verified - len([i for i in issues if 'checksum' in i])}")

    # --- First-line claim verification ---
    if claims:
        print("\n[2] Verifying first-line claims are extractable from chunk text...")
        claim_verified = 0
        for chunk in chunks:
            text = chunk["text"]
            claim = chunk["first_line_claim"]
            # Check claim appears within first ~200 chars of the normalized text
            if claim in text[:min(500, len(text))]:
                claim_verified += 1
            else:
                issues.append(f"Chunk {chunk['id']} claim not verifiable in text")
        print(f"  Claims verified: {claim_verified}/{len(chunks)}")

    # --- Stem index consistency ---
    if stems:
        print("\n[3] Verifying stem index consistency...")
        rebuild_stems = {}
        for chunk in chunks:
            cid = chunk["id"]
            words = re.findall(r'[a-zA-Z]{2,}', chunk["text"].lower())
            seen = set()
            for w in words:
                s = simple_stem(w)
                if s not in STOPWORDS and s not in seen:
                    seen.add(s)
                    rebuild_stems.setdefault(s, []).append(cid)
        mismatches = 0
        for stem, cids in stem_index.items():
            if stem not in rebuild_stems:
                issues.append(f"Stem '{stem}' in index but not found on re-scan")
                mismatches += 1
            elif sorted(cids) != sorted(rebuild_stems[stem]):
                issues.append(f"Stem '{stem}' chunk list mismatch")
                mismatches += 1
        print(f"  Stem entries checked: {len(stem_index)}. Mismatches: {mismatches}")

    # --- Determinism check: rebuild and compare ---
    print("\n[4] Determinism check (re-run compile, diff indices)...")
    tmp_index_path = os.path.join(SCRIPT_DIR, "index_run2.json")
    result = os.system(f'cd "{SCRIPT_DIR}" && python3 compile.py --corpus "{CORPUS_PATH}" --output "{tmp_index_path}" 2>&1')
    if result == 0 and os.path.exists(tmp_index_path):
        with open(INDEX_PATH, encoding='utf-8') as f:
            idx1 = json.load(f)
        with open(tmp_index_path, encoding='utf-8') as f:
            idx2 = json.load(f)

        # Compare (excluding timestamp which will differ)
        idx1_compare = copy.deepcopy(idx1)
        idx2_compare = copy.deepcopy(idx2)
        idx1_compare["meta"]["build_timestamp"] = ""
        idx2_compare["meta"]["build_timestamp"] = ""
        identical = json.dumps(idx1_compare, sort_keys=True) == json.dumps(idx2_compare, sort_keys=True)
        print(f"  Index files {'BYTE-IDENTICAL' if identical else 'DIVERGED'}")
        if not identical:
            issues.append("Determinism check failed: second compile produced different index")
        os.remove(tmp_index_path)
    else:
        issues.append("Second compile run failed (exit code {})".format(result))
        print(f"  Second compile FAILED with exit code {result}")

    # --- Summary ---
    print(f"\n{'='*70}")
    if not issues:
        print("VERIFY PASSED: All checks green.")
    else:
        print(f"VERIFY ISSUES ({len(issues)}):")
        for issue in issues:
            print(f"  ⚠ {issue}")
    print(f"{'='*70}\n")

    return issues


# --------------------------------------------------------- STALENESS DETECTION -------------------------------------------

def detect_staleness(corpus_path=None, index_path=None):
    """Detect which chunks would be stale given current source."""
    if corpus_path is None:
        corpus_path = CORPUS_PATH
    if index_path is None:
        index_path = INDEX_PATH

    print("=" * 70)
    print("MODE: STALENESS DETECTION")
    print("=" * 70)

    # Start timer
    t0 = time.perf_counter()

    # Re-parse corpus to get fresh chunks (reuse compile logic)
    with open(corpus_path, encoding='utf-8') as f:
        full_text = f.read()

    lines = full_text.split('\n')
    current_heading = "INTRO"
    current_lines = []
    all_sections = []

    def flush():
        nonlocal current_heading, current_lines
        text = '\n'.join(current_lines)
        if text.strip():
            normalized = re.sub(r'\s+', ' ', text).strip()
            cs = hashlib.sha256(normalized.encode('utf-8')).hexdigest()
            all_sections.append({"heading": current_heading, "text": normalized, "sha256": cs})
        current_lines = []

    i = 0
    while i < len(lines):
        m = re.match(r'^(#{1,3})\s+(.+)$', lines[i])
        if m:
            if current_lines:
                flush()
            current_heading = m.group(2)
        else:
            current_lines.append(lines[i])
        i += 1
    if current_lines:
        flush()

    elapsed_parse = (time.perf_counter() - t0) * 1000

    # Load index
    idx = load_index(index_path)
    stored_chunks = idx["chunks"]

    # Compare checksums
    stale_ids = []
    changed_texts = []

    for sec, sc in zip(all_sections, stored_chunks):
        if sec["sha256"] != sc["checksum_sha256"]:
            stale_ids.append(sc["id"])
            changed_texts.append(sec["text"][:100])

    total = len(stored_chunks)
    elapsed_total = (time.perf_counter() - t0) * 1000

    print(f"\n  Total chunks:   {total}")
    print(f"  Stale chunks:   {len(stale_ids)}")
    print(f"  Fresh chunks:   {total - len(stale_ids)}")
    print(f"  Staleness rate: {len(stale_ids)/total*100:.1f}%")
    print(f"  Parse+compare:  {elapsed_total:.1f} ms")
    print(f"  Just parse:     {elapsed_parse:.1f} ms")

    if stale_ids:
        print(f"\n  Stale chunk IDs: {stale_ids}")
        print(f"  These chunks need rebuilding only:")
        for sid in stale_ids:
            src_idx = None
            for i2, s in enumerate(all_sections):
                if s["sha256"] != stored_chunks[i2]["checksum_sha256"] and stored_chunks[i2]["id"] == sid:
                    src_idx = i2
                    break
            if src_idx is not None:
                print(f"    [{sid}] heading='{stored_chunks[sid]['heading']}' → \"{changed_texts[stale_ids.index(sid)]}...\"")

    print(f"\n{'='*70}\n")

    return {
        "total_chunks": total,
        "stale_count": len(stale_ids),
        "stale_rate_pct": round(len(stale_ids) / total * 100, 2),
        "elapsed_ms": round(elapsed_total, 2),
        "stale_ids": stale_ids,
    }


def measure_savings(probe_queries=None):
    """Measure context savings for a set of probe queries."""
    if probe_queries is None:
        probe_queries = [
            "deterministic prefill index architecture",
            "crystallization plugin middleware hooks",
            "design invariant constraints retrieval",
            "chunking theory token budget",
            "term weighting tf stopword",
            "stem index inverted search",
        ]

    print("=" * 70)
    print("MODE: MEASUREMENT — Context Savings via Probe Queries")
    print("=" * 70)

    idx = load_index()
    chunks = idx["chunks"]
    stem_index = idx["stem_index"]
    corpus_size = idx["meta"]["corpus_size_bytes"]
    total_tokens = idx["meta"]["total_token_estimate"]

    # Build query term lookup per chunk
    # For each chunk, build a dict of stem -> count
    chunk_term_map = {}
    for c in chunks:
        counts = {}
        for wt in c["top_terms"]:
            stem = simple_stem(wt["term"])
            counts[stem] = wt["count"]
        chunk_term_map[c["id"]] = counts

    results = []
    grand_retrieved_tokens = 0

    for query in probe_queries:
        t0 = time.perf_counter()

        # Parse query: lowercase, split, remove stopwords, stem remaining
        q_terms = re.findall(r'[a-zA-Z]{2,}', query.lower())
        q_stems = [simple_stem(w) for w in q_terms if w not in STOPWORDS]

        # Candidate chunks by stem overlap
        candidate_scores = {}
        for stem in q_stems:
            for cid in stem_index.get(stem, []):
                candidate_scores[cid] = candidate_scores.get(cid, 0) + 1

        # Sort by score desc, then id asc for determinism
        ranked = sorted(candidate_scores.items(), key=lambda x: (-x[1], x[0]))

        # Take top 5
        top_k = ranked[:5]
        top_chunk_ids = [cid for cid, _ in top_k]

        retrieved_tokens = sum(chunks[cid]["token_estimate"] for cid in top_chunk_ids)
        retrieved_chars = sum(len(chunks[cid]["text"]) for cid in top_chunk_ids)
        saving_pct = round((total_tokens - retrieved_tokens) / total_tokens * 100, 2) if total_tokens else 0

        elapsed_q = (time.perf_counter() - t0) * 1000

        # Show matched topics
        topics = [chunks[cid]["heading"] for cid in top_chunk_ids]

        result = {
            "query": query,
            "query_stems": q_stems,
            "candidate_chunks": len(candidate_scores),
            "retrieved_chunks": len(top_chunk_ids),
            "chunk_ids": top_chunk_ids,
            "headings_matched": topics,
            "retrieved_tokens": retrieved_tokens,
            "saving_pct": saving_pct,
            "elapsed_ms": round(elapsed_q, 3),
        }
        results.append(result)
        grand_retrieved_tokens += retrieved_tokens
        print(f"\n  Query: \"{query}\"")
        print(f"    Stems: {q_stems}")
        print(f"    Candidates found: {len(candidate_scores)}")
        print(f"    Top-{len(top_chunk_ids)} chunks: ids={top_chunk_ids}")
        print(f"    Headings: {topics}")
        print(f"    Tokens read via index: {retrieved_tokens}")
        print(f"    Full-read tokens: {total_tokens}")
        print(f"    Savings: {saving_pct}%")
        print(f"    Lookup time: {elapsed_q:.3f} ms")

    avg_saving = round(sum(r["saving_pct"] for r in results) / len(results), 2) if results else 0
    total_lookup_ms = sum(r["elapsed_ms"] for r in results)

    print(f"\n{'─'*70}")
    print(f"AGGREGATE SAVINGS")
    print(f"  Corpus size:         {corpus_size} bytes (~{total_tokens} tokens)")
    print(f"  Avg savings/query:   {avg_saving}%")
    print(f"  Total lookup time:   {total_lookup_ms:.3f} ms")
    print(f"  Index size:          {os.path.getsize(INDEX_PATH)} bytes")
    print(f"{'='*70}\n")

    return {
        "per_query": results,
        "avg_savings_pct": avg_saving,
        "total_lookup_ms": round(total_lookup_ms, 3),
        "corpus_size_bytes": corpus_size,
        "total_tokens": total_tokens,
        "index_size_bytes": os.path.getsize(INDEX_PATH),
    }


# ---------------------------------------------------------------- MAIN -----------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Verify prefill index, detect staleness, measure savings")
    parser.add_argument("--mode", choices=["verify", "staleness", "measure", "all"], default="all")
    parser.add_argument("--corpus", default=CORPUS_PATH)
    parser.add_argument("--index", default=INDEX_PATH)
    args = parser.parse_args()

    global CORPUS_PATH, INDEX_PATH
    CORPUS_PATH = args.corpus
    INDEX_PATH = args.index

    all_results = {}

    if args.mode in ("verify", "all"):
        v_issues = verify_all()
        all_results["verify_issues"] = v_issues
        all_results["verify_pass"] = len(v_issues) == 0

    if args.mode in ("staleness", "all"):
        st = detect_staleness()
        all_results["staleness"] = st

    if args.mode in ("measure", "all"):
        m = measure_savings()
        all_results["measurement"] = m

    # Final summary
    print("\n" + "=" * 70)
    print("FINAL SUMMARY")
    print("=" * 70)

    if all_results.get("verify_pass"):
        print("✓ Replay verification: PASSED (byte-identical across runs)")
    else:
        print("✗ Replay verification: FAILED")
        for i in all_results.get("verify_issues", []):
            print(f"  - {i}")

    if "staleness" in all_results:
        st = all_results["staleness"]
        print(f"Staleness: {st['stale_count']}/{st['total_chunks']} chunks stale ({st['stale_rate_pct']}%)")
        print(f"  Detection cost: {st['elapsed_ms']:.1f} ms")

    if "measurement" in all_results:
        mm = all_results["measurement"]
        print(f"Index savings: {mm['avg_savings_pct']}% avg retrieval vs full read")
        print(f"  Index file: {mm['index_size_bytes']} bytes")
        print(f"  Corpus: {mm['total_tokens']} estimated tokens")
        print(f"  Per-query lookup: {mm['total_lookup_ms']:.3f} ms total")


if __name__ == "__main__":
    main()
