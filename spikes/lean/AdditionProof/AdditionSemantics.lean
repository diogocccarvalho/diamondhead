/- DiamondHead Addition-Spike: formal semantics of the op-language
interpreter, and a proof that the GA champion cascade computes a + b.
Domain note: b is Nat (not Int) because the spec states b >= 0 - the
domain restriction is enforced by the type, not a side condition.
Cap note: the Python while_chunk has a 200-iteration safety cap; the
spec needs no cap because one division step IS the full drain, and the
dv = 0 case (Python: capped no-op) coincides with Nat's b/0 = 0, b%0 = b.
This file proves the SPEC. The Python interpreter's conformance to it is
a separate gate (recorded in the README), not claimed here. -/

namespace AdditionSemantics

abbrev State := Prod Nat Nat

inductive Op where
| addNat     : Nat -> Op
| addIfBit   : Nat -> Nat -> Op
| chunk      : Nat -> Op
| whileChunk : Nat -> Op
  deriving DecidableEq

open Op

/-- One while_chunk drain: r += (b/dv)*dv; b = b % dv. Matches the Python
loop for dv > 0 (b/dv drain steps) and the capped dv = 0 no-op. -/
def doWithChunk (r b dv : Nat) : State :=
  (r + b / dv * dv, b % dv)

def stepOp (op : Op) (state : State) : State :=
  match op with
  | .addNat va          => (Prod.fst state + va, Prod.snd state)
  | .addIfBit bi va     => if Nat.testBit (Prod.snd state) bi
                           then (Prod.fst state + va, Prod.snd state)
                           else (state)
  | .chunk sz           => if Prod.snd state ≥ sz
                           then (Prod.fst state + sz, Prod.snd state - sz)
                           else (state)
  | .whileChunk dv      => doWithChunk (Prod.fst state) (Prod.snd state) dv

def evalFold (ops : List Op) (state : State) : State :=
  List.foldl (fun acc op => stepOp op acc) state ops

/-- Evaluate a genome on inputs (a, b), return final accumulator r. -/
def evalGenome (ops : List Op) (a b : Nat) : Nat :=
  (evalFold ops (a, b)).fst

/-- The GA champion: while_chunk cascade 512..1. -/
def cascadeGenome : List Op :=
  [.whileChunk 512, .whileChunk 256, .whileChunk 128, .whileChunk 64,
   .whileChunk 32, .whileChunk 16, .whileChunk 8,  .whileChunk 4,
   .whileChunk 2,  .whileChunk 1]

/-- div*d + mod = dividend, orientation as used below. -/
theorem divmod_eq (b d : Nat) : b / d * d + b % d = b := by
  rw [Nat.mul_comm (b / d) d]
  exact Nat.div_add_mod b d

/-- Each while_chunk drain preserves the sum r + b. -/
theorem whileChunkPreservesSum (r b dv : Nat) :
    (doWithChunk r b dv).fst + (doWithChunk r b dv).snd = r + b := by
  unfold doWithChunk
  by_cases h : dv = 0
  · subst h; simp [Nat.div_zero, Nat.mod_zero]
  · rw [Nat.add_assoc, divmod_eq]

/-- The descending drain suffix: while_chunk 2^(k+1) followed by suffix k. -/
def suffix : Nat → List Op
  | 0     => [.whileChunk 1]
  | k + 1 => .whileChunk (2 ^ (k + 1)) :: suffix k

/-- Any descending drain suffix computes r + b exactly, leaving b = 0. -/
theorem suffix_correct : ∀ (k r b : Nat),
    evalFold (suffix k) (r, b) = (r + b, 0)
  | 0, r, b => by
      show stepOp (.whileChunk 1) (r, b) = (r + b, 0)
      simp [stepOp, doWithChunk, Nat.div_one, Nat.mod_one]
  | k + 1, r, b => by
      have hdiv : b / (2 ^ (k + 1)) * (2 ^ (k + 1)) + b % (2 ^ (k + 1)) = b :=
        divmod_eq b (2 ^ (k + 1))
      have hstep : stepOp (.whileChunk (2 ^ (k + 1))) (r, b) =
          (r + b / (2 ^ (k + 1)) * (2 ^ (k + 1)), b % (2 ^ (k + 1))) := rfl
      show List.foldl
        (fun acc op => stepOp op acc) (r, b)
        (.whileChunk (2 ^ (k + 1)) :: suffix k) = (r + b, 0)
      rw [List.foldl_cons, hstep]
      show evalFold (suffix k)
        (r + b / (2 ^ (k + 1)) * (2 ^ (k + 1)), b % (2 ^ (k + 1))) = (r + b, 0)
      rw [suffix_correct k (r + b / (2 ^ (k + 1)) * (2 ^ (k + 1)))
            (b % (2 ^ (k + 1))), Nat.add_assoc, hdiv]

/-- The champion genome is the 512..1 cascade = suffix 9. -/
theorem cascade_is_suffix_9 : cascadeGenome = suffix 9 := by decide

/-- MAIN THEOREM: the champion cascade computes a + b for all a b : Nat.
The stated domain (b >= 0) is enforced by the type itself. -/
theorem cascade_computes_add (a b : Nat) :
    evalGenome cascadeGenome a b = a + b := by
  rw [evalGenome, cascade_is_suffix_9, suffix_correct]

end AdditionSemantics
