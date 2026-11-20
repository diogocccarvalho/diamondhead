# p4-core.md — the from-scratch core, — design sketch

Sketch of the P4 architecture, recorded in
structure, cleaned only for wording. Not implemented; this is the capture of
the thinking, pre-autopsy (P2 still has to run).

## The core loop: a chain of thought, executed by a semantic router

The architecture's chain of thought is literally a chain, and the semantic
router is the link. Each link, in real time:

1. **Read the input** — the router grasps the incoming semantics. Reaction
   speed = how fast the router grasps the input; that is the whole
   performance budget.
2. **Per link, the router does two things (or either):**
   - **injects context** — pulls from memory (the database) by the same
     retrieval concept haystack uses today, and puts it where the next link
     needs it; or
   - **calls a crystallization block** — a deterministic, proven component.
   Blocks may themselves *depend on* context, and the router injects that
   too. It is circular: router → block → router → block.
3. **Repeat until the input is satisfied.** Input in, output out; semantics
   is what makes the code run around.

## Context, redefined

"Context" stops being a scrollback. It is exactly and only the amount of
information the semantic router injects at each link. Nothing else exists in
the working state — context is a routing product, not a history.

## Where the compute goes

- No encoders in the router itself — grasp happens on semantics, not tokens.
- The only compute-heavy part of the system is computing the semantics, and
  even THAT, if done with an encoder, is orders of magnitude cheaper than an
  LLM pass (an encoder forward vs a full decode). Built from scratch with
  this shape, the whole loop is fast by construction.
- Crystallized blocks are cheap: they were expensive once (at crystallization
  time), then they're proven deterministic code (D7, think-budget zero).

## Where training comes back — changed

Training stops being "predict the next token" and becomes: **which
crystallization block / action should I do next** — a routing/action-selection
objective over proven components, not a token objective. The model's job is
link selection; correctness comes from the blocks (proven) and the memory
(re-derivable), not from generation.

## Creativity, relocated

Creativity is the semantic router. What makes it "creative" is the
information retrieved from memory influencing the thinking/generation — new
combos of old parts, surfaced by routing, not conjured by a token model. This
is the design stance ("relate existing concepts in never-related ways")
turned into architecture: the router composes never-related pairings because
memory supplies the parts and the link choice supplies the novelty. Blocks
and memory are never creative; the *selection* is.

## The interface block 

The core decomposes by role at the boundary, and TWO roles are orthogonal
to any specific block:

1. the semantic router — decides WHAT happens (inject or call a block);
2. crystallization blocks — proven replay-verified functions, apply to
   everything;
3. the formation layer — decides IN WHAT SHAPE information crosses ANY
   boundary (query before retrieval, message before a classifier, prompt
   before an LLM, pointer before memory);
4. memory/context injection — what the router emits (D5).

The principle: every boundary is an interface, interfaces are first-class
citizens - they carry their own crystals (rewrite-operator genomes), their
own measured fitness per callee (Recall/MRR, TP/FP, output quality), and
their own dream loop. In a no-LLM core this is structural, not an
optimization: nothing "understands" sloppy input - the formation layer is
the only thing standing between human-shaped utterances and machine-shaped
function calls. D5 and D8 (pointers never replace; tokenizer-enforced
length at the boundary) were two scattered views of this; promoted to a
named block. Interface crystals differ from router crystals: the router
selects between alternatives, the formation layer rewrites the payload of
the selected path - different genome, different fitness, one pass each.

Audit of the interface block (2026-11-16, four errors found and fixed):

- I1 scope: no interface crystal without an OBSERVABLE downstream signal
  (retrieval: winning note read; classifier: verdict vs behavior; LLM
  prompts: none automatic - stay human/probe-judged until a probe exists).
  Prevents the formation layer from becoming a vibes layer.
- I2 anti-circularity: eval fixtures are RAW utterances, never
  pre-rewritten; the gate is always raw -> rewrite -> callee against frozen
  targets (hard_pairs.json is already raw - now deliberate).
- I3 vocabulary over genomes: target-agnostic ops (filler-strip) promoted
  once and shared; only target-specific ops carry their own gates. N x M
  independent genomes would starve the evidence budget (~20+/crystal).
- I4 runtime is frozen: chain selection happens OFFLINE in the dream loop;
  runtime runs the deterministic winner (D7 think-once). The router never
  picks rewrites per call - that would collapse formation into routing.
- I5 no implicit chaining: rewrites are single-boundary; a bad rewrite at
  boundary 1 must not silently mutate what boundary 2 receives.

## The meta-block: improvement of improvement 

'How do we maximize information usefulness across blocks - a semantic
block that trains itself to pass information around.' Audited: real, but
only as the DREAM LOOP APPLIED RECURSIVELY - the improvers' configuration
(rewrite-op genomes, chooser thresholds, selection weights) becomes itself
the genome set. Five errors fixed for it to be architecture:

