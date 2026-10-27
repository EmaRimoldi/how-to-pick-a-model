"""Exercise the information study's leakage, repeated design and funded boundary."""

import copy
import json
from decimal import Decimal

import pytest

from vao.analysis.repair_information import summarize
from vao.repair import contract_collection as cc
from vao.repair import stream_information_study as ds
from vao.repair.contracts import STREAM_TRACE_STUDY
from vao.repair.environment import canonical, identity
from vao.repair.provider import OpenRouterTransport, ProviderStopped
from vao.repair.records import rows

FIXED = "def solve(x):\n    return x\n"
BROKEN = "def solve(x):\n    return 0\n"


class Verifier:
    def preflight(self):
        return {"test_double": True}

    def invoke(self, files, entry, case):
        return {"status": "returned", "value": case["args"][0] if files["solution.py"] == FIXED else 0}

    def check(self, files, entry, cases):
        passed = files["solution.py"] == FIXED
        return {"passed": passed, "passed_cases": int(passed), "total_cases": 1,
                "cases": [{"id": cases[0]["id"], "passed": passed, "observed": self.invoke(files, entry, cases[0])}],
                "verifier_seconds": .01}

    def trace(self, files, entry, case):
        return {"available": True, "reason": None, "observed": self.invoke(files, entry, case),
                "trace": {"events": [{"file": "solution.py", "line": 2, "locals": {"x": case["args"][0]}}]}}


def records():
    output = []
    verifier = Verifier()
    for i in range(12):
        public = {"schema_version": 1, "task_id": f"development/mock-{i}", "instruction": "Return x",
                  "entrypoint": {"module": "solution", "function": "solve"},
                  "files": {"solution.py": BROKEN if i < 8 else FIXED},
                  "public_cases": [{"id": "public", "args": [2], "expected": 2}],
                  "provenance": {"kind": "engineering"}}
        result = verifier.check(public["files"], public["entrypoint"], public["public_cases"])
        result.pop("verifier_seconds")
        output.append({"public": public, "evaluator": {"cases": [{"id": "HIDDEN_CANARY", "args": [99], "expected": 99}]},
                       "source_attempt_id": f"source-{i}", "source_task_hash": f"task-{i}", "source_artifact": f"artifact-{i}",
                       "source_cost_usd": "0.0001", "source_public_result": result, "source_full_pass": i >= 8})
    return output


def packet():
    return ds.construct(records(), Verifier())


def prepare(tmp_path, monkeypatch):
    monkeypatch.setattr(cc, "source_commit", lambda: "a" * 40)
    monkeypatch.setattr(cc, "RepairVerifier", Verifier)
    monkeypatch.setattr(ds, "validate_origin", lambda p: None)  # The real frozen archive is separately audited.
    monkeypatch.setenv("OPENROUTER_API_KEY", "mock-key-only")
    monkeypatch.setattr("vao.repair.provider.time.sleep", lambda *_: None)
    prior = tmp_path / "prior.json"
    prior.write_text(json.dumps({"study": "repair-sse-wire-envelope-v1", "status": "complete_compatibility_probe",
        "gate": "larger_wire_envelope_observed", "scientific_results": False, "cap_exceeded": False,
        "old_limit_crossed_with_complete_receipt": True, "cumulative_committed_usd": "0.11785551"}))
    config = {"status": "authorized_contract_diagnostic", "study": STREAM_TRACE_STUDY, "live_calls_enabled": True,
              "authorization_reference": "TEST ONLY MOCK TRANSPORT", "monetary_authorization_usd": "0.47",
              "cumulative_limit_usd": "0.60", "minimum_request_interval_seconds": 60, "closed_pilot_report": str(prior)}
    p = packet()
    return p, config, cc.freeze(p, config, tmp_path / "freeze.json")


