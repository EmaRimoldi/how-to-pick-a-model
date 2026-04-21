# Phase 4 Step Diagnostics

Generated: `2026-04-21T15:51:23.957335Z`

Correct means the selected top-probability mode equals the verified-best gain mode for that checkpoint.

| profile | run | step | selected | verified best | correct | regret |
| --- | --- | ---: | --- | --- | ---: | ---: |
| `paper_development` | `opus_teacher_pilot_claude_opus_teacher_paper_development` | `0` | `layout` | `layout` | `True` | `0.0` |
| `paper_development` | `opus_teacher_pilot_claude_opus_teacher_paper_development` | `1` | `indexing` | `caching` | `False` | `0.04926446165976328` |
| `paper_development` | `opus_teacher_pilot_claude_opus_teacher_paper_development` | `2` | `topk` | `indexing` | `False` | `0.3551235986893463` |
| `development` | `opus_teacher_pilot_retry2_claude_opus_teacher_development` | `0` | `layout` | `caching` | `False` | `0.3511457094221968` |
| `development` | `opus_teacher_pilot_retry2_claude_opus_teacher_development` | `1` | `summaries` | `micro` | `False` | `4.217488474179428` |
| `development` | `opus_teacher_pilot_retry2_claude_opus_teacher_development` | `2` | `topk` | `micro` | `False` | `1.766929415789876` |
| `memory_development` | `opus_teacher_pilot_retry2_claude_opus_teacher_memory_development` | `0` | `layout` | `layout` | `True` | `0.0` |
| `memory_development` | `opus_teacher_pilot_retry2_claude_opus_teacher_memory_development` | `1` | `summaries` | `layout` | `False` | `3.413074223754801` |
| `memory_development` | `opus_teacher_pilot_retry2_claude_opus_teacher_memory_development` | `2` | `layout` | `layout` | `True` | `0.0` |
| `paper_development` | `opus_teacher_dev_r0` | `0` | `layout` | `indexing` | `False` | `0.4987979847608234` |
| `paper_development` | `opus_teacher_dev_r0` | `1` | `indexing` | `indexing` | `True` | `0.0` |
| `paper_development` | `opus_teacher_dev_r0` | `2` | `topk` | `layout` | `False` | `0.6106201933992755` |

## Per-Step Mode Probabilities And Gains

### 1. `paper_development` step `0`

Run: `opus_teacher_pilot_claude_opus_teacher_paper_development`
Step record: `runs/phase4_teacher_opus_pilot/opus_teacher_pilot_claude_opus_teacher_paper_development/steps/step_0000/step_record.json`

Selected: `layout`; verified best: `layout`; correct: `True`; regret: `0.0`

| mode | q_t probability | verified gain |
| --- | ---: | ---: |
| `layout` **selected** **best** | `0.38` | `0.18608443551370046` |
| `indexing` | `0.3` | `-0.16101804186599145` |
| `topk` | `0.1` | `-0.08026542006104931` |
| `caching` | `0.05` | `-0.07944881635698486` |
| `summaries` | `0.1` | `-2.4611291485426356` |
| `micro` | `0.07` | `-0.017870915144883037` |

### 2. `paper_development` step `1`

Run: `opus_teacher_pilot_claude_opus_teacher_paper_development`
Step record: `runs/phase4_teacher_opus_pilot/opus_teacher_pilot_claude_opus_teacher_paper_development/steps/step_0001/step_record.json`

Selected: `indexing`; verified best: `caching`; correct: `False`; regret: `0.04926446165976328`

| mode | q_t probability | verified gain |
| --- | ---: | ---: |
| `layout` | `0.03` | `-0.24164264894607979` |
| `indexing` **selected** | `0.55` | `-0.1171123092618983` |
| `topk` | `0.12` | `-0.48140323552045106` |
| `caching` **best** | `0.05` | `-0.06784784760213503` |
| `summaries` | `0.18` | `-3.0835782143510415` |
| `micro` | `0.07` | `-1.0104889839445255` |

### 3. `paper_development` step `2`

