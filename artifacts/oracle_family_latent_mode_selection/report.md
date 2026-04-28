# Oracle-Family Latent-Mode Selection

- Selection metric: `observable_only`
- Selected families: `negative_lookup_churn, topk_stress, temporal_repeat_windows, wide_range_churn`
- Observable min pairwise distance: `5.360`
- Combined min pairwise distance: `5.360`

## Observable Summaries

- `bursty_mixed`: topk_ratio=0.083, range_sum_ratio=0.195, aggregate_count_ratio=0.125, update_ratio=0.449, mean_range_width=25.0, mean_topk_k=5.1
- `distribution_shift`: topk_ratio=0.228, range_sum_ratio=0.240, aggregate_count_ratio=0.304, update_ratio=0.228, mean_range_width=78.3, mean_topk_k=10.9
- `negative_lookup_churn`: topk_ratio=0.000, range_sum_ratio=0.122, aggregate_count_ratio=0.119, update_ratio=0.285, mean_range_width=13.0, mean_topk_k=0.0
- `range_local_scans`: topk_ratio=0.183, range_sum_ratio=0.347, aggregate_count_ratio=0.282, update_ratio=0.188, mean_range_width=33.0, mean_topk_k=7.5
- `temporal_repeat_windows`: topk_ratio=0.168, range_sum_ratio=0.408, aggregate_count_ratio=0.253, update_ratio=0.045, mean_range_width=17.0, mean_topk_k=6.8
- `topk_stress`: topk_ratio=0.521, range_sum_ratio=0.171, aggregate_count_ratio=0.087, update_ratio=0.222, mean_range_width=190.4, mean_topk_k=21.4
- `uniform_read_heavy`: topk_ratio=0.126, range_sum_ratio=0.232, aggregate_count_ratio=0.146, update_ratio=0.196, mean_range_width=20.9, mean_topk_k=5.4
- `wide_range_churn`: topk_ratio=0.105, range_sum_ratio=0.240, aggregate_count_ratio=0.198, update_ratio=0.457, mean_range_width=512.7, mean_topk_k=15.9
- `zipf_hot_key`: topk_ratio=0.113, range_sum_ratio=0.153, aggregate_count_ratio=0.103, update_ratio=0.229, mean_range_width=14.7, mean_topk_k=5.4

## Selected Pairwise Distances

- `negative_lookup_churn` vs `topk_stress`: observable=`7.165`, combined=`7.165`
- `negative_lookup_churn` vs `temporal_repeat_windows`: observable=`6.882`, combined=`6.882`
- `negative_lookup_churn` vs `wide_range_churn`: observable=`6.838`, combined=`6.838`
- `topk_stress` vs `temporal_repeat_windows`: observable=`5.719`, combined=`5.719`
- `topk_stress` vs `wide_range_churn`: observable=`5.360`, combined=`5.360`
- `temporal_repeat_windows` vs `wide_range_churn`: observable=`7.311`, combined=`7.311`
