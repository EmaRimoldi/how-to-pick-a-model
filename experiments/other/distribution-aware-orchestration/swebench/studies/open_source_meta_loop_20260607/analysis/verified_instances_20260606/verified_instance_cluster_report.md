# SWE-bench Verified instance analysis

Generated from `princeton-nlp/SWE-Bench_Verified`, split `test`, n=500.

## Bottom line

The 500 instances are clusterizable, but not along one single clean axis. The strongest
axis is repository/domain: Django alone contributes 231 / 500
instances. A second useful axis is repair morphology: 405
instances are micro/small local changes, while 24 are broad or large changes.
Issue-text clustering is usable for routing, but it is noisier than repository/domain
clustering; the best hierarchical text silhouette in k=2..14 is k=2 with
mean silhouette 0.054.

Operationally, use repo/domain as the first router signal, then issue semantics and
prompt/test-budget signals as secondary routing features. Do not expect one universal
"bug type" taxonomy to partition all 500 cleanly.

## Repository/domain distribution

| repo | count | share |
| --- | --- | --- |
| django/django | 231 | 46.2% |
| sympy/sympy | 75 | 15.0% |
| sphinx-doc/sphinx | 44 | 8.8% |
| matplotlib/matplotlib | 34 | 6.8% |
| scikit-learn/scikit-learn | 32 | 6.4% |
| astropy/astropy | 22 | 4.4% |
| pydata/xarray | 22 | 4.4% |
| pytest-dev/pytest | 19 | 3.8% |
| pylint-dev/pylint | 10 | 2.0% |
| psf/requests | 8 | 1.6% |
| mwaskom/seaborn | 2 | 0.4% |
| pallets/flask | 1 | 0.2% |

## Difficulty distribution

| difficulty | count | share |
| --- | --- | --- |
| 15 min - 1 hour | 261 | 52.2% |
| <15 min fix | 194 | 38.8% |
| 1-4 hours | 42 | 8.4% |
| >4 hours | 3 | 0.6% |

## Observable issue modes

This uses only issue/hints text plus public repo metadata.

| observable_mode | count | share |
| --- | --- | --- |
| web_orm_config | 219 | 43.8% |
| array_numeric_ml | 61 | 12.2% |
| symbolic_math | 60 | 12.0% |
| docs_rendering | 56 | 11.2% |
| plotting_visual | 33 | 6.6% |
| http_io_packaging | 20 | 4.0% |
| test_lint_tooling | 17 | 3.4% |
| compatibility_errors | 15 | 3.0% |
| parser_serialization | 11 | 2.2% |
| web_framework_orm_config | 5 | 1.0% |
| symbolic_math_core | 2 | 0.4% |
| scientific_ml_api | 1 | 0.2% |

## Recommended routing-domain clusters

This is the cleanest practical partition for orchestration. It is observable before
solving because it only depends on the repository family.

| routing_domain_cluster | count | share |
| --- | --- | --- |
| web_framework_orm_config | 232 | 46.4% |
| symbolic_math_core | 75 | 15.0% |
| scientific_array_modeling | 44 | 8.8% |
| docs_build_rendering | 44 | 8.8% |
| plotting_visualization | 36 | 7.2% |
| scientific_ml_api | 32 | 6.4% |
| developer_testing_tooling | 29 | 5.8% |
| http_io_protocol | 8 | 1.6% |

## Routing-domain by repair shape

Rows use the observable repository/domain partition. Columns use gold-patch shape and
are post-hoc diagnostics for sizing the worker budget.

| routing_domain_cluster | micro_single_file | small_local | medium_local | broad_multi_file_or_large | total |
| --- | --- | --- | --- | --- | --- |
| developer_testing_tooling | 11 | 9 | 6 | 3 | 29 |
| docs_build_rendering | 18 | 17 | 7 | 2 | 44 |
| http_io_protocol | 8 | 0 | 0 | 0 | 8 |
| plotting_visualization | 14 | 18 | 4 | 0 | 36 |
| scientific_array_modeling | 17 | 15 | 7 | 5 | 44 |
| scientific_ml_api | 14 | 12 | 5 | 1 | 32 |
| symbolic_math_core | 35 | 23 | 12 | 5 | 75 |
| web_framework_orm_config | 103 | 91 | 30 | 8 | 232 |

## Gold-patch domain clusters

This is post-hoc diagnostic information derived from gold patch metadata and repo/domain.
It should not be used as a solver prompt feature.

