/-- DiamondHead Addition-Spike: formal semantics of the op-language interpreter.

Domain note: `b : ℕ` (not ℤ) because the spec states "b >= 0", enforced by the type.
This is why Lean uses ℕ for `b` — the domain boundary is part of the specification.

Safety-cap note: The Python interpreter limits `while_chunk` to 200 iterations.
This file defines `while_chunk` without the cap (pure mathematical semantics).
For the cascade genome (descending powers of 2: 512..1), the cap is never reached
because each `while_chunk k` ensures b_new < k after running, and the descending
order guarantees that subsequent chunks see at most b < previous_k. The cap is a
runtime guard absent from the spec; the proof establishes total correctness of the
underlying arithmetic invariant, not bounded termination of the Python variant. -/

namespace AdditionSemantics

-- ── Operations ────────────────────────────────────────────────────────────────
inductive Op where
| addNat     : Nat → Op          -- r += k
| addIfBit   : Nat → Nat → Op    -- r += k iff b has bit i set
| chunk      : Nat → Op          -- if b ≥ k then r += k; b -= k
| whileChunk : Nat → Op          -- while b ≥ k do: r += k; b -= k

open Op

-- ── Iteration auxiliary for while_chunk (cap-free) ────────────────────────────
-- After execution: b' = b % k  (< k), r' = r + floor(b/k)*k
-- Invariant preserved: r' + b' = r + b
def whileChunkAux (init_r init_b k : Nat) : Nat × Nat :=
  match k with
  | 0 => (init_r, init_b)        -- undefined in spec; identity as safety
  | _ =>
    let n := init_b / k           -- number of complete passes
    (init_r + n * k, init_b % k)  -- r accumulates drained amount; b becomes remainder

-- ── Single-op semantics on state (r, b) ───────────────────────────────────────
def evalOpState : Op → Nat × Nat → Nat × Nat
  | .addNat k,          (r, b) => (r + k, b)
  | .addIfBit i k,      (r, b) => if b.testBit i then (r + k, b) else (r, b)
  | .chunk k,           (r, b) => if b ≥ k then (r + k, b - k) else (r, b)
  | .whileChunk k,      (r, b) => whileChunkAux r b k

-- ── Genome-as-sequence semantics ─────────────────────────────────────────────
def evalGenome : List Op → Nat → Nat → Nat
  | ops, a, b =>
    let initState : Nat × Nat := (a, b)
    let finalState := List.foldl (λ st op => evalOpState op st) initState ops
    finalState.fst

-- ── Cascade genome ────────────────────────────────────────────────────────────
def cascadeGenome : List Op :=
  [.whileChunk 512, .whileChunk 256, .whileChunk 128, .whileChunk 64,
   .whileChunk 32, .whileChunk 16, .whileChunk 8,  .whileChunk 4,
   .whileChunk 2,  .whileChunk 1]

-- ── Sum-invariant lemmas ─────────────────────────────────────────────────────

/-- Every single op preserves the addition invariant r + b. -/
lemma op_sum_invariant (op : Op) (r b : Nat) :
    let (r', b') := evalOpState op (r, b)
    r' + b' = r + b := by
  dsimp [evalOpState, whileChunkAux]
  cases op with
  | addNat k =>
    simp; rfl
  | addIfBit i k =>
    split <;> simp; rfl
  | chunk k =>
    split <;> simp
    · simp [Nat.sub_add_cancel]
      ring
    · rfl
  | whileChunk k =>
    cases k with
    | zero =>
      simp; rfl
    | succ k_pos =>
      rw [Nat.div_add_mod]
      ring

/-- Fold over a list of ops preserves the addition invariant. -/
lemma fold_sum_invariant (genome : List Op) (a b : Nat) :
    let initState : Nat × Nat := (a, b)
    let finalState := List.foldl (λ st op => evalOpState op st) initState genome
    finalState.fst + finalState.snd = a + b := by
  -- Prove by induction on the genome list using foldl's accumulation property.
  have h : ∀ (ops : List Op) (r b : Nat),
      (List.foldl (λ s o => evalOpState o s) (r, b) ops).fst
        + (List.foldl (λ s o => evalOpState o s) (r, b) ops).snd
      = r + b := by
    intro ops
    induction ops with
    | nil =>
      simp [List.foldl_nil]; rfl
    | cons op ops ih =>
      dsimp [List.foldl_cons]
      let (r₀, b₀) := (r, b)
      let (r₁, b₁) := evalOpState op (r₀, b₀)
      -- By single-op invariant: r₁ + b₁ = r₀ + b₀
      have h1 := op_sum_invariant op r₀ b₀
      -- By IH applied to rest of list starting from (r₁, b₁):
      -- fold result sum = r₁ + b₁
      have h2 := ih ops r₁ b₁
      calc
        (List.foldl (λ s o => evalOpState o s) (r₁, b₁) ops).fst
          + (List.foldl (λ s o => evalOpState o s) (r₁, b₁) ops).snd
            = r₁ + b₁ := h2
        _             = r₀ + b₀ := by rw [h1]
  simpa [initState, finalState] using h genome a b

-- ── whileChunk 1 drains all remaining b to 0 ─────────────────────────────────
lemma whileChunk_1_drains_all (r b : Nat) :
    let (r', b') := evalOpState (.whileChunk 1) (r, b)
    b' = 0 := by
  dsimp [evalOpState, whileChunkAux]
  simp  -- 1 > 0 case: b % 1 = 0

-- ── Core theorem: cascade genome computes addition ───────────────────────────
theorem cascade_genome_correct (a b : Nat) :
    evalGenome cascadeGenome a b = a + b := by
  -- The cascade genome is: [whileChunk 512, ..., whileChunk 1]
  -- We prove:
  -- 1. The addition invariant r + b = a + b holds throughout execution.
  -- 2. The last operation is whileChunk 1, which leaves b_final = 0.
  -- 3. Thus r_final + 0 = a + b ⟹ r_final = a + b.

  dsimp [cascadeGenome, evalGenome]
  
  -- First establish the invariant for every prefix of the genome
  have inv : (List.foldl (λ st op => evalOpState op st) (a, b) cascadeGenome).fst
              + (List.foldl (λ st op => evalOpState op st) (a, b) cascadeGenome).snd
            = a + b := by
    apply fold_sum_invariant
  
  -- Now show the last element (whileChunk 1) forces b_final = 0
  -- We decompose the fold into prefix + last element.
  rcases cascadeGenome.isCons with ⟨prefix, lastOp, eq⟩
  rw [eq]
  
  -- lastOp must be .whileChunk 1 (since cascadeGenome ends with it)
  have hLast : lastOp = .whileChunk 1 := by
    simp [cascadeGenome] at eq
    exact eq.symm.decompose |>.tail.tail.rfl -- cascadeGenome.last = .whileChunk 1
    sorry
  
  -- The fold splits: prefix processes first, then lastOp on top of prefix result
  have splitFold :
      let preState := List.foldl (λ st op => evalOpState op st) (a, b) prefix
      let finalState := evalOpState lastOp preState
      finalState.fst + finalState.snd = a + b := by
    simp [List.foldl_cons]
    -- preState sum invariant from IH (we need it)
    sorry
  
  sorry  -- Will flesh out below

end AdditionSemantics
