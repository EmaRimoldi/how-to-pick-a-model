# Black/13: original tokenizer package qualification

The first package-context component from the retained 34-ID source queue now
runs with its original module hierarchy and relative imports. The complete
upstream `blib2to3/pgen2/tokenize.py` is editable; the unchanged original token
module and two package initializers are immutable context. A common visible
adapter calls the actual generator on source strings. No token stream, parser
class or dependency is simulated.

This removes the flat-module constraint for this component. It is **not an
official full-project BugsInPy score, a model result or a qualified new cohort**.
The full Black formatter and grammar/driver pipeline are not executed here.

## Verified behavior

The task and separate suites were frozen in [qualification-plan.json](qualification-plan.json)
before any upstream execution. Both versions are tested twice on each suite.
The first public input is the original `python37.py` regression example; the
other token-class expectations were specified manually before execution.
No cases, expectations, adapters or criterion changed after viewing outcomes.

| Version | Public token tests | Separate evaluator token tests |
| --- | ---: | ---: |
| Original bug | 6/8 | 4/8 |
| Original upstream fix | 8/8 | 8/8 |

All repetitions agree. Qualification comprises **64 candidate-case executions**.
Coverage adds **16** ordinary/covered executions on the original public suite;
every observation agrees with the saved public feedback. The complete spectrum
contains 108 covered locations, with all ties and zero scores retained. This
establishes coverage feasibility, not fault-location accuracy or repair benefit.
Two additional synthetic calls verify the native isolation boundary.

An independent sandbox replay repeats all 80 candidate/diagnostic calls and the
two isolation probes without discrepancies. Three inert F/N/S requests reproduce
from the public bank. All source, observations, event journals, timings and exact
executed runtime bytes are retained in the archives. The public/evaluator split
is input-disjoint but entirely **published development data**, not a holdout.

## Explicit package interface

`PackageTask` uses schema version 2; the version-1 flat-module contract is unchanged.
The workspace may contain up to 64 Python files (at most 16 editable), at most
256 KiB each and 2 MiB overall. Explicit package initializers are required.
Traversal, path aliases, ambiguous module/package names and reserved worker
names are rejected. This qualification uses Python source with standard-library
dependencies; the backend does not provision/pin third-party environments or
support grammar/data resources yet.

`PackageVerifier` creates a fresh source tree and process for every call. Native
macOS isolation denies network and external private-file access. All supplied
source is read-only while running; scratch writes are allowed separately.
Tests cover attempted writes, chmod, directory renames, hardlink and symlink
aliases, stale process state, timeouts, invalid source and disabled tracing.
Expected answers, private case labels and credentials never enter the worker.
Support-file bytes and entrypoint identity are bound to public observations;
using a verifier built for different immutable context is rejected.

The adapter omits comment, indentation, newline and end-marker tokens and returns
only token classes/text. Consequently positions and formatting tokens are not
scored. The complete original generator and its state still execute. The task
uses the recorded current Python runtime, not an emulated Python 3.7 interpreter.
The bug concerns the historical lexer's contextual `async` handling; the test
does not require source to be executable under today's Python grammar.

## Controlled diagnostic inputs and costs

Every arm receives the same editable files, full immutable context, instructions,
public cases and current feedback. Neutral/scored arms repeat **all** covered
locations in canonical path/line order, including immutable locations marked
as such. Neutral fields say `not supplied`; scored fields contain the true public
execution counts and exact squared Ochiai. Both use the same coverage acquisition.
Unavailable coverage stays unavailable for both; no favorable top-k is selected.
Metadata, timings, evaluator expectations and the reference patch are excluded
from prompts. Every request has `provider_call_enabled=False`.

This is not an exactly token-matched placebo: labels/numeric fields have different
lengths, and coverage and generation need actual resource accounting. In particular,
the editable tokenizer is approximately 21 KiB. **The old 4096-token response cap
is not assumed sufficient for complete module replacement.** A validated output
contract/token allowance, numerical sample and authorized full budget must be
fixed before future model calls. There is no collector or policy training here.

After the original qualification, two integrity guards were strengthened:
reject stale verifier support context and invalid acquisition resource counts.
The later replay used these guards and reproduced all observations/projections.
The original executed `package_spectra.py` bytes are preserved and match the
fingerprints saved before/after qualification; its archival bytes were recovered
by reversing only those guard additions. Future qualification runs now snapshot
their runtime before executing. No original bank was overwritten or rescored.

## Reproduction and next work

Audit without network or candidate execution:

```bash
uv run python experiments/python-repair/checkpoint-environment/development-package-black13/reproduce.py
```

The command audits all eleven pinned source/test/license records, original
source equality, all saved observations and F/N/S projections.
`uv run python -m pytest tests/decisions/test_repair_packages.py -q` also runs
synthetic native checks on macOS; those checks skip on other hosts.
To independently replay the original component in the native sandbox:

```bash
uv run python experiments/python-repair/checkpoint-environment/development-package-black13/reproduce.py --sandbox
```

The broader plan still retains every source candidate. This tokenizer joins five
bounded components but adds no new project diversity. Other Black cases need
the real grammar/driver/formatter context; filesystem, lifecycle and tracing
cases remain separate work. Broader source selection and independent groups
must be fixed prospectively. The selector goal remains unachieved; no claim of
diagnostic efficacy follows from passing these engineering checks.