| gold_domain_cluster | count | share |
| --- | --- | --- |
| web_orm_schema_query | 163 | 32.6% |
| symbolic_math_core | 72 | 14.4% |
| web_framework_orm_config | 63 | 12.6% |
| docs_build_rendering | 43 | 8.6% |
| plotting_visualization | 36 | 7.2% |
| scientific_ml_api | 32 | 6.4% |
| array_shape_dtype_semantics | 28 | 5.6% |
| developer_testing_tooling | 26 | 5.2% |
| scientific_array_modeling | 14 | 2.8% |
| http_io_protocol | 8 | 1.6% |
| large_web_framework_orm_config | 6 | 1.2% |
| large_developer_testing_tooling | 3 | 0.6% |
| large_symbolic_math_core | 3 | 0.6% |
| large_scientific_array_modeling | 2 | 0.4% |
| large_docs_build_rendering | 1 | 0.2% |

## Gold repair-shape distribution

Patch size summary: median changed lines = 7.0, mean changed lines =
14.3; median files touched = 1.0, mean files touched =
1.25.

| repair_shape | count | share |
| --- | --- | --- |
| micro_single_file | 220 | 44.0% |
| small_local | 185 | 37.0% |
| medium_local | 71 | 14.2% |
| broad_multi_file_or_large | 24 | 4.8% |

## Semantic text clusters

These clusters come from TF-IDF over problem statement + hints only, no repo or patch text.

| cluster | count | top_terms | top_repos | examples |
| --- | --- | --- | --- | --- |
| 8 | 377 | django, self, models, https, python, com, class, you | django/django:200; sphinx-doc/sphinx:43; matplotlib/matplotlib:30; scikit-learn/scikit-learn:30 | astropy__astropy-13033; astropy__astropy-13236; astropy__astropy-13398; astropy__astropy-13453 |
| 9 | 86 | sympy, import, false, symbol, expr, return, python, true | sympy/sympy:69; astropy/astropy:6; django/django:6; matplotlib/matplotlib:2 | astropy__astropy-12907; astropy__astropy-14096; astropy__astropy-14182; astropy__astropy-7336 |
| 3 | 10 | template, decimal, filter, string, django, utils, description, show_versions | django/django:9; scikit-learn/scikit-learn:1 | django__django-11206; django__django-13794; django__django-14373; django__django-15103 |
| 5 | 8 | command, arguments, argument, management, checks, passed, skip, provided | django/django:7; scikit-learn/scikit-learn:1 | django__django-11292; django__django-11749; django__django-12262; django__django-13809 |
| 4 | 5 | currently, raised, non, add, given, allow, calling, passed | django/django:2; matplotlib/matplotlib:1; pallets/flask:1; sympy/sympy:1 | django__django-14089; django__django-16560; matplotlib__matplotlib-25775; pallets__flask-5014 |
| 7 | 5 | enough, internal, self, bit, connection, session, signature, paths | django/django:4; matplotlib/matplotlib:1 | django__django-12741; django__django-13279; django__django-14765; django__django-9296 |
| 1 | 3 | poly, sqrt, domain, points, point, dimension, together, documents | sympy/sympy:3 | sympy__sympy-11618; sympy__sympy-13757; sympy__sympy-20428 |
| 6 | 3 | tuple, queries, list, union, type, input, query, columns | django/django:3 | django__django-11490; django__django-12050; django__django-13590 |
| 2 | 2 | mod, root, param, cross, function, condition, regarding, submit | sphinx-doc/sphinx:1; sympy/sympy:1 | sphinx-doc__sphinx-8551; sympy__sympy-18199 |
| 10 | 1 | encoding, correct, contains, incorrect, current | sympy/sympy:1 | sympy__sympy-16886 |

## Text-cluster silhouette sweep

| k | mean_silhouette |
| --- | --- |
| 2 | 0.054 |
| 3 | 0.039 |
| 4 | 0.028 |
| 5 | 0.021 |
| 6 | 0.017 |
| 7 | 0.014 |
| 8 | 0.011 |
| 9 | 0.007 |
| 10 | 0.015 |
| 11 | 0.013 |
| 12 | 0.012 |
| 13 | 0.011 |
| 14 | 0.027 |

## Output files

- `instance_features.csv`: one row per instance with derived non-textual features and cluster labels.
- `semantic_cluster_summary.csv`: text-cluster summaries and examples.
- `summary.json`: machine-readable headline counts and silhouette scores.
- `repo_counts.png`, `difficulty_counts.png`, `repair_shape_counts.png`, `semantic_cluster_counts.png`,
  `semantic_cluster_by_repo.png`: quick inspection plots.
