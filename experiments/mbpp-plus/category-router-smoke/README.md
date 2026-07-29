# Category Router Smoke on MBPP+

This development bundle tests four-way semantic categories and a math/non-math
split. It contains full/smoke configs, launchers, and ten historical smoke
figures. Full category labels and full router result files are absent, so the
bundle is not complete evidence.

`scripts/smoke_category.sh` uses mock routing after loading the checked-in
worker traces; category tagging and any live router rerun may require external
model access depending on the selected backend.
