"""Plot all four terminal repair-interface conditions; never read a live collection."""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

ARMS = ('original', 'claim_removed', 'helpers_explicit', 'both')
NAMES = ('Original', 'Claim removed', 'Helpers editable', 'Both cues')
CATEGORIES = (
    ('exact_copy', 'Exact copy', '#ad8555'),
    ('format_or_comment_only', 'Formatting/comments', '#d6bd96'),
    ('entrypoint_only_syntax_change', 'Entrypoint only', '#7066a8'),
    ('other_syntax_change', 'Other syntax change', '#3f8c92'),
    ('unparseable', 'Unparseable', '#bb6868'),
    ('no_artifact', 'No artifact', '#5d6570'),
)


def validate(report, synthetic):
    if report.get('study') != 'repair-interface-cues-v1':
        raise ValueError('Expected interface-cue report')
    if report.get('status') not in ('complete_development_interface_probe', 'incomplete_development_interface_probe'):
        raise ValueError('Only a terminal report may be plotted')
    if bool(report.get('synthetic_layout_test')) != synthetic:
        raise ValueError('Synthetic flag and report marker must agree')
    table = report['arm_table']
    if tuple(row['arm'] for row in table) != ARMS:
        raise ValueError('All four conditions must retain declared order')
    for row in table:
        if any(type(row[key]) is not int for key in ('planned', 'observed', 'successes', 'missing')):
            raise ValueError('Outcome counts must be integers')
        if row['planned'] != 32 or not 0 <= row['successes'] <= row['observed'] <= row['planned']:
            raise ValueError('Invalid outcome counts')
        if row['observed'] + row['missing'] != row['planned']:
            raise ValueError('Missing cells were lost')
        categories = row['edit_categories']
        if set(categories) != {key for key, _, _ in CATEGORIES} or any(type(n) is not int or n < 0 for n in categories.values()):
            raise ValueError('Invalid syntax categories')
        if sum(categories.values()) != row['observed']:
            raise ValueError('Every observed response needs an edit classification')
    if report['status'] == 'complete_development_interface_probe' and any(row['missing'] for row in table):
        raise ValueError('Complete reports cannot contain missing outcomes')
    return table


def plot(report, output, *, synthetic=False):
    table = validate(report, synthetic)
    output.mkdir(parents=True, exist_ok=False)
    matplotlib.rcParams['svg.hashsalt'] = 'repair-interface-terminal-v1'
    fig, axes = plt.subplots(1, 2, figsize=(12.8, 6.1))
    fig.subplots_adjust(left=.14, right=.97, bottom=.29, top=.75, wspace=.34)
    outcomes = [('successes', 'Full repair', '#287e62'), ('failed', 'Observed failure', '#315a7d'), ('missing', 'Unknown', '#d9dde3')]
    for i, row in enumerate(table):
        left = 0
        for key, _, color in outcomes:
            count = row['observed'] - row['successes'] if key == 'failed' else row[key]
            axes[0].barh(i, count, left=left, color=color, height=.67)
            if count >= 2:
                axes[0].text(left + count/2, i, str(count), ha='center', va='center', color='#202020' if key == 'missing' else 'white', fontsize=10)
            elif count:
                axes[0].annotate(str(count), (left + count/2, i), (left + count/2, i-.43), ha='center', fontsize=9)
            left += count
        left = 0
        for key, _, color in CATEGORIES:
            count = row['edit_categories'][key]
            axes[1].barh(i, count, left=left, color=color, height=.67)
            if count >= 2:
                axes[1].text(left + count/2, i, str(count), ha='center', va='center', color='white', fontsize=10)
            elif count:
                axes[1].annotate(str(count), (left + count/2, i), (left + count/2, i-.43), ha='center', fontsize=9)
            left += count
    axes[0].set(yticks=range(4), yticklabels=NAMES, xlabel='Planned cells per condition', title='Complete repair and missingness')
    axes[1].set(yticks=range(4), yticklabels=NAMES, xlabel='Received responses; unknown cells excluded', title='What changed in the returned code')
    for ax in axes:
        ax.invert_yaxis(); ax.set_xlim(0, 33); ax.set_xticks([0, 8, 16, 24, 32])
        ax.spines[['top','right']].set_visible(False)
    axes[0].legend(handles=[Patch(facecolor=color,label=label) for _,label,color in outcomes], frameon=False, loc='upper left', bbox_to_anchor=(-.02,-.2), ncol=3, fontsize=9)
    axes[1].legend(handles=[Patch(facecolor=color,label=label) for _,label,color in CATEGORIES], frameon=False, loc='upper left', bbox_to_anchor=(-.02,-.2), ncol=2, fontsize=8)
    observed = sum(row['observed'] for row in table); successes = sum(row['successes'] for row in table)
    fig.suptitle('SYNTHETIC LAYOUT TEST — NO MODEL RESULTS' if synthetic else 'Repair-interface control · development evidence', fontsize=16, y=.97, color='#a62525' if synthetic else '#151515')
    fig.text(.5,.88,f'{observed}/128 received · {successes} full repairs · 8 selected failure checkpoints × 4 draws × 4 conditions',ha='center',fontsize=11)
    represented = sum(any(c['observed'] for c in t['cells']) for t in report.get('task_table', []))
    coverage = f'Received responses cover {represented}/8 selected checkpoints. ' if report.get('task_table') else ''
    fig.text(.5,.04,coverage + 'Repeated draws are not independent bugs.\nUnknown outcomes are not failures. Syntax categories do not establish semantic equivalence\nor the cause of a repair failure.',ha='center',fontsize=9,color='#49515b')
    for extension in ('png','svg'):
        path = output / ('interface-summary.' + extension)
        fig.savefig(path, dpi=170, facecolor='white')
        if extension == 'svg':
            path.write_text('\n'.join(line.rstrip() for line in path.read_text().splitlines()) + '\n')
    plt.close(fig)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--synthetic',action='store_true')
    args=parser.parse_args()
    plot(json.loads(args.input.read_text()),args.output,synthetic=args.synthetic)


if __name__=='__main__': main()
