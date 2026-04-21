# Replay Online-Like Summary

Replay uses logged per-mode counterfactuals at each checkpoint. It cannot simulate new future states after alternate routing choices.

Records: `12`

| policy | expected regret | top-1 regret | accuracy | logged best loss |
| --- | ---: | ---: | ---: | ---: |
| `original_teacher` | `0.9438246618709512` | `0.9385370051379591` | `0.3333333333333333` | `0.818687615046632` |
| `saved_routing_student` | `0.4924397490840365` | `0.19060538911168567` | `0.5` | `0.8264304456933047` |
| `always_layout` | `0.3347770188314449` | `0.3347770188314449` | `0.5` | `0.7882688036773859` |
| `frequency_baseline` | `0.4588127976786531` | `0.3347770188314449` | `0.5` | `0.7882688036773859` |
| `random_seeded` | `0.8173871052726692` | `0.8173871052726692` | `0.16666666666666666` | `0.8322256783265312` |

This is not a live online experiment. It is a replay over already materialized six-branch counterfactual tensors.
