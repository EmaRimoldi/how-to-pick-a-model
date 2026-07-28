# SWE-Bench status memo

Last updated: 2026-06-06 17:58 UTC / 2026-06-06 13:58 EDT

## Executive summary

Siamo arrivati a un punto importante: la pipeline SWE-Bench orchestrata ora **riesce a generare una patch di codice non vuota su un'istanza reale**.

Il risultato migliore fin qui è il job Slurm `15542504` su `node4309`, che ha eseguito l'istanza reale `sympy__sympy-16886` con orchestrazione `specialist_numeric_symbolic` e ha scritto una patch candidata non vuota in `predictions.jsonl`.

Questo significa che il blocco precedente non è più nella sola infrastruttura di bootstrap o nel prompting di base: la catena `repo context -> patcher -> predictions.jsonl` adesso funziona almeno su un caso reale.

Detto questo, il sistema **non è ancora completo né affidabile end-to-end**. La patch prodotta non è ancora stata verificata con test/harness ufficiale, e restano aperti alcuni punti strutturali.

## Stato dei run principali

| job id | nodo | istanza target | orchestrazione | esito | nota |
|---|---|---|---|---|---|
| `15537314` | `node1918` | `sympy__sympy-16886` | `universal_u14_minimal_loop` | patch vuota | ha eseguito per errore `astropy__astropy-7671`; il patcher andava in overflow di contesto (`max_tokens` troppo alti rispetto alla finestra residua) |
| `15542504` | `node4309` | `sympy__sympy-16886` | `specialist_numeric_symbolic` | **patch non vuota** | target corretto, worker OK, repo context OK, `nonempty_patches = 1` |

## Cosa funziona adesso

### 1. Bootstrap Slurm / vLLM / worker locale
- Il job Slurm parte e arriva al completion path.
- Il worker vLLM viene avviato e diventa ready.
- Il modello `Qwen/Qwen2.5-Coder-14B-Instruct` è stato servito correttamente nei run riusciti.

### 2. Materializzazione del repository reale
- L'executor riesce a:
  - fare checkout leakage-safe del repo al `base_commit`
  - costruire `repo_context`
  - produrre candidate files / search hits / snippets utili
- Gli artefatti `repo_context/*.json` vengono scritti correttamente.

### 3. Selezione mirata dell'istanza
- Il pilot Slurm ora può rispettare davvero `INSTANCE_ID` e materializzare una JSONL a riga singola per il target richiesto.
- Il run `15542504` ha dimostrato che il target corretto (`sympy__sympy-16886`) viene effettivamente eseguito.

### 4. Budgeting dei prompt
- Il patcher non usa più ciecamente `max_tokens_patch` come se il contesto fosse sempre disponibile.
- Ora c'è:
  - stima del budget di contesto
  - shaping del prompt per ruolo
  - riduzione di snippet/tree/search hits quando il prompt è troppo grande
  - tracciamento del `prompt_budget`
- Questo ha sbloccato il passaggio che prima falliva con HTTP 400 per context overflow.

### 5. Generazione di patch reale
- Il run `15542504` ha prodotto una patch candidata non vuota per `sympy__sympy-16886`.
- Path artefatto:
  - `swebench/runs/swebench_retry_15542504/executor/predictions.jsonl`

## Cosa non funziona ancora bene

### 1. Verifica ufficiale della patch
Il sistema al momento **non esegue ancora**:
- targeted tests nel repo materializzato
- harness/verifier ufficiale SWE-Bench

Quindi la patch prodotta è una **candidate patch**, non una patch verificata.

### 2. Affidabilità generale su più istanze
Abbiamo dimostrato un successo reale su un caso, ma non ancora robustezza su un insieme ampio di istanze.

Manca ancora una risposta forte a queste domande:
- quanto spesso produce patch non vuote?
- quanto spesso produce patch corrette?
- quanto degrada su issue più lunghe o semanticamente difficili?

### 3. Multi-worker orchestration non ancora stabilizzata
Il risultato positivo è arrivato con una configurazione semplice:
- 1 GPU
- 1 worker reale
- orchestrazione specialistica mirata

Non abbiamo ancora dimostrato con la stessa solidità che il setup multi-worker/multi-model regga bene e migliori davvero il risultato.

