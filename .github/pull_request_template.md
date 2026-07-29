## Summary

What changed?

## Verification

```bash
make check
python scripts/validate_agent_readiness.py
uv run pytest tests -q
```

## Notes

- Does this affect live Claude Code runs?
- Does this affect checked-in experiment evidence?
- Are docs or examples updated?
