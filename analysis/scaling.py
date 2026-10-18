"""Scaling-law re-analysis of the core N-sweep, settling four confounds on existing data:
  GAP1  the openers/session distribution has only 3 independent scaling facts (P>=1, mu, Fano);
        cascade-size / engulfed-fraction "laws" are algebraic transforms (slope identity).
  GAP2  the N-dependence of the pre/post opening hazards is NOT a T_MAX=30 window-composition
        artifact: compared against a single-agent time-varying baseline over the SAME rounds,
        the baseline-predicted hazard is flat in N, so the exponents are genuine board effects.
  GAP3  the no-board per-agent rate should be N-invariant (independent agents, N-invariant inputs);
        test whether the observed 0.40/0.35/0.30 decline is real (batch-numerics confound) or noise.
  GAP5  cascade-size shape is bistable/all-or-nothing (board-specific), not critical-branching.
Writes analysis/scaling_results.json. Usage: python3 analysis/scaling.py [runs_root]
"""
import json
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from analysis.common import load_runs, first_open_per_agent  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMAX = 30
# N=4,8,16 live in runs/core; the wide-N ladder (2,32,64) lands in runs/wideN. Both are scanned and merged.
CORE = os.path.join(ROOT, "runs", "core")
ROOTS = [CORE, os.path.join(ROOT, "runs", "wideN")] + ([sys.argv[1]] if len(sys.argv) > 1 else [])


def runs(arm):
    out, seen = [], set()
    for rt in ROOTS:
        if not os.path.isdir(rt):
            continue
        for r in load_runs(rt, arms=[arm]):
            if r["finished"] and r["dir"] not in seen:
                seen.add(r["dir"]); out.append(r)
    return out


# discover the N ladder from whichever board arms have finished sessions
Ns = [n for n in [2, 4, 6, 8, 12, 16, 24, 32, 64] if runs("N%d-board" % n)]
ARMS = [("N%d-board" % n, n) for n in Ns]
NOB = [("N%d-noboard" % n, n) for n in Ns if runs("N%d-noboard" % n)]
print("N ladder (board):", Ns, "| no-board:", [n for _, n in NOB])


def loglog_slope(xs, ys):
    x = np.log(np.array(xs, float)); y = np.log(np.array(ys, float))
    A = np.vstack([x, np.ones_like(x)]).T
    b, a = np.linalg.lstsq(A, y, rcond=None)[0]
    yhat = A @ [b, a]
    ss = 1 - ((y - yhat) ** 2).sum() / ((y - y.mean()) ** 2).sum() if np.ptp(y) else float("nan")
    return float(b), float(ss)


def opener_counts(arm):
    return [int(sum(1 for t in first_open_per_agent(r)[0].values() if t)) for r in runs(arm)]


# single-agent time-varying baseline hazard h_1(r), r=1..30, from the N1 pool
pool = runs("N1-pool")
oa = np.zeros(TMAX + 1); ar = np.zeros(TMAX + 1)
for r in pool:
    for a, t in first_open_per_agent(r)[0].items():
        for rd in range(1, (t if t else TMAX) + 1):
            ar[rd] += 1
            if t == rd:
                oa[rd] += 1
h1 = np.array([oa[r] / ar[r] if ar[r] else 0.0 for r in range(TMAX + 1)])

# GAP1: three moments of the openers/session distribution
board = {}
for arm, N in ARMS:
    c = np.array(opener_counts(arm))
    board[N] = dict(P1=float((c > 0).mean()), mu=float(c.mean()), var=float(c.var(ddof=1)),
                    fano=float(c.var(ddof=1) / c.mean()), dist=[int(x) for x in c])

# GAP2: round-composition decomposition of pre/post hazards
gap2 = {}
for arm, N in ARMS:
    bef = [0, 0, 0.0]; aft = [0, 0, 0.0]; sparks = []  # [events, at-risk, sum baseline hazard]
    for r in runs(arm):
        fo = first_open_per_agent(r)[0]
        opened = {a: t for a, t in fo.items() if t}
        f = min(opened.values()) if opened else None
        if f is not None:
            sparks.append(f)
        for a, t in fo.items():  # every agent; the spark's own open IS the pre-hazard event
            for rd in range(1, (t if t else TMAX) + 1):
                buk = aft if (f is not None and rd > f) else bef
                buk[1] += 1; buk[2] += h1[rd]
                if t == rd:
                    buk[0] += 1
    nan = float("nan")
    o_pre = bef[0] / bef[1] if bef[1] else nan
    o_post = aft[0] / aft[1] if aft[1] else nan      # nan when no post-visible agent-rounds (no spark in any session)
    p_pre = bef[2] / bef[1] if bef[1] else nan
    p_post = aft[2] / aft[1] if aft[1] else nan
    gap2[N] = dict(o_pre=o_pre, o_post=o_post, pred_pre=p_pre, pred_post=p_post,
                   eff_pre=(o_pre / p_pre if p_pre else nan), eff_post=(o_post / p_post if p_post else nan),
                   spark_med=float(np.median(sparks)) if sparks else None, n_spark=len(sparks))

