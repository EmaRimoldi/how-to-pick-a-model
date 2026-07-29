# Trial Index

The public experiment uses a compact, gap-free trial index. Invalid, corrupted, or
non-executed historical cells are not part of this index.

| Trial | Condition | Memory | Search style | Budget | Attempts | Best `val_bpb` | Mean `val_bpb` |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: |
| `T01` | parallel, mixed search styles | none | mixed | 15 min | 14 | 0.980 | 1.136 |
| `T02` | single-agent control | none | default | 15 min | 8 | 0.936 | 1.070 |
| `T03` | single agent, 30-second train | none | default | 15 min | 10 | 1.103 | 1.447 |
| `T04` | parallel, mixed search styles | none | mixed | 30 min | 29 | 0.971 | 1.190 |
| `T05` | parallel, same search style | none | same | 15 min | 14 | 0.960 | 1.090 |
| `T06` | exploratory, no memory | none | exploratory | 45 min | 21 | 0.933 | 1.816 |
| `T07` | exploratory + shared memory | shared | exploratory | 45 min | 41 | 0.914 | 1.049 |
| `T08` | two exploratory agents | none | exploratory | 45 min | 44 | 0.961 | 1.852 |
| `T09` | seeded learning-rate hint | none | exploratory | 45 min | 13 | 0.880 | 1.501 |
| `T10` | start from seeded baseline | none | default | 45 min | 21 | 0.962 | 1.216 |
| `T11` | shared + private memory | shared and private | mixed | 45 min | 32 | 0.955 | 1.064 |

The strongest workflow comparison is `T06` vs `T07`: exploratory search without
memory is unstable, while exploratory search with shared memory stays closer to
the baseline and avoids the worst regressions.
