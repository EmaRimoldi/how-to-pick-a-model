"""Exhaustively compare robust bounds with every completion on a small grid."""
from itertools import product
from vao.analysis.repair_missingness import evaluate, Criteria


def test_robust_screen_all_small_grid_completions():
    bugs = ('a','b'); draws=2; criteria=Criteria(repeated_bugs=1,trace_successes_per_bug=1,net_successes=1)
    keys=[(b,d,a) for b in bugs for d in range(draws) for a in ('focused','trace')]
    configurations=completions=0
    for values in product((False,True,None),repeat=len(keys)):
     cells=dict(zip(keys,values));actual=evaluate(cells,bugs=bugs,draws=draws,criteria=criteria)
     missing=[k for k,v in cells.items() if v is None]
     outcomes=[];diffs=[]
     for assignment in product((False,True),repeat=len(missing)):
      full={**cells,**dict(zip(missing,assignment))}
      # Independent direct calculation, not the candidate's extreme helper.
      trace=sum(v for (b,d,a),v in full.items() if a=='trace')
      focused=sum(v for (b,d,a),v in full.items() if a=='focused')
      repeated=sum(any(full[(b,d,'trace')] for d in range(draws)) for b in bugs)
      halves=[sum(int(full[(b,d,'trace')])-int(full[(b,d,'focused')]) for b in bugs) for d in range(draws)]
      outcomes.append(repeated>=1 and trace-focused>=1 and all(h>0 for h in halves));diffs.append((trace-focused)/4)
      completions+=1
     assert actual['all_completions_pass']==all(outcomes)
     assert actual['no_completion_passes']==(not any(outcomes))
     assert [float(x) for x in actual['bounds']]==[min(diffs),max(diffs)]
     assert actual['mean'] is None if missing else actual['mean']==actual['bounds'][0]
     configurations+=1
    assert configurations==6561 and completions==65536
