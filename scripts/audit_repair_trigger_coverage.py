"""Audit only closed 27B source checkpoints, never ongoing model outcomes."""
import argparse
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
from vao.repair.diagnostic_study import source_records, SOURCE, ARCHIVE_SHA
from vao.repair.contracts import public_feedback
from vao.repair.verifier import RepairVerifier


def audit():
    verifier = RepairVerifier()
    preflight = verifier.preflight()
    records = source_records()
    table = []
    for r in records:
        p = r['public']
        public = verifier.check(p['files'], p['entrypoint'], p['public_cases'])
        evaluation = verifier.check(p['files'], p['entrypoint'], r['evaluator']['cases'])
        assert public_feedback(public) == r['source_public_result']
        full = public['passed'] and evaluation['passed']
        assert full == r['source_full_pass']
        table.append({'task': p['task_id'], 'source_attempt_id': r['source_attempt_id'],
                      'public_pass': public['passed'], 'full_pass': full,
                      'triggered': not public['passed'],
                      'untriggered_evaluator_failure': public['passed'] and not full,
                      'prefix_usd': r['source_cost_usd'],
                      'verification_seconds': public['verifier_seconds'] + evaluation['verifier_seconds']})
    triggered = sum(r['triggered'] for r in table)
    accepted_correct = sum(r['public_pass'] and r['full_pass'] for r in table)
    accepted_evaluator_failure = sum(r['untriggered_evaluator_failure'] for r in table)
    assert triggered + accepted_correct + accepted_evaluator_failure == len(table)
    # Counterfactual ceiling only: no claim about actual intervention success.
    upper = triggered + accepted_correct
    return {'schema_version': 1, 'kind': 'closed_source_trigger_coverage_audit',
            'checked_utc': datetime.now(timezone.utc).isoformat(),
            'source_result': SOURCE, 'source_archive_sha256': ARCHIVE_SHA,
            'api_calls': 0, 'active_collection_outcomes_read': False,
            'historical_outcomes_changed': False, 'source_evaluations_reexecuted': 24,
            'sandbox_preflight': preflight, 'source_candidates': len(table),
            'public_failure_triggered': triggered, 'untriggered_full_passes': accepted_correct,
            'untriggered_evaluator_failures': accepted_evaluator_failure,
            'perfect_recovery_counterfactual_ceiling': {'full_passes': upper, 'denominator': len(table),
                'fraction': upper / len(table),
                'assumptions': ['Every triggered source is fully repaired.',
                    'Public-pass source artifacts are accepted unchanged.',
                    'The original frozen public-plus-evaluator criterion is retained.'],
                'not_an_observed_policy_result': True},
            'original_prefix_cost_once_usd': str(sum((Decimal(r['prefix_usd']) for r in table), Decimal(0))),
            'known_specification_ambiguity': {'task': 'development/bugsinpy-adapted/youtube-dl-027',
                'source': 'experiments/python-repair/checkpoint-environment/results/diagnostic-audit-20261026/README.md',
                'note': 'One of the three untriggered evaluator failures involves the previously documented timestamp ambiguity; do not count all three as unambiguous model errors.'},
            'interpretation': 'Success conditional on eight triggered failures must remain separate from end-to-end success over twelve retained sources. A recovery-only policy cannot change accepted unchanged sources. A future verifier/specification revision needs separate versioning and evaluation; current tasks and gates stay frozen.',
            'fit_selector': False, 'task_table': table}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = audit()
    result['reproducer_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    with args.output.open('x') as out:
        json.dump(result, out, indent=2); out.write('\n')
    print(json.dumps({k:result[k] for k in ('source_candidates','public_failure_triggered','untriggered_full_passes','untriggered_evaluator_failures','perfect_recovery_counterfactual_ceiling','api_calls','active_collection_outcomes_read')}))
