# Profile Split Audit

- Dev profiles: hard_balanced_dev, hard_range_dev, hard_churn_dev
- Holdout profiles: hard_balanced_holdout, hard_range_holdout, hard_churn_holdout
- Dev/holdout overlap: none
- Dev/holdout seed overlap: none

| profile | split | seed | initial_size | key_space | trace_length | families |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| hard_balanced_dev | dev | 510100 | 2600 | 120000 | 1200 | uniform_read_heavy, zipf_hot_key, bursty_mixed, range_local_scans, distribution_shift, wide_range_churn, temporal_repeat_windows, topk_stress, negative_lookup_churn |
| hard_balanced_holdout | holdout | 910100 | 3000 | 150000 | 1400 | uniform_read_heavy, zipf_hot_key, bursty_mixed, range_local_scans, distribution_shift, wide_range_churn, temporal_repeat_windows, topk_stress, negative_lookup_churn |
| hard_churn_dev | dev | 530100 | 2400 | 100000 | 1300 | bursty_mixed, topk_stress, negative_lookup_churn, zipf_hot_key, distribution_shift, wide_range_churn, uniform_read_heavy |
| hard_churn_holdout | holdout | 930100 | 3000 | 160000 | 1500 | bursty_mixed, topk_stress, negative_lookup_churn, zipf_hot_key, distribution_shift, wide_range_churn, temporal_repeat_windows |
| hard_optimization | legacy | 424200 | 2600 | 120000 | 1200 | uniform_read_heavy, zipf_hot_key, bursty_mixed, range_local_scans, distribution_shift, wide_range_churn, temporal_repeat_windows, topk_stress, negative_lookup_churn |
| hard_range_dev | dev | 520100 | 2800 | 140000 | 1300 | range_local_scans, wide_range_churn, temporal_repeat_windows, distribution_shift, uniform_read_heavy, bursty_mixed, negative_lookup_churn |
| hard_range_holdout | holdout | 920100 | 3200 | 180000 | 1500 | range_local_scans, wide_range_churn, temporal_repeat_windows, distribution_shift, zipf_hot_key, bursty_mixed, negative_lookup_churn |
