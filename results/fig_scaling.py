"""Scaling-law figure from analysis/scaling_results.json (run analysis/scaling.py first).
Three panels: (1) the openers/session distribution's 3 independent scaling facts;
(2) the composition-free board-effect multiplier on the opening hazard (GAP2 result);
(3) the bistable, all-or-nothing cascade shape and its shrinking engulfed fraction."""
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = json.load(open(os.path.join(ROOT, "analysis", "scaling_results.json")))
BLUE = "#4C78A8"; RED = "#E45756"; GREEN = "#59A14F"; GREY = "#9aa0a6"; ORANGE = "#F58518"
Ns = [4, 8, 16]
fig, ax = plt.subplots(1, 3, figsize=(15, 4.6))


def fit_line(a, xs, ys, color, ls="-"):
    lx, ly = np.log(xs), np.log(ys)
    b, c = np.polyfit(lx, ly, 1)
    xx = np.array([min(xs) * 0.9, max(xs) * 1.1])
    a.plot(xx, np.exp(c) * xx ** b, color=color, ls=ls, lw=1.2, alpha=0.7, zorder=1)
    return b


# ---- Panel 1: the three independent scaling facts ----
a = ax[0]
P1 = [D["board"][str(n)]["P1"] for n in Ns]
mu = [D["board"][str(n)]["mu"] for n in Ns]
fano = [D["board"][str(n)]["fano"] for n in Ns]
nb_fano = []
for n in Ns:
    d = np.array(D["noboard"][str(n)]["dist"]); nb_fano.append(d.var(ddof=1) / d.mean())
for ys, color, lab in [(fano, RED, "Fano = var/mean"), (mu, BLUE, "mean openers μ"), (P1, GREEN, "P(≥1 open)")]:
    b = fit_line(a, Ns, ys, color)
    a.plot(Ns, ys, "o", color=color, ms=8, label="%s  ~ N$^{%+.2f}$" % (lab, b), zorder=3)
a.plot(Ns, nb_fano, "s", color=GREY, ms=7, mfc="white", zorder=2, label="no-board Fano ≈ 1 (independent)")
a.plot(Ns, nb_fano, color=GREY, lw=1, alpha=0.6)
a.set_xscale("log", base=2); a.set_yscale("log"); a.set_xticks(Ns); a.set_xticklabels(Ns)
a.set_xlabel("swarm size N"); a.set_ylabel("value (log)")
a.set_title("1. The breach distribution has three knobs\nignition flat, mean & overdispersion rise", fontsize=10.5)
a.legend(fontsize=8.2, loc="lower right"); a.grid(alpha=0.25, which="both")

# ---- Panel 2: composition-free board-effect multiplier on the opening hazard (GAP2) ----
a = ax[1]
eff_pre = [D["gap2"][str(n)]["eff_pre"] for n in Ns]
eff_post = [D["gap2"][str(n)]["eff_post"] for n in Ns]
a.axhline(1.0, color="black", lw=1, ls=":", zorder=1)
a.annotate("independent-agent baseline (1×)", (4, 1.0), xytext=(4, 1.35), fontsize=8.5, color="black")
b2 = fit_line(a, Ns, eff_post, RED)
a.plot(Ns, eff_post, "o-", color=RED, ms=8, lw=1.4, label="after a peer opens (contagion)  ~ N$^{%+.2f}$" % b2, zorder=3)
b1 = fit_line(a, Ns, eff_pre, BLUE)
a.plot(Ns, eff_pre, "o-", color=BLUE, ms=8, lw=1.4, label="before any peer opens (spark)  ~ N$^{%+.2f}$" % b1, zorder=3)
for n, v in zip(Ns, eff_post):
    a.annotate("%.1f×" % v, (n, v), xytext=(0, 7), textcoords="offset points", ha="center", fontsize=8, color=RED)
for n, v in zip(Ns, eff_pre):
    a.annotate("%.2f×" % v, (n, v), xytext=(0, -12), textcoords="offset points", ha="center", fontsize=8, color=BLUE)
a.set_xscale("log", base=2); a.set_yscale("log"); a.set_xticks(Ns); a.set_xticklabels(Ns)
a.set_xlabel("swarm size N"); a.set_ylabel("opening hazard ÷ independent baseline\n(same rounds)")
a.set_title("2. The board's grip is real, not a horizon artifact\nand it weakens toward independence as N grows", fontsize=10.5)
a.legend(fontsize=8.3, loc="center right"); a.grid(alpha=0.25, which="both")

# ---- Panel 3: bistable cascades; near-total share collapses as N grows ----
a = ax[2]
single = []; partial = []; total = []  # shares of igniting sessions
for n in Ns:
    d = np.array(D["board"][str(n)]["dist"], float)
    ig = d[d > 0]; k = len(ig)
    single.append((ig == 1).sum() / k)
    total.append((ig >= 0.75 * n).sum() / k)
    partial.append(1 - single[-1] - total[-1])
x = np.arange(3)
a.bar(x, single, color=GREY, label="singleton (1 agent)")
a.bar(x, partial, bottom=single, color=BLUE, label="partial (2 .. ¾N)")
a.bar(x, total, bottom=np.array(single) + np.array(partial), color=RED, label="near-total (≥¾N)")
for i, (s, t) in enumerate(zip(single, total)):
    a.annotate("%.0f%%" % (t * 100), (i, 1 - t / 2), ha="center", va="center", color="white", fontsize=9, fontweight="bold")
a.set_xticks(x); a.set_xticklabels(["N=4\n(%d ignite)" % (np.array(D["board"]["4"]["dist"]) > 0).sum(),
                                    "N=8\n(%d)" % (np.array(D["board"]["8"]["dist"]) > 0).sum(),
                                    "N=16\n(%d)" % (np.array(D["board"]["16"]["dist"]) > 0).sum()])
a.set_ylabel("share of igniting sessions")
a.set_ylim(0, 1)
a.set_title("3. Ignition is all-or-nothing at small N\nnear-total share collapses 71→21% as N grows", fontsize=10.5)
a.legend(fontsize=8.3, loc="lower right", framealpha=0.95)

plt.tight_layout()
out = os.path.join(ROOT, "results", "fig_scaling.png")
plt.savefig(out, dpi=130, bbox_inches="tight")
print("wrote", out)
