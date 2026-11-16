# Spike: proof-gated crystallization of addition

First running instance of the PROOF station (vault note, station 3) at leaf
granularity. Throwaway — the artifact of record is `ledger.jsonl`.

## The loop

1. ORACLE: `naive_add` (frozen, never mutated). Ground truth.
2. DREAM: mutants from a small addition grammar (double-and-add, chunk-4,
   hot-value lookup table).
3. GATE: mutant is promoted only if (byte-identical outputs over the workload
   distribution) AND (measured cheaper than the oracle on that same
   distribution). 70% of the workload is small hot values, 30% is long-tail —
   the distribution, not the mutant author, decides.
4. LEDGER: every verdict is appended, never edited. Replays are lossless
   (each mutant's LATEST verdict wins; earlier verdicts stay as history).

## Honest log (2026-11-16)

- `double_add` v1 was agent-authored garbage (computed a*b) — the oracle
  rejected it. Fixed twice (seed error), promoted third pass at ~33x cheaper.
- Lesson recorded: a broken dream costs one gate round, nothing else. The
  gate, not the dreamer, is the quality control.

## Run

    python3 spike.py

Ledger grows append-only across runs. `replay_ledger()` rebuilds the
promoted/rejected sets from the ledger alone.
