# DiamondHead

A crystallization architecture: an agent (or any system) that repeatedly solves
the same sub-problem stops re-deriving it each time — the proven procedure is
compiled into a small, deterministic, checkable component that fires on trigger.
Muscle memory for software agents.

Companion to [haystack](https://github.com/diogocccarvalho/haystack), whose
failure catalog ([docs/SHORTCOMINGS.md](https://github.com/diogocccarvalho/haystack/blob/main/docs/SHORTCOMINGS.md))
supplied the design rules collected in [docs/design.md](docs/design.md).
Haystack indexes what the system KNOWS (content); DiamondHead indexes what it
DOES (procedures). The pre-LLM chooser is the join.

## Why it was done

Watching reasoning models work, they visibly loop on the same thoughts and
re-derive the same steps. This is measured, not anecdotal:

- Circular Reasoning: self-reinforcing loops in LRMs → wasted compute + failures [6]
- ENTRA / APR: overthinking/redundancy attacked from the reward side [7]
- Current efficiency work (DeepSeek DSA [10], AREX-2 [1], speculative decoding)
  makes inference faster but never touches *what* gets thought.

The fixed point / anchor is Lean (or any proof assistant): the strongest
concrete instance of "external un-gameable verifier" — non-learned,
deterministic, nothing in it to hack. This instantiates the Gödel machine [21]
practically — the system's output IS the proof the referee checks
(AlphaProof-style loop [31]).

## What it is

Two layers, one repo:

**The architecture (the thesis).** A system that is not a model but an
architecture: drop it into any problem (data in, expected out), it runs a
validator loop, and it crystallizes each sub-problem it repeatedly solves into
a deterministic, checkable component — instead of one giant transformer doing
everything with full inference every step. Five components:

1. **Latent-native generator blocks** — small specialists communicating in
   latent space, not tokens; per-job internal "dialects". Anchors: latent-space
   agent communication [22][23], emergent communication [24], COCONUT [5].
2. **Adversarial co-evolution (blue/red)** — generator blocks vs auditor
   blocks, each pushing the other. NOT a fixed judge — the judge is a block too.
3. **Invariant blocks** — cheap, NON-learned sandboxes that make whole classes
   of cheats impossible by construction (not detection). Steal from computer
   security: invariants endure, signature-chasing is always one generation
   behind [26].
4. **One external task referee** — neither blue nor red controls it, or the
   arms race becomes self-referential theater.
5. **Staggered self-replication** — the system rewrites its own blocks, but
   layers crystallize at different times; never all mutating at once.

Recursion bottom: "drop the architecture inside each block" ends at invariant
blocks (non-learned). If a block has neither an external check nor an
invariant, the system is unfalsifiable there — stop.

First concrete target: **the prefill problem**. Prefill = O(n²) re-derivation
of structure already in the text. Closest prior art: Gist tokens [30]
(learned, lossy). Differentiator: **deterministic + checkable** crystallized
context (replayable against the source), plus a cheap staleness detector — a
deterministic stale artifact is worse than slow re-reading.

**The working plugin (this is what runs today).** A pre-LLM hook that watches
an LLM agent's live traffic and crystallizes its repeated behavior:
- a semantic function chooser — one single-question d1 classifier call per
  candidate crystal, run concurrently, O(1) hint prefilter first;
- an append-only rule store (mined candidates from the behavior log fire as
  hints, never auto-enforced);
- a per-use **SPRT sequential promotion gate**: each injection is one Bernoulli
  trial (consumed AND judge-correct); promote on decisive precision,
  futility-demote on failures, burn-in 8, no wall-clock age;
- a post-hoc context judge ("was firing the right response to that message?");
- a genetic dream loop (structural mutation of existing crystals — fitness
  improves, never creates);
- a behavior log storing message HASHES only, never raw text.

## Results

- The loop runs end-to-end on live agent traffic: injections fire and are
  consumed (100% consumed to date, deviation rate ~2%).
- The first GA run (`spikes/addition/ga.py`) rediscovered double-and-add,
  replay-proven, under a latency fitness axis; the space axis correctly
  refused. Same loop, different axis, opposite outcome.
- Golden fixture (`tests/golden.json`) freezes the working chooser behavior;
  every change replays identical or is re-blessed with a reason. 73/73 tests.
- The promotion gate itself is **built-but-unproven**: no crystal has yet
  survived SPRT to `enforced` on live traffic — that proof is accumulating,
  not assumed. Full current state: `scripts/dogfood.py`.

Honest boundaries: true constrained decoding is impossible from a hook
(pre-LLM injection is soft; the model can deviate — deviation rate is
measured). Stage-2 issues (embeddings are a model, token-counting at the
boundary) are catalogued in docs/haystack-crystallization-map.md.

## The three open walls (the actual research)

1. **Shared-latent drift.** Latent-space communication requires a shared
   embedding geometry = co-training; but independent self-modification drifts
   the geometry and breaks every interface. Tokens are the stable
   low-bandwidth protocol that survives independent mutation — this tension is
   THE unsolved problem. Partial answer: staggered crystallization + per-pair
   medium choice.
2. **Local vs global objectives.** Independent blocks optimizing local proxies
   co-adapt into global local-optima. Self-modifying systems that escape this
   need external checkable benchmarks and STILL get objective-hacked (DGM [19]).
   The Gödel machine solves it with proofs (slow); Lean-anchoring is the fast
   version.
3. **Simultaneous self-replication.** A system that rewrites its own judge
   cannot certify its own improvements. Reward hacking is an equilibrium under
   finite evaluation — delayable, not eliminable [26]. Rule: the judge may
   evolve but only against data from a representation it didn't just mutate.

## The project ladder

- P1 — haystack as context-saver: replace context with retrieval, POC +
  token/money savings. (DONE, live.)
- P2 — crystallization of the agent's repeated behavior into automated,
  checked components (muscle memory, not a rewrite). This repo.
- P3 — the query-formation pass, its own layer: before any callee
  (retrieval, classifier, LLM call), form the input that maximizes that
  callee's MEASURED performance — form(text, target, state) -> text.
  Consumed by DiamondHead AND haystack; a layer consumed by N callees
  belongs to neither.
- P4 — from the autopsy of P1–P3, develop the from-scratch architecture
  (no LLM at the core; concepts related deterministically, prediction as
  glue only). See [docs/p4-core.md](docs/p4-core.md).

Design stance: models (and arguably minds) never make new concepts, only
relate existing ones in never-related ways — the goal is the most flawless
relation possible; perfection lives in re-derivability, not novelty.

## Prior art

The closest lines of research, and what we take from each (full survey with
deltas: [research/prior-art-p2-plugin.md](research/prior-art-p2-plugin.md)):

- **Voyager** (2023) — the existence proof: environment-verified skills stored
  as executable code. Our delta: promotion to deterministic auto-fire.
- **SCBT — Self-Crystallizing Behavior Trees** (Oct 2026,
  [arXiv:2610.25455](https://arxiv.org/abs/2610.25455)) — the same word and
  the "compiler not runtime" idea; they compile on FAILURE via call-rate
  decay, we compile on SUCCESS via verified-use evidence.
- **Zep Agent Skills** (Nov 2026, [arXiv:2611.01386](https://arxiv.org/abs/2611.01386))
  — capture→compile→curate→admit pipeline with gated admission; batch/
  scheduled, selection stays search-based. Our delta: live-traffic promotion
  of a procedure past scoring.
- **RSPM** ([arXiv:2610.25561](https://arxiv.org/abs/2610.25561)),
  **WikiSkill** ([arXiv:2608.27454](https://arxiv.org/abs/2608.27454)),
  **AutoSkill/SkillEvo** — offline confidence-gated promotion variants.
- **Gödel Machine** (Schmidhuber), **Darwin Gödel Machine**, **AlphaEvolve**
  — self-modification anchored to external verifiers.
- **Massalin's Synthesis superoptimizer** — dreaming: exhaustive offline
  mutation of tiny proven kernels; the oracle disposes.
- **Haystack** — the companion project: indexes what the system knows;
  DiamondHead indexes what it does. The chooser is the join.

Claims to novelty are stated narrowly in the prior-art survey and re-verified
against late-2026 literature; corrections welcome.

## License

MIT
