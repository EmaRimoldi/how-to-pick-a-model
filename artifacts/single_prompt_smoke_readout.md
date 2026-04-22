# Single-Prompt Batch Smoke Readout

Protocol: C(a), `candidate_generation: batched`, `structured_edits`.

Each step uses one model-generation prompt asking for `mode_probs`, `mode_ranking`,
and six mode-specific candidate edits in a single response. Strict configs
disable fallback to six per-mode prompts.

## Haiku

- Run: `runs/hard_profile/single_prompt/haiku_batch_structured/hard_haiku_single_prompt_smoke_1step_r0`
- Validation: passed `vao.validate_run`
- Steps: 1
- Branch evaluations: 6
- Elapsed wall-clock: 520.3 seconds
- Agent cost: `$0.2166`
- Branch correctness: 6/6
- Selected mode: `layout`
- Best counterfactual mode: `indexing`
- Selected visible loss: `0.1616895565`
- Best counterfactual loss: `0.1218360621`

Mode probabilities:

| mode | probability |
|---|---:|
| layout | 0.28 |
| caching | 0.22 |
| indexing | 0.20 |
| topk | 0.15 |
| summaries | 0.08 |
| micro | 0.07 |

Interpretation: Haiku satisfies the single-prompt batch protocol and produces a
useful routing-regret example: it selected `layout`, while the best verified
counterfactual branch was `indexing`.

## Qwen Coder Local MPS

- Run: `runs/hard_profile/single_prompt/qwen_batch_structured/hard_qwen_coder_single_prompt_smoke_1step_r1_promptfix`
- Model: `Qwen/Qwen2.5-Coder-1.5B-Instruct`
- Serving path: local OpenAI-compatible server on MPS
- Validation: passed `vao.validate_run`
- Steps: 1
- Branch evaluations: 6
- Elapsed wall-clock: 377.7 seconds
- Agent cost: `$0` local
- Branch correctness: 6/6
- Selected mode: `caching`
- Best counterfactual mode: `micro`
- Selected visible loss: `0.9949925893`
- Best counterfactual loss: `0.9907873587`

Mode probabilities:

| mode | probability |
|---|---:|
| caching | 1.00 |
| layout | 0.00 |
| indexing | 0.00 |
| topk | 0.00 |
| summaries | 0.00 |
| micro | 0.00 |

Interpretation: Qwen Coder can satisfy the single-prompt batch protocol after
the prompt was made explicit that `candidates` must be an object keyed by mode,
not a list. Routing is degenerate in this smoke: it assigns all probability to
`caching`, while the best verified counterfactual branch was `micro`.

The raw malformed first-attempt probe is saved at
`artifacts/qwen_coder_single_prompt_raw_probe.txt`.

## Qwen Local Cached

- Run: `runs/hard_profile/single_prompt/qwen_batch_structured/hard_qwen_local_cached_single_prompt_smoke_1step_r0_retry1`
- Model: `Qwen/Qwen3-0.6B-Base`
- Validation: not applicable; run did not reach branch evaluation
- Baseline verifier: completed
- Branch evaluations: 0
- Failure: `single_prompt_batch_parse_failed: ModelOutputError Extra data`
- Per-mode fallback: disabled

Interpretation: the local cached Qwen smoke exercised the strict single-prompt
path and failed honestly at the batch JSON contract. This is not a framework
failure and it did not silently become seven prompts. The production Qwen
comparison still needs the stronger Qwen Coder endpoint on Engaging or another
OpenAI-compatible GPU server.
