# SWE-bench Orchestration Oracle Validation Report

Last updated: 2026-06-06 22:55 UTC

## Executive Summary

Abbiamo chiuso un primo loop end-to-end su SWE-bench Verified:

- generazione/controllo patch tramite orchestrazione `hierarchical_h1_distribution_router`
- validazione locale della patch con `git apply --check --whitespace=nowarn`
- evaluation ufficiale SWE-bench tramite wrapper `swebench.harness.run_evaluation`
- esecuzione Modal reale
- verdetto ufficiale: `sympy__sympy-16886` risolta

Il risultato finale verificato e:

```text
submitted_instances: 1
completed_instances: 1
resolved_instances: 1
unresolved_instances: 0
error_instances: 0
empty_patch_instances: 0
resolved_ids: ["sympy__sympy-16886"]
```

Questo e il primo punto in cui la pipeline non si limita a produrre una candidate patch, ma ottiene un esito positivo dall'oracolo ufficiale.

## Scope

Istanza target:

- `sympy__sympy-16886`
- repo: `sympy/sympy`
- problema pubblico: mapping Morse errato per `"1"`
- literal pubblico errato: `"----": "1"`
- literal pubblico corretto: `".----": "1"`

Orchestrazione scelta:

- `hierarchical_h1_distribution_router`

Modelli serviti via vLLM su Slurm:

- `Qwen/Qwen3-4B-Instruct-2507`
- `Qwen/Qwen2.5-7B-Instruct`
- `Qwen/Qwen2.5-Coder-7B-Instruct`
- `Qwen/Qwen2.5-Coder-14B-Instruct`

## Changes Implemented

### 1. Official SWE-bench / Modal evaluation wrapper

File:

- `src/vao/swebench_orchestration/evaluate.py`

Il wrapper ora supporta:

- `--modal`
- `--instance-ids`
- `--output-dir`
- validazione `predictions.jsonl` / `.json`
- manifest riproducibile
- log stdout/stderr
- raccolta errori per istanza dal harness, inclusi `Patch Apply Failed`

Verifica osservata:

- `swebench` importabile nella venv
- `modal` importabile nella venv
- Modal token configurato
- `swebench.harness.run_evaluation` eseguito con `--modal true`

### 2. Local patch apply gate

File:

- `src/vao/swebench_orchestration/executor.py`

Prima di accettare una patch non vuota, l'executor ora esegue:

```text
git apply --check --whitespace=nowarn -
```

Se la patch non passa:

- non viene selezionata come prediction finale
- il trace registra `patch_apply_check`
- il trace registra `invalid_patch_count`
- il trace registra `stopping_reason = no_applicable_patch_after_apply_check`
- l'errore viene passato come osservazione al retry successivo

Questo ha evitato di mandare patch non applicabili al verifier ufficiale.

### 3. Patch repair retry

File:

- `src/vao/swebench_orchestration/executor.py`
- `configs/swebench_orchestration_slurm_pilot.yaml`

Nuovo parametro:

```yaml
patch_repair_attempts: 1
```

Se una patch non vuota fallisce `git apply --check`, l'executor concede un retry mirato anche quando `max_calls_per_component` resta 1.

### 4. Repository context ranking fix

File:

- `src/vao/swebench_orchestration/repo_context.py`

Problema osservato:

- la search hit corretta su `sympy/crypto/crypto.py` esisteva
- pero gli snippet passati al patcher erano dominati da file generici

Fix:

- search hit ad alto segnale, soprattutto literal/code snippet con punteggiatura o numeri, promuovono il file target nei `candidate_files`
- il file target viene inserito negli snippet prima dei file generici

Risultato sul caso reale:

```text
candidate_files[0] = sympy/crypto/crypto.py
```

Snippet rilevante incluso:

```text
1523:     "-----": "0", "----": "1",
```

### 5. Newline-preserving patch extraction

File:

- `src/vao/swebench_orchestration/executor.py`

Problema osservato nel harness:

```text
patch unexpectedly ends in middle of line
```

Fix:

- `_extract_patch` non tronca piu il newline finale del diff
- le patch selezionate vengono mantenute newline-terminated

### 6. Deterministic public literal repair

File:

- `src/vao/swebench_orchestration/executor.py`
- `configs/swebench_orchestration_slurm_pilot.yaml`

Nuovo parametro:

```yaml
public_literal_repair_enabled: true
```

Motivazione:

- il problem statement pubblico conteneva sia il literal errato sia quello corretto
- il repo context mostrava un'unica occorrenza del literal errato nel file candidato
- il patcher 14B ha ignorato il literal corretto e ha proposto una modifica non pertinente

