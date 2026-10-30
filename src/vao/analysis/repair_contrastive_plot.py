"""Terminal three-arm report visualization; never reads raw collection outcomes.

Accepts only terminal, source-bound reports or explicitly marked rendering fixtures.
"""
import argparse
from decimal import Decimal
import hashlib
import json
import math
import re
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

STUDY = 'repair-qwen-contrastive-trace-development-v1'
ARMS = ('focused', 'single_trace', 'paired_trace')
LABELS = ('Code + feedback', '+ Single trace', '+ Paired traces')
CONTRASTS = (('paired_trace', 'focused', 'Paired − baseline (primary)'),
             ('paired_trace', 'single_trace', 'Paired − single'),
             ('single_trace', 'focused', 'Single − baseline'))
COLORS = ('#555E6C', '#2A6FBB', '#B85A28')


def close(a, b):
    return type(a) in (int, float) and math.isfinite(a) and abs(a - b) <= 1e-10


def prepare(report, *, fixture=False):
    if report.get('synthetic_render_fixture', False) != fixture:
        raise ValueError('Synthetic rendering requires an explicit fixture flag')
    if report.get('study') != STUDY or report.get('status') not in (
            'complete_contrastive_development_probe', 'incomplete_contrastive_development_probe'):
        raise ValueError('Expected a terminal contrastive report, not active raw data')
    if not fixture and (report.get('model_results') is not True or any(not re.fullmatch(r'[a-f0-9]{' + str(length) + r'}', str(report.get(key, ''))) for key, length in (('source_commit', 40), ('packet_id', 64), ('freeze_id', 64)))):
        raise ValueError('Real figure requires a source-bound model report')
    complete = report['status'] == 'complete_contrastive_development_probe'
    accounting = report['accounting']
    if complete != (accounting['sealed'] and not accounting['cap_exceeded']):
        raise ValueError('Terminal completeness and accounting disagree')
    rows = report['arm_table']
    if tuple(r['arm'] for r in rows) != ARMS or len(report['task_table']) != 12 or sum(t['eligible'] for t in report['task_table']) != 8:
        raise ValueError('Declared arm order or all-source denominator changed')
    by_arm = {r['arm']: r for r in rows}
    for r in rows:
        for k in ('planned', 'observed', 'successes', 'missing'):
            if type(r[k]) is not int or r[k] < 0: raise ValueError('Invalid outcome count')
        if r['planned'] != 24 or r['observed'] + r['missing'] != 24 or r['successes'] > r['observed']:
            raise ValueError('A selected outcome was excluded or miscounted')
        expected = (r['successes'] / 24, (r['successes'] + r['missing']) / 24)
        if len(r['success_bounds']) != 2 or not all(close(a, b) for a, b in zip(r['success_bounds'], expected)):
            raise ValueError('Success bound denominator differs')
        known, committed = Decimal(r['known_usd']), Decimal(r['committed_usd'])
        if not known.is_finite() or not committed.is_finite() or not 0 <= known <= committed:
            raise ValueError('Unknown commitment cannot be negative or hidden')
        if complete and r['missing']:
            raise ValueError('Complete report has missing cells')
    if (sum(Decimal(r['known_usd']) for r in rows) != Decimal(accounting['settled_usd'])
        or sum(Decimal(r['committed_usd']) for r in rows) != Decimal(accounting['study_committed_usd'])):
        raise ValueError('Figure arm costs do not reconcile')
    cumulative = Decimal(accounting['carried_committed_usd']) + Decimal(accounting['study_committed_usd'])
    exceeded = (Decimal(accounting['study_committed_usd']) > Decimal(report['study_limit_usd']) or cumulative > Decimal(report['cumulative_limit_usd']))
    if cumulative != Decimal(accounting['cumulative_committed_usd']) or accounting['cap_exceeded'] != exceeded:
        raise ValueError('Cap flag or cumulative costs do not reconcile')
    intervals = []
    for index, (a, b, label) in enumerate(CONTRASTS):
        r = report['contrasts'][a + '_minus_' + b]
        if r['primary'] != (index == 0): raise ValueError('Primary comparison changed')
        expected = (by_arm[a]['success_bounds'][0] - by_arm[b]['success_bounds'][1],
                    by_arm[a]['success_bounds'][1] - by_arm[b]['success_bounds'][0])
        if len(r['selected_cell_difference_bounds']) != 2 or not all(close(x, y) for x, y in zip(r['selected_cell_difference_bounds'], expected)):
            raise ValueError('Contrast bounds do not reconcile with every selected cell')
        if complete:
            mean, bounds = r['mean_difference'], r['descriptive_bug_bootstrap_95']
            if not close(mean, (by_arm[a]['successes'] - by_arm[b]['successes']) / 24):
                raise ValueError('Displayed mean does not match paired selected sample')
            if not isinstance(bounds, list) or len(bounds) != 2 or any(not math.isfinite(v) for v in bounds) or not -1 <= bounds[0] <= bounds[1] <= 1:
                raise ValueError('Invalid descriptive interval')
        else:
            if r['mean_difference'] is not None or r['descriptive_bug_bootstrap_95'] is not None:
                raise ValueError('Incomplete reports must not show imputed means or intervals')
            mean, bounds = None, r['selected_cell_difference_bounds']
        intervals.append({'label': label, 'mean': mean, 'bounds': bounds, 'primary': index == 0})
    return {'complete': complete, 'arms': rows, 'contrasts': intervals,
            'interval_semantics': 'descriptive 95% bug bootstrap' if complete else 'finite selected-cell bounds; no mean',
            'fixture': fixture, 'cap_exceeded': accounting['cap_exceeded']}


