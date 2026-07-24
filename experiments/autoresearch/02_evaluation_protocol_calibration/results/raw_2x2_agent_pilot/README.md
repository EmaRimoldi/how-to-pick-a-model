# Raw 2x2 Agent Pilot Data

This directory preserves the machine-readable artifacts behind the first 2x2
agent workflow pilot.

The important fact is simple: these are raw artifacts from the 2x2 agent pilot.

## Files

| file | contents |
| --- | --- |
| `pilot_raw_data.json` | consolidated metrics used by the report: cell mapping, three repetitions, decomposition statistics, hypothesis counts, context summaries, raw per-cell metrics, and figure provenance |
| `decomposition_rep1.json` | decomposition terms and hypothesis checks for repetition 1 |
| `decomposition_rep2.json` | decomposition terms and hypothesis checks for repetition 2 |
| `decomposition_rep3.json` | decomposition terms and hypothesis checks for repetition 3 |

## What These Artifacts Support

They support the historical feasibility claim:

- the 2x2 agent workflow was executable;
- token and wall-clock metrics could be collected;
- proposed and accepted edit categories could be extracted;
- decomposition terms could be computed mechanically.

They do not support a strong empirical claim about which workflow is best. The
pilot had only three repetitions per cell and too few accepted edits for stable
decomposition estimates.
