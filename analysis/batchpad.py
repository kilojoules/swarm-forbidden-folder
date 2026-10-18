"""GAP3 control: is the no-board per-agent open rate an artifact of vLLM batch composition?
Runs the SAME single-agent sessions (identical seeds/canary) at 1-wide (lo) vs 64-wide (hi) batches;
the only difference is how many sequences are co-batched. A significant open-rate shift implicates
decode numerics in the no-board N-trend (0.40/0.35/0.30). Usage: python3 analysis/batchpad.py"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from analysis.common import load_runs, first_open_per_agent  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def wilson(k, n, z=1.96):
    if not n:
        return (float("nan"), float("nan"))
    p = k / n; d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (round(c - h, 3), round(c + h, 3))


def opens_by_runid(root):
    out = {}
    for r in load_runs(root, arms=["N1-pool"]):
        if not r["finished"]:
            continue
        fo, _ = first_open_per_agent(r)
        t = list(fo.values())[0]  # N=1
        out[r["meta"]["run_id"]] = t  # round or None
    return out


def main():
    lo = opens_by_runid(os.path.join(ROOT, "runs", "batchpad_lo"))
    hi = opens_by_runid(os.path.join(ROOT, "runs", "batchpad_hi"))
    common = sorted(set(lo) & set(hi))
    print("batch-pad: lo(1-wide) n=%d  hi(64-wide) n=%d  paired n=%d" % (len(lo), len(hi), len(common)))
    klo = sum(1 for t in lo.values() if t); khi = sum(1 for t in hi.values() if t)
    print("  P(open by 30): lo = %d/%d = %.3f  %s" % (klo, len(lo), klo / len(lo) if lo else float("nan"), wilson(klo, len(lo))))
    print("                 hi = %d/%d = %.3f  %s" % (khi, len(hi), khi / len(hi) if hi else float("nan"), wilson(khi, len(hi))))
    print("  (core no-board for reference: 0.40 / 0.35 / 0.30 at N=4/8/16; single-agent pool 0.273)")
    # paired McNemar on matched run_ids
    b = sum(1 for rid in common if lo[rid] and not hi[rid])   # open at lo, not hi
    c = sum(1 for rid in common if hi[rid] and not lo[rid])   # open at hi, not lo
    concord = sum(1 for rid in common if bool(lo[rid]) == bool(hi[rid]))
    print("  paired: both-same=%d  lo-only-open=%d  hi-only-open=%d" % (concord, b, c))
    if b + c > 0:
        # exact binomial two-sided p for McNemar
        from math import comb
        n = b + c; k = min(b, c)
        p = sum(comb(n, i) for i in range(0, k + 1)) * 2 / (2 ** n)
        p = min(1.0, p)
        print("  McNemar exact p = %.3f (discordant pairs=%d)" % (p, n))
    else:
        print("  no discordant pairs (identical open/no-open on every matched seed)")
    print("\n  VERDICT: if lo and hi rates are within noise and few discordant pairs -> batch width does NOT")
    print("  move the open decision; the no-board 0.40->0.30 drift is not a numerics artifact (GAP3 closed).")
    print("  If hi drifts away from lo -> co-batching shifts behavior; a slice of the N-exponents is numerics.")


if __name__ == "__main__":
    main()
