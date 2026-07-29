# Figures

Use the `figure-*` files for presentations, papers, and README embeds. The
`fig*` files are retained historical pilot plots and should be treated as
provenance rather than the current public visual narrative.

## Current Figures

| file | message |
| --- | --- |
| `figure-01-fixed-time-compute-loss.png` / `.pdf` | fixed wall-clock evaluation gives each worker fewer optimizer updates as concurrency rises, and validation loss worsens |
| `figure-02-fixed-step-latency-cost.png` / `.pdf` | fixed-step evaluation keeps validation loss unchanged and moves the cost to latency |
| `figure-03-throughput-efficiency.png` / `.pdf` | throughput improves sublinearly, so parallel efficiency falls with contention |

## Historical Figures

The `fig01_*` through `fig05_*` images came from the earlier 2x2 pilot report.
They are kept so the original analysis can still be audited, but they are not
the recommended figures for explaining the compute-allocation calibration.
