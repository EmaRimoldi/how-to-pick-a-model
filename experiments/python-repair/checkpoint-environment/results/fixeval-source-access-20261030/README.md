# FixEval source access and prospective development queue

This is an offline source-feasibility result, not a repair experiment. It establishes
access to submission metadata and test-directory information and selects development
items before their code or test bodies are inspected. No model calls were made.
The cumulative model commitment remains $0.25463059 of $0.60, including fourteen
historical uncertain reserves. No new collection is funded by this artifact.

## Verified inventory

| Stage | Count | Meaning |
| --- | ---: | --- |
| Submission metadata | 13,916,868 | All languages, 154,178 users, 4,048 observed problem IDs |
| Python submissions | 3,286,314 | 3,235 problems; no repeated Python submission IDs |
| Problem map | 4,053 | Includes five IDs without observed submission records |
| Provisionally matched test directories | 710 | 19,743 paired input/output cases |
| Complete directory layouts | 688 | No unpaired files under the recorded convention |
| Metadata-feasible problems | 579 | CPython 3 accepted and failed records; not execution-qualified |
| Eligible development candidates | 212 | In 80 connected groups, after the frozen size/pair filters |
| Selected development groups | 12 | One problem per group, three ordered human submission pairs each |
| Reserved eligible groups | 68 | Contents unopened here; not certified independent evaluation data |

The official Python archive is 652,946,195 bytes and the test archive is
11,594,274,942 bytes. Reading 12,933,068 bytes of directory/tail ranges identified
144 and 103,009 ZIP entries, respectively. Exact HTTP ranges, lengths, archive
sizes, directory hashes and Last-Modified consistency were checked. ETags were
absent: these are **not full remote-archive checksums**. Future member retrieval
must revalidate directory identity and verify local headers, decompression and CRC.

The complete 194,876,871-byte `processed.zip` metadata archive was hashed and
streamed. Every record was checked against the six-field metadata schema. The
archive has no source/test payload fields. A separate bounded 32 MiB CodeNet
prefix lookup did not reach its problem map; its failure is retained in
`prefix-lookup-receipt.json`. No source bodies from that opaque prefix were
inspected or executed. The exact map was then obtained from the pinned FixEval
repository instead.

## Selection and limitations

`selected-development.json` retains all 36 selected pairs, runtime/verdict/date
metadata and all IDs in their connected groups. The frozen seed and rules are in
`development-inspection-plan.json` inside `evidence.zip`. All 4,053 mapped IDs
participate in grouping: same-contest and normalized identical-title links form
transitive components. A large 112-ID component is kept intact. All 74 groups
touching documented examples, hardcoded evaluation IDs or the paper's illustrative
biscuit problem are quarantined.

Eligible pairs are adjacent same-user submissions in the same CPython 3 runtime:
Wrong Answer or Runtime Error followed by Accepted at a strictly later timestamp.
Pairs and groups are ordered by seeded SHA256 before source inspection. Problems
must have 8–64 complete cases, input size at most 64 KiB, expected output at most
8 KiB and total test size at most 4 MiB. These are feasibility filters, not evidence
that a human pair is a localized repair or that any model can recover from it.

The official evaluation code maps contest tasks **positionally**, only when counts
match. We reproduce that convention provisionally and retain all rejected groups,
missing files and the 40 hardcoded invalid IDs. A reference must still pass the
actual tests before we accept a mapping. We do not execute the upstream runner:
its input stripping, Python 2 fallback and shell execution are unsuitable for our
controlled environment. No public/evaluator partition or acceptance comparator
is frozen yet.

The catalog-join recording has a disclosed deviation: the intended metadata rules
were supplied before execution, but writing their plan failed with a syntax error.
The plan was persisted after the join started. It is not a pre-execution freeze or
model preregistration. The later development-inspection plan was saved successfully
before queue selection and before any candidate/test member was opened.

Documentation inspection exposed a tokenized C example for p00000 and other
explicitly named IDs; their complete groups are quarantined. Identical-title and
contest grouping does not detect all semantic duplicates or establish absence of
pretraining exposure. The 68 reserved groups therefore remain candidates, not a
validated holdout. Competitive-programming repairs are a distinct population from
repository maintenance; all earlier BugsInPy results and their limitations remain.

## Reproduce

From the repository root, the small offline audit verifies all published hashes,
independently decodes both ZIP/ZIP64 directories with Python's standard library,
checks source Git blobs, catalog arithmetic, mapping uniqueness and the prospective
group boundary. Its sparse ZIP reader cannot open member bodies:

```sh
uv run python experiments/python-repair/checkpoint-environment/results/fixeval-source-access-20261030/reproduce.py
```

To reconstruct every catalog row, join and selection from the original metadata:

```sh
uv run experiments/python-repair/checkpoint-environment/results/fixeval-source-access-20261030/reproduce.py \
  --metadata-archive runs/fixeval-access-20261030/processed.zip
```

The original archive is available from the authors' [public data folder](https://drive.google.com/drive/folders/1dzuHuouuWzlFCy1CMj9DYG9JGraEay27)
as file ID `1gxZYObARqJytI9gf6gEX-CZhCpc4JPE6`. Its SHA256 is
`9f470e12546e48df059a9d22d49887b9f5d0dc2084ceaa34483d2f76aab4862f`.
The full local replay processed all 13,916,868 metadata records with **zero
catalog/join/queue discrepancies**. Default CI audits the saved evidence; it does
not download or replay the large original metadata archive. Neither command calls
a model or executes dataset source/test code.

Reports use lossless gzip with deterministic timestamps. The ZIP preserves frozen
readers, all selection plans, source maps, raw central directories and inert
upstream documentation. It contains no candidate source/test members; the
documentation example described above remains disclosed. Large metadata caches,
SQLite tables and opaque gzip prefixes stay outside Git.

## Next executable milestone

Retrieve only the frozen 36 submission pairs and selected test members, establish
raw-source provenance and implement an isolated, faithful stdin/stdout verifier.
Freeze the comparator, public/evaluator split and qualification rule before running
any candidate. Preserve all selected exclusions and failures. Later F/N/S recovery
must start from an actual model-generated failed repair, not silently substitute a
human failed submission. No selector training or new paid collection is enabled.

## Sources and notices

FixEval map and adapter: revision `0b86cd4256d6bc3be23a07e4f3c9a75ecef7c057`
of [mahimanzum/FixEval](https://github.com/mahimanzum/FixEval); MIT notice included.
CodeNet duplicate documentation: revision
`03a03589f02f3bb3868e3c9490b52fddb2e74a43` of
[IBM/Project_CodeNet](https://github.com/IBM/Project_CodeNet); Apache 2.0 notice
included. CodeNet-derived data carry the included CDLA-Permissive 2.0 text;
the authors describe the data/software licensing distinction in the
[CodeNet paper, Appendix A.6](https://jiechenjiechen.github.io/pub/codenet.pdf).
These notices accompany the metadata evidence and do not certify rights for any
uninspected third-party test payload. No credentials or signed download links are
stored in the published artifact.
