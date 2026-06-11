# HumanEval Step 1 Orchestration

This artifact is task-bespoke by design and is not intended to transfer unchanged to other benchmarks.
Live solving nodes may use only the prompt, public docstring examples, generated tests run on the candidate, self-consistency, and the terminal verifier.
`canonical_solution` is reserved for offline diagnostic oracles only.

```yaml
meta:
  task: humaneval
  description: Prompt-only Python function synthesis with verifier-guided repair over
    HumanEval-164.
  bespoke: true
  meta_model: gpt-5.5 xhigh
  source_plan: swebench/step_1_induction/PLAN.md
roles_and_dag:
  nodes:
  - id: route
    type: code
    io_contract:
      inputs:
      - profile_features
      - public_examples
      outputs:
      - route_decision
      output_schema:
        difficulty: string
        path: list
        repair_rounds: integer
        model_tier: string
    system_prompt_ref: null
    oracle:
      inference:
        kind: code
        ref: oracles/check_route.py
      diagnostic:
        kind: terminal
    model_tier: deterministic
    verification_criterion: route decision uses only prompt-profile features and selects
      an allowed path
  - id: understand_spec
    type: llm
    io_contract:
      inputs:
      - problem_prompt
      - entry_point
      - public_examples
      outputs:
      - spec_struct
      output_schema:
        signature: string
        docstring_summary: string
        input_types: list
        output_type: string
        examples: list
        edge_cases: list
        invariants: list
    system_prompt_ref: prompts/roles/understand_spec.txt
    oracle:
      inference:
        kind: code
        ref: oracles/check_understand_spec.py
      diagnostic:
        kind: code
        ref: oracles/check_understand_spec_gold.py
    model_tier: node_agent
    verification_criterion: signature and doctest examples are internally consistent
      with the prompt
  - id: plan
    type: llm
    io_contract:
      inputs:
      - spec_struct
      outputs:
      - plan_struct
      output_schema:
        algorithm: string
        cases: list
        complexity: string
        implementation_notes: list
    system_prompt_ref: prompts/roles/plan.txt
    oracle:
      inference:
        kind: rubric
        ref: oracles/check_plan_rubric.yaml
      diagnostic:
        kind: terminal
    model_tier: node_agent
    verification_criterion: plan covers algorithm, cases, and implementation notes
      without gold access
  - id: generate_tests
    type: llm
    io_contract:
      inputs:
      - spec_struct
      - plan_struct
      - public_examples
      outputs:
      - test_suite
      output_schema:
        tests: list
        rationale: string
    system_prompt_ref: prompts/roles/generate_tests.txt
    oracle:
      inference:
        kind: code
        ref: oracles/check_generate_tests.py
      diagnostic:
        kind: code
        ref: oracles/check_generate_tests_gold.py
    model_tier: node_agent
    verification_criterion: generated tests execute on the produced candidate and
      include public examples
  - id: implement
    type: llm
    io_contract:
      inputs:
      - problem_prompt
      - spec_struct
      - plan_struct
      - test_suite
      outputs:
      - candidate_completion
      output_schema:
        completion: string
        notes: string
    system_prompt_ref: prompts/roles/implement.txt
    oracle:
      inference:
        kind: code
        ref: oracles/check_implement.py
      diagnostic:
        kind: terminal
    model_tier: node_agent
    verification_criterion: candidate completion parses and passes public doctest
      examples in the sandbox
  - id: run_tests
    type: code
    io_contract:
      inputs:
      - problem_prompt
      - candidate_completion
      - test_suite
      - entry_point
      outputs:
      - test_result
      output_schema:
        public_examples_pass: boolean
        generated_tests_pass: boolean
        terminal_pass: boolean
        failures: list
    system_prompt_ref: null
    oracle:
      inference:
        kind: terminal
      diagnostic:
        kind: terminal
    model_tier: deterministic
    verification_criterion: sandboxed verifier returns structured public/generated/terminal
      verdicts
  - id: repair
    type: llm
    io_contract:
      inputs:
      - problem_prompt
      - spec_struct
      - plan_struct
      - candidate_completion
      - test_result
      outputs:
      - candidate_completion
      output_schema:
        completion: string
        repair_summary: string
    system_prompt_ref: prompts/roles/repair.txt
    oracle:
      inference:
        kind: code
        ref: oracles/check_repair.py
      diagnostic:
        kind: terminal
    model_tier: node_agent_hard
    verification_criterion: repaired completion improves the sandboxed self-test verdict
      or preserves a pass
  - id: aggregate
    type: code
    io_contract:
      inputs:
      - candidate_completions
      - test_results
      outputs:
      - selected_completion
      output_schema:
        completion: string
        selection_reason: string
    system_prompt_ref: null
    oracle:
      inference:
        kind: terminal
      diagnostic:
        kind: terminal
    model_tier: deterministic
    verification_criterion: selected completion comes from candidates that passed
      the deepest available verifier
  edges:
  - - route
    - understand_spec
  - - understand_spec
    - plan
  - - understand_spec
    - implement
  - - plan
    - generate_tests
  - - plan
    - implement
  - - generate_tests
    - implement
  - - implement
    - run_tests
  - - run_tests
    - repair
  - - repair
    - run_tests
  - - run_tests
    - aggregate
routing_rules:
- if:
    difficulty: easy
  then:
    model_tier: cheap_fast
    path:
    - understand_spec
    - implement
    - run_tests
    repair_rounds: 0
  rationale: short path for prompts with public examples and low structural complexity
- if:
    difficulty: medium
  then:
    model_tier: cheap_fast
    path:
    - understand_spec
    - plan
    - implement
    - run_tests
    - repair
    repair_rounds: 1
  rationale: planned path plus one repair for moderate edge-case risk
- if:
    difficulty: hard
    has_edge_cases: true
  then:
    model_tier: mid
    path:
    - understand_spec
    - plan
    - generate_tests
    - implement
    - run_tests
    - repair
    repair_rounds: 2
  rationale: TDAG-style conditional expansion with generated tests and two repair
    rounds
routing_calibration:
  method: DAAO difficulty estimator lifted to HumanEval distribution clusters
  thresholds:
    easy_max_score: 2
    hard_min_score: 4
    medium_max_score: 3
  cluster_counts: &id001
    easy: 108
    hard: 7
    medium: 49
  tdag_policy:
    expand_when:
    - difficulty == hard
    - has_edge_cases == true
    - public examples are missing or generated tests are needed for repair signal
    fixed_short_path_when:
    - difficulty == easy
    - public examples are present
    error_propagation_control: hard paths add generate_tests and bounded repair; easy
      paths skip those nodes to avoid unnecessary cost and static-decomposition failures
handoff_oracles:
  route:
    inference: code
    discriminates: null
    diagnostic: terminal
  understand_spec:
    inference: code
    discriminates: null
    diagnostic: code
  plan:
    inference: rubric
    discriminates: null
    diagnostic: terminal
  generate_tests:
    inference: code
    discriminates: null
    diagnostic: code
  implement:
    inference: code
    discriminates: null
    diagnostic: terminal
  run_tests:
    inference: terminal
    discriminates: null
    diagnostic: terminal
  repair:
    inference: code
    discriminates: null
    diagnostic: terminal
  aggregate:
    inference: terminal
    discriminates: null
    diagnostic: terminal
cost_success:
  R: 1.0
  c: 1.0e-05
  U: R * pass - c * sum(T_k)
  T: sum(T_k)
  criterion: "U(h) = R\xB71[pass] \u2212 c\xB7T(h), T(h) = \u03A3 T_k"
provenance:
  profile_sample_size: 164
  difficulty_counts: *id001
  seed_ids: []
  inference_oracle_discriminating_fraction: null
```

## Notes

- The graph is a typed DAG with one bounded repair back-edge implemented as an iteration limit in the runner.
- `run_tests`, `aggregate`, and `route` are deterministic code nodes.
- The live utility notation is `U(h) = R·1[pass] − c·T(h)`, `T(h) = Σ T_k`.
