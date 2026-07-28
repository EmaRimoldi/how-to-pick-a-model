# Step 1 — Reusable Orchestration Induction (HumanEval, online verifier‑guided)

**Implementation spec for a coding agent (Codex‑class meta‑orchestrator).**

This document tells you how to implement **Step 1**: given a *verifiable task* and the
instances of its distribution, **induce a task‑bespoke solution structure** —
`orchestration.md` (agents, roles, I/O contracts, per‑node verifiers, conditional routing,
cost–success criterion) — by running a **single online, verifier‑guided loop over the whole
dataset**.

Dataset: **HumanEval (all 164 problems)**. Meta‑orchestrator: a coding agent with filesystem
access and a code‑execution sandbox. Faithfully reuse the cited paper methods (mapping in §10).

> **Framing (read first).** The contribution is the *induction method*, not a transferable
> artifact: HumanEval gets its own orchestration; a different task gets a different one.
> Therefore the orchestration is **task‑bespoke by design** — fitting it tightly to HumanEval
> is intended, not a defect. There is **no train/val/test split** and no held‑out set. We run
> one online loop over all 164 instances; **iteration 1 = the first pass**. This is the
> *online* regime of Agent Workflow Memory (induce from the test stream on the fly).
>
> **The one hard rule:** `canonical_solution` never enters the *solving* of an instance. It is
> used **only offline**, to measure oracle discrimination (§4‑D). Live solving uses only signal
> derivable from the instance without its gold answer + the terminal verifier. This is what
> keeps the reported pass@1 comparable to the benchmark.

---

## 0. Goal and success metric

**Deliverable:** a validated, task‑bespoke `orchestration.md` plus per‑node `check_k`
functions, produced by the online loop over HumanEval‑164.

**Primary success metric:** the **fraction of DAG nodes with a *discriminating inference‑time*
oracle** (Case 1‑inf in §4‑D). Only inference‑time oracles can run in the live loop, so only
they count toward exact downstream attribution. Gold‑based oracles are diagnostic, not part of
this number.

**Reported result (for comparability):** **pass@1 on the full 164** under the protocol
*"test‑time, verifier‑only, no gold access."* Also report the **adaptation curve**
(pass@1 and mean $U$ vs. number of instances seen) to characterize the online process — not as
a generalization claim, but to show how the induced structure stabilizes.

**Why oracles matter (criterion coupling).** Downstream we optimize per‑instance **net utility**

$$U(h) = R\cdot \mathbb{1}[f(x,y)=1] - c\cdot T(h), \qquad T(h)=\textstyle\sum_k T_k,$$

$f$ = terminal verifier, $T_k$ = cost of node $k$. The **cost** side decomposes for free from a
single run ($T_k$ observed, additive). The **success** side decomposes per node only where a
node has an inference‑time handoff oracle. Step 1's job is to manufacture as many of those as
possible.

---

## 1. Dataset and loop: HumanEval‑164, online

- **Source.** `datasets.load_dataset("openai_humaneval")` (HF) **or** the official
  `openai/human-eval` repo (recommended for its guarded execution harness). 164 problems.
- **Fields:** `task_id`, `prompt` (signature + docstring, often with `>>>` examples),
  `canonical_solution` (reference body), `test` (defines `check(candidate)`), `entry_point`.
- **Terminal verifier $f$.** Build `prompt + completion`, execute `test` + `check(entry_point)`
  in the sandbox; pass ⇔ no assertion/exception under a timeout. Reuse the official guarded
  `unsafe_execute` pattern; never execute untrusted code in‑process. A few HumanEval tests are
  weak (cf. *AI Agents That Matter*) — handle exec errors gracefully, never crash a batch.

**No splits.** All 164 instances form one stream. Process them online:

```
for each instance (or small batch) x in stream(HumanEval-164):
    y = run_orchestration(x)              # live: NO canonical_solution
    verdict = verifier(x, y)              # terminal pass/fail
    log(per-node cost T_k, intermediate states s_k, verdict)
    refine_structure(orchestration.md)    # AWM-online induction / oracle update
# iteration 1 = the first full pass; the loop may take further passes.
```

**Cold‑start seed.** At $t=0$ there is no orchestration yet. Solve the **first ~15–30 instances
with a single strong agent** (verifier‑only) to seed the DAG and derive oracles (§4‑D). These
seed instances are still part of the 164 and are still scored by the verifier — no leakage,
because gold is never used in their solving.

**Two oracle classes (keep strictly separate):**

