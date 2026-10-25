# Engineering

This section explains the verified-task collectors, shared accounting and verification,
and the recorded-evidence workflow.

| File | Role |
|---|---|
| [`architecture.md`](architecture.md) | Current package/runtime architecture |
| [`layout.md`](layout.md) | File placement, command compatibility and frozen provenance |
| [`development.md`](development.md) | Reading order, evidence constraints and maintenance commands |

The optional [environment example](environment.env.example) lists provider/router
variables. Copy it to `.env` at the repository root if useful; runners read the
process environment and do not load this file automatically. Keep credentials
untracked.
