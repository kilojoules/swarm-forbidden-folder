"""First-open cumulative incidence vs the independence null.
Pool = individual agents from --pool-arms (their first open of any class, or deliberate only with --deliberate).
For each --compare arm: session-level first-open curve vs (a) closed-form null 1-(1-F1)^N, (b) a PREDICTIVE band for an
arm of that many sessions (two-level bootstrap: resample the pool, then draw M sessions each = min of N draws), and
(c) an agent-level log-rank test against the pool (tests whether being one of N changes per-agent hazard).
Usage: python3 analysis/km.py runs/core --pool-arms N1-pool --compare N4-noboard N4-board --N 4 [--deliberate] [--out km_N4.png]"""
import argparse
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from analysis.common import load_runs as load_runs_all, load_labels, first_open_per_agent, cdf, logrank, unlabeled_first_opens  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--pool-arms", nargs="+", default=["N1-pool"])
    ap.add_argument("--compare", nargs="*", default=[])
    ap.add_argument("--N", type=int, required=True)
    ap.add_argument("--deliberate", action="store_true")
    ap.add_argument("--B", type=int, default=2000)
    ap.add_argument("--out", default=None)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--variant", default=None, help="only sessions of this prompt variant")
    ap.add_argument("--labels-file", default=None, help="labels file name in root (default labels.csv; env SWARM_LABELS)")
    args = ap.parse_args()
    def runs_of(root, arms=None, model=None):   # variant-filtered loader
        for run in load_runs_all(root, arms=arms, model=model):
            if args.variant is None or run["meta"].get("variant", "base") == args.variant:
                yield run
    labels = load_labels(args.root, args.labels_file)
    rng = np.random.default_rng(args.seed)

    pool, t_max = [], None
    for run in runs_of(args.root, arms=args.pool_arms):
        if run["finished"]:
            fo, t_max = first_open_per_agent(run, labels, deliberate_only=args.deliberate)
            pool.extend(fo.values())
    if not pool:
        print("empty pool"); sys.exit(2)
    if args.deliberate:
        unlab = [x for run in runs_of(args.root, arms=args.pool_arms + list(args.compare)) if run["finished"] for x in unlabeled_first_opens(run, labels)]
        if unlab:
            sys.exit("--deliberate: {} unlabeled first-open events in {}; label them first (analysis/events.py)".format(len(unlab), args.pool_arms + list(args.compare)))
    n_pool = len(pool)
    F1 = np.array(cdf(pool, t_max))
    closed = 1 - (1 - F1) ** args.N
    pool_arr = np.array([t if t is not None else t_max + 1 for t in pool])

    report = {"pool_arms": args.pool_arms, "pool_agents": n_pool, "deliberate_only": args.deliberate, "N": args.N,
              "F1_at_Tmax": round(float(F1[t_max]), 3), "null_P_open_by_Tmax": round(float(closed[t_max]), 3), "arms": {}}
    curves = {}
    for arm in args.compare:
        sess, agents = [], []
        for run in runs_of(args.root, arms=[arm]):
            if not run["finished"]:
                continue
            fo, _ = first_open_per_agent(run, labels, deliberate_only=args.deliberate)
            agents.extend(fo.values())
            opened = [v for v in fo.values() if v]
            sess.append(min(opened) if opened else None)
        if not sess:
            continue
        M = len(sess)
        F = np.array(cdf(sess, t_max))
        boots = np.zeros((args.B, t_max + 1))
        for b in range(args.B):
            pb = rng.choice(pool_arr, size=n_pool, replace=True)
            mins = rng.choice(pb, size=(M, args.N), replace=True).min(axis=1)
            boots[b] = [np.mean(mins <= r) for r in range(t_max + 1)]
        lo, hi = np.quantile(boots, 0.025, axis=0), np.quantile(boots, 0.975, axis=0)
        chi2, p, O, E = logrank(agents, pool, t_max)
        inside = float(np.mean([(lo[r] <= F[r] <= hi[r]) for r in range(1, t_max + 1)]))
        curves[arm] = (F, lo, hi, M)
        report["arms"][arm] = {
            "sessions": M, "agents": len(agents),
            "P_open_by_Tmax": round(float(F[t_max]), 3), "band95_at_Tmax": [round(float(lo[t_max]), 3), round(float(hi[t_max]), 3)],
            "frac_rounds_inside_95_band": round(inside, 3),
            "logrank_agents_vs_pool": {"chi2": round(chi2, 3), "p": round(p, 4), "observed_events": O, "expected_under_null": round(E, 2),
                                       "direction": ("more/earlier opens than solo" if O > E else "fewer/later opens than solo")},
            "table": {str(r): {"observed": round(float(F[r]), 3), "null": round(float(closed[r]), 3),
                               "band95": [round(float(lo[r]), 3), round(float(hi[r]), 3)]} for r in (5, 10, 20, t_max) if r <= t_max},
        }
    print(json.dumps(report, indent=1))

    if args.out:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        r = np.arange(t_max + 1)
        fig, ax = plt.subplots(figsize=(7.5, 4.8))
        ax.plot(r, F1, color="#777", lw=1, label="solo F1(r), {} agents".format(n_pool))
        ax.plot(r, closed, "k--", label="independence null 1-(1-F1)^{}".format(args.N))
        for arm, (F, lo, hi, M) in curves.items():
            line, = ax.step(r, F, where="post", lw=2, label="{} ({} sessions)".format(arm, M))
            ax.fill_between(r, lo, hi, color=line.get_color(), alpha=0.12, label="95% predictive band for {} sessions".format(M))
        ax.set_xlabel("round"); ax.set_ylabel("P(first open by round)"); ax.set_ylim(0, 1); ax.set_xlim(0, t_max)
        ax.legend(fontsize=7); ax.set_title("Session first-open incidence vs independence null, N={}{}".format(args.N, " (deliberate)" if args.deliberate else ""))
        fig.tight_layout(); fig.savefig(args.out, dpi=130)
        sys.stderr.write("wrote {}\n".format(args.out))


if __name__ == "__main__":
    main()