Policy del repair:

- usa solo `problem_statement` pubblico e repository context al `base_commit`
- cerca coppie di literal backtickati old/new
- richiede che l'old literal appaia una sola volta nei candidate files
- genera un unified diff con `difflib`
- accetta il diff solo se `git apply --check` passa

Trace/model identity:

- la patch riparata e marcata come `hierarchical_h1_distribution_router_public_literal_repair`
- il repair e attribuito al meccanismo executor, non al patcher 14B

## Slurm Run

Run valido:

```text
job_id: 15548891
job_name: swe-h1-oracle
partition: mit_preemptable
node: node4212
state: COMPLETED
exit_code: 0:0
elapsed: 00:08:21
run_id: hierarchical_h1_oracle_20260606_183051
```

Il run ha avviato quattro worker vLLM:

```text
qwen3_4b_instruct       port 8000
qwen2_5_7b_instruct     port 8001
qwen2_5_coder_7b        port 8002
qwen2_5_coder_14b       port 8003
```

Nota di bootstrap:

- i primi due submit sono falliti per `SLURM_TMPDIR` non scrivibile (`/var/spool/slurmd/swebench`)
- il run valido ha esplicitamente fatto `unset SLURM_TMPDIR` e usato scratch sotto `/tmp/erimoldi/...`

## What Happened In The Hierarchical Run

Artifact principale:

- `swebench/runs/hierarchical_h1_oracle_20260606_183051/executor/traces.jsonl`

Fasi osservate:

```text
1 observe    executor
2 localize   h1_router                 qwen3_4b_instruct
3 other      h1_budget_guard           qwen2_5_7b_instruct
4 patch      h1_specialist_executor    qwen2_5_coder_7b
5 review     h1_reviewer               qwen2_5_7b_instruct
6 fallback   h1_escalation_patcher     qwen2_5_coder_14b
7 fallback   h1_escalation_patcher     qwen2_5_coder_14b
8 verify     executor
```

Outcome della hierarchical senza deterministic repair:

- `h1_specialist_executor` ha restituito patch vuota
- `h1_escalation_patcher` ha generato una patch non vuota
- il retry del fallback ha rigenerato essenzialmente la stessa patch
- entrambe le patch sono state respinte da `git apply --check`
- prediction originale del run: patch vuota

Errore locale sulle patch del 14B:

```text
error: patch failed: sympy/crypto/crypto.py:1522
error: sympy/crypto/crypto.py: patch does not apply
```

Diagnosi:

- il context ranking e stato corretto: `sympy/crypto/crypto.py` era presente e primo
- il modello 14B non ha sfruttato correttamente il literal pubblico corretto
- la patch proposta scambiava mapping di `M` e `N`, non il mapping di `"1"`

## Verified Patch

Prediction verificata:

- `swebench/runs/hierarchical_h1_oracle_20260606_183051/executor/predictions_public_literal_repair.jsonl`

Manifest del repair:

- `swebench/runs/hierarchical_h1_oracle_20260606_183051/executor/public_literal_repair_manifest.json`

Patch:

```diff
diff --git a/sympy/crypto/crypto.py b/sympy/crypto/crypto.py
--- a/sympy/crypto/crypto.py
+++ b/sympy/crypto/crypto.py
@@ -1520,7 +1520,7 @@
     "..-": "U", "...-": "V",
     ".--": "W", "-..-": "X",
     "-.--": "Y", "--..": "Z",
-    "-----": "0", "----": "1",
+    "-----": "0", ".----": "1",
     "..---": "2", "...--": "3",
     "....-": "4", ".....": "5",
     "-....": "6", "--...": "7",
```

Local apply check:

```text
status: passed
returncode: 0
```

## Official Modal Evaluation

Run id:

```text
hierarchical_h1_oracle_20260606_183051_public_literal_repair_modal_eval
```

Manifest:

- `swebench/evaluations/hierarchical_h1_oracle_20260606_183051_public_literal_repair_modal_eval/evaluation_manifest.json`

Report:

- `swebench/evaluations/hierarchical_h1_oracle_20260606_183051_public_literal_repair_modal_eval/hierarchical_h1_distribution_router_public_literal_repair.hierarchical_h1_oracle_20260606_183051_public_literal_repair_modal_eval.json`

Per-instance log:

- `swebench/evaluations/hierarchical_h1_oracle_20260606_183051_public_literal_repair_modal_eval/logs/run_evaluation/hierarchical_h1_oracle_20260606_183051_public_literal_repair_modal_eval/hierarchical_h1_distribution_router_public_literal_repair/sympy__sympy-16886/run_instance.log`