| Class | Uses gold? | Runs where | Purpose |
|---|---|---|---|
| **Inference‑time** | No | inside the live orchestration | actual per‑node signal; counts toward the success metric |
| **Derivation‑time (gold‑based)** | Yes (`canonical_solution`) | **offline only** | measure whether an oracle *discriminates*; validate the inference‑time checker |

Inference‑time signal allowed in the loop: docstring `>>>` examples (they are in the prompt),
self‑generated tests executed **on the candidate itself** (not on gold), self‑consistency, and
the terminal verifier verdict.

---

## 2. Repository layout

```
step1/
  data/            # cached HumanEval-164 (jsonl)
  blocks/          # Phase A: building-block library (yaml)
  profile/         # Phase B: task_profile.json, clusters
  artifact/        # dag_candidate.json, orchestration.md (the deliverable)
  oracles/         # Phase D: check_<node>.py (inference) + *_gold.py (diagnostic) + rubrics
  runners/         # single-agent seed, orchestration runner, sandbox, online loop
  logs/            # raw per-node traces + per-instance verdicts (kept separate)
  metrics/         # step1_report.json + adaptation_curve.json (computed FROM logs)
  prompts/         # SELECT/ADAPT/IMPLEMENT, AWM-induce, difficulty, oracle-synth
```

**Engineering conventions (follow exactly):**
- Use a project virtualenv: look for `.venv`; if absent create it with `uv venv` +
  `uv pip install ...`. **Never use the base Python interpreter.**
- Do **not** run the full online loop yourself beyond a smoke test (1–3 instances). Emit the
  command; the operator runs the full pass.
- Long loops use `tqdm` and log metrics to the console.
- **Separate data saving from metric/plot computation:** runners write raw traces + verdicts to
  `logs/`; a separate script computes `metrics/` (report, adaptation curve, any plots) from
  `logs/`, so results are regenerable without re‑running.

---

## 3. The artifact: `orchestration.md`

Task‑bespoke, reusable across HumanEval instances (refined online), with per‑instance routing.
Keep `roles_and_dag` and `routing` **typed** (closed, valid‑by‑construction — MASS /
MermaidFlow); keep domain knowledge in prose.

```yaml
meta:
  task: humaneval
  description: "<task family description inferred in Phase B>"
  bespoke: true                 # by design; not meant to transfer
  meta_model: "<codex / gpt-5.5 xhigh>"

roles_and_dag:
  nodes:
    - id: understand_spec
      type: llm
      io_contract: {inputs: [problem_prompt], outputs: [spec_struct]}
      system_prompt_ref: prompts/roles/understand_spec.txt
      oracle: {inference: {kind: code, ref: oracles/check_understand_spec.py},
               diagnostic: {kind: code, ref: oracles/check_understand_spec_gold.py}}
    - id: generate_tests
      type: llm
      io_contract: {inputs: [spec_struct], outputs: [test_suite]}
      oracle: {inference: {kind: code, ref: oracles/check_generate_tests.py},   # tests run on candidate
               diagnostic: {kind: code, ref: oracles/check_generate_tests_gold.py}}  # tests vs canonical
    # ... plan, implement, run_tests(code), repair, aggregate ...
  edges: [[understand_spec, plan], [plan, implement], [implement, run_tests], [run_tests, repair]]

routing_rules:                  # DAAO/TDAG, calibrated on clusters (distribution-level)
  - if: {difficulty: easy}      then: {path: [understand_spec, implement, run_tests], model: cheap}
  - if: {difficulty: hard, has_edge_cases: true} then: {path: full, repair_rounds: 2, model: cheap}

handoff_oracles:                # discrimination status, measured offline
  understand_spec: {inference: code, discriminates: <bool>}
  generate_tests:  {inference: code, discriminates: <bool>}
  plan:            {inference: terminal}

cost_success:
  R: 1.0
  c: <per-token or per-call cost>
  U: "R * pass - c * sum(T_k)"   # net utility, K=1 per instance

provenance:
  seed_ids: [...]
  inference_oracle_discriminating_fraction: <float>   # the success metric
```

---

## 4. Pipeline (Phases A–F, run as one online loop)

Phases A–C run **once** to bootstrap the structure; D–F run **continuously** as the stream is
consumed (D refines oracles/structure, E routes, F measures). Iteration 1 = first full pass.

### Phase A — Building‑block library (seed, once)

A **typed pool of orchestration operators** — the orchestration‑level analogue of
Self‑Discover's atomic reasoning modules; also the closed search space (MASS / MermaidFlow).

