/- DiamondHead Addition-Spike: formal semantics of the op-language interpreter.
   Domain note: b is Nat (not Int) because the spec states b ≥ 0.
   Safety-cap note: Python limits while_chunk to 200 iterations;
   this file defines while_chunk without the cap. -/

namespace AdditionSemantics

def State := Prod Nat Nat

inductive Op where
| addNat     : Nat -> Op
| addIfBit   : Nat -> Nat -> Op
| chunk      : Nat -> Op
| whileChunk : Nat -> Op

open Op

def doWithChunk (r b dv : Nat) : State :=
  match dv with
  | 0 => (r, b)
  | k' => let q := b / (k'+1); (r + q*(k'+1), b % (k'+1))

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

def cascadeGenome : List Op :=
  [.whileChunk 512, .whileChunk 256, .whileChunk 128, .whileChunk 64,
   .whileChunk 32, .whileChunk 16, .whileChunk 8,  .whileChunk 4,
   .whileChunk 2,  .whileChunk 1]

-- Lemma: for any positive divisor d > 0, div*d + mod = dividend  
theorem divmod_eq_dividend {d b : Nat} (hd : 0 < d) :
    b / d * d + b % d = b := by sorry

-- Key lemma: each whileChunk preserves fst+snd invariant  
theorem whileChunkPreservesSum {dv r b : Nat} :
    (doWithChunk r b dv).fst + (doWithChunk r b dv).snd = r + b := by sorry

end AdditionSemantics
