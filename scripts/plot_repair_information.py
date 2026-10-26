"""Plot the frozen information report and separate post hoc edit audit, offline."""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = json.loads((args.input / 'analysis.json').read_text())
    audit = json.loads((args.input / 'stagnation-audit.json').read_text())
    manifest = json.loads((args.input / 'evidence-manifest.json').read_text())
    assert audit['archive_sha256'] == manifest['archive_sha256']
    assert sum(a['observed'] for a in report['arm_table']) == audit['summary']['observed']
    args.output.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.2), gridspec_kw={'width_ratios': [1.1, 1]})
    fig.subplots_adjust(left=.19, right=.97, bottom=.24, top=.73, wspace=.84)
    colors = {'success': '#287e62', 'failed': '#315a7d', 'missing': '#d9dde3'}
    names = {'raw': 'Existing feedback', 'focused': 'Focused feedback', 'focused_trace': 'Focused + trace'}
    for i, row in enumerate(report['arm_table']):
        failed = row['observed'] - row['successes']
        axes[0].barh(i, row['successes'], color=colors['success'], label='Full pass' if i == 0 else None)
        axes[0].barh(i, failed, left=row['successes'], color=colors['failed'], label='Observed failure' if i == 0 else None)
        axes[0].barh(i, row['missing'], left=row['observed'], color=colors['missing'], label='Unknown' if i == 0 else None)
        if failed: axes[0].text(row['successes'] + failed / 2, i, str(failed), ha='center', va='center', color='white')
        if row['missing']: axes[0].text(row['observed'] + row['missing']/2, i, str(row['missing']), ha='center', va='center')
    axes[0].set(yticks=range(len(report['arm_table'])), yticklabels=[names[a['arm']] for a in report['arm_table']],
        xlabel='Planned response cells', title='Frozen outcome accounting')
    axes[0].invert_yaxis()
    axes[0].legend(loc='upper left', bbox_to_anchor=(-.05, -.24), frameon=False, ncol=3, fontsize=8)
    mapping = [('exact_copy', 'Exact copy'), ('format_or_comment_only', 'Formatting only'),
        ('entrypoint_only_syntax_change', 'Entrypoint only'), ('other_syntax_change', 'Other syntax change'),
        ('unparseable', 'Unparseable'), ('no_artifact', 'No artifact')]
    active = [(name, label, audit['summary']['edit_categories'].get(name, 0)) for name, label in mapping
              if audit['summary']['edit_categories'].get(name, 0)]
    axes[1].barh(range(len(active)), [x[2] for x in active], color='#967348')
    axes[1].set(yticks=range(len(active)), yticklabels=[x[1] for x in active],
        xlabel='Received responses', title='Post hoc edit audit')
    axes[1].set_xlim(0, max(x[2] for x in active) * 1.22)
    axes[1].invert_yaxis()
    for i, (_, _, count) in enumerate(active): axes[1].text(count + .5, i, str(count), va='center')
    for ax in axes:
        ax.spines[['top', 'right']].set_visible(False)
        ax.xaxis.get_major_locator().set_params(integer=True)
    fig.suptitle('Usable outputs did not become complete repairs', fontsize=17, x=.52, y=.96)
    total = audit['summary']['observed']; successes = audit['summary']['full_successes']
    fig.text(.52, .86, f'{total} received / 96 planned · {successes} complete repairs · 8 exposed failure checkpoints', ha='center', fontsize=11)
    fig.text(.5, .035, 'Unknown outcomes are not failures. Repeated answers are not independent bugs.\nSyntax categories do not identify the cause or establish semantic equivalence.', ha='center', fontsize=9, color='#49515b')
    for extension in ('png', 'svg'):
        fig.savefig(args.output / ('information-summary.' + extension), dpi=170, facecolor='white')
    plt.close(fig)


if __name__ == '__main__':
    main()