```yaml
- {id: understand_spec, type: llm, io_contract: {inputs: [problem_prompt], outputs: [spec_struct]}}
- {id: plan,            type: llm}
- {id: generate_tests,  type: llm}
- {id: implement,       type: llm}
- {id: run_tests,       type: code}   # deterministic node (HyEvo): sandbox execution, no LLM
- {id: repair,          type: llm}
- {id: aggregate,       type: code}   # best-of-N / voting
- {id: route,           type: code}   # deterministic conditional dispatch
- {id: reflect_verify,  type: llm}    # used only where no code oracle exists
```

### Phase B — Task profiling from the stream (top‑down, no solving)

Read instance prompts (statements only, **do not solve**); extract operative features with a
cheap LLM + parsers: I/O types, #`>>>` examples, edge‑case presence, deterministic vs
reasoning‑heavy sub‑steps, and a **difficulty proxy**. Cluster into difficulty/type buckets →
these define the routing dimensions for Phase E. **Replicate DAAO's difficulty estimator**, but
**lift it to the distribution level**: calibrate difficulty→allocation thresholds on the
clusters (good on average), not per single query. Output: `profile/task_profile.json`.

### Phase C — Self‑Discover the DAG (once, task‑level)

Replicate Self‑Discover's **SELECT → ADAPT → IMPLEMENT**, lifted from reasoning modules to
orchestration blocks, run **once for the task** and reused across all instances:

1. **SELECT** — from the Phase‑A library + profile + 3–5 sample prompts, select the blocks
   relevant to this task family.
2. **ADAPT** — rephrase each selected block to be task‑specific (write its role system prompt,
   specialize its I/O contract to HumanEval coding).
