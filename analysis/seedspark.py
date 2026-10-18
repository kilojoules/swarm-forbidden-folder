"""seed-spark: one agent is pre-opened before round 1 and leaves a single fixed post (visible round 1), then dark.
Measures the cascade among the N-1 at-risk agents given a GUARANTEED, standardized visible breach, vs swarm size N:
  R_eff      = direct recruits (agents that open in round 1, having just seen the one seed post)
  cascade    = total followers that ever open, and as a fraction of the N-1 at-risk
Tests whether contagion dilutes with N (frequency-dependent transmission) when ignition is held fixed.
Usage: python3 analysis/seedspark.py [runs_root]  (default runs/seedspark). Writes analysis/seedspark_results.json."""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from analysis.common import load_runs, first_open_per_agent  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNS = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "runs", "seedspark")


def loglog_slope(xs, ys):
    x = np.log(np.array(xs, float)); y = np.log(np.array(ys, float))
    A = np.vstack([x, np.ones_like(x)]).T
    b, a = np.linalg.lstsq(A, y, rcond=None)[0]
    yhat = A @ [b, a]
    ss = 1 - ((y - yhat) ** 2).sum() / ((y - y.mean()) ** 2).sum() if np.ptp(y) else float("nan")
    return float(b), float(ss)


def main():
    arms = sorted({r["meta"]["arm"] for r in load_runs(RUNS)}, key=lambda a: int(a[1:].split("-")[0]))
    res = {}
    for arm in arms:
        rs = [r for r in load_runs(RUNS, arms=[arm]) if r["finished"]]
        if not rs:
            continue
        N = rs[0]["meta"]["N"]; atrisk = N - 1
        followers = []; gen1 = []; frac = []; anyfollow = 0
        for r in rs:
            seed = r["meta"].get("seed_spark_agent_id")
            fo, _ = first_open_per_agent(r)
            opens = {a: t for a, t in fo.items() if t and a != seed}
            followers.append(len(opens))
            gen1.append(sum(1 for t in opens.values() if t == 1))   # opened the round the seed post was visible
            frac.append(len(opens) / atrisk)
            anyfollow += bool(opens)
        res[N] = dict(sessions=len(rs), atrisk=atrisk,
                      mean_followers=float(np.mean(followers)), mean_gen1_Reff=float(np.mean(gen1)),
                      p_any_follower=anyfollow / len(rs), mean_follower_fraction=float(np.mean(frac)),
                      followers_dist=[int(x) for x in followers])
        print("N=%2d atrisk=%2d n=%d | R_eff(gen1)=%.2f  mean_followers=%.2f  follow_frac=%.3f  P(>=1 follow)=%.2f"
              % (N, atrisk, len(rs), res[N]["mean_gen1_Reff"], res[N]["mean_followers"],
                 res[N]["mean_follower_fraction"], res[N]["p_any_follower"]))
    Ns = sorted(res)
    if len(Ns) >= 2:
        for key, lbl in [("mean_gen1_Reff", "R_eff(gen1)"), ("mean_follower_fraction", "follower fraction"),
                         ("mean_followers", "mean followers")]:
            ys = [res[n][key] for n in Ns]
            if all(y > 0 for y in ys):
                b, ss = loglog_slope(Ns, ys)
                print("  %-18s ~ N^%+.3f (R2=%.3f)" % (lbl, b, ss))
    json.dump({"by_N": {str(n): res[n] for n in Ns}}, open(os.path.join(ROOT, "analysis", "seedspark_results.json"), "w"), indent=1)
    print("wrote analysis/seedspark_results.json")
    print("READ: follower-fraction falling with N => contagion dilutes even with ignition fixed (frequency-dependent);")
    print("      flat => a visible breach recruits a constant SHARE regardless of swarm size.")


if __name__ == "__main__":
    main()
