# DiamondHead

Crystallization for software agents: procedures an agent repeatedly proves on
live traffic stop being re-judged each time and compile into components that
fire on trigger — muscle memory, not another prompt.

Built on top of [haystack](https://github.com/diogocccarvalho/haystack): its
failure catalog supplied the design rules in [docs/design.md](docs/design.md),
and its retrieval is what the chooser routes to. Haystack indexes what a
system knows (content); DiamondHead indexes what it does (procedures).

## Why it was done

Reasoning models visibly re-derive the same steps every session. Efficiency
work (speculative decoding, overthinking-reward research [6][7][10][1]) makes
inference faster but never touches *what* gets thought. The fix taken here:
compile the repeated thought once, prove it, and stop paying for it. The
inversion matters — prior art compiles on FAILURE (call-rate decay [2610.25455]);
this compiles on SUCCESS (verified-use evidence).

## What it is

A running Hermes plugin: a pre-LLM hook that watches an LLM agent's live
traffic and crystallizes its repeated behavior.

- **Semantic function chooser** — an O(1) hint prefilter, then one
  single-question d1 classifier call per candidate crystal, run concurrently.
- **Append-only rule store** — candidates mined from the behavior log fire as
  hints, never auto-enforced.
- **Per-use SPRT promotion gate** — each injection is one Bernoulli trial
  (consumed AND judge-correct); promote on decisive precision, futility-demote
  on failures, burn-in 8, no wall-clock age. Promotion binds to the exact
  contract version that earned it.
- **Context judge** — post-hoc check that firing was the right response to
  that message; the judged ratio is promotion evidence.
- **Genetic dream loop** — structural mutation of existing crystals only
  (fitness improves, never creates); mutants contend on real traffic, the
  promotion gate decides.
- **Behavior log** — message hashes only, never raw text.

## Results

- The loop runs end-to-end on live agent traffic: injections fire and are
  consumed (100% consumed to date, deviation rate ~2%).
- First GA run (`spikes/addition/ga.py`) rediscovered double-and-add,
  replay-proven, under a latency fitness axis; the space axis correctly
  refused. Same loop, different axis, opposite outcome.
- Golden fixture (`tests/golden.json`) freezes working chooser behavior;
  every change replays identical or is re-blessed with a reason. 73/73 tests.
- The promotion gate is **built-but-unproven**: no crystal has yet survived
  SPRT to `enforced` on live traffic — that proof is accumulating, not
  assumed. Current per-crystal state: `scripts/dogfood.py`.

Honest boundary: pre-LLM injection is soft — the model can deviate, and the
deviation rate is measured. There is no constrained decoding from a hook.

## Prior art

Novelty was checked against the closest lines of work — Voyager (2023,
environment-verified skills as code), SCBT (2026, arXiv:2610.25455), Zep
Agent Skills (2026, arXiv:2611.01386), RSPM/WikiSkill/AutoSkill
(offline-gated promotion variants), Gödel Machine/DGM/AlphaEvolve — with the
narrow surviving claim: live-traffic promotion of a procedure past scoring.
Full survey with deltas: [research/prior-art-p2-plugin.md](research/prior-art-p2-plugin.md).
Corrections welcome.

## License

MIT
