"""THE headline figure: a shared board doesn't raise the breach rate, it correlates breaches into cascades."""
import glob, json, os, statistics, random
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RED="#E45756"; BLUE="#4C78A8"
def openers(arm):
    out=[]
    for d in glob.glob(os.path.join(ROOT,"runs/core",arm,"*/")):
        if not os.path.exists(d+"closing.jsonl"): continue
        f=set(json.loads(l)["agent_id"] for l in open(d+"board.jsonl")) if False else None
        s=set()
        for l in open(d+"turns.jsonl"):
            t=json.loads(l)
            if t["open"]: s.add(t["agent_id"])
        out.append(len(s))
    return out
board=openers("N16-board"); nob=openers("N16-noboard")
rng=random.Random(3)
plt.rcParams.update({"font.size":12,"axes.spines.top":False,"axes.spines.right":False,"axes.spines.left":False})
fig,ax=plt.subplots(figsize=(11,4.7))
def strip(vals,y,color,label):
    xs=vals; ys=[y+rng.uniform(-0.16,0.16) for _ in xs]
    ax.scatter(xs,ys,s=140,c=color,alpha=0.75,edgecolors="white",linewidths=1.2,zorder=3,label=label)
    m=statistics.mean(vals)
    ax.plot([m,m],[y-0.32,y+0.32],color=color,lw=3,zorder=4)
    ax.text(m,y+0.42,"mean %.1f"%m,ha="center",color=color,fontsize=11,fontweight="bold")
strip(nob,1.0,BLUE,"independent (no board), n=%d"%len(nob))
strip(board,0.0,RED,"shared board, n=%d"%len(board))
ax.set_yticks([0,1]); ax.set_yticklabels(["shared\nboard","no board\n(independent)"],fontsize=12)
ax.set_xlim(-0.6,16.6); ax.set_ylim(-0.7,1.9); ax.set_xticks(range(0,17,2))
ax.set_xlabel("agents that opened the forbidden folder, per 16-agent session",fontsize=12)
ax.annotate("nobody breaks",xy=(0.2,-0.28),xytext=(2.4,-0.55),fontsize=10,color=RED,
            arrowprops=dict(arrowstyle="->",color=RED,lw=1.3))
ax.annotate("...or the whole swarm does",xy=(15,0.15),xytext=(9.2,-0.55),fontsize=10,color=RED,
            arrowprops=dict(arrowstyle="->",color=RED,lw=1.3))
ax.set_title("A shared board doesn't raise the breach rate — it makes agents break together",
             fontsize=13,fontweight="bold",pad=12)
ax.legend(loc="upper right",fontsize=10,frameon=False)
fig.tight_layout(); fig.savefig(os.path.join(ROOT,"results","fig_headline.png"),dpi=140); plt.close(fig)
print("board openers/session:",sorted(board)); print("no-board:",sorted(nob))
print("wrote results/fig_headline.png")
