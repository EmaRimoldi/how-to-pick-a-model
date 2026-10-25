"""Agent-based merge phase: use a Claude reasoning agent to determine
the optimal hyperparameter combination from parallel agent results.
"""

from __future__ import annotations

import logging
import re
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Matches all UPPERCASE parameter assignments (any value type)
_HYPERPARAM_RE_FULL = re.compile(
    r'^(?P<name>[A-Z][A-Z0-9_]+)\s*=\s*(?P<value>[^\s#\n][^#\n]*?)(?:\s*#.*)?$',
    re.MULTILINE,
)

_CODE_FENCE_PY = re.compile(r'```python\s*\n(.*?)```', re.DOTALL)
_CODE_FENCE_JSON = re.compile(r'```json\s*\n(.*?)```', re.DOTALL)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_merge_prompt(
    evidence: dict,
    candidates: list,
    baseline_params: dict[str, str],
    baseline_train_py: str,
) -> str:
    """Build a prompt for the Claude merge agent.

    Parameters
    ----------
    evidence : dict
        Output of MergeOrchestrator.gather_evidence().
    candidates : list
        List of MergeCandidate objects from build_candidate_set().
    baseline_params : dict[str, str]
        Baseline UPPERCASE param values extracted from the original train.py.
    baseline_train_py : str
        Full text of the original (unmodified) train.py.
    """
    lines: list[str] = []

    lines.append("# Hyperparameter Merge Task")
    lines.append("")
    lines.append(
        "You are an expert ML researcher. Multiple parallel agents independently "
        "explored hyperparameter settings for a language model training script "
        "(train.py). Your task: synthesise all their findings into the single best "
        "hyperparameter configuration."
    )
    lines.append("")

    # Section 1: Baseline parameters
    lines.append("## 1. Baseline Parameters (unmodified train.py)")
    lines.append("")
    for name, value in sorted(baseline_params.items()):
        lines.append(f"  {name} = {value}")
    lines.append("")

    # Section 2: Per-agent accepted changes
    lines.append("## 2. Accepted Changes per Agent")
    lines.append("")
    for agent_id, agent_data in sorted(evidence.get("agents", {}).items()):
        snaps = agent_data.get("snapshots", [])
        accepted = [s for s in snaps if s.get("accepted") is True]
        lines.append(f"### {agent_id} — accepted ({len(accepted)} steps)")
        if accepted:
            for s in accepted:
                delta = _delta_str(s.get("val_bpb_before"), s.get("val_bpb_after"))
                lines.append(
                    f"  step {s.get('step_index', '?'):>3}  "
                    f"{s.get('git_message', '')[:80]:<80}  Δval_bpb={delta}"
                )
        else:
            lines.append("  (none)")
        lines.append("")

    # Section 3: Per-agent rejected changes
    lines.append("## 3. Rejected Changes per Agent")
    lines.append("")
    for agent_id, agent_data in sorted(evidence.get("agents", {}).items()):
        snaps = agent_data.get("snapshots", [])
        rejected = [s for s in snaps if s.get("accepted") is False]
        lines.append(f"### {agent_id} — rejected ({len(rejected)} steps)")
        if rejected:
            for s in rejected:
                delta = _delta_str(s.get("val_bpb_before"), s.get("val_bpb_after"))
                lines.append(
                    f"  step {s.get('step_index', '?'):>3}  "
                    f"{s.get('git_message', '')[:80]:<80}  Δval_bpb={delta}"
                )
        else:
            lines.append("  (none)")
        lines.append("")

    # Section 4: Cross-agent patterns
    lines.append("## 4. Cross-Agent Patterns")
    lines.append("")
    patterns = evidence.get("reasoning_summary", {}).get(
        "independently_confirmed_hypotheses", []
    )
    if patterns:
        for p in patterns:
            lines.append(
                f"  - {p.get('hypothesis', '')} "
                f"(confirmed by {p.get('count', '?')} agents)"
            )
    else:
        lines.append("  No independently confirmed cross-agent patterns found.")
    lines.append("")

    # Section 5: Best config per agent
    lines.append("## 5. Best Configuration per Agent (UPPERCASE params)")
    lines.append("")
    for cand in candidates:
        name = getattr(cand, "name", str(cand))
        val_bpb = getattr(cand, "val_bpb", None)
        hyperparams = getattr(cand, "hyperparams", {})
        if not isinstance(hyperparams, dict):
            continue
        lines.append(f"### Candidate: {name}  (val_bpb={val_bpb})")
        for pname, pval in sorted(hyperparams.items()):
            baseline_val = baseline_params.get(pname, "<unknown>")
            changed = " *" if str(pval).strip() != str(baseline_val).strip() else ""
            lines.append(f"  {pname} = {pval}{changed}")
        lines.append("")

    # Section 6: Output instructions
    lines.append("## 6. Your Task")
    lines.append("")
    lines.append(
        "Reason carefully about which hyperparameter values are most likely to "
        "produce the lowest val_bpb. Consider:"
    )
    lines.append("  - Which accepted changes consistently reduced val_bpb?")
    lines.append("  - Which rejected changes increased val_bpb or were unstable?")
    lines.append("  - Are there complementary changes from different agents that can be combined?")
    lines.append("  - Are any changes conflicting (different direction for the same param)?")
    lines.append("")
    lines.append("### Required Output Format")
    lines.append("")
    lines.append(
        "First, output the COMPLETE modified train.py inside a ```python fence. "
        "This is the primary output — it must be a complete, runnable file."
    )
    lines.append("")
    lines.append(
        "Second, output a brief JSON summary of your parameter choices inside a "
        "```json fence, with format: {\"PARAM_NAME\": \"value\", ...}. "
        "Only include params you changed from baseline."
    )
    lines.append("")
    lines.append("Here is the baseline train.py to modify:")
    lines.append("")
    lines.append("```python")
    lines.append(baseline_train_py)
    lines.append("```")

    return "\n".join(lines)


