---
title: "papers"
date: 2026-11-06
status: active
---

# Papers & sources — self-crystallizing architecture

All from retrieval 2026-11-06 (chat research session). Bracketed ids = citation
order from the session ledger. Grouped by role in the argument.

## The spark / context
- [1] AREX-2 (BAAI, 27B): agent that improves solutions at test time via propose-measure-reflect — https://huggingface.co/BAAI/AREX-2
- [10] DeepSeek-V3.2-Exp / DSA: trainable sparse attention over the KV cache — https://huggingface.co/deepseek-ai/DeepSeek-V3.2-Exp

## The problem is real (repetitive thinking)
- [6] Circular Reasoning: Self-Reinforcing Loops in LRMs — https://arxiv.org/pdf/2601.05693.pdf
- [7] ENTRA: Entropy-Based Redundancy Avoidance in LLM Reasoning — https://arxiv.org/pdf/2601.07123
- (related) APR: Anchor-based Process Rewards vs structural redundancy — https://arxiv.org/html/2602.00760

## Architectural memory primitives
- [2] Titans: Learning to Memorize at Test Time (Google) — https://arxiv.org/abs/2501.00663
  - caveat: critical reimplementation found gains smaller/fragile — arxiv.org/abs/2510.09551
- [3] Memory Layers at Scale (Meta FAIR): trainable key-value lookup layer — https://arxiv.org/abs/2412.09764
- [4] Recurrent Memory Transformer — https://arxiv.org/abs/2207.06881
- [5] COCONUT: reasoning in continuous latent space — https://arxiv.org/abs/2412.06769

## Modularity (the Lego idea, formalized)
- [11] Modular Deep Learning (taxonomy survey) — https://arxiv.org/abs/2302.11529
- [12] Branch-Train-MiX: train experts separately, merge into one MoE — https://arxiv.org/abs/2403.07816
- [13] Self-MoE: monolith → self-specialized experts — https://arxiv.org/abs/2406.12034
- [15] Task-Specific Small Models (Interfaze system paper) — https://arxiv.org/html/2602.04101v1
- [16] Neural Module Networks (CVPR 2016): per-task module assembly — https://arxiv.org/abs/1601.01705
- [17] Dynamic Routing Between Capsules: blocks negotiate routing per pass — https://arxiv.org/abs/1710.09829
- [14] Induction heads: the monolith already self-organizes into circuits — https://arxiv.org/abs/2404.07129

## Self-modification lineage
- [21] Gödel Machine (Schmidhuber 2003): provably optimal self-rewrite, proof system frozen — https://arxiv.org/abs/cs/0309048
- [19] Darwin Gödel Machine (Sakana, ICLR 2026): self-rewriting agent, 14%→50%, but objective-hacks — https://arxiv.org/abs/2505.22954
- [20] AlphaEvolve (DeepMind): evolutionary coding agent, real algorithmic wins — https://arxiv.org/abs/2506.13131

## The referee problem
- [26] Reward Hacking as Equilibrium under Finite Evaluation: hacking is an equilibrium under minimal axioms — https://arxiv.org/pdf/2603.28063v1.pdf
- [27] Adversarial Reward Auditing: red-team judge trained on exploits, active detection — https://arxiv.org/pdf/2602.01750v1
- [28] Self-Trained Verification for Training- and Test-Time Self-Improvement — https://arxiv.org/html/2605.30290v1
- [29] The Verification Horizon: learned verifiers are proxies, exploitable; no silver bullet — https://arxiv.org/pdf/2606.26300
- [25] Inference-Time Reward Hacking in LLMs — https://arxiv.org/abs/2506.19248
- [31] AlphaProof (DeepMind): Lean-checker-as-reward, IMO silver — https://deepmind.google/blog/ai-solves-imo-problems-at-silver-medal-level
- (related) Code-A1: adversarial evolving of code LLM vs test LLM via RL — https://arxiv.org/pdf/2603.15611v1

## The medium (latent communication)
- [22] Enabling Agents to Communicate Entirely in Latent Space — https://arxiv.org/abs/2511.09149
- [23] Latent Collaboration in Multi-Agent Systems — https://arxiv.org/abs/2511.20639
- [24] Emergent Multi-Agent Communication in the Deep Learning Era (Lazaridou & Baroni) — https://arxiv.org/abs/2006.02419

## The beachhead (prefill)
- [30] Gist Tokens: Learning to Compress Prompts (Mu et al. 2023) — https://arxiv.org/pdf/2304.08467v1.pdf
  - learned+lossy; our differentiator: deterministic + replayable
- [18] Credit assignment in modular RL (why reflection-as-messages ≈ slow backprop) — https://arxiv.org/html/2610.14750v1

## Agent-memory cousins (software-level versions of the idea)
- [8] Graph-Memoized Reasoning: reusable reasoning workflow graphs — https://arxiv.org/pdf/2511.15715
- [9] AgentSM: semantic memory for agentic text-to-SQL — https://arxiv.org/abs/2601.15709
