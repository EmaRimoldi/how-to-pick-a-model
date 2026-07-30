# GPU Model Landscape For SAI-3

Research cutoff: **2026-07-30**.

This note records the model search used to design the SAI-3 experiment. It is
not an empirical model ranking. Public coding results are screening evidence
only: they use different prompts, reasoning budgets, contexts, agents, and
tool scaffolds. The final eligibility decision must come from the frozen SAI-3
development split, never from confirmation data.

## What The Experiment Needs

The best model for this experiment is not automatically the model with the
highest SWE-bench score. SAI-3 uses independent, 192-token patch attempts with
no feedback. A model trained for long, tool-using repository trajectories may
be excellent on SWE-bench and poorly matched to this fixed-slot regime.

A primary model must satisfy all of the following:

1. Publicly downloadable weights and a license that permits the study.
2. Reproducible local GPU serving through vLLM or SGLang.
3. A stable instruct/chat checkpoint capable of emitting a parseable patch in
   the fixed output envelope.
4. Focused pass probability in `[0.15, 0.65]` on the frozen development split.
5. At least 95% parseable outputs and no model-specific retry or repair step.
6. A declared checkpoint revision, precision, chat template, reasoning mode,
   sampling configuration, serving image, and hardware topology.

Precision, reasoning mode, speculative decoding, and serving software are part
of the deployed system `M`. Changing one of them creates a different system;
it is not a harmless implementation detail.

## Memory Tiers

The weight-memory estimates below use two bytes per parameter for BF16 and do
not include KV cache, CUDA graphs, activations, or serving overhead. They are
planning lower bounds, not promises that a checkpoint will fit.

| Hardware tier | Practical BF16 target for short SAI-3 contexts | Notes |
| --- | --- | --- |
| 24 GB consumer GPU | about 7B dense | 12B requires quantization or aggressive memory controls |
| 48 GB workstation GPU | about 16B-20B dense | 24B BF16 leaves little serving headroom |
| 80 GB datacenter GPU | about 30B dense or 30B-total MoE | 35B BF16 is tight; use short context or tensor parallelism |
| 2 x 80 GB | 35B-80B total weights | preferred for 35B MoE with throughput headroom |
| 4-8 x 80 GB | 80B+ and frontier MoE | unnecessary for the primary identification test |

MoE active parameters predict per-token compute better than total parameters,
but all expert weights still have to be resident unless the runtime offloads
them. For example, a 30B-A3B model has roughly 60 GB of BF16 weights, not 6 GB.

## Candidate Audit

`BF16 GB` is the approximate language-model weight size. Vendor benchmark
numbers are reported only as evidence that a model is worth scouting; they are
not directly comparable across rows.

