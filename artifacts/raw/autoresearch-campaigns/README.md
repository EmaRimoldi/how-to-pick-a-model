# Raw AutoResearch campaign snapshot

These archives preserve the ignored cluster directory
`autoresearch/campaigns/h20_delta005_20260505/`, including all 250 worker
confirmation run directories. Archives are split into Git LFS parts no larger
than 1.9 GB. Each component archive retains its repository-relative paths.

Verify every part with `SHA256SUMS`, then reconstruct a component by
concatenating all parts with the same `.tar.zst.part-` prefix, decompressing the
Zstandard stream, and extracting the tar archive. Components are independent;
extract all of them into the same destination to reconstruct the complete
campaign tree.

`ARCHIVES.tsv` records the component name, part count, compressed byte count,
and number of tar entries.