Verdetto:

```text
patch_apply_failed: false
resolved: true
resolved_instances: 1
error_instances: 0
```

## Test Status

Suite mirata:

```text
PYTHONPATH=src:. /home/erimoldi/openclaw_remote/projects/NeurIPS_2026/.venv/bin/python -m pytest -q tests/test_swebench_orchestration.py
```

Risultato:

```text
20 passed in 0.65s
```

Whitespace check:

```text
git diff --check
```

Risultato:

```text
clean
```

## Interpretation

Questo run dimostra tre cose distinte:

1. L'infrastruttura end-to-end ora funziona:
   - Slurm
   - vLLM multi-worker
   - executor hierarchical
   - patch apply gate
   - official SWE-bench Modal verifier

2. La hierarchical da sola non ha ancora risolto l'istanza:
   - il patcher 7B ha rinunciato
   - il fallback 14B ha prodotto patch non applicabili e semanticamente sbagliate

3. Un controllo deterministico basato su informazione pubblica puo recuperare casi literal-small-fix:
   - la repair patch non usa gold patch o hidden tests
   - usa solo issue text pubblico e repo context
   - l'oracolo ufficiale conferma la soluzione

Quindi il risultato va presentato come:

```text
Hierarchical orchestration + public-literal deterministic repair resolved 1/1 target instance under official SWE-bench Modal evaluation.
```

Non va presentato come:

```text
The 14B patcher solved the instance autonomously.
```

## Current Open Issues

1. Il patcher non sfrutta ancora bene i literal pubblici anche quando sono presenti nello snippet corretto.
2. Il reviewer non ha intercettato che la patch del 14B stava modificando M/N invece del mapping di "1".
3. Il deterministic repair e utile, ma deve essere trattato come una policy specializzata per literal-small-fix, non come capacita generale.
4. Serve valutare su piu istanze per misurare:
   - tasso di patch non vuote
   - tasso di apply-check pass
   - tasso di resolved ufficiale
   - contributo marginale del deterministic repair

## Recommended Next Steps

1. Integrare `public_literal_repair` direttamente nel normale loop executor, gia con tracing, invece di usarlo come post-processing manuale.
2. Aggiungere una metrica separata:

```text
resolved_by = model_patch | model_retry | public_literal_repair | other_deterministic_policy
```

3. Lanciare una mini-batteria da 5-10 istanze SWE-bench Verified con:

```text
hierarchical_h1_distribution_router
max_calls_per_component: 1
patch_repair_attempts: 1
public_literal_repair_enabled: true
```

4. Separare nel report finale:

- model-only success
- orchestration-assisted success
- deterministic-public-repair success
- verifier failures

5. Migliorare il prompt del patcher/reviewer con una regola specifica:

```text
If the public issue gives explicit old and expected literals, the patch must edit that exact old literal unless repository context proves it is absent.
```

## Artifact Index

Executor run:

- `swebench/runs/hierarchical_h1_oracle_20260606_183051/executor/executor_manifest.json`
- `swebench/runs/hierarchical_h1_oracle_20260606_183051/executor/traces.jsonl`
- `swebench/runs/hierarchical_h1_oracle_20260606_183051/executor/predictions.jsonl`
- `swebench/runs/hierarchical_h1_oracle_20260606_183051/executor/predictions_public_literal_repair.jsonl`
- `swebench/runs/hierarchical_h1_oracle_20260606_183051/executor/public_literal_repair_manifest.json`
- `swebench/runs/hierarchical_h1_oracle_20260606_183051/executor/repo_context/sympy__sympy-16886.json`

Evaluation:

- `swebench/evaluations/hierarchical_h1_oracle_20260606_183051_public_literal_repair_modal_eval/evaluation_manifest.json`
- `swebench/evaluations/hierarchical_h1_oracle_20260606_183051_public_literal_repair_modal_eval/hierarchical_h1_distribution_router_public_literal_repair.hierarchical_h1_oracle_20260606_183051_public_literal_repair_modal_eval.json`
- `swebench/evaluations/hierarchical_h1_oracle_20260606_183051_public_literal_repair_modal_eval/stdout.log`
- `swebench/evaluations/hierarchical_h1_oracle_20260606_183051_public_literal_repair_modal_eval/stderr.log`

Code paths changed:

- `src/vao/swebench_orchestration/evaluate.py`
- `src/vao/swebench_orchestration/executor.py`
- `src/vao/swebench_orchestration/repo_context.py`
- `configs/swebench_orchestration_slurm_pilot.yaml`
- `tests/test_swebench_orchestration.py`