Run: `opus_teacher_pilot_claude_opus_teacher_paper_development`
Step record: `runs/phase4_teacher_opus_pilot/opus_teacher_pilot_claude_opus_teacher_paper_development/steps/step_0002/step_record.json`

Selected: `topk`; verified best: `indexing`; correct: `False`; regret: `0.3551235986893463`

| mode | q_t probability | verified gain |
| --- | ---: | ---: |
| `layout` | `0.03` | `0.05918430880418957` |
| `indexing` **best** | `0.07` | `0.15268354315022192` |
| `topk` **selected** | `0.42` | `-0.20244005553912436` |
| `caching` | `0.06` | `-0.05305432078884631` |
| `summaries` | `0.32` | `0.02179532705842535` |
| `micro` | `0.1` | `0.04267658225333071` |

### 4. `development` step `0`

Run: `opus_teacher_pilot_retry2_claude_opus_teacher_development`
Step record: `runs/phase4_teacher_opus_pilot/opus_teacher_pilot_retry2_claude_opus_teacher_development/steps/step_0000/step_record.json`

Selected: `layout`; verified best: `caching`; correct: `False`; regret: `0.3511457094221968`

| mode | q_t probability | verified gain |
| --- | ---: | ---: |
| `layout` **selected** | `0.35` | `-0.05682848666718987` |
| `indexing` | `0.3` | `-0.05696530327472071` |
| `topk` | `0.08` | `-0.3673642113232044` |
| `caching` **best** | `0.07` | `0.29431722275500694` |
| `summaries` | `0.15` | `-4.0705833875628095` |
| `micro` | `0.05` | `-0.10185960409029249` |

### 5. `development` step `1`

Run: `opus_teacher_pilot_retry2_claude_opus_teacher_development`
Step record: `runs/phase4_teacher_opus_pilot/opus_teacher_pilot_retry2_claude_opus_teacher_development/steps/step_0001/step_record.json`

Selected: `summaries`; verified best: `micro`; correct: `False`; regret: `4.217488474179428`

| mode | q_t probability | verified gain |
| --- | ---: | ---: |
| `layout` | `0.05` | `0.01202471492003987` |
| `indexing` | `0.12` | `-0.01978070749583072` |
| `topk` | `0.25` | `-0.48351109898482836` |
| `caching` | `0.15` | `-0.061869255801551004` |
| `summaries` **selected** | `0.35` | `-4.176649382435418` |
| `micro` **best** | `0.08` | `0.040839091744010125` |

### 6. `development` step `2`

Run: `opus_teacher_pilot_retry2_claude_opus_teacher_development`
Step record: `runs/phase4_teacher_opus_pilot/opus_teacher_pilot_retry2_claude_opus_teacher_development/steps/step_0002/step_record.json`

Selected: `topk`; verified best: `micro`; correct: `False`; regret: `1.766929415789876`

| mode | q_t probability | verified gain |
| --- | ---: | ---: |
| `layout` | `0.08` | `-0.9234994551820046` |
| `indexing` | `0.18` | `-1.250034641665147` |
| `topk` **selected** | `0.3` | `-0.005546208876104686` |
| `caching` | `0.12` | `-0.15959514265662023` |
| `summaries` | `0.22` | `-1.0574013450956041` |
| `micro` **best** | `0.1` | `1.7613832069137714` |

### 7. `memory_development` step `0`

Run: `opus_teacher_pilot_retry2_claude_opus_teacher_memory_development`
Step record: `runs/phase4_teacher_opus_pilot/opus_teacher_pilot_retry2_claude_opus_teacher_memory_development/steps/step_0000/step_record.json`

Selected: `layout`; verified best: `layout`; correct: `True`; regret: `0.0`

| mode | q_t probability | verified gain |
| --- | ---: | ---: |
| `layout` **selected** **best** | `0.42` | `0.27736156334486395` |
| `indexing` | `0.3` | `-0.19980240010094374` |
| `topk` | `0.05` | `-0.6197951154957575` |
| `caching` | `0.08` | `-0.14032670255234714` |
| `summaries` | `0.1` | `-3.4586681146378626` |
| `micro` | `0.05` | `0.07194159953367951` |

