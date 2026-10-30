"""Reject known development leakage without asserting that unknown IDs are fresh."""

import json

import pytest

from vao.repair.exposure import ROOT, REGISTRY, assess_candidate, build, normalize


def test_published_exposure_registry_matches_authoritative_sources():
    registry = build()
    assert json.loads((ROOT / REGISTRY).read_text()) == registry
    assert registry["known_exposed_bug_count"] == 208
    assert len(registry["known_exposed_projects"]) == 10
    for bug in ("black/1", "tqdm/1", "PySnooper/1", "cookiecutter/3", "luigi/3", "thefuck/20"):
        assert assess_candidate(registry, bug, project_disjoint=False) == "reject_known_development_bug"
    for bug in ('BLACK/013', 'cookiecutter/2', 'PySnooper/002', 'tqdm/9'):
        assert assess_candidate(registry, bug, project_disjoint=False) == 'reject_known_development_bug'
        assert any(e['source'].endswith('/spectrum-ablation-preparation-20261030/source-screen.json')
                   for e in registry['exposure_evidence'][normalize(bug)])
    for bug in ("scrapy/2", "scrapy/36", "luigi/10", "tornado/5", "thefuck/22", "thefuck/29"):
        assert any(e['source'].endswith('/development-broader/pool.json')
            and e['level'] == 'published_development_adapter'
            for e in registry['exposure_evidence'][bug])

    for bug in ("scrapy/26", "scrapy/40"):
        assert any(e['source'].endswith('/development-stateful/pool.json')
            and e['level'] == 'published_development_adapter'
            for e in registry['exposure_evidence'][bug])


def test_aliases_cannot_evade_bug_or_project_exclusion():
    registry = build()
    assert assess_candidate(registry, "YOUTUBE-DL/003", project_disjoint=False) == "reject_known_development_bug"
    # Synthetic nonexistent numbers exercise logic; no real holdout is inspected.
    assert assess_candidate(registry, "PySnooper/999999", project_disjoint=True) == "reject_exposed_project"
    assert assess_candidate(registry, "synthetic-project/999999", project_disjoint=True) == "not_known_exposed_further_audit_required"


@pytest.mark.parametrize("bug", ["luigi/0", "../luigi/3", "luigi/3/variant", "luigi/-3", "luigi/３", None])
def test_malformed_ids_do_not_silently_pass(bug):
    with pytest.raises(ValueError):
        normalize(bug)