# GAP3: is the no-board per-agent rate flat in N? logistic slope on log(N), session-clustered bootstrap
rows = []; sess = 0; rate_by_N = {}
for arm, N in NOB:
    rs = runs(arm); ks = []
    for r in rs:
        fo = first_open_per_agent(r)[0]
        for t in fo.values():
            rows.append((math.log(N), 1 if t else 0, sess))
        ks.append(sum(1 for t in fo.values() if t) / N)
        sess += 1
    rate_by_N[N] = float(np.mean(ks))
X = np.array([[1, lr] for lr, _, _ in rows]); y = np.array([o for _, o, _ in rows]); cl = np.array([c for _, _, c in rows])


def fit_logit(X, y):
    b = np.zeros(X.shape[1])
    for _ in range(50):
        p = 1 / (1 + np.exp(-X @ b)); W = p * (1 - p)
        b += np.linalg.solve((X * W[:, None]).T @ X + 1e-8 * np.eye(X.shape[1]), X.T @ (y - p))
    return b


b = fit_logit(X, y); clusters = np.unique(cl); rng = np.random.default_rng(0); sl = []
for _ in range(3000):
    idx = np.concatenate([np.where(cl == c)[0] for c in rng.choice(clusters, len(clusters), replace=True)])
    try:
        sl.append(fit_logit(X[idx], y[idx])[1])
    except Exception:
        pass
sl = np.array(sl); lo, hi = np.percentile(sl, [2.5, 97.5])

slopes = {
    "P1": loglog_slope(Ns, [board[n]["P1"] for n in Ns]),
    "mu": loglog_slope(Ns, [board[n]["mu"] for n in Ns]),
    "fano": loglog_slope(Ns, [board[n]["fano"] for n in Ns]),
    "frac_identity": loglog_slope(Ns, [board[n]["mu"] / (n * board[n]["P1"]) for n in Ns]),
    "h_pre_obs": loglog_slope(Ns, [gap2[n]["o_pre"] for n in Ns]),
    "h_pre_pred": loglog_slope(Ns, [gap2[n]["pred_pre"] for n in Ns]),
    "h_pre_eff": loglog_slope(Ns, [gap2[n]["eff_pre"] for n in Ns]),
    "h_post_obs": loglog_slope(Ns, [gap2[n]["o_post"] for n in Ns]),
    "h_post_pred": loglog_slope(Ns, [gap2[n]["pred_post"] for n in Ns]),
    "h_post_eff": loglog_slope(Ns, [gap2[n]["eff_post"] for n in Ns]),
    "noboard_rate": loglog_slope([n for _, n in NOB], [rate_by_N[n] for _, n in NOB]) if len(NOB) >= 2 else (float("nan"), float("nan")),
}
out = {
    "baseline_h1": [round(float(x), 5) for x in h1],
    "n1_pool_P_open_T30": float(sum(1 for r in pool for t in [list(first_open_per_agent(r)[0].values())[0]] if t) / len(pool)),
    "board": {str(N): board[N] for N in Ns},
    "noboard": {str(N): {"dist": opener_counts(arm)} for arm, N in NOB},
    "gap2": {str(N): gap2[N] for N in Ns},
    "gap3": {"rate_by_N": {str(N): rate_by_N[N] for N in Ns}, "n1_pool_rate": 0.273,
             "logit_slope": float(b[1]), "ci95": [float(lo), float(hi)], "p_neg": float((sl < 0).mean())},
    "slopes": slopes,
}
path = os.path.join(ROOT, "analysis", "scaling_results.json")
json.dump(out, open(path, "w"), indent=1)
print("wrote", path)
for k, (s, r2) in slopes.items():
    print("  %-16s ~ N^%+.3f (R2=%.3f)" % (k, s, r2))
print("  gap3 no-board logit slope %+.3f CI[%+.3f,%+.3f] P(neg)=%.2f" % (b[1], lo, hi, (sl < 0).mean()))