def network(monkeypatch, p, *, interrupt=False, useful=False, overage=False):
    import io
    from email.message import Message
    from vao.repair import streaming
    sent = []
    metadata = {canonical(r["provider_body"]): r["metadata"] for r in p["requests"]}
    assert len(metadata) == 64
    def preflight(self, endpoint, body=None):
        assert body is None
        if endpoint.endswith("/endpoints"):
            return {"data": {"id": self.settings.model, "endpoints": [{"tag": self.settings.endpoint,
                "provider_name": self.settings.provider_name, "quantization": self.settings.quantization,
                "context_length": 131072, "max_completion_tokens": 8192,
                "supported_parameters": ["seed", "temperature", "max_tokens", "response_format"],
                "pricing": {"prompt": ".00000012", "completion": ".00000080"}}]}}
        if endpoint == "/key": return {"data": {"limit_remaining": 1}}
        if endpoint == "/credits": return {"data": {"total_credits": 1, "total_usage": 0}}
        raise AssertionError("A nonstreaming POST was attempted")

    class Response:
        def __init__(self, data):
            self.data = io.BytesIO(data)
            self.headers = Message()
            self.headers['Content-Type'] = 'text/event-stream'
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def read1(self, size): return self.data.read(size)

    class Opener:
        def open(self, request, timeout):
            body = json.loads(request.data)
            assert body['stream'] is True and timeout == 180
            assert "HIDDEN_CANARY" not in canonical(body)
            sent.append(body)
            meta = metadata[canonical(body)]
            fixed = useful and meta['arm'] == 'focused_trace' and meta['task_index'] < 3
            content = canonical({'solution.py': FIXED if fixed else BROKEN})
            message = {'id': f'mock-{len(sent)}', 'model': 'qwen/qwen3-coder-next', 'provider': 'Parasail',
                'choices': [{'index': 0, 'delta': {'content': content}, 'finish_reason': 'stop'}],
                'usage': {'cost': .02 if overage else .00008, 'prompt_tokens': 100, 'completion_tokens': 10, 'total_tokens': 110}}
            usage = message.pop('usage')
            accounting = {**message, 'choices': [], 'usage': usage}
            data = 'data: '+json.dumps(message)+'\n\ndata: '+json.dumps(accounting)+'\n\n'
            if not (overage or interrupt and len(sent) == 2): data += 'data: [DONE]\n\n'
            return Response(data.encode())
    monkeypatch.setattr(OpenRouterTransport, "_exchange", preflight)
    monkeypatch.setattr(streaming.urllib.request, 'build_opener', lambda *_: Opener())
    return sent


def test_exact_repeated_design_controls_and_public_only_selection():
    p = packet()
    assert len(p["tasks"]) == 12 and len(p["requests"]) == 64
    assert sum(r["eligible"] for r in p["tasks"]) == 8
    assert p["maximum_new_reservations_usd"] == "0.46137344"
    assert p["maximum_cumulative_commitment_usd"] == "0.57922895"
    seeds = {}
    for r in p["requests"]:
        m = r["metadata"]
        seeds.setdefault((m["task_index"], m["draw"]), set()).add(r["provider_body"]["seed"])
        assert "HIDDEN_CANARY" not in canonical(r["provider_body"])
    assert len(seeds) == 32 and all(len(s) == 1 for s in seeds.values())
    assert len(set.union(*seeds.values())) == 32
    changed = records()
    for r in changed:
        r["source_full_pass"] = not r["source_full_pass"]
        r["evaluator"]["cases"][0]["expected"] = -100
    q = ds.construct(changed, Verifier())
    assert [r["provider_body"] for r in p["requests"]] == [r["provider_body"] for r in q["requests"]]


def test_rehashed_design_or_request_drift_is_rejected():
    for mutate in (lambda p: p["requests"].reverse(),
                   lambda p: p["requests"][0]["provider_body"].update(temperature=1),
                   lambda p: p["design"].update(draws_per_arm=2),
                   lambda p: p.update(closed_pilot_commitment_usd="0")):
        p = packet()
        mutate(p)
        p["packet_id"] = identity({k: v for k, v in p.items() if k != "packet_id"})
        with pytest.raises(ValueError): ds.validate_packet(p)


@pytest.mark.parametrize("useful,expected", [(False, "no_repeated_information_benefit_demonstrated"),
                                            (True, "candidate_for_independent_acquisition_calibration")])