3. **IMPLEMENT** — compose into an explicit **DAG** as structured JSON (`nodes` with
   `io_contract` + `verification_criterion` placeholder, `edges`), in the **Meta‑Agent** artifact
   format. Get topological variety from `library + SELECT`, not from a single LLM monologue
   (Meta‑Agent's collapse‑to‑pipeline weakness).

Output: `artifact/dag_candidate.json` (oracles filled in D).

### Phase D — Online solve‑and‑abstract (produces the oracles)

**D1 — Solve (seed, then live).** Seed: single strong agent on the first ~15–30 instances,
verifier‑only, keep successes, log node‑aligned intermediate states $s_k$. After the structure
exists, the *orchestration itself* runs and continues to feed D.

**D2 — Abstract (AWM‑online + FlowMind).** From successful traces, **induce/confirm the recurring
sub‑structure** (Agent Workflow Memory's online induction of reusable routines; FlowMind's
execute‑then‑summarize). Prune nodes never used in successful solving; add recurring missing
steps.

**D3 — Derive oracles, in both classes.** For each node $k$:

- **Inference‑time `check_k(x, s_k) -> {0,1}` (counts for the metric; NO gold):**
  - `understand_spec`: parse the docstring `>>>` examples and assert the extracted
    `examples`/`signature` are consistent and complete.
  - `generate_tests`: run the generated tests **on the produced candidate code** and check
    behavioral consistency (e.g., they execute and agree with the docstring examples).
  - `implement`: code parses and runs on the public `>>>` examples without error (syntactic/exec).
  - `run_tests` / `repair`: after repair, the self‑generated suite passes.
- **Derivation‑time `check_k_gold` (offline diagnostic only; uses `canonical_solution`):**
  - `generate_tests`: execute the generated tests against `canonical_solution` → must pass;
    optionally against a mutated buggy variant → must fail. Used **only** to *measure* whether
    the node’s inference‑time oracle discriminates correctly. Never called during solving.
- **Case 2 — rubric (LLM‑judge, noisy fallback)** for free‑text nodes (`plan`): structured
  rubric, binary output, criteria from common features of successful $s_k$. Flag noisy
  (the ~14% step‑level signal of *Who&When*); trust only aggregated over instances.
- **Case 3 — `terminal`:** no sensible local oracle → mark explicitly. **Do not fabricate** a
  checker; a constant/fake oracle is worse than none (Phase F drops non‑discriminating ones).

Output: `oracles/check_<node>.py` (inference) + `oracles/check_<node>_gold.py` (diagnostic) +
rubric specs; annotate each node with `oracle.inference.kind` and `discriminates`.

### Phase E — Conditional routing (DAAO + TDAG)

Attach routing rules `feature/difficulty (B) → branch/depth/operators/model`, calibrated on
clusters (distribution‑level). **DAAO**: difficulty → allocate depth/operators/model routing.
**TDAG**: when to expand conditionally vs keep a fixed pipeline; route hard/edge‑case instances
into `verify`/`repair`, the antidote to static‑decomposition error propagation.

### Phase F — Iteration‑1 checkpoint (replaces the pre‑Step‑3 gate)

This is no longer a separate gate but the **first measurement of the running loop**. After the
first pass over the stream, check:

1. **Structural validity** — the graph executes (near‑free given the typed space).
2. **Inference‑time oracles discriminate** — each Case‑1‑inf oracle returns both 0s and 1s
   across instances seen. Use the **gold diagnostic** to confirm the inference oracle agrees
   with ground truth often enough; if an oracle is constant or disagrees with gold, **downgrade
   to `terminal`** and record it.
3. **Beats the single‑agent baseline on $\mathbb{E}[U]$** — the orchestration’s cost–success
   exceeds the strong single agent over instances seen. If a multi‑node orchestration does not
   beat a single agent, it is not worth keeping (*MAST*); return to C/D.

Compute `inference_oracle_discriminating_fraction` and the adaptation curve. The loop then
continues (refine → next pass), so F recurs each pass.

---

## 5. Models per phase (Codex suite)

You have the Codex suite; **map these tiers to your concrete model strings.** Logic: ADAS
("strong model for design, cheap model for execution") + Self‑Discover (the discovered structure
is universal across model families — discover once with the strong model, execute with the cheap
one). **Spend the top model where leverage is highest and volume lowest** (design‑time, once);
keep per‑instance solving cheap so the cost term of $U$ stays meaningful and the MAST baseline
comparison stays honest.

| Phase / role | Volume | Model tier | Reasoning effort | Rationale (paper) |
|---|---|---|---|---|
| **Meta‑orchestrator** — pipeline control, SELECT/ADAPT/IMPLEMENT (C), oracle synthesis (D3) | low (once) | **top = GPT‑5.5** | **XHIGH** | high‑leverage design; Self‑Discover discovers structure once; ADAS uses the strongest model for the meta role |
| **Profiling / difficulty** (B) | medium | mid | low–medium | near‑classification; DAAO uses a light estimator |
| **Seed solver** (D1) — generate successful traces to derive oracles | low (15–30) | top or mid | high | needs *successes* to abstract/derive from; decoupled from the baseline |
| **Node agents** (the object being optimized; live B/E/F) | high (all instances × nodes) | **cheap/fast** | low (mid on the "hard" cluster via DAAO routing) | the criterion optimizes the orchestration, not the model; ADAS evaluates on the cheap model; keep $U$’s cost term significant |
| **LLM‑judge** for Case‑2 rubric oracles | medium | mid | low | noisy anyway; aggregated over instances (Who&When) |
| **Deterministic nodes** (run_tests, aggregate, route) | high | none (code) | — | HyEvo: deterministic execution outside the LLM |
| **Phase‑F baseline** = single agent | = #instances | **same cheap model** as node agents | match | fair MAST comparison: does the orchestration beat one cheap agent? |

> Putting GPT‑5.5 XHIGH on the per‑instance node agents would inflate both cost and the baseline
> comparison. Use it only design‑time (C, D3). The seed solver may be strong (its only job is to
> produce correct intermediate states to learn checkers from); it is **not** the Phase‑F baseline.

---

## 6. Net utility, cost logging, adaptation curve

- $U(h)=R\cdot\mathbb{1}[\text{pass}] - c\cdot T(h)$, $T(h)=\sum_k T_k$, **K = 1** per instance
  (online; no rollouts).
- Instrument every node: `tokens_in`, `tokens_out`, `calls`, `wall_ms` → `logs/`. $T_k$ observed
  and additive ⇒ **exact cost decomposition for free**.
- Keep raw per‑node logs separate from computed `metrics/` (regenerable).
- **Adaptation curve:** from `logs/`, compute pass@1 and mean $U$ vs. #instances seen →
  `metrics/adaptation_curve.json`. Saving (runners) is separate from this computation (a metrics
  script), so curves are regenerable without re‑running.
- If you experiment with best‑of‑N nodes, use a **Luby restart schedule** with a cutoff (avoids
  divergent expected cost); otherwise K = 1.

---

## 7. Prompt templates (skeletons — write originals)

Under `prompts/`: `select.txt`, `adapt.txt`, `implement.txt` (Meta‑Agent DAG format),
`awm_induce.txt` (K successful traces → recurring routine + confirm/prune verdict),
`difficulty.txt` (one prompt → bucket + flags), `oracle_synth.txt` (node spec + positive $s_k$
[+ `canonical_solution` for the *diagnostic* variant] → Python `check_k` / rubric / `TERMINAL`).

---

## 8. Environment and run commands

```bash
uv venv .venv && source .venv/bin/activate
uv pip install datasets tqdm pydantic openai   # + human-eval execution harness

python -m runners.profile --limit 3            # Phase B smoke
# (operator) python -m runners.profile
python -m runners.self_discover --profile profile/task_profile.json   # Phase C
python -m runners.seed_solve --limit 3         # Phase D1 smoke
# (operator) python -m runners.online_loop      # full online pass over all 164 (D-F)
python -m metrics.compute_step1                # reads logs/ -> step1_report.json + adaptation_curve.json
```

Run candidate code only inside `runners/sandbox.py` (subprocess + timeout + restricted env;
reuse the official human‑eval guarded execution).

---

## 9. Faithful‑to‑paper mapping

| Phase | Mechanism reused | Paper | Link |
|---|---|---|---|
| online loop | induce from the test stream on the fly (no train set) | Agent Workflow Memory (online) | [2409.07429](https://arxiv.org/abs/2409.07429) |
| A | atomic modules → closed typed space | Self‑Discover; MASS; MermaidFlow | [2402.03620](https://arxiv.org/abs/2402.03620) · [2502.02533](https://arxiv.org/abs/2502.02533) · [2505.22967](https://arxiv.org/abs/2505.22967) |
| B | difficulty estimation → allocation (lifted to distribution) | DAAO | [2509.11079](https://arxiv.org/abs/2509.11079) |
| C | SELECT → ADAPT → IMPLEMENT (once per task); DAG/IO/verifier format | Self‑Discover; Meta‑Agent | [2402.03620](https://arxiv.org/abs/2402.03620) · [2605.25233](https://arxiv.org/abs/2605.25233) |
| D | solve‑then‑abstract; induce reusable routines from successes | FlowMind; Agent Workflow Memory | [2602.11782](https://arxiv.org/abs/2602.11782) · [2409.07429](https://arxiv.org/abs/2409.07429) |
| D (nodes) | hybrid LLM + deterministic (code) nodes | HyEvo | [2603.19639](https://arxiv.org/abs/2603.19639) |
| E | conditional expansion; avoid static‑decomposition error propagation | TDAG; DAAO | [2402.10178](https://arxiv.org/abs/2402.10178) · [2509.11079](https://arxiv.org/abs/2509.11079) |
| F | "MAS must beat single agent"; verification discipline | MAST; Meta‑Agent | [2503.13657](https://arxiv.org/abs/2503.13657) · [2605.25233](https://arxiv.org/abs/2605.25233) |
| models | strong‑for‑design / cheap‑for‑execution; structure transfers across models | ADAS; Self‑Discover | [2408.08435](https://arxiv.org/abs/2408.08435) · [2402.03620](https://arxiv.org/abs/2402.03620) |
| metric | net utility / cost–success; control cost not accuracy alone | Proper time; AI Agents That Matter | [2510.12066](https://arxiv.org/abs/2510.12066) · [2407.01502](https://arxiv.org/abs/2407.01502) |

**Out of scope for Step 1 (consume *orchestration* traces → Step 3):** ABSTRAL
([2603.22791](https://arxiv.org/abs/2603.22791)), CausalFlow ([2605.25338](https://arxiv.org/abs/2605.25338)),
LEGOMem ([2510.04851](https://arxiv.org/abs/2510.04851)), Trace/OptoPrime
([2406.16218](https://arxiv.org/abs/2406.16218)), Optimas ([2507.03041](https://arxiv.org/abs/2507.03041)),
Who&When ([2505.00212](https://arxiv.org/abs/2505.00212)).

---

## 10. Definition of done

- `artifact/orchestration.md` exists, is structurally valid, task‑bespoke, and passes the
  Phase‑F checks on the first pass.
- `oracles/` has, per node, an inference‑time `check_k` (or explicit `terminal`) plus, where
  applicable, a gold diagnostic `check_k_gold`.
- `metrics/step1_report.json` reports `inference_oracle_discriminating_fraction` and the three
  Phase‑F results; `metrics/adaptation_curve.json` reports pass@1 and mean $U$ vs. #instances.
- The orchestration beats the single‑agent baseline on $\mathbb{E}[U]$, and `canonical_solution`
  was used **only** in offline diagnostics — never in solving.