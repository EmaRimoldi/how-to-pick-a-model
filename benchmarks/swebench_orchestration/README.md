# SWE-bench Orchestration Benchmark Surface

This directory contains the repository-local entrypoint for the distribution-aware
orchestration experiment.  The experiment itself writes data and outputs under
`experiments/swebench_orchestration/`.

The first target is a batch-transductive smoke:

1. download a leakage-safe slice of `princeton-nlp/SWE-Bench_Verified`;
2. render a meta-designer prompt for Codex/GPT-5.5;
3. have Codex generate frozen orchestration specs offline;
4. serve open-source Qwen workers through external OpenAI-compatible GPU
   endpoints;
5. execute those frozen orchestrations with the open-source workers and log
   JSONL traces;
6. evaluate patches with the official SWE-bench harness;
7. compute certified deployment-loss diagnostics.

Gold patches are not included in `instances_public.jsonl`.
