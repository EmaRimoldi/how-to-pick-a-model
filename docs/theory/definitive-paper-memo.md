# Memo Per La Versione Definitiva

## Tesi Da Preservare

Il paper finale deve essere un framework OR, task-first, graph-aware e deployment-aware per il design di agenti verificabili.

Gerarchia dei claim:

1. Il design di agenti verificabili e' un problema di progettazione stocastica vincolata.
2. Il task non e' il grafo di esecuzione: il grafo e' indotto da design, modello e run.
3. Deployment ricorrente e singleton search sono lo stesso obiettivo a orizzonti diversi.
4. La scelta del modello dipende da compressione del grafo contro costo per-step/service cost.
5. L'identita' packed-family e' il caso trattabile pulito, non l'intero paper.

## File Da Usare

- `.local_archive/overleaf-theory-notes/final_paper_2.tex`
  - Base primaria per la versione definitiva.
  - Migliore struttura integrata: definizioni dei task, problema OR, equivalenza, packed identity, conseguenze per model choice, limiti, assumption audit.

- `.local_archive/overleaf-theory-notes/version_5.tex`
  - Da usare per la spina OR pulita: task/design/run graph, deployment objective, amortization threshold, graph compression.
  - Non copiare interamente: ha sezioni deployment duplicate e non ha bibliografia.

- `.local_archive/overleaf-theory-notes/final_paper_1.tex`
  - Da usare per la versione compatta piu' pulita di `Delta = G - epsilon` e della decomposizione a quattro termini.

- `.local_archive/overleaf-theory-notes/overnight_figures.tex`
  - Da usare per i guardrail rigorosi su certified time vs expected log-time, claim status e diagnostica.

- `docs/theory/BP.pdf`
  - Reference teorica locale da allineare prima di fissare i claim.

- `.local_archive/overleaf-theory-notes/reviewer_facing.tex`
  - Guida editoriale: prima tesi OR, poi packed decomposition come teorema di supporto.

## File Da Non Usare Come Base

- `.local_archive/overleaf-theory-notes/final_paper_0.tex`
  - Troppo ampio e contiene un `<` iniziale che rompe la compilazione.
  - Utile solo come archivio di componenti.

- `.local_archive/overleaf-theory-notes/version_4.tex`
  - Draft di merge rumoroso con label/teoremi duplicati e un ref indefinito.

- `.local_archive/overleaf-theory-notes/final_paper_3.tex`
  - Draft OR storico utile, ma troppo aggressivo: congetture e claim empirici sono troppo in evidenza.

## Guardrail Matematici

- `Delta = G - epsilon` e' esatta solo nel packed latent-mode model su expected log-time, con baseline prior-matched e support conditions.
- Non presentarla come teorema universale su wall-clock o certified quantile senza bridge esplicito.
- L'upper-envelope theorem e' un bound di supporto con assunzioni forti: tenerlo secondario.
- Transfer, continuous reward, SDS/proper-time bridge e graph-compression tree theorem vanno in appendice o come estensioni condizionali, salvo nuova prova pulita.
- Ogni claim empirico va ricollegato ad artifact reali della repo oppure rimosso.

## Prossimi Step

1. Costruire l'outline finale da `final_paper_2.tex`.
2. Riscrivere front matter seguendo la gerarchia di `reviewer_facing.tex`.
3. Importare le definizioni OR da `version_5.tex`, de-duplicate.
4. Importare solo la prova packed-family pulita da `final_paper_1.tex` / `overnight_figures.tex`.
5. Creare un claim ledger: exact, sufficient-condition, heuristic, open.
6. Mappare ogni frase empirica a un artifact reale della repo oppure rimuoverla.
