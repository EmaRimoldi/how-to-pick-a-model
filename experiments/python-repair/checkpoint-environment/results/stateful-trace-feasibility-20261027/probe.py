"""Offline compatibility/trace feasibility, not a new model cohort or protocol."""
import ast
import argparse
import hashlib
import json
from pathlib import Path
from vao.repair.verifier import RepairVerifier
from vao.repair.environment import canonical

ROOT=Path(__file__).resolve().parent
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
args.output.mkdir(parents=True,exist_ok=False)
OUTPUT=args.output
NAMES={'SETTINGS_PRIORITIES','get_settings_priority','SettingsAttribute','BaseSettings','_DictProxy'}
def extracts(path,names):
 text=path.read_text();lines=text.splitlines(True);pieces=[]
 for node in ast.parse(text).body:
  name=getattr(node,'name',None)
  if isinstance(node,ast.Assign) and len(node.targets)==1:name=getattr(node.targets[0],'id',None)
  if name in names:pieces.append(''.join(lines[node.lineno-1:node.end_lineno]))
 assert len(pieces)==len(names)
 return '\n\n'.join(pieces)
header='''import json
import copy
import warnings
from collections.abc import MutableMapping
from importlib import import_module
from types import SimpleNamespace
# Exact Python3 semantics for the two six APIs used by these preserved classes.
six=SimpleNamespace(string_types=(str,), iteritems=lambda mapping:iter(mapping.items()))
'''
wrapper='''
def solve(defaults, base, updates):
    component = BaseSettings(defaults, priority='default')
    settings = BaseSettings({'COMPONENT': component})
    if base is not None:
        settings.set('COMPONENT_BASE', base, priority='project')
    for key, value, priority in updates:
        component.set(key, value, priority)
    result = settings._getcomposite('COMPONENT')
    return [[key, result[key], result.getpriority(key)] for key in sorted(result)]
'''
files={version:{'solution.py':header+extracts(ROOT/'exceptions.txt',{'ScrapyDeprecationWarning'})+'\n\n'+extracts(ROOT/(version+'.txt'),NAMES)+wrapper} for version in ('buggy','fixed')}
cases=[
 {'id':'upstream-default-exclusion','args':[{'a':10,'x':30},{'a':1,'b':2},[['y',4,'project']]],'expected':[['a',1,0],['b',2,0],['y',4,20]]},
 {'id':'explicit-empty-base','args':[{'q':5},{},[['z',9,'command']]],'expected':[['z',9,10]]},
 {'id':'no-base','args':[{'a':1,'b':2},None,[['a',7,'project']]],'expected':[['a',7,20],['b',2,0]]},
 {'id':'keep-high-priority','args':[{'a':10},{'a':1},[['a',8,'command'],['a',99,'default']]],'expected':[['a',8,10]]},
]
# Expected values above are specified before running either candidate.
(OUTPUT/'probe-inputs.json').write_text(json.dumps({'cases':cases,'expected_source':'Restricted upstream contract and manual values; no reference-output generation.'},indent=2)+'\n')
verifier=RepairVerifier();preflight=verifier.preflight();report={}
entry={'module':'solution','function':'solve'}
for version,artifact in files.items():
 result=verifier.check(artifact,entry,cases)
 report[version]={'result':result,'source_sha256':hashlib.sha256(canonical(artifact).encode()).hexdigest(),'source_bytes':len(artifact['solution.py'].encode()),'traces':[]}
 for case in cases:
  trace=verifier.trace(artifact,entry,case)
  ordinary=verifier.invoke(artifact,entry,case)
  assert trace['observed']==ordinary
  events=trace['trace']['events']
  item={'case':case['id'],'matches_ordinary':True,'available':trace['available'],'events_seen':trace['trace']['events_seen'],'events_dropped':trace['trace']['events_dropped'],'capture_limit_reached':trace['trace']['capture_limit_reached'],'retained_target_events':sum(e['function']=='_getcomposite' for e in events),'retained_functions':sorted({e['function'] for e in events}),'trace':trace}
  report[version]['traces'].append(item)
report={'kind':'engineering_only_one_already_exposed_candidate','benchmark_bug':'scrapy/26','api_calls':0,'model_results':False,'preflight':preflight,'variants':report,'limits':['Four engineering examples, not public/evaluator model task suites.','Complete named upstream definitions preserved; import compatibility and solve wrapper are explicit.','Only strings/JSON values and the selected priority APIs are exercised; no crawler lifecycle or dynamic module loading.','Trace coverage is measured, not assumed. No new acquisition protocol or paid calls.']}
(OUTPUT/'probe-results.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({v:{'passed_cases':r['result']['passed_cases'],'total_cases':r['result']['total_cases'],'source_bytes':r['source_bytes'],'traces':[{k:x[k] for k in ['case','events_seen','events_dropped','capture_limit_reached','retained_target_events']} for x in r['traces']]} for v,r in report['variants'].items()},indent=2))
