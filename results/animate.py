"""Animation: how a breach spreads through a 16-agent swarm on a shared board.
Left = last-word poison (opener leaves one message, then goes dark): the message recruits the swarm.
Right = silent poison (opener vanishes wordlessly): nothing spreads.
Built from real session transcripts in runs/poison. Output: results/contagion.gif"""
import glob, json, os, math
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, PillowWriter
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def load(session_glob):
    d = sorted(glob.glob(os.path.join(ROOT, session_glob)))[0]
    meta = json.load(open(os.path.join(d, "meta.json")))
    ids = meta["agent_ids"]; N = meta["N"]; T = meta["T_MAX"]
    opened = {}
    for l in open(os.path.join(d, "turns.jsonl")):
        t = json.loads(l)
        if t["open"] and t["agent_id"] not in opened:
            opened[t["agent_id"]] = t["round"]
    return ids, N, T, opened

LW_IDS, N, T, LW_OPEN = load("runs/poison/N16-board/*p-lastword*005*/")
SI_IDS, _, _, SI_OPEN = load("runs/poison/N16-board/*p-silent*006*/")

# 4x4 grid positions
def grid_pos(n):
    side = int(math.ceil(math.sqrt(n)))
    return [ (i % side, side - 1 - i // side) for i in range(n) ]
POS = grid_pos(N)

WORKING = "#4C78A8"   # blue
OPENING = "#E45756"   # red flash the round it opens
DARK    = "#C9CCD1"   # faded: gone dark (after opening)
plt.rcParams.update({"font.size": 11})

FPR = 3   # frames per round (for smooth flashes)
frames = T * FPR

fig, (axL, axR) = plt.subplots(1, 2, figsize=(11, 6.2))
fig.patch.set_facecolor("white")

def draw(ax, ids, opened, title, r, sub):
    ax.clear(); ax.set_xlim(-0.7, 3.7); ax.set_ylim(-0.9, 3.9); ax.axis("off")
    ax.set_title(title, fontsize=13, fontweight="bold", pad=8)
    n_open = sum(1 for a in ids if opened.get(a) and opened[a] <= r)
    # draw recruiting pulse: if any agent opened THIS round, lines from it to still-working agents
    just = [a for a in ids if opened.get(a) == r]
    if just and "last-word" in title:
        for jo in just:
            x0, y0 = POS[ids.index(jo)]
            for a in ids:
                if not (opened.get(a) and opened[a] <= r):
                    x1, y1 = POS[ids.index(a)]
                    ax.plot([x0, x1], [y0, y1], color=OPENING, alpha=0.18, lw=1, zorder=1)
    for i, a in enumerate(ids):
        x, y = POS[i]; o = opened.get(a)
        if o is None or o > r:
            c, ec, s = WORKING, "none", 620
        elif o == r:
            c, ec, s = OPENING, "black", 900       # flash on the opening round
        else:
            c, ec, s = DARK, "none", 500            # gone dark
        ax.scatter([x], [y], s=s, c=c, edgecolors=ec, linewidths=1.5, zorder=3)
        if o is not None and o < r:
            ax.text(x, y, "x", ha="center", va="center", color="#8a8f98", fontsize=13, zorder=4)
    ax.text(1.5, -0.75, sub.format(n=n_open, s=N - n_open), ha="center", fontsize=11, color="#333")

def update(f):
    r = f // FPR + 1
    draw(axL, LW_IDS, LW_OPEN, "last-word: opener leaves one message",  r, "opened: {n}/16    still working: {s}")
    draw(axR, SI_IDS, SI_OPEN, "silent: opener vanishes wordlessly", r, "opened: {n}/16    still working: {s}")
    fig.suptitle("Round {:2d}/30  —  a forbidden-folder breach spreading through a 16-agent swarm".format(r),
                 fontsize=13.5, y=0.98)
    return []

from matplotlib.lines import Line2D
_handles=[Line2D([0],[0],marker='o',color='w',markerfacecolor=WORKING,markersize=12,label='working'),
          Line2D([0],[0],marker='o',color='w',markerfacecolor=OPENING,markeredgecolor='black',markersize=13,label='opens folder this round'),
          Line2D([0],[0],marker='o',color='w',markerfacecolor=DARK,markersize=11,label='gone dark (opened, removed)')]
fig.legend(handles=_handles, loc='lower center', ncol=3, frameon=False, fontsize=10)
fig.subplots_adjust(bottom=0.12, top=0.86)
anim = FuncAnimation(fig, update, frames=frames, interval=1000/6, blit=False)
out = os.path.join(ROOT, "results", "contagion.gif")
anim.save(out, writer=PillowWriter(fps=6))
print("wrote", out, os.path.getsize(out)//1024, "KB")
