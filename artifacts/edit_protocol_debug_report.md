# Edit Protocol Debug Report

Generated: `2026-04-21T17:07:56.976762+00:00`

## Observed Existing Runs

| dataset | proposals | mean raw chars | median raw chars | est mean output tokens | errors | validation failures |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `phase3_haiku_replacement` | `54` | `3706.0` | `3571.0` | `926.5` | `1` | `1` |
| `phase35_haiku_patch` | `54` | `2957.8` | `3053.5` | `739.4` | `10` | `7` |
| `phase4_opus_replacement` | `54` | `3738.5` | `3710.0` | `934.6` | `7` | `7` |

## Compact Structured Edit Examples

| payload | chars | ratio vs full template replacement |
| --- | ---: | ---: |
| full replacement template | `2496` | `1.0` |
| structured one-line edit | `219` | `0.088` |
| structured function replacement | `533` | `0.214` |

## Decision

Use structured_edits as the default real-model edit protocol; keep replacement and unified-diff as legacy fallbacks.

Reason: unified diffs reduced output length somewhat, but had high apply/repair failure rates. Structured edits avoid hunk-number/context ambiguity, reject full files, and still let the harness materialize and validate the full candidate locally.
