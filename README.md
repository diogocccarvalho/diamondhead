# DiamondHead

Self-Crystallizing Architecture — plan of record + working plugin. Born
2026-11-06 from a chat brainstorm ("what if models stop re-thinking the same
thoughts"). Companion to [haystack](https://github.com/diogocccarvalho/haystack),
whose failure catalog ([docs/SHORTCOMINGS.md](https://github.com/diogocccarvalho/haystack/blob/main/docs/SHORTCOMINGS.md))
supplied the design rules collected in [docs/design.md](docs/design.md).

Status: **plugin built, live on my agent's traffic** — pre-LLM semantic
function chooser (one single-question d1 call per crystal, concurrent),
append-only rule store, behavior log (hashes only), SPRT sequential promotion
gate (promote on decisive precision, futility-demote, burn-in 8), post-hoc
context judge, proactive nudges, golden-fixture regression suite (73/73),
genetic dream loop (mock of station 5 until sequence crystals fire), mined
candidates fire as hints. The promotion gate itself is **built-but-unproven**:
no crystal has yet survived SPRT to `enforced` on live traffic — that proof is
accumulating, not assumed. Full current state in the Status section below and
`scripts/dogfood.py`.

## The thesis (one paragraph)

A system that is **not a model but an architecture**: you drop it into any problem
(data in, expected out), it runs a validator loop, and it **crystallizes** each
sub-problem it repeatedly solves into a small, deterministic, checkable component —
instead of one giant transformer doing everything with full inference every step.
Beachhead use case: **replace prefill** — walk the context once, compile it into a
deterministic structure, and have every later pass read the structure instead of
re-reading text (O(n²) prefill → O(structure)).

## Why the idea exists (the motivating observation)

Watching reasoning models think, they visibly loop on the same thoughts and re-derive
the same steps. This is measured, not anecdotal:

- Circular Reasoning: self-reinforcing loops in LRMs → wasted compute + failures [6]
- ENTRA / APR: overthinking/redundancy attacked from the reward side [7]
- Current efficiency work (DeepSeek DSA [10], AREX-2 [1], speculative decoding)
  makes inference faster but never touches *what* gets thought.

## The architecture (5 components)

1. **Latent-native generator blocks.** Small specialists communicating in latent
   space, not tokens; per-modality/per-job internal "dialects" (one protocol for
   vision, one for code, some things as equations). Anchors: latent-space agent
   communication [22][23], emergent communication [24], COCONUT [5].
2. **Adversarial co-evolution (blue/red).** Generator blocks vs auditor blocks,
   each pushing the other. Anchors: Adversarial Reward Auditing [27], adversarial
   evolving of code+test LLMs. NOT a fixed judge — the judge is a block too.
3. **Invariant blocks.** The cheap, NON-learned sandboxes that make whole *classes*
   of cheats impossible by construction (not detection): "output must be re-derivable
   from inputs", "an audit must run on a representation the auditor didn't mutate",
   "improvement claims must replay against stored tasks". Steal from computer
   security: invariants endure, signature-chasing is always one generation behind [26].
4. **One external task referee.** Neither blue nor red controls it, or the arms race
   becomes self-referential theater.
5. **Staggered self-replication.** The system rewrites its own blocks — but layers
   crystallize at different times; never all mutating at once (see walls).

**The fixed point / anchor: Lean (or any proof assistant).** The strongest concrete
instance of "external un-gameable verifier": non-learned, deterministic, nothing in
it to hack. This instantiates Schmidhuber's Gödel machine [21] practically — the
system's output IS the proof the referee checks (AlphaProof-style loop [31]).
Bootstrapping: old deterministic proofs stay valid under system evolution, so the
architecture can be dropped *inside* its own crystallized blocks and optimize them
using old proofs. Determinism is what makes the recursion non-collapsing.

**Recursion bottom:** "drop the architecture inside each block" cannot be infinite.
It ends at invariant blocks (non-learned). If a block has neither an external check
nor an invariant, the system is unfalsifiable there — stop.

## First concrete target: the prefill problem

Prefill = O(n²) re-derivation of structure already in the text. Closest prior art:
Gist tokens [30] (learned, lossy compression of prompts). Our differentiator:
**deterministic + checkable** crystallized context (replayable against the source),
which gist tokens can't offer. Needs a cheap external staleness detector
(checksum-like relation between live task state and the crystallized structure,
recomputed every pass) — a deterministic stale artifact is worse than slow re-reading.

## The three open walls (the actual research)

1. **Shared-latent drift.** Latent-space communication requires a shared embedding
   geometry = co-training; but independent self-modification drifts the geometry and
   breaks every interface. Tokens are the stable low-bandwidth protocol that survives
   independent mutation — this tension is THE unsolved problem. Partial answer:
   staggered crystallization + per-pair medium choice (latent when co-trained,
   tokens/proxies when independently evolved).
2. **Local vs global objectives.** Independent blocks optimizing local proxies
   co-adapt into global local-optima. Self-modifying systems that escape this need
   external checkable benchmarks and STILL get objective-hacked (DGM [19]).
   The Gödel machine solves it with proofs (slow); Lean-anchoring is the fast version.
3. **Simultaneous self-replication.** A system that rewrites its own judge cannot
   certify its own improvements. Reward hacking is an equilibrium under finite
   evaluation — delayable, not eliminable [26]. Rule: the judge may evolve but only
   against data from a representation it didn't just mutate. Anchor = frozen
   *relative to* whatever it's judging, not frozen forever.

## Design rules harvested from production (docs/design.md)

The live haystack tool produced a measured failure catalog; each failure's
architectural implication is a spec line here: invariant layer as HARD constraint
(D1), graceful degradation never degrades constraints (D2), O(1)-ish relevance
judgment (D3), append-only crystalline substrate that derived structures rebuild
from (D4), pointers serve never replace (D5), set-valued corrections (D6),
zero think-budget for bounded tasks (D7), tokenizer-enforced length at the
boundary (D8). See [docs/design.md](docs/design.md).

## The project ladder (sequencing is the point)

- P1 — haystack as context-saver: complement LLMs, replace context with
  retrieval, POC + token/money savings. (DONE, live.)
- P2 — crystallization, haystack-style: plug the LLM (the agent) into the
  architecture and crystallize ITS repeated behavior into automated, checked
  components — muscle memory, not a rewrite. The canonical example: today
  Diogo must tell the agent "use the notes-router skill" (and it still
  sometimes has to be told); crystallized, the retrieval step fires
  automatically on any notes question — no thinking, no asking. Skills,
  learned corrections, and validators are the P2 building blocks. P2 lives
  here because its product is the observed behavior log: which tasks
  crystallized cleanly, which resisted, and why.
- P3 — the query-formation pass, its own layer (Diogo, 2026-11-16): before
  any callee (haystack retrieval, a d1 classifier, an LLM call), form the
  input that maximizes that callee's MEASURED performance —
  form(text, target, state) -> text. State (the task direction) supplies
  intent; the pass supplies form. Reformatting is not intent resolution.
  Consumed BY diamondhead AND haystack - a layer consumed by N callees
  belongs to neither. The rewriter itself is a crystallized rewrite-operator
  chain (genome per target; mutation random, selection strict), so it is
  P3-shaped from birth. Prototype nursery: haystack's distro-cluster
  nickname-query failure (measured first).
- P4 — only after P1, P2 and P3 have run: autopsy haystack AND the P2
  agent-in-the-loop setup — collect failures and the good parts of each —
  and from that evidence develop the from-scratch architecture (no LLM at
  the core; concepts related deterministically, prediction as glue only).
  The design rules in docs/design.md are the first input to P4. The core
  shape as spoken by Diogo 2026-11-13: [docs/p4-core.md](docs/p4-core.md) —
  a chain of thought whose links are a semantic router that either injects
  context from memory or calls a proven crystallization block; context IS
  what the router injects; training becomes link-selection, not
  next-token prediction; the only heavy compute is computing semantics.

Design stance (Diogo): models (and arguably minds) never make new concepts, only
relate existing ones in never-related ways — the goal is the most flawless relation
possible; perfection lives in re-derivability, not novelty. "Perfect" = minimize
the measured failure modes of current tech (overthinking/re-derivation,
hallucination, context cost), not literal perfection.

The cognition frame: context = reaction (working memory, discarded); haystack =
memory (deliberate recall, retrieval-on-demand); crystallization = muscle memory
(automated tasks = computation hardened past consciousness). Memory is the
substrate crystallization acts on.

## Open research question (the one thing flagged as missing)

How do we KNOW the organization (markdown structure + retrieval policy) is the
BEST? Three candidate paths: (a) audit — apply research-verified best practice;
(b) learn-from-user — reorganize per actual access patterns; (c) black-box learned
organization — REJECTED (unverifiable; "might be simplest, not best"). Working
resolution: compose them per the architecture's own pattern — (b) supplies the
referee's tasks (real query log = ground truth), (a) supplies candidate moves,
(c)-style generators may PROPOSE reorganizations but acceptance only via frozen
gates re-run on the user's measured query distribution; "best" is operationalized
as dominance on that distribution, never in the abstract.

## Reading order (dependency order, see research/papers.md for full list)

1. Modular Deep Learning survey [11] — the Lego framing, formalized
2. Neural Module Networks [16] + Capsules [17] — what "negotiated interfaces" tried
   and why it lost (negotiation ≈ attention, worse)
3. Memory Layers [3] + Titans [2] — architectural memory primitives
4. Circular Reasoning [6] + ENTRA [7] — the problem, measured
5. Emergent communication survey [24] — dynamic protocols: efficient but unstable
6. Gödel Machine [21] → Darwin Gödel Machine [19] → AlphaEvolve [20] — self-modification
7. Reward hacking equilibrium [26] + Adversarial Reward Auditing [27] — the referee problem
8. Latent-space communication [22][23] — the medium
9. Gist tokens [30] + AlphaProof [31] — the beachhead + the anchor

## Next actions (when picked up again)

- [ ] Read the reading-order stack (start with 11, 26, 19)
- [ ] Spike: deterministic context-crystallization toy — take a 10k-token context,
      compile to structured artifact (index/claims/equations), verify by replay,
      measure pass-time savings vs re-prefill
- [ ] Write the Lean-anchored validator loop sketch for the prefill case
- [ ] Search for any published "online crystallization of verified sub-procedures"
      work again before claiming novelty (checked 2026-11-06: not found)

## Status (2026-11-16): the loop runs end-to-end

- **Plugin v0.3 — every crystal routes.** The chooser classifies one
  single-question d1 call per candidate crystal, concurrently; candidates
  mined from the behavior log fire as hints beside their parents; promotion
  to `enforced` (0ms, bypasses the classifier) stays gate-earned:
  evidence>=20, injections>=5, consumed>=80%, judge-correct>=80% over >=5,
  age>=7d. **First live injection fired AND consumed on 2026-11-16**
  (conf 0.94, notes->haystack); obedience instrument: 6/6 consumed, 0%
  deviation. Acceptance criterion (learned the hard way): injections fired
  AND consumed, never "it runs".
- **Dynamic dimensions.** Per-crystal report in dogfood: conf mean/std
  (trigger stability), near_miss (d1 yes-under-gate wobble class),
  contention (multi-crystal arbitration pressure), context-judge score.
  Task direction: the session's main task is distilled once and injected as
  a reasoning scaffold; the task also biases dream priority (never the
  firing math).
- **Dreaming is genetic, not directed.** Mutation = uniform structural
  operators on the genome; usage only decides who dreams; the failure
  profile is a SELECTION signal judged by the gates, never generator
  steering. Plugin dreams are a MOCK until sequence crystals fire — the
  real genetic run lives in the spike.
- **First real GA run (spikes/addition/ga.py).** Genome = executable
  op-sequence; structural mutation; fitness axis (--fitness latency|space)
  is the only human choice. Result: the GA rediscovered double-and-add
  replay-proven under latency; the workload selected the 13-bit
  representation; the space axis correctly refuses (seed is the primitive
  floor). Same loop, different axis, opposite outcome.
- **Golden fixture.** tests/golden.json freezes the working chooser
  behavior; every change replays identical or re-blesses with a reason.
- **Honest boundaries.** True constrained decoding is impossible from a
  hook (pre-LLM injection is soft; the model can deviate — deviation rate
  is measured). The d1 conf wobbles ±0.2 on identical input; gate 0.80,
  per-crystal gates for supervised hints. Stage-2 issues (embeddings are a
  model, chars/4 vs D8) catalogued in docs/haystack-crystallization-map.md
  — P4 concerns, not plugin blockers.

## Prior art & credits

DiamondHead is built on the shoulders of a lot of recent work. The closest
lines of research, and what we take from each (full survey with deltas:
[research/prior-art-p2-plugin.md](research/prior-art-p2-plugin.md)):

- **Voyager** (2023) — the existence proof: environment-verified skills stored
  as executable code. Our delta: promotion to deterministic auto-fire.
- **SCBT — Self-Crystallizing Behavior Trees** (Oct 2026,
  [arXiv:2610.25455](https://arxiv.org/abs/2610.25455)) — the same word and the
  "compiler not runtime" idea; they compile on FAILURE via call-rate decay, we
  compile on SUCCESS via verified-use evidence.
- **Zep Agent Skills** (Nov 2026,
  [arXiv:2611.01386](https://arxiv.org/abs/2611.01386)) — capture→compile→
  curate→admit pipeline with gated admission; batch/scheduled, selection stays
  search-based. Our delta: live-traffic promotion of a procedure past scoring.
- **RSPM** ([arXiv:2610.25561](https://arxiv.org/abs/2610.25561)),
  **WikiSkill** ([arXiv:2608.27454](https://arxiv.org/abs/2608.27454)),
  **AutoSkill/SkillEvo** — offline confidence-gated promotion variants.
- **Gödel Machine** (Schmidhuber), **Darwin Gödel Machine**,
  **AlphaEvolve** — self-modification anchored to external verifiers.
- **Massalin's Synthesis superoptimizer** — dreaming: exhaustive offline
  mutation of tiny proven kernels; the oracle disposes.
- **Hippocampal replay / sleep consolidation** — the two-clock design
  (serving frozen, dreaming offline).
- **Haystack** ([github.com/diogocccarvalho/haystack](https://github.com/diogocccarvalho/haystack))
  — the companion project: indexes WHAT WE KNOW; DiamondHead indexes WHAT WE
  DO. The chooser is the join.

Claims to novelty are stated narrowly in the prior-art survey and re-verified
against late-2026 literature; corrections welcome.

## License

MIT

## Separation of concerns (2026-11-16, Diogo framing)
- haystack and diamondhead are TWO separate things: haystack = the relation/index layer over CONTENT (notes, facts, memory); diamondhead = the same shape over ACTIONS (skills, tools, procedures). The pre-LLM hook is a SEMANTIC FUNCTION CHOOSER: it selects which function runs (diamondhead's own substrate: behavior log + rule store) and the chosen function's INPUTS come from haystack (content retrieval). Two consumption edges, never merged. Crystallization = promoting a function from judged-each-time to proven-once-fires-on-trigger. Abstract: haystack indexes what we know, diamondhead indexes what we do; the chooser is the join.