def test_complete_mock_bank_and_screening_never_train_a_selector(tmp_path, monkeypatch, useful, expected):
    p, config, frozen = prepare(tmp_path, monkeypatch)
    sent = network(monkeypatch, p, useful=useful)
    output, claims = tmp_path / "run", tmp_path / "claims"
    cc.collect(frozen, output, claim_root=claims)
    report = summarize(output)
    assert len(sent) == 64 and report["accounting"]["sealed"] and len(report["task_table"]) == 12
    assert report["gate"] == expected and not report["fit_selector"]
    assert sum(t["planned"] for t in report["arm_table"]) == 64
    assert report["accounting"]["cumulative_committed_usd"] == "0.12297551"
    if useful:
        assert report["contrasts"]["focused_trace_minus_focused"]["mean_difference"] == .375
    with pytest.raises(FileExistsError): cc.collect(frozen, tmp_path / "duplicate", claim_root=claims)
    assert len(sent) == 64
    from vao.analysis.contract_diagnostic import summarize as old_report
    with pytest.raises(ValueError, match="historical contract gate"): old_report(output)


def test_unknown_request_is_reserved_and_report_bounds_preserve_missingness(tmp_path, monkeypatch):
    p, config, frozen = prepare(tmp_path, monkeypatch)
    sent = network(monkeypatch, p, interrupt=True)
    output = tmp_path / "run"
    with pytest.raises(ProviderStopped): cc.collect(frozen, output, claim_root=tmp_path / "claims")
    report = summarize(output)
    assert len(sent) == 2 and sum(t["missing"] for t in report["arm_table"]) == 63
    assert len(report["accounting"]["pending"]) == 1
    assert Decimal(report["accounting"]["cumulative_committed_usd"]) == Decimal(".11785551") + Decimal(".00008") + Decimal(".00720896")
    assert report["gate"] == "inconclusive_incomplete_bank"
    primary = report["contrasts"]["focused_trace_minus_focused"]
    assert primary["descriptive_bug_bootstrap_95"] is None and primary["mean_difference"] is None
    (output / "interruption.json").unlink()
    with pytest.raises(ValueError, match="before collection terminates"): summarize(output)


def test_changed_trace_is_rejected_before_provider_dispatch(tmp_path, monkeypatch):
    p, config, frozen = prepare(tmp_path, monkeypatch)
    sent = network(monkeypatch, p)
    class Changed(Verifier):
        def trace(self, *args):
            result = super().trace(*args)
            result["trace"]["events"][0]["locals"]["x"] = 100
            return result
    monkeypatch.setattr(cc, "RepairVerifier", Changed)
    with pytest.raises(ValueError, match="diagnostic does not reproduce"):
        cc.collect(frozen, tmp_path / "run", claim_root=tmp_path / "claims")
    assert not sent and not (tmp_path / "run").exists()


def test_zero_response_archive_replays_without_an_empty_cells_directory(tmp_path, monkeypatch):
    import hashlib
    import zipfile
    from vao.analysis import contract_verification as cv
    from vao.analysis.repair_information import render

    p, config, frozen = prepare(tmp_path, monkeypatch)
    network(monkeypatch, p)
    network(monkeypatch, p, overage=True)
    run = tmp_path / 'run'
    with pytest.raises(ProviderStopped): cc.collect(frozen, run, claim_root=tmp_path / 'claims')
    report = summarize(run)
    source = tmp_path / 'export'
    source.mkdir()
    (source / 'analysis.json').write_text(json.dumps(report))
    (source / 'REPORT.md').write_text(render(report))
    members = {}
    with zipfile.ZipFile(source / 'evidence.zip', 'w') as z:
        for path in run.rglob('*'):
            if path.is_file():
                name = 'collection/' + path.relative_to(run).as_posix()
                content = path.read_bytes()
                z.writestr(name, content)
                members[name] = hashlib.sha256(content).hexdigest()
    assert not any(name.startswith('collection/cells/') for name in members)
    (source / 'evidence-manifest.json').write_text(json.dumps({
        'files': members, 'archive_sha256': hashlib.sha256((source / 'evidence.zip').read_bytes()).hexdigest()}))
    monkeypatch.setattr(cv, 'RepairVerifier', Verifier)
    result = tmp_path / 'reverified.json'
    cv.reproduce(source, result)
    verified = json.loads(result.read_text())
    assert verified['full_analysis_and_markdown_reproduced']
    assert verified['public_diagnostic_projections_reexecuted']
    assert verified['checked_evaluation_records'] == 0 and verified['discrepancies'] == []



