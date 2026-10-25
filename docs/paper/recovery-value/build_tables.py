"""Generate paper tables from the completed offline audit, without model calls."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path


ARMS = ("fresh", "artifact", "feedback", "artifact_feedback", "distractor")
MODELS = {"small": "9B", "large": "27B"}
VIEWS = {"global": "Global prior", "task": "Task", "feedback": "Feedback", "state": "State"}
CONTROLS = {
    "feedback": "Feedback (primary)",
    "best_static": "Source-selected static",
    "state_model_only": "Model only",
    "task": "Task only",
    "global": "Global prior",
    "escalation_diagnostic": "Fixed escalation (diagnostic)",
}
CONTRASTS = {
    "artifact-fresh": "Code -- fresh",
    "artifact_feedback-fresh": "Both -- fresh",
    "artifact_feedback-feedback": "Both -- feedback",
    "artifact_feedback-distractor": "Both -- irrelevant",
}


def ci_text(ci, scale=1, digits=2):
    return f"[{scale*ci['low']:+.{digits}f}, {scale*ci['high']:+.{digits}f}]"


def tabular(columns, header, rows):
    return "\n".join([
        "\\begin{tabular}{"+columns+"}", "\\toprule",
        " & ".join(header)+r"\\", "\\midrule",
        *(" & ".join(row)+r"\\" for row in rows),
        "\\bottomrule", "\\end{tabular}", "",
    ])


def generate(report, source_hash, *, allow_incomplete_descriptive=False):
    n = report["complete_states"]
    selected=report["selected_states"]
    bounds=report["missing_state_utility_bounds"]
    incomplete=report["status"]=="incomplete_descriptive_bank"
    if selected!=96 or not 2<=n<=selected:
        raise ValueError("This manuscript expects the frozen96-state selected cohort")
    if incomplete:
        if not allow_incomplete_descriptive:
            raise ValueError("Incomplete tables require explicit descriptive opt-in")
        if n>=selected or bounds is None or not all(math.isfinite(bounds[k]) for k in ("low","high")) or bounds["low"]>bounds["high"]:
            raise ValueError("Missing-state bounds and incomplete coverage must remain explicit")
    elif report["status"]!="complete_confirmatory_bank" or n!=selected or bounds is not None:
        raise ValueError("A censored bank cannot be labelled complete")
    for model in MODELS:
        for arm in ARMS:
            if report["rates"][model][arm]["draws"] != 3*n:
                raise ValueError("Incomplete matched model/context cell")
    primary = report["primary"]
    if primary["tasks"]!=n:
        raise ValueError("Primary task count differs from table coverage")
    if primary != report["policy_comparisons"]["0"]["feedback"]["net_utility_usd"]:
        raise ValueError("Primary comparison does not match the original draw rotation")
    if not all(math.isfinite(primary[k]) for k in ("estimate", "low", "high")):
        raise ValueError("Nonfinite primary statistic")
    out = {}
    rows = [[label, *(f"{100*report['rates'][m][arm]['success']['estimate']:.1f}\\%" for arm in ARMS)]
            for m,label in MODELS.items()]
    out["context-rates.tex"] = tabular("lrrrrr", ["Model", "Fresh", "Code", "Feedback", "Both", "Irrel."], rows)
    rows = []
    for model,label in MODELS.items():
        for key,contrast in CONTRASTS.items():
            pair = report["effects"][model][key]
            rows.append([label,contrast,f"{100*pair['ordinary_95']['estimate']:+.1f}",
                         ci_text(pair["ordinary_95"],100,1), ci_text(pair["simultaneous_99_583"],100,1)])
    for key,contrast in CONTRASTS.items():
        pair = report["model_context_interactions"][key]
        rows.append(["9B -- 27B",contrast,f"{100*pair['ordinary_95']['estimate']:+.1f}",
                     ci_text(pair["ordinary_95"],100,1), ci_text(pair["simultaneous_99_583"],100,1)])
    out["context-effects.tex"] = tabular("llrrr",["Model", "Contrast", "Effect (pp)", "95\\%", "99.583\\%"],rows)
    policies = {"best_static":"Static (source)","feedback":"Feedback","state":"State",
                "state_model_only":"Model only","escalation_diagnostic":"Escalation*"}
    rows = []
    for key,label in policies.items():
        row = report["policy_summary"]["0.01"][key]
        solved = row["success"]*n
        if not math.isclose(solved,round(solved),abs_tol=1e-9):
            raise ValueError("Nonintegral task outcome count")
        rows.append([label,f"{round(solved)}/{n}",f"{1000*row['cost_usd']:.5f}",f"{1000*row['net_utility_usd']:.5f}"])
    out["policy-results.tex"] = tabular("lrrr",["Policy", "Solved", "Cost", "Utility"],rows)
    rows = []
    for key,label in CONTROLS.items():
        ci = report["policy_comparisons"]["0"][key]["net_utility_usd"]
        rows.append([label,f"{1000*ci['estimate']:+.5f}",ci_text(ci,1000,5)])
    out["policy-comparisons.tex"] = tabular("lrr",["Control", "State -- control", "95\\%"],rows)
    out["prediction-results.tex"] = tabular("lrr",["View", "Brier", "Benefit MSE"],
        [[label,f"{report['brier'][key]:.6f}",f"{report['benefit_mse'][key]:.6f}"] for key,label in VIEWS.items()])
    rows = []
    for key,row in report["policy_summary"]["0.01"].items():
        if key.startswith("fixed:"):
            label=key.removeprefix("fixed:").replace("artifact_feedback","both").replace("artifact","code").replace("_",r"\_")
            rows.append([label,f"{100*row['success']:.1f}\\%",f"{1000*row['cost_usd']:.5f}",f"{1000*row['net_utility_usd']:.5f}"])
    out["all-fixed-policies.tex"] = tabular("lrrr",["Fixed action", "Success", "Cost", "Utility"],rows)
    macros = {"MbppN":str(n),"MbppSelectedN":str(selected),"BankStatus":"Descriptive" if incomplete else "Complete",
              "PrimaryEstimate":f"{primary['estimate']:+.8f}",
              "PrimaryLow":f"{primary['low']:+.8f}","PrimaryHigh":f"{primary['high']:+.8f}",
              "PrimaryKnownCost":f"{report['collection']['known_cost_usd']:.8f}",
              "PrimaryCampaignUpper":f"{report['collection']['campaign_upper_usd']:.8f}"}
    if incomplete:
        macros.update(MissingUtilityLow=f"{bounds['low']:+.8f}",MissingUtilityHigh=f"{bounds['high']:+.8f}")
        out["bank-status.tex"]=(r"\noindent\textbf{Incomplete descriptive bank.} "
            +f"{n}/{selected} selected failed tasks have all30 observed recovery cells. "
            +"Complete-case intervals are descriptive. All selected states remain in the worst-case bounds "
            +"for the mean state-minus-feedback utility difference: "
            +f"[\\${bounds['low']:+.8f}, \\${bounds['high']:+.8f}]. "
            +"These are missing-state bounds, not confidence intervals.\n")
    else:
        out["bank-status.tex"]=f"All {selected} selected failed tasks have all30 observed recovery cells.\n"
    out["results-macros.tex"] = "\n".join(r"\newcommand{"+"\\"+k+"}{"+v+"}" for k,v in macros.items())+"\n"
    if "semantic_control" in report:
        s = report["semantic_control"]
        rows = []
        for key,label in (("task_only","Task"),("feedback_only","Feedback"),("state","State")):
            row=s["policy_summary"]["0.01"][key]
            rows.append([label,f"{s['prediction_metrics'][key]['brier']:.6f}",
                         f"{s['prediction_metrics'][key]['benefit_mse']:.6f}",
                         f"{100*row['success']:.1f}\\%",f"{1000*row['cost_usd']:.5f}"])
        out["semantic-results.tex"] = (f"% Matched forecast states: {s['complete_states']}/{s['selected_states']}; "
            "complete-case comparisons descriptive if incomplete.\n"+tabular("lrrrr",["API view", "Brier", "Benefit MSE", "Success", "Cost"],rows))
    prefix = ("% Generated from audited analysis.json; SHA256 "+source_hash+"\n"
              "% Policy table cost and utility units: USD x 1,000 per failed task.\n"
              "% Macros retain USD units. Escalation is an added diagnostic, not a frozen primary.\n")
    for name,body in out.items():
        if r"\begin{tabular}" in body:
            count=report["semantic_control"]["complete_states"] if name=="semantic-results.tex" else n
            status="Descriptive complete cases" if incomplete or count!=selected else "Complete bank"
            out[name]=body+"\\par\\smallskip{\\footnotesize "+f"{status}: {count}/{selected} selected tasks."+"}\n"
    return {name:prefix+body.replace("all30","all 30").replace("frozen96","frozen 96") for name,body in out.items()}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--allow-incomplete-descriptive",action="store_true",
                   help="Require visible descriptive coverage and missing-state bounds, never relabel a censored bank complete.")
    args=p.parse_args()
    raw=args.input.read_bytes()
    outputs=generate(json.loads(raw),hashlib.sha256(raw).hexdigest(),allow_incomplete_descriptive=args.allow_incomplete_descriptive)
    args.output.mkdir(parents=True,exist_ok=True)
    for name,body in outputs.items():(args.output/name).write_text(body)
    print(json.dumps({"tables":len(outputs),"output":str(args.output)}))


if __name__ == "__main__":
    main()
