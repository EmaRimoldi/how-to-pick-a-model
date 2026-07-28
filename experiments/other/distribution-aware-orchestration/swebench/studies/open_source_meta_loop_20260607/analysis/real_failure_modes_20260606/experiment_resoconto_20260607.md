# Resoconto esperimenti SWE-bench hierarchical meta-loop

Data: 2026-06-07

## Obiettivo

Testare la pipeline completa in cui:

1. si esegue una sola orchestrazione, `hierarchical_h1_distribution_router`;
2. si valuta la patch con il verifier ufficiale SWE-bench via Modal;
3. il meta-orchestrator osserva failure, trace e verifier output;
4. il meta-orchestrator aggiorna la sola policy hierarchical;
5. si rilancia la hierarchical aggiornata e si rivaluta con Modal.

Istanza usata:

- `sympy__sympy-16886`

## Risultato finale

Il loop finale ha funzionato:

- `submitted_instances: 1`
- `completed_instances: 1`
- `resolved_instances: 1`
- `unresolved_instances: 0`
- `error_instances: 0`
- `empty_patch_instances: 0`

La patch verificata e stata prodotta dalla hierarchical aggiornata tramite la primitive decisa dal meta-orchestrator:

- `hierarchical_h1_distribution_router:public_literal_repair`

## Sequenza degli esperimenti

### 1. Run iniziale hierarchical

Run:

- `hierarchical_meta_loop_20260607_013249_initial`

Slurm:

- job `15552386`
- node `node4305`
- `COMPLETED`, exit `0:0`
- elapsed `00:06:42`

Config:

- `public_literal_repair_enabled: false`
- `patch_repair_attempts: 1`
- `max_calls_per_component: 1`

Esito:

- patch non vuota
- patch applicabile
- verifier ufficiale Modal: `resolved_instances: 0`

Interpretazione: la hierarchical base e riuscita a produrre una patch formalmente applicabile, ma semanticamente sbagliata.

### 2. Primo meta-update

Il meta-orchestrator ha ricevuto un failure bundle troppo compatto.

Decisione prodotta:

- aumentare il budget di chiamate;
- tenere `public_literal_repair_enabled: false`;
- trattare il problema come failure di localizzazione/review SymPy.

Esito del run aggiornato:

- run `hierarchical_meta_loop_20260607_013249_updated`
- job `15552679`
- node `node4305`
- `COMPLETED`, exit `0:0`
- elapsed `00:07:13`
- prediction vuota
- Modal: `No instances to run`
- `empty_patch_ids: ["sympy__sympy-16886"]`

Interpretazione: il meta-update non era ancora informato abbastanza. Il modello ha provato la correzione giusta concettualmente, ma con hunk non applicabili; siccome il repair deterministico era ancora disabilitato, l'executor ha scartato tutto.

### 3. Correzione del failure bundle

Ho aggiornato il modulo `meta_update.py` per includere nel prompt del meta-orchestrator:

- public instance fields sicuri;
- trace events con `payload_summary`;
- note del router/reviewer;
- repo context snippets da `repo_context_path`;
- valutazione Modal precedente.

Questa correzione e importante per il termine "information loss": il primo meta-update ha fallito per perdita di informazione nel riassunto passato al meta-orchestrator.

### 4. Secondo meta-update

Run meta-update:

- `meta_update_context_v2`

Decisione prodotta:

```json
{
  "max_calls_per_component": 1,
  "patch_repair_attempts": 2,
  "public_literal_repair_enabled": true
}
```

Diagnosi del meta-orchestrator:

- il router aveva identificato correttamente un caso di literal Morse-code mapping;
- il patcher primario aveva restituito patch nulla;
- il fallback 14B stava sprecando budget su un edit deterministico;
- la policy doveva abilitare `public_literal_repair` in modo condizionato e leakage-safe.

### 5. Run hierarchical aggiornato v2

Run:

- `hierarchical_meta_loop_20260607_013249_updated_context_v2`

Slurm:

- job `15552860`
- node `node4305`
- `COMPLETED`, exit `0:0`
- elapsed `00:07:14`

Config:

- `public_literal_repair_enabled: true`
- `patch_repair_attempts: 2`
- `max_calls_per_component: 1`

Trace:

- i model patcher hanno ancora prodotto hunk non applicabili;
- l'executor ha poi eseguito `executor_public_literal_repair`;
- la patch deterministica ha passato `git apply --check`;
- Modal ufficiale ha verificato la patch.

Patch finale:

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

Verifier ufficiale:

- run `hierarchical_meta_loop_20260607_013249_updated_context_v2_modal_eval`
- `resolved_instances: 1`
- per-instance `resolved: true`
- `patch_apply_failed: false`

## Conclusione

Gli esperimenti sono andati bene come test di pipeline, non come benchmark statistico.

Abbiamo dimostrato un ciclo completo:

- failure iniziale;
- feedback ufficiale Modal;
- diagnosi del meta-orchestrator;
- aggiornamento della policy hierarchical;
- rerun;
- patch verificata ufficialmente.

Il punto scientifico piu importante e che il meta-orchestrator migliora solo se riceve failure evidence abbastanza ricca. Con un bundle troppo compresso ha scelto un update sbagliato; con trace notes e repo context pubblico ha scelto la primitive giusta.

## Artifact principali

Report tecnico completo:

- `swebench/analysis/real_failure_modes_20260606/hierarchical_meta_loop_report_20260607.md`

Run root:

- `swebench/runs/hierarchical_meta_loop_20260607_013249`

Meta-update riuscito:

- `swebench/runs/hierarchical_meta_loop_20260607_013249/meta_update_context_v2/meta_update.json`
- `swebench/runs/hierarchical_meta_loop_20260607_013249/meta_update_context_v2/orchestration_design_updated.json`
- `swebench/runs/hierarchical_meta_loop_20260607_013249/meta_update_context_v2/updated_config.yaml`

Evaluation riuscita:

- `swebench/evaluations/hierarchical_meta_loop_20260607_013249/updated_context_v2_modal_eval/evaluation_manifest.json`

Analisi aggregata:

- `swebench/analysis/real_failure_modes_20260606/hierarchical_meta_loop_20260607/failure_report.md`
- `swebench/analysis/real_failure_modes_20260606/hierarchical_meta_loop_20260607/failure_summary.json`
