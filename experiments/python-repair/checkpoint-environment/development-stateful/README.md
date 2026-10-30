# Stateful and recursive development adapters

Two previously exposed Scrapy bugs now have complete function/class adapters,
six public cases and six separate evaluator cases each. All original buggy
versions fail both suites; the original fixes pass every case. These are
**offline engineering qualifications, not model results or unseen tests**.

| Source | Restricted behavior | Buggy public / evaluator passes | Fixed passes |
| --- | --- | --- | --- |
| Scrapy/26 | Compose explicit bases, component defaults and priority updates | 3/6, 3/6 | 6/6 in both |
| Scrapy/40 | Recursively export typed values, with optional UTF-8 encoding | 3/6, 2/6 | 6/6 in both |

[pool.json](pool.json) contains instructions, wrappers, literal expected answers,
all test inputs, original source URLs and SHA-256 hashes. All inputs and expected
answers were authored before qualification, from the declared contracts and
upstream examples. No expected output was obtained by running the reference fix.
Public/evaluator inputs are disjoint within each task. Both finite suites are
published development data, with evaluator cases excluded from solver prompts.

Scrapy/26 retains complete original definitions of `BaseSettings`,
`SettingsAttribute`, `_DictProxy`, `get_settings_priority` and the priority map.
The four examples from the earlier engineering probe remain public; two public
and six evaluator inputs extend the explicit contract. It uses only JSON scalar
values, string keys and named priority levels. No crawler or dynamic settings
module is invoked.

Scrapy/40 retains complete `BaseItemExporter` and `PythonItemExporter` classes,
original `is_listlike`, `to_bytes`, `to_unicode`, `BaseItem` and `object_ref`
definitions. Common support comes from the pinned buggy revision for both
variants. Input is a JSON mapping with string keys; no custom item instances,
custom field serializers, input bytes or non-UTF-8 encoding is exercised.
The wrapper encodes output bytes as `{"bytes_hex": ...}` and mappings as sorted
`{"dict": [[key, value], ...]}` pairs so types can be checked through JSON.
This explicit observation encoding is identical in buggy and fixed variants.

The only compatibility aliases replace the referenced `six` operations with
their Python 3 equivalents; the settings adapter imports `MutableMapping` from
`collections.abc`. Original target/helper definitions are preserved rather than
replaced by behavioral stubs. Native execution uses the existing OS sandbox.
Original licenses and full source/test/support files remain under `upstream/`.
The inert [builder source](build-adapters-source.py.txt) documents extraction and
manual case creation; it is provenance, not an additional executable collector.

The [source audit](source-audit.json) verifies fifteen pinned full files and
exact target extraction ranges. The benchmark revision remains
`11c5f1eea954a42132cfd06bf257766a7963e0fd`. The
[qualification](qualification.json) executes both versions and both suites twice;
all checks pass. Repetition demonstrates adapter consistency, not independent
repair success. [Qualification history](qualification-history.json) preserves
the first and subsequent qualification records.

Both IDs were already in the exposure registry. Publishing these adapters keeps
its totals at **174 known development IDs across ten projects**. Neither source
nor any variant may enter an untouched evaluation split. Model difficulty,
conditional recoverability after a generated failed patch, and diagnostic value
remain unmeasured on these adapters.

From the repository root:

```bash
uv run python scripts/qualify_python_repair_pool.py --pool experiments/python-repair/checkpoint-environment/development-stateful
uv run python scripts/qualify_python_repair_pool.py qualify \
  --pool experiments/python-repair/checkpoint-environment/development-stateful \
  --output runs/stateful-qualification-fresh
```

For the source audit, place pinned downloads at
`<cache>/<benchmark_id>/<role>.txt` and run `audit-sources --source-cache <cache>`
with the same `--pool`. No upstream setup scripts, model APIs or paid services
are used by qualification.
