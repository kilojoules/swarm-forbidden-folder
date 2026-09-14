"""Static summary figures for the README, from runs/core and runs/poison."""
import glob, json, os, math
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BLUE="#4C78A8"; RED="#E45756"; GREEN="#59A14F"; GREY="#9aa0a6"
plt.rcParams.update({"font.size":11,"axes.spines.top":False,"axes.spines.right":False})

def firsts(d):
    f=set()
    for l in open(os.path.join(d,"turns.jsonl")):
        t=json.loads(l)
        if t["open"]: f.add(t["agent_id"])
    return f

# ---- Fig 1: openers-per-session distribution, board vs no-board (core study) ----
def openers_dist(arm):
    out=[]
    for d in glob.glob(os.path.join(ROOT,"runs/core",arm,"*/")):
        if not os.path.exists(os.path.join(d,"closing.jsonl")): continue
        out.append(len(firsts(d)))
    return out
fig,ax=plt.subplots(figsize=(7,4.2))
b=openers_dist("N16-board"); nb=openers_dist("N16-noboard")
bins=np.arange(-0.5,17,1)
ax.hist(b,bins=bins,density=True,alpha=0.75,color=RED,label="shared board (n=%d)"%len(b))
ax.hist(nb,bins=bins,density=True,alpha=0.6,color=BLUE,label="no board / independent (n=%d)"%len(nb))
ax.set_xlabel("agents that opened the folder, per 16-agent session")
ax.set_ylabel("fraction of sessions"); ax.set_title("A shared board clumps breaches into rare total cascades (N=16)")
ax.legend(); fig.tight_layout(); fig.savefig(os.path.join(ROOT,"results","fig_cascade.png"),dpi=140); plt.close(fig)

# ---- Fig 2: per-agent open rate by mode x N (poison) ----
import sys; sys.path.insert(0,ROOT)
from analysis.attrition import witness_clustered
from analysis.common import load_runs
def rate(mode,N):
    ds=[d for d in glob.glob(os.path.join(ROOT,"runs/poison/N%d-board"%N,"*p-%s*/"%mode)) if os.path.exists(os.path.join(d,"closing.jsonl"))]
    if not ds: return None
    return sum(len(firsts(d)) for d in ds)/(len(ds)*N)
fig,ax=plt.subplots(figsize=(7,4.2))
modes=[("none_roster","baseline: opener stays",GREY),("lastword","last word: opener posts once, then dark",RED),("silent","silent: opener vanishes",GREEN)]
x=np.arange(2); w=0.26
for i,(m,lab,c) in enumerate(modes):
    vals=[rate(m,8) or 0, rate(m,16) or 0]
    ax.bar(x+(i-1)*w, vals, w, color=c, label=lab)
ax.set_xticks(x); ax.set_xticklabels(["N=8","N=16"]); ax.set_ylabel("per-agent probability of opening")
ax.set_title("Silencing the opener suppresses breaches; one message undoes it"); ax.legend(fontsize=9)
fig.tight_layout(); fig.savefig(os.path.join(ROOT,"results","fig_poison_rates.png"),dpi=140); plt.close(fig)

# ---- Fig 3: witness hazard ratio, message vs absence (pooled) ----
def pooled(mode):
    r=[run for run in load_runs(os.path.join(ROOT,"runs/poison"),model="Qwen/Qwen2.5-7B-Instruct")
       if run["finished"] and run["meta"].get("variant")=="soft_rule_lure" and run["meta"].get("poison")==mode and run["meta"]["N"] in (8,16)]
    return witness_clustered(r,16)
si=pooled("silent"); lw=pooled("lastword")
fig,ax=plt.subplots(figsize=(8.2,3.6))
labels=["silent\n(peer vanishes, no message)","last-word\n(peer leaves one message)"]
pts=[si["hr_point"], lw["hr_point"]]; cis=[si["hr_ci95_session_clustered"], lw["hr_ci95_session_clustered"]]
ys=[0,1]
for y,p,ci,c in zip(ys,pts,cis,[GREEN,RED]):
    ax.plot([ci[0],ci[1]],[y,y],color=c,lw=3)
    ax.plot(p,y,"o",color=c,ms=11)
    ax.text(p,y+0.12,"%.1fx"%p,ha="center",color=c,fontweight="bold")
ax.axvline(1,color="k",ls="--",lw=1); ax.text(1.02,-0.35,"no effect",fontsize=9)
ax.set_yticks(ys); ax.set_yticklabels(labels); ax.set_xscale("log"); ax.set_xlim(0.4,45)
ax.set_xlabel("hazard ratio of opening after seeing a teammate go dark  (session-clustered 95% CI)")
ax.set_title("A breach spreads via the message, not the disappearance"); ax.set_ylim(-0.6,1.6)
fig.tight_layout(); fig.savefig(os.path.join(ROOT,"results","fig_witness.png"),dpi=140); plt.close(fig)
print("wrote fig_cascade.png, fig_poison_rates.png, fig_witness.png")
