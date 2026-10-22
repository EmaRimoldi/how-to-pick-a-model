# Precollection funding amendment

The initial freeze, commit `9dbeb4a`, declared a $4.80 collection ceiling within
the user's $5 additional authorization. Its read-only account preflight stopped
before any model request: effective shared-wallet credit was $4.258312502.
The first output directory's `budget.jsonl` is empty (zero reservations, zero
settlements), and no `calls.jsonl` or `transport.jsonl` was created. Preserve
that directory as a stopped preparation attempt; never reuse its path.

Before any evaluation outcome, reduce the collection ceiling to **$4.00**.
No task, policy, prompt, model, provider, verifier, objective or statistical
comparison changes. Per-policy deployment admission remains $0.006 per task.
With one replicate, 157 tasks and four policies, their deployment ceilings sum
to $3.768; collection additionally shares three policies' initial 9B response.
Thus the new collection cap covers the theoretical per-policy sum while leaving
wallet margin. The user authorization remains an upper bound of $5, not a demand
to spend $5 or permission to charge another study automatically.

Refresh the protocol source hash and commit the amendment/config before calling
models. Use a new output path. Read-only metadata requests are not model attempts
and have not consumed this experiment's generation budget. The earlier completed
$2 campaign remains separate.