- M1 credit assignment: one change per boundary at a time; fitness is
  attributed per boundary, never joint (aggregate fitness is confounded).
- M2 Goodhart at every level: each meta-level needs the two-gate law
  (measured fitness + frozen raw fixtures). The outermost guards are user
  + community + time (the A3 stance recursing).
- M3 regress terminates: the improver needs no meta-improver - mutation is
  random, selection is strict; more MEASURED GENERATIONS do the work, not
  more layers. A6 is the boundary: informed seeds are a one-time human
  cost, not a regress.
- M4 usefulness is marginal, not intrinsic: value = measured downstream
  delta GIVEN receiver state (supersession is the canonical case). The
  plugin's dimensions (superseded, contention, near_miss, consumed) are
  already the training data - the meta-block dreams over logged
  dimensions.
- M5 no live self-training: I4 recurses - all self-training is offline in
  the dream loop; runtime is always frozen; B5 contract versioning is the
  drift safety net.

Sequencing decision : the formation layer is ITS OWN
project, not folded into current workstreams - do not build yet. Scope:
implemented ONCE, deployed across all layers - as a plugin proof of
concept (diamondhead + haystack boundaries) and natively in P4 per the
interface block above. Build trigger: after the finish-everything wave
lands and the prototype nursery (haystack distro-cluster case) has
measured numbers.

## Truth maintenance: the ground-truth bit 

The architecture's stance today is "provable to work" (replay, gates). It
has no "is it TRUE" verdict. Added: every stored claim carries a
ground-truth bit, one of: TRUE / UNTRUE / BEST-AVAILABLE / NO-BETTER-
OPTION-YET. The bit is assigned by the system's OWN work and research
(runs, experiments, citations, contradictions found), not by authority or
provenance alone - finding something that at least SEEMS like the actual
truth, with the evidence linked. The bit is upgradable: BEST-AVAILABLE ->
TRUE when independent evidence accumulates; TRUE -> UNTRUE on a
contradiction (the supersession chain's head). Contradiction detection is
the trigger that flips bits; retrieval surfaces the bit with the claim.
This makes truth maintenance a first-class block: assertions enter with a
bit, bits move only through evidence events, and the append-only log
records every move.

## The ceiling principle 

The architecture has a performance ceiling: set by the quality of the
crystallization of all involved parts, the dreaming budget, and the
evidence gates - it can always get theoretically better, but at any
moment there is a MAX PERFORMANCE, and it is a measurable number, not a
mood. Two consequences: (1) per-block ceilings are stated and measured
(the spike's space floor is the seed; retrieval's MRR ceiling is bounded
by index quality), so "how close are we" is always answerable; (2) the
architecture's job is to approach the ceiling, not to claim perfection -
claims of unlimited upside are flagged as unmeasured. The ceiling is
itself movable only by new primitives (a new op language, a new index),
which are one-time human or A6-costed decisions.

## Missing concepts (audited 2026-11-16, open until designed)

1. Truth maintenance (above - the ground-truth bit is its mechanism).
2. Forgetting/decay: additive memory needs demotion; D4 makes storage
   forgetting cheap (re-derivable), but retrieval needs validity decay -
   stale notes and dead crystals occupy ranking/candidate lists forever.
3. Identity resolution: nickname/alias -> canonical concept (the distro-
   cluster failure IS this); user-taught aliases in the D1 invariant
   layer, learned aliases gated like crystals.
4. Confidence propagation: verdicts carry confidence downstream and gate
   spend (low conf -> ask, don't act); near_miss/min_conf are partial
   instances.
5. Time/freshness: "when was this true" - validity windows distinct from
   relevance.
6. Budget/priority scheduling: finite compute across candidate actions;
   dream-priority is the first instance, a global allocator comes when
   blocks multiply.

## Relation to the design rules

- D3 (relevance judgment O(1)-ish): the router IS the relevance judge, and it
  judges semantics once per link, not every candidate against every query.
- D4 (append-only memory): memory is the database all blocks are re-derivable
  from; nothing learned is ever a cache.
- D7 (zero think-budget): every block in the chain is crystallized — thinking
  was spent once, at crystallization, behind a validator.
- D1 (invariant layer): user-taught mappings sit above the router's opinion.

## Open questions (the autopsy from P2 feeds these)

- What IS the router's "grasp" without an encoder — similarity on what
  representation? ( haystack's scale-free pin rule is the current best
  hint: relative beats absolute. )
- How do blocks declare their context dependencies so the router can inject
  them? ( Interface negotiation — see wall 1 and the modularity reading: NN
  modules [16] and capsules [17] lost by making negotiation attention. )
- What is the training signal for link selection when a chain misfires —
  the P2 behavior log is the first source of ground truth for exactly this.