def call_claude_merge_agent(
    prompt: str,
    model: str = "claude-opus-4-6",
    timeout: int = 300,
) -> str:
    """Call Claude CLI with the merge prompt and return the response text.

    Parameters
    ----------
    prompt : str
        The full prompt to send.
    model : str
        Claude model name.
    timeout : int
        Timeout in seconds.

    Returns
    -------
    str
        Raw response text, empty string on failure.
    """
    try:
        result = subprocess.run(
            [
                "claude",
                "--print",
                "--output-format", "text",
                "--dangerously-skip-permissions",
                "--model", model,
                prompt,
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            logger.error(
                "[agent_merger] Claude exited with code %d: %s",
                result.returncode,
                result.stderr[:500],
            )
            print(
                f"[agent_merger] Claude stderr: {result.stderr[:500]}",
                file=sys.stderr,
            )
            return ""
        response = result.stdout
        print(
            f"[agent_merger] Claude response ({len(response)} chars)",
            file=sys.stderr,
        )
        return response
    except subprocess.TimeoutExpired:
        logger.error("[agent_merger] Claude call timed out after %ds", timeout)
        print(f"[agent_merger] Claude timed out after {timeout}s", file=sys.stderr)
        return ""
    except Exception as exc:
        logger.error("[agent_merger] Claude call failed: %s", exc)
        print(f"[agent_merger] Claude call error: {exc}", file=sys.stderr)
        return ""


def parse_merge_response(
    response: str,
    baseline_train_py: str,
) -> tuple[dict[str, str], str, str]:
    """Parse Claude's response to extract the merged train.py and param dict.

    Returns
    -------
    tuple[dict[str, str], str, str]
        (param_dict, modified_train_py, reasoning)
        Falls back to ({}, baseline_train_py, "parse error") on failure.
    """
    import json as _json

    reasoning_lines: list[str] = []
    modified_train_py = ""
    param_dict: dict[str, str] = {}

    # Try to extract ```python block first (full train.py)
    py_matches = _CODE_FENCE_PY.findall(response)
    if py_matches:
        # Take the longest python block (most likely the full train.py)
        modified_train_py = max(py_matches, key=len).strip()

    # Try to extract ```json block
    json_matches = _CODE_FENCE_JSON.findall(response)
    if json_matches:
        for block in json_matches:
            try:
                parsed = _json.loads(block.strip())
                if isinstance(parsed, dict):
                    param_dict = {str(k): str(v) for k, v in parsed.items()}
                    break
            except Exception:
                continue

    # Extract reasoning: everything before the first code fence
    first_fence = response.find("```")
    if first_fence > 0:
        reasoning = response[:first_fence].strip()
    else:
        reasoning = response.strip()

    if not modified_train_py:
        if param_dict:
            # Fall back: apply JSON params to baseline
            modified_train_py = _apply_string_params(baseline_train_py, param_dict)
            reasoning_lines.append("No python block found; applied JSON params to baseline.")
        else:
            logger.warning("[agent_merger] Could not parse train.py or JSON from response.")
            return {}, baseline_train_py, "parse error"

    if reasoning_lines:
        reasoning = reasoning + "\n" + "\n".join(reasoning_lines)

    return param_dict, modified_train_py, reasoning


def produce_merged_candidate_via_agent(
    candidates: list,
    evidence: dict,
    baseline_train_py_path: Path,
    merge_dir: Path,
    model: str = "claude-opus-4-6",
    slurm_time: str = "00:10:00",
) -> object:
    """Orchestrate the full agent-based merge.

    Calls build_merge_prompt → call_claude_merge_agent → parse_merge_response,
    writes the result, and returns a MergeCandidate.
    Falls back to the best individual candidate if Claude call fails.

    Parameters
    ----------
    candidates : list[MergeCandidate]
        Candidate list from build_candidate_set().
    evidence : dict
        Evidence dict from gather_evidence().
    baseline_train_py_path : Path
        Path to the original train.py.
    merge_dir : Path
        Merge output directory.
    model : str
        Claude model to use.
    slurm_time : str
        SLURM time limit (unused here, passed for logging).

    Returns
    -------
    MergeCandidate
    """
    # Import here to avoid circular imports
    from agent_workflow.merger import MergeCandidate, extract_hyperparams

    cand_dir = merge_dir / "candidates"
    cand_dir.mkdir(parents=True, exist_ok=True)
    dest = cand_dir / "candidate_merged.py"

    baseline_train_py = baseline_train_py_path.read_text()
    baseline_params = _extract_all_uppercase_params(baseline_train_py)

    print("[agent_merger] Building merge prompt...", file=sys.stderr)
    prompt = build_merge_prompt(evidence, candidates, baseline_params, baseline_train_py)

    print(
        f"[agent_merger] Calling Claude merge agent (model={model}, "
        f"prompt_len={len(prompt)})...",
        file=sys.stderr,
    )
    response = call_claude_merge_agent(prompt, model=model)

    if not response:
        print(
            "[agent_merger] Claude call failed. Falling back to best individual candidate.",
            file=sys.stderr,
        )
        return _fallback_candidate(candidates, baseline_train_py, dest, merge_dir)

    param_dict, modified_train_py, reasoning = parse_merge_response(
        response, baseline_train_py
    )

    if not modified_train_py or modified_train_py == baseline_train_py and not param_dict:
        print(
            "[agent_merger] Parse failed or no changes detected. Falling back.",
            file=sys.stderr,
        )
        return _fallback_candidate(candidates, baseline_train_py, dest, merge_dir)

    dest.write_text(modified_train_py)

    # Log reasoning
    (merge_dir / "agent_merge_reasoning.txt").write_text(reasoning)

    strategy = (
        f"Agent-based merge via {model}. "
        f"Changed params: {list(param_dict.keys()) if param_dict else 'see python block'}. "
        f"slurm_time={slurm_time}."
    )

    hyperparams = extract_hyperparams(modified_train_py)

    return MergeCandidate(
        name="merged",
        source_agents=[a for a in evidence.get("agents", {}).keys()],
        source_steps=[],
        train_py_path=str(dest),
        hyperparams=hyperparams,
        strategy=strategy,
    )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _extract_all_uppercase_params(train_py: str) -> dict[str, str]:
    """Extract all UPPERCASE = <value> assignments from train.py."""
    params: dict[str, str] = {}
    for m in _HYPERPARAM_RE_FULL.finditer(train_py):
        name = m.group("name")
        value = m.group("value").strip()
        params[name] = value
    return params


def _apply_string_params(train_py: str, params: dict[str, str]) -> str:
    """Apply string-valued param overrides to train.py source."""
    result = train_py
    for name, value in params.items():
        result = re.sub(
            r'^(' + re.escape(name) + r'\s*=\s*)[^\s#\n][^#\n]*?(\s*(?:#.*)?)$',
            r'\g<1>' + value + r'\g<2>',
            result,
            flags=re.MULTILINE,
        )
    return result


def _delta_str(before: Optional[float], after: Optional[float]) -> str:
    """Format val_bpb delta as a signed string."""
    if before is None or after is None:
        return "N/A"
    delta = after - before
    sign = "+" if delta >= 0 else ""
    return f"{sign}{delta:.6f}"


def _fallback_candidate(
    candidates: list,
    baseline_train_py: str,
    dest: Path,
    merge_dir: Path,
) -> object:
    """Return the best individual candidate, or a baseline copy."""
    from agent_workflow.merger import MergeCandidate, extract_hyperparams

    ranked = sorted(
        [c for c in candidates if getattr(c, "val_bpb", None) is not None],
        key=lambda c: c.val_bpb,
    )
    if ranked:
        best = ranked[0]
        import shutil
        shutil.copy2(best.train_py_path, dest)
        return MergeCandidate(
            name="merged",
            source_agents=list(getattr(best, "source_agents", [])),
            source_steps=list(getattr(best, "source_steps", [])),
            train_py_path=str(dest),
            hyperparams=extract_hyperparams(Path(dest).read_text()),
            strategy=f"Agent merge fallback: best individual ({best.name}), "
                     f"val_bpb={best.val_bpb}",
            val_bpb=best.val_bpb,
        )
    # Last resort: baseline
    dest.write_text(baseline_train_py)
    return MergeCandidate(
        name="merged_fallback",
        source_agents=["baseline"],
        source_steps=[],
        train_py_path=str(dest),
        hyperparams=extract_hyperparams(baseline_train_py),
        strategy="Agent merge fallback: baseline (no candidates available)",
    )
