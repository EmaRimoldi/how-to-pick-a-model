"""Plot the prespecified two-arm terminal report, never inspect a live collection."""
import argparse,json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

STUDY='repair-qwen-public-trace-information-v1'
NAMES={'focused':'Focused feedback','focused_trace':'Focused feedback + trace'}
COLORS={'success':'#218267','failure':'#426688','missing':'#d5dbe3','primary':'#222b35'}


def draw(report,output):
    if report['study']!=STUDY or report['status'] not in {'complete_development_information_probe','incomplete_development_information_probe'}:
        raise ValueError('Expected terminal matched Qwen information report')
    synthetic=report.get('synthetic_layout_fixture') is True
    if not synthetic and report.get('model_results') is not True:
        raise ValueError('Mark synthetic fixtures explicitly')
    rows=report['arm_table'];by_arm={r['arm']:r for r in rows}
    assert set(by_arm)==set(NAMES) and len(rows)==2
    tasks=[t for t in report['task_table'] if t['eligible']]
    assert len(tasks)==8 and len(report['task_table'])==12
    complete=report['status']=='complete_development_information_probe'
    primary=report['contrasts']['focused_trace_minus_focused']
    assert primary['primary'] is True and len(report['contrasts'])==1
    if complete:
        assert primary['mean_difference'] is not None and primary['descriptive_bug_bootstrap_95'] is not None
    else:
        assert primary['mean_difference'] is None and primary['descriptive_bug_bootstrap_95'] is None
    for r in rows:
        assert r['planned']==32 and r['observed']+r['missing']==32
        assert 0<=r['successes']<=r['observed'] and (not complete or r['missing']==0)
        cells=[c for t in tasks for c in t['cells'] if c['arm']==r['arm']]
        assert len(cells)==32 and sum(c['full_pass'] is True for c in cells)==r['successes']
        assert sum(not c['observed'] for c in cells)==r['missing']
    fig=plt.figure(figsize=(13.0,8.8),facecolor='white')
    grid=fig.add_gridspec(2,2,height_ratios=[2.8,1],width_ratios=[1,1.12],left=.18,right=.97,top=.82,bottom=.16,hspace=.42,wspace=.67)
    counts=fig.add_subplot(grid[0,0]);delta=fig.add_subplot(grid[0,1]);cost=fig.add_subplot(grid[1,:]);cost.axis('off')
    for i,arm in enumerate(NAMES):
        r=by_arm[arm]
        counts.barh(i,r['successes'],height=.5,color=COLORS['success'],label='Full repair' if i==0 else None)
        counts.barh(i,r['observed']-r['successes'],left=r['successes'],height=.5,color=COLORS['failure'],label='Observed non-repair' if i==0 else None)
        counts.barh(i,r['missing'],left=r['observed'],height=.5,color=COLORS['missing'],label='Unknown' if i==0 else None)
        for start,value,color in [(0,r['successes'],'white'),(r['successes'],r['observed']-r['successes'],'white'),(r['observed'],r['missing'],'#222b35')]:
            if value>=3:counts.text(start+value/2,i,str(value),ha='center',va='center',color=color,fontweight='bold')
        counts.text(0,i+.38,f"Full repairs: {r['successes']}/32; unknown: {r['missing']}/32",fontsize=9,va='center')
    counts.set(yticks=[0,1],yticklabels=[NAMES[a] for a in NAMES],xlim=(0,32),ylim=(1.65,-.55),xlabel='All planned response cells',title='Outcome accounting')
    counts.set_xticks([0,8,16,24,32]);counts.legend(loc='upper left',bbox_to_anchor=(-.47,-.22),ncol=3,frameon=False,fontsize=8)
    labels=[]
    for i,t in enumerate(tasks):
        label=t['task'].split('/')[-1]
        labels.append(label)
        rates={}
        for arm in NAMES:
            selected=[c for c in t['cells'] if c['arm']==arm]
            assert len(selected)==4
            good=sum(c['full_pass'] is True for c in selected);unknown=sum(not c['observed'] for c in selected)
            rates[arm]=(good/4,(good+unknown)/4)
        lo=rates['focused_trace'][0]-rates['focused'][1];hi=rates['focused_trace'][1]-rates['focused'][0]
        if complete:delta.plot(lo,i,'o',color=COLORS['failure'],markersize=6)
        else:delta.hlines(i,lo,hi,color='#7e8894',lw=2);delta.plot([lo,hi],[i,i],'|',color='#7e8894',markersize=9)
    total_y=len(tasks)+.5
    if complete:
        estimate=primary['mean_difference'];lo,hi=primary['descriptive_bug_bootstrap_95']
        assert abs(estimate-(by_arm['focused_trace']['successes']-by_arm['focused']['successes'])/32)<1e-12
        delta.hlines(total_y,lo,hi,lw=3,color=COLORS['primary']);delta.plot(estimate,total_y,'D',color=COLORS['primary'],markersize=7)
        primary_text=f'Paired difference: {100*estimate:+.1f} pp; descriptive 95% bug-bootstrap interval [{100*lo:+.1f}, {100*hi:+.1f}] pp'
    else:
        lo,hi=primary['selected_cell_difference_bounds']
        delta.hlines(total_y,lo,hi,lw=3,color=COLORS['primary']);delta.plot([lo,hi],[total_y,total_y],'|',color=COLORS['primary'],markersize=12)
        primary_text=f'Incomplete bank: selected-cell bounds [{100*lo:+.1f}, {100*hi:+.1f}] pp; no mean or confidence interval'
    delta.axvline(0,ls='--',color='#a3aab3',lw=1)
    delta.set(yticks=list(range(len(tasks)))+[total_y],yticklabels=labels+['All selected bugs'],xlim=(-1.05,1.05),ylim=(total_y+.7,-.7),xlabel='Trace minus focused (percentage points)',title='Prespecified primary comparison')
    delta.set_xticks([-1,-.5,0,.5,1]);delta.xaxis.set_major_formatter(FuncFormatter(lambda value,_: f'{100*value:.0f}'))
    headers=['Strategy','Known API USD','Committed API USD','Diagnostic seconds¹','False public passes','Public regressions']
    data=[]
    for arm in NAMES:
        r=by_arm[arm]
        data.append([NAMES[arm],f"{float(r['known_usd']):.6f}",f"{float(r['committed_usd']):.6f}",f"{r['diagnostic_seconds_if_deployed']:.3f}",str(r['false_positives']),str(r['regressions'])])
    table=cost.table(cellText=data,colLabels=headers,cellLoc='center',colWidths=[.24,.14,.16,.17,.15,.14],loc='center')
    table.auto_set_font_size(False);table.set_fontsize(8.3);table.scale(1,1.8)
    for (r,c),cell in table.get_celld().items():
        cell.set_edgecolor('#d6dce4')
        if r==0:cell.set_facecolor('#edf1f6');cell.set_text_props(weight='bold')
    for ax in (counts,delta):ax.spines[['top','right']].set_visible(False)
    title='SYNTHETIC LAYOUT CHECK — NOT EXPERIMENT RESULTS' if synthetic else 'Does a public execution trace improve repair?'
    fig.suptitle(title,x=.54,y=.96,fontsize=16,fontweight='bold')
    fig.text(.54,.91,'8 exposed development checkpoints × 4 draws × 2 arms · Qwen3-Coder-Next / Parasail / BF16',ha='center',fontsize=10)
    fig.text(.54,.866,primary_text,ha='center',fontsize=10)
    if complete and lo == hi:
        fig.text(.5,.025,'A degenerate descriptive bootstrap interval does not establish population equivalence.',ha='center',fontsize=9,color='#46515e')
    fig.text(.5,.075,'Unknown outcomes are not failures. Draws are nested within bugs; this is a development screen, not a policy evaluation.\n¹ Diagnostic time covers all 32 planned decisions per arm, including missing cells; API columns include prompt tokens and retained uncertain reserves.\nPrefix and verifier costs are in the report. Equal per-call limits do not establish equal-total-budget policy benefit.',ha='center',fontsize=9,color='#46515e')
    output.mkdir(parents=True,exist_ok=True)
    for ext in ('png','svg'):fig.savefig(output/('qwen-information-summary.'+ext),dpi=170,facecolor='white')
    plt.close(fig)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();draw(json.loads(args.input.read_text()),args.output)

if __name__=='__main__':main()
