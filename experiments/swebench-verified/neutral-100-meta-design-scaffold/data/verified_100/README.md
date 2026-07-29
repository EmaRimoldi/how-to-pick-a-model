# Verified 100 Dataset Slice

This directory contains the fixed 100-instance slice used by the study.

- `download_manifest.json` records provenance: dataset
  `princeton-nlp/SWE-Bench_Verified`, split `test`, seed `20260605`, limit
  `100`, and creation time.
- `instances_public.jsonl` is the prompt-safe file used by solver prompts and
  runtime execution.
- `instances_private_metadata.jsonl` stores private bookkeeping metadata and
  must not be injected into solver prompts.

The manifest declares `include_gold_patches: false` and
`include_hints_in_public: false`. Keep those constraints intact so future trial
designs are evaluated without gold-patch or hint leakage.
