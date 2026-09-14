"""Inverted-U: rule-breaking peaks at middle capability. Too small = loops (never tempted);
mid = breaks the rule; larger = aware and declines. (Single agent, soft-rule-lure prompt.)"""
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import os
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RED="#E45756"; GREY="#9aa0a6"; BLUE="#4C78A8"
# (size B, P(open), n, condition, label)
pts=[(0.5,0.0,10,"loops forever,\nnever gets tempted"),
     (7.0,0.40,30,"gets stuck,\nthen opens the folder"),
     (14.0,0.0,30,"aware of it,\nkeeps declining"),
     (32.0,0.0,20,"declines")]
plt.rcParams.update({"font.size":12,"axes.spines.top":False,"axes.spines.right":False})
fig,ax=plt.subplots(figsize=(9.5,5))
xs=[p[0] for p in pts]; ys=[p[1] for p in pts]
ax.plot(xs,ys,"-",color=GREY,lw=1.5,zorder=1,alpha=0.6)
for x,y,n,lab in pts:
    c=RED if y>0.1 else BLUE
    ax.scatter([x],[y],s=260,c=c,edgecolors="white",linewidths=1.5,zorder=3)
    ax.annotate(lab,xy=(x,y),xytext=(x,y+0.055),ha="center",fontsize=10,color="#333")
    ax.text(x,-0.045,"n=%d"%n,ha="center",fontsize=9,color="#888")
ax.set_xscale("log"); ax.set_xticks([0.5,1.5,3,7,14,32]); ax.set_xticklabels(["0.5B","1.5B","3B","7B","14B","32B"])
ax.set_xlabel("model size (Qwen2.5, log scale)",fontsize=12)
ax.set_ylabel("P(opens the forbidden folder)",fontsize=12); ax.set_ylim(-0.08,0.52); ax.set_xlim(0.35,45)
ax.axvspan(0.35,3.5,color=BLUE,alpha=0.05); ax.axvspan(3.5,10,color=RED,alpha=0.06); ax.axvspan(10,45,color=BLUE,alpha=0.05)
ax.text(1.2,0.47,"too incompetent\nto get tempted",ha="center",fontsize=10,color=BLUE,style="italic")
ax.text(7,0.47,"susceptible",ha="center",fontsize=10,color=RED,style="italic",fontweight="bold")
ax.text(19,0.47,"capable enough\nto refuse",ha="center",fontsize=10,color=BLUE,style="italic")
ax.set_title("Rule-breaking peaks at middle capability, not at the top",fontsize=13.5,fontweight="bold",pad=10)
fig.tight_layout(); fig.savefig(os.path.join(ROOT,"results","fig_capability.png"),dpi=140); plt.close(fig)
print("wrote fig_capability.png")
