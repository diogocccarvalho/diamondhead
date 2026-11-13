# crystallization

Self-Crystallizing Architecture — plan of record. Pre-implementation; research
repo only. Born 2026-11-06 from a chat brainstorm ("what if models stop
re-thinking the same thoughts"). Companion to [haystack](https://github.com/diogocccarvalho/haystack),
whose failure catalog ([docs/SHORTCOMINGS.md](https://github.com/diogocccarvalho/haystack/blob/main/docs/SHORTCOMINGS.md))
supplied the design rules collected in [docs/design.md](docs/design.md).

Status: **research idea, no code yet** (by design — see the project ladder).

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
- P2 — use the finished haystack as substrate to develop crystallization
  (muscle memory: repeated tasks hardened into automated, checked skills).
- P3 — use P1+P2 together to develop the new architecture (self-crystallizing).

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

## License

MIT