def test_matched_request_diff_is_only_runtime_diagnostic_and_balanced_order():
    p = packet()
    orders = {}
    for a, b in zip(p["requests"][::2], p["requests"][1::2]):
        assert a["metadata"]["trajectory"] == b["metadata"]["trajectory"]
        assert a["provider_body"]["seed"] == b["provider_body"]["seed"]
        pair = {r["metadata"]["arm"]: copy.deepcopy(r["provider_body"]) for r in (a, b)}
        focused = json.loads(pair["focused"]["messages"][1]["content"])
        trace = json.loads(pair["focused_trace"]["messages"][1]["content"])
        assert trace.pop("runtime_diagnostic")
        assert focused == trace
        pair["focused_trace"]["messages"] = pair["focused"]["messages"]
        assert pair["focused_trace"] == pair["focused"]
        orders[a["metadata"]["arm"]] = orders.get(a["metadata"]["arm"], 0) + 1
    assert orders == {"focused": 16, "focused_trace": 16}


def test_budget_and_qualification_cannot_be_relabelled(tmp_path, monkeypatch):
    p, config, frozen = prepare(tmp_path, monkeypatch)
    prior = frozen["prior_report"]
    for changed in ({**config, "monetary_authorization_usd": ".46"},
                    {**config, "cumulative_limit_usd": ".50"},
                    {**config, "live_calls_enabled": False}):
        with pytest.raises(ValueError): cc.authorization(changed, p, prior)
    with pytest.raises(ValueError):
        cc.authorization(config, p, {**prior, "gate": "no_repeated_solver_compatibility_demonstrated"})
    with pytest.raises(ValueError):
        cc.authorization(config, p, {**prior, "cumulative_committed_usd": "0"})


def test_larger_cost_without_done_is_retained_and_terminal_is_audited(tmp_path, monkeypatch):
    p, config, frozen = prepare(tmp_path, monkeypatch)
    sent = network(monkeypatch, p, overage=True)
    run = tmp_path / 'run'
    with pytest.raises(ProviderStopped): cc.collect(frozen, run, claim_root=tmp_path / 'claims')
    report = summarize(run)
    assert len(sent) == 1 and report['accounting']['study_committed_usd'] == '0.02'
    assert report['accounting']['cumulative_committed_usd'] == '0.13785551'
    assert sum(a['missing'] for a in report['arm_table']) == 64
    assert report['gate'] == 'inconclusive_incomplete_bank'
    terminal = json.loads((run / 'interruption.json').read_text())
    terminal['study_commitment_usd'] = '0.00720896'
    (run / 'interruption.json').write_text(json.dumps(terminal))
    with pytest.raises(ValueError, match='Terminal stream accounting'): summarize(run)


def test_missing_or_changed_stream_receipt_metrics_rejected(tmp_path, monkeypatch):
    p, config, frozen = prepare(tmp_path, monkeypatch)
    network(monkeypatch, p, interrupt=True)
    run = tmp_path / 'run'
    with pytest.raises(ProviderStopped): cc.collect(frozen, run, claim_root=tmp_path / 'claims')
    key = p['requests'][0]['metadata']['attempt_id']
    path = run / 'stream-metrics' / (key + '.json')
    original = json.loads(path.read_text())
    for changes in ({'done_received': False}, {'wire_limit_bytes': 1048576}, {'reported_cost_usd': '0'}, {'stream_complete': False}):
        path.write_text(json.dumps({**original, **changes}))
        with pytest.raises(ValueError): summarize(run)
    path.unlink()
    with pytest.raises(ValueError): summarize(run)


def test_history_scan_preserves_sources_and_forbids_even_unsent_repetition():
    data = {'tasks': ds.source_records(), 'requests': packet()['requests']}
    review = ds.validate_origin(data)
    assert review['historical_archives'] == 13
    assert review['historical_unique_bodies'] == 492 and review['historical_overlap'] == 0
    import zipfile
    with zipfile.ZipFile(ds.PRIOR + '/evidence.zip') as z:
        old = next(ds.archived_requests(json.loads(z.read('collection/manifest.json'))))
    data['requests'][0] = old
    with pytest.raises(ValueError, match='historical planned request'): ds.validate_origin(data)


def test_source_candidate_tampering_rejected():
    data = {'tasks': ds.source_records(), 'requests': packet()['requests']}
    data['tasks'][0]['source_cost_usd'] = '0'
    with pytest.raises(ValueError, match='Source candidate content'): ds.validate_origin(data)
