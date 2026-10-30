"""Render terminal solver draws; synthetic layout data requires an explicit flag."""
import argparse
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch, Rectangle

COLORS={'full':'#287e62','public_only':'#c58a32','failure':'#426782','missing':'#e0e4e9'}


def validate(report, synthetic):
    if report.get('study')!='repair-solver-compatibility-v1':
        raise ValueError('Expected solver compatibility study')
    if report.get('status') not in ('complete_development_solver_probe','incomplete_development_solver_probe'):
        raise ValueError('Only terminal reports may be plotted')
    if bool(report.get('synthetic_layout_test'))!=synthetic:
        raise ValueError('Synthetic flag and input marker must agree')
    tasks=report['task_table']; selected=[t for t in tasks if t['eligible']]
    if len(tasks)!=12 or len(selected)!=8:
        raise ValueError('Retain all twelve sources and eight eligible checkpoints')
    for t in tasks:
        if t['eligible'] and sorted(c['draw'] for c in t['cells'])!=[0,1,2,3]:
            raise ValueError('Every eligible checkpoint needs all four planned cells')
        if not t['eligible'] and t['cells']:
            raise ValueError('Public-pass source has unexpected intervention')
        for c in t['cells']:
            if type(c['observed']) is not bool:
                raise ValueError('Invalid observation marker')
            if c['observed']:
                if type(c['full_pass']) is not bool or type(c['public_pass']) is not bool:
                    raise ValueError('Observed cells require boolean outcomes')
                if c['full_pass'] and not c['public_pass']:
                    raise ValueError('Full repair cannot fail public tests')
            elif c['full_pass'] is not None or c['public_pass'] is not None:
                raise ValueError('Missing cells cannot be assigned outcomes')
    cells=[c for t in selected for c in t['cells']]
    expected={'planned':32,'observed':sum(c['observed'] for c in cells),
              'successes':sum(c['full_pass'] is True for c in cells),
              'missing':sum(not c['observed'] for c in cells)}
    if any(report['summary'][k]!=v for k,v in expected.items()):
        raise ValueError('Summary counts disagree with complete cell grid')
    if report['status']=='complete_development_solver_probe' and expected['missing']:
        raise ValueError('Complete reports cannot contain missing cells')
    return selected


def plot(report, output, *, synthetic=False):
    tasks=validate(report,synthetic)
    output.mkdir(parents=True,exist_ok=False)
    plt.rcParams['svg.hashsalt']='repair-solver-terminal-v1'
    fig,ax=plt.subplots(figsize=(10.4,7.2))
    fig.subplots_adjust(left=.25,right=.91,bottom=.27,top=.76)
    for y,t in enumerate(tasks):
        for c in t['cells']:
            kind='missing' if not c['observed'] else ('full' if c['full_pass'] else ('public_only' if c['public_pass'] else 'failure'))
            ax.add_patch(Rectangle((c['draw']-.46,y-.41),.92,.82,color=COLORS[kind]))
            label={'full':'Full repair','public_only':'Public only','failure':'No public pass','missing':'Unknown'}[kind]
            ax.text(c['draw'],y,label,ha='center',va='center',fontsize=8,color='#303943' if kind=='missing' else 'white')
        halves=[sum(c['full_pass'] is True for c in t['cells'] if c['draw'] in half) for half in ({0,1},{2,3})]
        unknown=[sum(not c['observed'] for c in t['cells'] if c['draw'] in half) for half in ({0,1},{2,3})]
        label=' | '.join(f'{n}–{n+m}' if m else str(n) for n,m in zip(halves,unknown))
        ax.text(4.0,y,label,ha='center',va='center',fontsize=9)
    ax.axvline(1.5,color='#66727e',lw=1.2,linestyle='--')
    ax.set(xlim=(-.6,4.6),ylim=(7.6,-.6),xticks=range(4),xticklabels=['Draw 1','Draw 2','Draw 3','Draw 4'],
           yticks=range(8),yticklabels=[t['task'].rsplit('/',1)[-1] for t in tasks])
    ax.xaxis.tick_top(); ax.tick_params(length=0,pad=8)
    for spine in ax.spines.values(): spine.set_visible(False)
    ax.text(4.0,-.95,'Full fixes by half\n(ranges if unknown)',ha='center',va='bottom',fontsize=9)
    title='SYNTHETIC LAYOUT TEST — NO MODEL RESULTS' if synthetic else 'Coding-solver compatibility · development evidence'
    fig.suptitle(title,fontsize=15,y=.97,color='#a62525' if synthetic else '#18222c')
    s=report['summary']
    fig.text(.5,.89,f"{s['observed']}/32 received · {s['successes']} full repairs · {s['missing']} unknown cells",ha='center',fontsize=12)
    legend=[Patch(color=COLORS[k],label=l) for k,l in [('full','Public + evaluator pass'),('public_only','Public pass, evaluator fail'),('failure','No public pass (including unusable)'),('missing','Missing outcome')]]
    fig.legend(handles=legend,frameon=False,loc='lower center',bbox_to_anchor=(.5,.16),ncol=2,fontsize=9)
    fig.text(.5,.10,'Screen requires a complete bank and ≥3 bugs solved in both draw halves.',ha='center',fontsize=10)
    fig.text(.5,.035,'Eight exposed failure checkpoints; four additional public-pass sources retained without intervention.\nDraws are not independent bugs. This is not a causal comparison with historical Gemma results.',ha='center',fontsize=9,color='#49515b')
    for extension in ('png','svg'):
        target=output/('solver-summary.'+extension)
        fig.savefig(target,dpi=170,facecolor='white')
        if extension=='svg':
            target.write_text('\n'.join(line.rstrip() for line in target.read_text().splitlines())+'\n')
    plt.close(fig)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--synthetic',action='store_true')
    args=parser.parse_args()
    plot(json.loads(args.input.read_text()),args.output,synthetic=args.synthetic)