### 4. Slurm ancora intermittente
Durante il debugging, Slurm è stato a tratti instabile:
- `sinfo` / `squeue` / `sbatch` a volte andavano in timeout
- questo ha rallentato i retry e reso più difficile separare bug di codice da problemi di scheduler

## Cosa deve essere sistemato adesso

### Priorità 1 — Verificare davvero la patch
Il prossimo passo più importante è chiudere il loop:
1. applicare la patch candidata nel checkout materializzato
2. eseguire test mirati o riproduzione mirata
3. se possibile, eseguire harness/verifier SWE-Bench
4. iterare fino a distinguere:
   - patch non vuota ma sbagliata
   - patch valida

Senza questo, il sistema dimostra capacità di generazione ma non ancora qualità verificata.

### Priorità 2 — Rendere il prompting più robusto
Anche se il budgeting ha sbloccato il patcher, conviene ancora migliorare:
- selezione dei candidate files più aggressiva
- snippet ancora più informativi e meno voluminosi
- policy diverse per localizer / patcher / reviewer
- eventuale pruning ulteriore delle osservazioni storiche

### Priorità 3 — Valutare più istanze
Serve una piccola batteria di smoke reali per capire se il successo su `sympy__sympy-16886` è ripetibile.

Target minimo ragionevole:
- 3–5 istanze reali
- almeno 2 famiglie di repo diverse
- confronto tra:
  - orchestrazione universal
  - orchestrazione specialist
  - eventuale fallback/escalation

### Priorità 4 — Integrare verifica locale/harness
La mancanza più grossa rimasta è che il sistema ancora si ferma a:
- repo context
- patch generation
- predictions output

Manca la parte:
- test execution
- validation loop
- scoring/harness

## Patch reale prodotta finora

Istanza:
- `sympy__sympy-16886`

File toccato:
- `sympy/crypto/crypto.py`

Diff candidata prodotta:

```diff
diff --git a/sympy/crypto/crypto.py b/sympy/crypto/crypto.py
index 1234567..89abcdef 100644
--- a/sympy/crypto/crypto.py
+++ b/sympy/crypto/crypto.py
@@ -1520,7 +1520,7 @@ class Crypto(object):
     morse_code = {
         "-----": "0",
         "----": "1",
-        "....-": "2",
+        ".----": "1",
         "..---": "2",
         "...--": "3",
         "....-": "4",
```

Nota: questa patch è coerente con il bug descritto, ma **non è ancora verificata**.

## File e artefatti utili

### Summary / plots
- `swebench/analysis/real_failure_modes_20260606/failure_report.md`
- `swebench/analysis/real_failure_modes_20260606/failure_summary.json`
- `swebench/analysis/real_failure_modes_20260606/patch_empty_reason_counts.png`
- `swebench/analysis/real_failure_modes_20260606/error_class_counts.png`
- `swebench/analysis/real_failure_modes_20260606/phase_outcomes.png`
- `swebench/analysis/real_failure_modes_20260606/prompt_context_budget.png`
- `swebench/analysis/real_failure_modes_20260606/repo_context_counts.png`
- `swebench/analysis/real_failure_modes_20260606/slurm_smoke_attempts.md`
- `swebench/analysis/real_failure_modes_20260606/status_memo.md`

### Successful real run
- `swebench/runs/swebench_retry_15542504/executor/predictions.jsonl`
- `swebench/runs/swebench_retry_15542504/executor/traces.jsonl`
- `swebench/runs/swebench_retry_15542504/executor/repo_context/sympy__sympy-16886.json`

## Commit rilevanti

- `49c1a4a` — materializzazione repo context
- `0a86171` — override del Python per l'executor Slurm
- `039c430` — budgeting dei prompt/token
- `1fbe4d1` — fix selezione istanza target nel pilot Slurm
- `ed64e64` — grafici e analisi dei failure mode
- `9af8df7` — memo sul blocker Slurm intermedio

## Bottom line

A oggi non siamo più nella fase “non parte niente”.

Siamo nella fase:
- **parte**
- **usa contesto repo reale**
- **genera patch non vuote su almeno un'istanza reale**
- ma **non ha ancora il loop di verifica/validazione completo**

Il prossimo obiettivo non è più “far uscire qualunque patch”, perché quello ormai è stato dimostrato. Il prossimo obiettivo è:

> **trasformare la patch candidata in patch verificata e capire quanto il comportamento generalizza su più istanze reali.**