| Model | Architecture | BF16 GB | License | Coding evidence and runtime | SAI-3 disposition |
| --- | ---: | ---: | --- | --- | --- |
| [Qwen2.5-Coder-3B-Instruct](https://huggingface.co/Qwen/Qwen2.5-Coder-3B-Instruct) | 3B dense, code-specific | 6 | Apache-2.0 | Stable code family; standard Transformers/vLLM path | Primary low-cost identification anchor |
| [Qwen2.5-Coder-7B-Instruct](https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct) | 7B dense, code-specific | 14 | Apache-2.0 | Same tokenizer and training family as 3B/14B | Primary middle identification anchor |
| [Qwen2.5-Coder-14B-Instruct](https://huggingface.co/Qwen/Qwen2.5-Coder-14B-Instruct) | 14B dense, code-specific | 28 | Apache-2.0 | Same-family competence and cost contrast | Primary high identification anchor and baseline |
| [Qwen3.5-4B](https://huggingface.co/Qwen/Qwen3.5-4B) | 4B dense, hybrid attention, multimodal | 8 | Apache-2.0 | Official LiveCodeBench v6 55.8; vLLM/SGLang; thinking is configurable | Current compact scout; text-only, non-thinking configuration |
| [Seed-Coder-8B-Instruct](https://huggingface.co/ByteDance-Seed/Seed-Coder-8B-Instruct) | 8B dense, code-specific | 16 | MIT | Official LiveCodeBench slice 24.7 and BigCodeBench-Hard 26.4; vLLM supported | Compact code-specialist alternate |
| [SERA-8B](https://huggingface.co/allenai/SERA-8B) | 8B dense, repository-agent fine-tune | 16 | Apache-2.0 | 31.7% SWE-bench Verified at 32K; official vLLM path | Practical scout; reject if its SWE-style `submit` artifact or long-horizon format harms fixed slots |
| [Gemma-4-12B-it](https://huggingface.co/google/gemma-4-12B-it) | 12B dense, unified multimodal | 24 | Apache-2.0 | Official LiveCodeBench v6 72.0; configurable thinking | Medium alternate; new runtime and unused modalities are confounders |
| [DeepSeek-Coder-V2-Lite-Instruct](https://huggingface.co/deepseek-ai/DeepSeek-Coder-V2-Lite-Instruct) | 16B total / 2.4B active, code-specific MoE | 32 | DeepSeek model license | Mature 128K coding checkpoint with vLLM support | Legacy sparse alternate; license and age reduce priority |
| [gpt-oss-20b](https://huggingface.co/openai/gpt-oss-20b) | 20.9B total / 3.6B active MoE, native MXFP4 | under 16 at native precision | Apache-2.0 | Agentic reasoning model; official vLLM support | Cost-efficient alternate; Harmony format and reasoning tokens may not fit 192-token slots |
| [Devstral-Small-2-24B-Instruct](https://huggingface.co/mistralai/Devstral-Small-2-24B-Instruct-2512) | 24B dense, code-agent specific | 48 | Apache-2.0 | Vendor reports 68.0% SWE-bench Verified; designed for codebase tools | Practical dense code scout |
| [Qwen3.6-27B](https://huggingface.co/Qwen/Qwen3.6-27B) | 27B dense, hybrid attention, multimodal | 54 | Apache-2.0 | Vendor reports 77.2 SWE-bench Verified, 59.3 Terminal-Bench 2.0; vLLM >= 0.19 | Strong current single-80-GB scout; text-only serving and fixed reasoning mode required |
| [Qwen3-Coder-30B-A3B-Instruct](https://huggingface.co/Qwen/Qwen3-Coder-30B-A3B-Instruct) | 30.5B total / 3.3B active, code-specific MoE | 61 | Apache-2.0 | 256K agentic coding checkpoint with vLLM/SGLang support | Stable sparse code alternate |
| [North-Mini-Code-1.0](https://huggingface.co/CohereLabs/North-Mini-Code-1.0) | 30B total / 3B active, code-specific MoE | 60 | Apache-2.0 | 67.6 SWE-bench Verified, 36 Terminal-Bench 2.0; vLLM main plus Melody currently required | Preferred current sparse code scout, conditional on runtime smoke |
| [GLM-4.7-Flash](https://huggingface.co/zai-org/GLM-4.7-Flash) | 30B total / about 3B active MoE | 60 | MIT | Vendor reports 59.2 SWE-bench Verified; official example uses TP=4 and main/nightly serving branches | Reserve because runtime maturity is weaker |
| [Qwen3.6-35B-A3B](https://huggingface.co/Qwen/Qwen3.6-35B-A3B) | 35B total / 3B active, hybrid MoE, multimodal | 70 | Apache-2.0 | Vendor reports 73.4 SWE-bench Verified and 51.5 Terminal-Bench 2.0 | Strong sparse reserve; 2 x 80 GB preferred for BF16 throughput headroom |
| [KAT-Coder-V2.5-Dev](https://huggingface.co/Kwaipilot/KAT-Coder-V2.5-Dev) | 35B total / 3B active, text-only code MoE | 70 | Apache-2.0 | Qwen3.6-based agentic code model; release and runtime are less than one month old at cutoff | Watchlist only; too new for the frozen primary protocol |

### Models Not Suitable For The Core Run

- [StarCoder2-15B](https://huggingface.co/bigcode/starcoder2-15b) is a base/FIM
  model whose own card warns that instruction prompts do not work well. It is
  not comparable to instruct checkpoints without an additional fine-tune.
- [Qwen3-Coder-Next](https://huggingface.co/Qwen/Qwen3-Coder-Next) has 80B
  resident weights and about 159 GB of BF16 files. It is a useful high-end
  stress test, not a cost-effective primary model.
- [Kimi-Linear-48B-A3B-Instruct](https://huggingface.co/moonshotai/Kimi-Linear-48B-A3B-Instruct)
  has about 96 GB of BF16 weights and a custom hybrid runtime. Its million-token
  strength is irrelevant to short SAI-3 slots.
- [DeepSeek-V4-Flash](https://huggingface.co/deepseek-ai/DeepSeek-V4-Flash)
  has 284B total and 13B active parameters. Its mixed FP4/FP8 checkpoint still
  belongs to a multi-GPU frontier tier.
- [MiMo-V2.5](https://huggingface.co/XiaomiMiMo/MiMo-V2.5) has 310B total and
  15B active parameters, plus unused multimodal components.
- MiniMax-M2.1, GLM-5, DeepSeek-V4-Pro, and trillion-parameter coding models
  are excluded for the same reason: resident-weight and serving requirements
  would make infrastructure scale the dominant experimental variable.

## Recommended Staged Design

### Stage 0: infrastructure and eligibility scout

Run 24 development tasks per mode, eight correct-shard attempts, and two
attempts per wrong shard for each of these checkpoints:

1. Qwen2.5-Coder 3B, 7B, and 14B;
2. Qwen3.5-4B;
3. SERA-8B;
4. Gemma-4-12B-it;
5. Devstral-Small-2-24B;
6. Qwen3.6-27B;
7. North-Mini-Code-1.0.

This is 864 completions or 165,888 decoded tokens per model. It is an
infrastructure and regime check, not evidence for the theorem. The scout
records parse rate, focused pass probability, wrong-shard success, output
length, aggregate throughput, GPU memory, joules, and verifier time. It must
not inspect closure residuals or confirmation seeds.

North Mini Code is replaced by Qwen3-Coder-30B-A3B if its required main-branch
runtime or response parser fails the smoke. SERA-8B is replaced by
Seed-Coder-8B-Instruct if it emits scaffold-specific actions or cannot produce
parseable fixed-slot patches. These substitutions are operational, not based
on which model appears to win.

### Stage 1: primary identification

Retain Qwen2.5-Coder 3B/7B/14B for the full confirmatory protocol if all three
pass the eligibility gates. This family is intentionally code-specific,
dense, non-thinking, mature, and same-tokenizer. It gives the cleanest test of
the four-term identity because architecture and chat-protocol changes are not
confounded with model scale.

If one member fails the preregistered focused-probability range, do not silently
replace it after seeing confirmation data. Adjust task difficulty using only
the generator-development split. If no common difficulty supports all three,
report that the planned scale panel is not jointly identifiable and confirm
the largest eligible adjacent pair plus the 7B anchor.

### Stage 2: current-model transport

Only after Stage 1 analysis is frozen, run the practitioner decision test on:

1. Qwen3.5-4B as the compact current model;
2. SERA-8B as the compact coding-agent specialist;
3. Qwen3.6-27B as the strongest dense single-node candidate;
4. North-Mini-Code-1.0 as the sparse coding specialist.

This arm tests whether the deployment score transports across model families.
It is not pooled with the primary BF16 dense FLOP closure. Its primary clocks
are isolated GPU-seconds and joules, with architecture-aware FLOPs reported as
a diagnostic. Each checkpoint uses its frozen text-only chat protocol and a
non-thinking mode when its official protocol supports one. If reasoning cannot
be disabled, all generated reasoning tokens count against the fixed slot.

Devstral Small 2 is the predeclared dense alternate if Qwen3.6-27B cannot run
within the available memory topology. Gemma 4 12B is the medium alternate if
SERA fails its format gate. Do not choose alternates by SAI-3 rank.

## How Long The Run Takes

The current full protocol creates, before rare calibration extensions:

- 36,864 calibration completions per model;
- 221,184 confirmation completions per model;
- 258,048 completions and **49,545,216 decoded tokens per model**.

Output-only generation time is therefore

```text
hours per model = 49,545,216 / sustained aggregate decoded tokens per second / 3,600.
```

| Measured aggregate throughput | Hours per model | Three-model Stage 1, sequential | Four-model Stage 2, sequential |
| ---: | ---: | ---: | ---: |
| 250 token/s | 55.1 | 165.2 | 220.2 |
| 500 token/s | 27.5 | 82.6 | 110.1 |
| 1,000 token/s | 13.8 | 41.3 | 55.1 |
| 2,000 token/s | 6.9 | 20.6 | 27.5 |
| 4,000 token/s | 3.4 | 10.3 | 13.8 |

These rows are arithmetic scenarios, not assumed GPU benchmarks. Add 30%-100%
for prompt prefill, verifier execution, scheduler overhead, loading, profiler
runs, failed jobs, and the 10% live-replay audit. The Stage-0 smoke must replace
the scenarios with measured per-model throughput before reserving hardware.

A realistic planning envelope is:

- Stage 0: several GPU-hours of generation, but one working day for runtime
  setup, downloads, and format fixes;
- Stage 1 on one 80 GB GPU: roughly 2-5 wall-clock days;
- Stage 1 on three independent 80 GB GPUs: roughly 12-36 hours;
- Stage 2 on four suitable GPUs: roughly 18-48 hours after all runtimes work;
- both full stages sequentially on one GPU: about one to two weeks.

The wide ranges are deliberate. Until the exact prompt length, batch size,
GPU, serving engine, and verifier throughput are measured, a tighter estimate
would be fabricated precision. Model-parallel checkpoints can also consume
multiple GPUs without increasing the number of independent model endpoints,
so GPU count alone does not determine elapsed time.

## Decision

Do not replace the Qwen2.5-Coder identification panel merely because newer
models have higher public coding scores. It is already coding-optimized and is
the cleaner causal test. Add the heterogeneous current-model arm to establish
practical relevance. The two arms answer different questions:

- Stage 1: does the four-term decomposition close under controlled model-scale
  variation?
- Stage 2: does the resulting resource-to-solution score still choose well
  among current GPU-deployable systems?
