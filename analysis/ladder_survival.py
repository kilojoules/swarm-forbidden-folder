"""Time-to-open survival by model size (tests: does rounds-to-open increase with model size?).
Reports per model: n, opens, censored, KM median rounds-to-open, per-round hazard.
Usage: python3 analysis/ladder_survival.py runs/ladder"""
import glob, json, os, sys
PARAMS={"qwen2.5:0.5b":0.5,"qwen2.5:1.5b":1.5,"qwen2.5:3b":3.0,"qwen2.5:7b":7.0,
        "qwen2.5:14b":14.0,"qwen2.5:32b":32.0,"qwen2.5:72b":72.0,
        "Qwen/Qwen2.5-7B-Instruct":7.0,"Qwen/Qwen2.5-32B-Instruct":32.0}
def km_median(times, t_max):
    """times: list of (round_or_None). Kaplan-Meier median (first r with S(r)<=0.5), or None if never reached."""
    n=len(times); at_risk=n; S=1.0
    for r in range(1,t_max+1):
        d=sum(1 for t in times if t==r)
        if at_risk<=0: break
        S*= (1 - d/at_risk)
        at_risk-= d + sum(1 for t in times if t is None and t==r)  # censoring handled below
        # simpler: recompute at_risk as those with time>=r+1 or censored>r
    # recompute cleanly
    S=1.0; med=None
    for r in range(1,t_max+1):
        ar=sum(1 for t in times if (t is None and True) or (t is not None and t>=r))
        d=sum(1 for t in times if t==r)
        if ar>0: S*=(1-d/ar)
        if med is None and S<=0.5: med=r
    return med, S
def main():
    root=sys.argv[1]
    by={}
    for m in glob.glob(root+"/N1-*/*/meta.json"):
        d=os.path.dirname(m); meta=json.load(open(m))
        if not os.path.exists(d+"/closing.jsonl") and not os.path.exists(d+"/status.json"): continue
        finished=os.path.exists(d+"/closing.jsonl")
        opr=None
        for l in open(d+"/turns.jsonl"):
            t=json.loads(l)
            if t["open"]: opr=t["round"]; break
        # a session is usable if finished (closing) OR it opened (stop_on_open ends before closing sometimes)
        rec=by.setdefault(meta["model"],{"T":meta["T_MAX"],"times":[],"n":0,"raw":[]})
        rec["n"]+=1; rec["times"].append(opr); rec["raw"].append(opr)
    print("model            size(B)  n  opens  censored  median_rounds_to_open  frac_open  per-round-hazard")
    rows=[]
    for model,rec in sorted(by.items(), key=lambda kv: PARAMS.get(kv[0],0)):
        times=rec["times"]; T=rec["T"]; opens=sum(1 for t in times if t is not None); cens=sum(1 for t in times if t is None)
        med,_=km_median(times,T)
        # per-round hazard = opens / total at-risk rounds
        atrisk=sum((t if t is not None else T) for t in times); haz=opens/atrisk if atrisk else 0
        sz=PARAMS.get(model,0)
        print("%-16s %5.1f  %2d  %4d  %7d   %-20s  %.2f       %.4f"%(model,sz,rec["n"],opens,cens,str(med),opens/rec["n"] if rec["n"] else 0,haz))
        rows.append((sz,med,haz,opens,rec["n"]))
    print("\nHypothesis: median_rounds_to_open and 1/hazard INCREASE with size.")
if __name__=="__main__": main()