### 8. `memory_development` step `1`

Run: `opus_teacher_pilot_retry2_claude_opus_teacher_memory_development`
Step record: `runs/phase4_teacher_opus_pilot/opus_teacher_pilot_retry2_claude_opus_teacher_memory_development/steps/step_0001/step_record.json`

Selected: `summaries`; verified best: `layout`; correct: `False`; regret: `3.413074223754801`

| mode | q_t probability | verified gain |
| --- | ---: | ---: |
| `layout` **best** | `0.04` | `0.028440110816334574` |
| `indexing` | `0.12` | `-0.1855921763878874` |
| `topk` | `0.25` | `-0.5333952331660498` |
| `caching` | `0.15` | `-0.09405792479442121` |
| `summaries` **selected** | `0.38` | `-3.3846341129384663` |
| `micro` | `0.06` | `-0.5360300833833008` |

### 9. `memory_development` step `2`

Run: `opus_teacher_pilot_retry2_claude_opus_teacher_memory_development`
Step record: `runs/phase4_teacher_opus_pilot/opus_teacher_pilot_retry2_claude_opus_teacher_memory_development/steps/step_0002/step_record.json`

Selected: `layout`; verified best: `layout`; correct: `True`; regret: `0.0`

| mode | q_t probability | verified gain |
| --- | ---: | ---: |
| `layout` **selected** **best** | `0.4` | `2.9571001775099166` |
| `indexing` | `0.22` | `0.4419078570964885` |
| `topk` | `0.2` | `-0.014861201075283326` |
| `caching` | `0.07` | `-0.01703335919230131` |
| `summaries` | `0.03` | `0.026001288401479528` |
| `micro` | `0.08` | `-0.033125474260875976` |

### 10. `paper_development` step `0`

Run: `opus_teacher_dev_r0`
Step record: `runs/phase4_teacher_opus/opus_teacher_dev_r0/steps/step_0000/step_record.json`

Selected: `layout`; verified best: `indexing`; correct: `False`; regret: `0.4987979847608234`

| mode | q_t probability | verified gain |
| --- | ---: | ---: |
| `layout` **selected** | `0.35` | `-0.14257249965528007` |
| `indexing` **best** | `0.3` | `0.3562254851055433` |
| `topk` | `0.09` | `-0.09590824822064681` |
| `caching` | `0.07` | `-0.1450289965502619` |
| `summaries` | `0.14` | `-2.315011078751937` |
| `micro` | `0.05` | `0.13444834376155024` |

### 11. `paper_development` step `1`

Run: `opus_teacher_dev_r0`
Step record: `runs/phase4_teacher_opus/opus_teacher_dev_r0/steps/step_0001/step_record.json`

Selected: `indexing`; verified best: `indexing`; correct: `True`; regret: `0.0`

| mode | q_t probability | verified gain |
| --- | ---: | ---: |
| `layout` | `0.05` | `0.07648622936297345` |
| `indexing` **selected** **best** | `0.45` | `0.2628756865475682` |
| `topk` | `0.18` | `-0.30500265541843397` |
| `caching` | `0.08` | `-0.06863327361520244` |
| `summaries` | `0.18` | `-1.677445919658879` |
| `micro` | `0.06` | `-0.23988057921704353` |

### 12. `paper_development` step `2`

Run: `opus_teacher_dev_r0`
Step record: `runs/phase4_teacher_opus/opus_teacher_dev_r0/steps/step_0002/step_record.json`

Selected: `topk`; verified best: `layout`; correct: `False`; regret: `0.6106201933992755`

| mode | q_t probability | verified gain |
| --- | ---: | ---: |
| `layout` **best** | `0.05` | `0.08121041974060983` |
| `indexing` | `0.1` | `-0.40784359431651784` |
| `topk` **selected** | `0.35` | `-0.5294097736586657` |
| `caching` | `0.18` | `-0.07163120968285042` |
| `summaries` | `0.25` | `0.008258758968930913` |
| `micro` | `0.07` | `0.006227064644743763` |
