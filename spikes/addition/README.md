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

## GA results (2026-11-16, ga.py - real structural mutation)

- Genome = executable op-sequence over add/addifbit/chunk primitives; uniform
  structural operators + uniform crossover; fitness axis (--fitness
  latency|space) is the only human choice.
- LATENCY: the GA re-derives the 13-op bit ladder every run (replay-proven).
  The workload SELECTS the representation (cold b<=5000 forces 13 bits; a
  6-bit first run had zero viable genomes).
- SPACE: still no champion, and now we know why - one-shot chunk ops cannot
  cover b<=5000 within the 14-op budget (b/64 = ~79 repetitions), so the bit
  ladder IS the compaction floor at this primitive strength. Headroom needs a
  looping primitive (e.g. while>=k), which is control flow - the next genome
  expressiveness step.
- TOTAL vs DISTRIBUTIONAL proof: replay byte-equality is a DISTRIBUTIONAL
  proof only - a genome can pass the workload and fail off-distribution (the
  domain probe checked crashes, never correctness). ga.py now adds an
  exhaustive total-correctness gate (a=0, b in 0..8191, checked against the
  oracle) as a PROOF gate. Law: distributional pass is evidence, exhaustive
  pass is proof; promoted-by-replay-but-failing-exhaustive genomes are
  overfit crystals. This carries straight into stage 2: crystals must prove
  on their claimed domain, not their training traffic.