def plot(report, output, *, fixture=False):
    data = prepare(report, fixture=fixture)
    output = Path(output); output.mkdir()
    fig, axes = plt.subplots(1, 3, figsize=(15, 5.9), gridspec_kw={'width_ratios': [1.05, 1.35, 1]})
    a, b, c = axes
    for i, (r, color) in enumerate(zip(data['arms'], COLORS)):
        lower, upper = [100 * v for v in r['success_bounds']]
        a.bar(i, lower, width=.62, color=color)
        if upper > lower:
            a.bar(i, upper - lower, bottom=lower, width=.62, facecolor='white', edgecolor=color, hatch='///')
        missing = f"\n{r['missing']} missing" if r['missing'] else ''
        a.text(i, min(upper + 2, 104), f"{r['successes']}/{r['planned']}{missing}", ha='center', va='bottom', fontsize=9)
    a.set_ylim(0, 116); a.set_yticks([0, 25, 50, 75, 100]); a.set_ylabel('Full repair fraction of planned cells (%)')
    a.set_xticks(range(3), ['Code +\nfeedback', '+ Single\ntrace', '+ Paired\ntraces'])
    a.set_title('All 24 selected cells per arm', fontsize=11)
    a.grid(axis='y', alpha=.18); a.set_axisbelow(True)
    a.text(.5, -.23, 'Hatching: unresolved outcome range', transform=a.transAxes, ha='center', fontsize=9)
    for i, row in enumerate(data['contrasts']):
        lo, hi = [100 * x for x in row['bounds']]; color = COLORS[2] if row['primary'] else '#777777'
        b.plot([lo, hi], [i, i], color=color, linewidth=2.4)
        b.plot([lo, hi], [i, i], '|', color=color, markersize=9)
        if row['mean'] is not None:
            b.plot(row['mean'] * 100, i, 'o', color=color, markersize=5)
        b.text(0, i - .27, row['label'], transform=b.get_yaxis_transform(), fontsize=9,
               fontweight='bold' if row['primary'] else 'normal')
    b.axvline(0, color='#222222', linestyle=':', linewidth=1)
    b.set_xlim(-105, 105); b.set_ylim(2.5, -.65); b.set_yticks([])
    b.set_xticks([-100, -50, 0, 50, 100]); b.set_xlabel('Difference in percentage points')
    b.set_title('Fixed comparisons: primary first', fontsize=11)
    b.text(.5, -.23, data['interval_semantics'], transform=b.transAxes, ha='center', fontsize=9)
    known = [float(Decimal(r['known_usd'])) for r in data['arms']]
    unknown = [float(Decimal(r['committed_usd']) - Decimal(r['known_usd'])) for r in data['arms']]
    c.bar(range(3), known, width=.62, color=COLORS, label='Known charges')
    c.bar(range(3), unknown, bottom=known, width=.62, color='white', edgecolor=COLORS, hatch='///', label='Unresolved commitment')
    ceiling = max((x + y for x, y in zip(known, unknown)), default=0)
    c.set_ylim(0, max(.0001, ceiling * 1.35))
    for i, (k, u) in enumerate(zip(known, unknown)):
        c.text(i, k + u + max(ceiling * .03, .000002), f'${k + u:.5f}', ha='center', va='bottom', fontsize=9)
    c.set_xticks(range(3), ['Code +\nfeedback', '+ Single\ntrace', '+ Paired\ntraces'])
    c.set_ylabel('Actual study API USD / commitment')
    c.set_title('All charges and unresolved reserves', fontsize=11)
    c.grid(axis='y', alpha=.18); c.set_axisbelow(True)
    c.legend(loc='upper left', fontsize=8, frameon=False)
    title = 'SYNTHETIC RENDER CHECK — NOT MODEL RESULTS' if fixture else 'Contrastive trace calibration — exposed development checkpoints'
    fig.suptitle(title, fontsize=14, y=.98)
    state = 'Complete bank' if data['complete'] else 'Incomplete or accounting-limited bank'
    if data['cap_exceeded']: state += '; accounting cap exceeded'
    gate_label = {'no_completion_meets_development_screen': 'Development screen failed.', 'candidate_for_independent_acquisition_calibration': 'Screen permits independent calibration only.'}.get(report.get('gate'), 'Screen remains inconclusive.' if not fixture else 'Synthetic screen not evaluated.')
    fig.text(.5, .91, state + '. ' + gate_label + ' No selector trained.', ha='center', fontsize=10)
    fig.text(.5, .085, 'Shared code, public tests and feedback. Eight exposed checkpoints × three draws; twelve source candidates retained.', ha='center', fontsize=10)
    fig.text(.5, .05, 'Equal per-call limits are not equal total-resource policies. Prefix and local diagnostic/verification resources are reported separately.', ha='center', fontsize=9)
    fig.subplots_adjust(left=.055, right=.98, top=.80, bottom=.30, wspace=.40)
    fig.savefig(output / 'summary.png', dpi=160); plt.close(fig)
    metadata = {'report_sha256': hashlib.sha256(json.dumps(report, sort_keys=True).encode()).hexdigest(),
        'plot_source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'image_sha256': hashlib.sha256((output / 'summary.png').read_bytes()).hexdigest(),
        'figure_data': data, 'synthetic_render_fixture': fixture}
    (output / 'figure-data.json').write_text(json.dumps(metadata, indent=2) + '\n')
    return metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--fixture', action='store_true')
    args = parser.parse_args()
    plot(json.loads(args.input.read_text()), args.output, fixture=args.fixture)


if __name__ == '__main__':
    main()
