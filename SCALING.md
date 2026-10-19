# Scaling laws in the swarm forbidden-folder study

*How do the breach dynamics change with swarm size N? A hunt for scaling laws, now on a
five-point log-ladder N ∈ {2, 4, 8, 16, 32} (Qwen2.5-7B, `soft_rule_lure`, board=live; 30
sessions each for N≤16, 9 for N=32), stress-tested against the confounds that can manufacture a
fake exponent — and with two dedicated controls run to settle them: a **seed-spark** arm
(ignition forced, N ∈ {4, 8}) and a **batch-pad** arm (vLLM batch-width numerics). Reproduce with
`python3 analysis/scaling.py && python3 analysis/seedspark.py && python3 analysis/batchpad.py &&
python3 results/fig_scaling.py`.*

![Scaling figure](results/fig_scaling.png)

## The one-line version

Adding agents does **not** make a swarm more likely to breach — ignition is size-invariant across
a 16× range of N — but it changes *how* a breach happens: the board couples agents into rare,
**all-or-nothing** cascades. The board's per-agent, per-round grip (both the spark it suppresses
and the contagion it carries) **dilutes toward independence as the swarm grows** — yet when we
force a clean ignition, the *share* of the swarm that follows stays constant (~84% at N=4 and
N=8). So what dilutes with N is the per-round hazard, not the eventual reach of a well-lit fire.

## The breach distribution has exactly three independent knobs

The number of agents that open the folder in a session is one distribution; everything else
("mean cascade size", "fraction of the swarm engulfed") is an algebraic transform of it. There
are only three freely-moving scaling facts, fit on the full ladder:

| Quantity | N=2 | N=4 | N=8 | N=16 | N=32† | Fit |
|---|---|---|---|---|---|---|
| **P(≥1 open)** — ignition | 0.467 | 0.467 | 0.400 | 0.467 | 0.667 | **~ N⁺⁰·¹⁰ (flat; see L1)** |
| **mean openers μ** | 0.87 | 1.47 | 1.73 | 3.27 | 4.67 | ~ N⁺⁰·⁶⁰ |
| **Fano = var/mean** — overdispersion | 1.09 | 2.06 | 3.78 | 6.63 | 6.21 | ~ N⁺⁰·⁶⁷ |

† N=32 is **n=9 sessions** (the big-N board arm is ~65 min/session and only one fits under the
KV-safe concurrency cap, so N=32×30 was ~23 h — infeasible; N=64 worse still and dropped). Treat
N=32 as a thin anchor with wide CIs, not a precise point.

The "engulfed fraction declines as N⁻⁰·⁵⁰" result is **not a fourth law** — it is pinned by the
identity `slope(fraction) = slope(μ) − slope(P≥1) − 1` (reproduced to the digit). Report P≥1, μ,
and Fano; the rest follow.

**The exponents moved when the ladder widened** — exactly as the first pass warned they might.
On {4,8,16} alone, Fano fit N⁺⁰·⁸⁴ and contagion grip N⁻⁰·⁶³; on {2,4,8,16,32} they are N⁺⁰·⁶⁷ and
N⁻⁰·⁹¹. The *directions* are stable; the *magnitudes* were never pinned by three points, and still
are not fully pinned by five (the endpoints N=2 and N=32 are the least reliable and do much of the
slope-setting). Believe the signs and the "dilutes toward independence" shape; do not quote the
decimals as universal.

## L1 — Ignition is size-invariant (the one robust law)

P(a session has ≥1 breach) ≈ **0.46, flat across N ∈ {2…32}** — a 16× range. Every point's 95%
Wilson CI brackets ~0.46:

| N | 2 | 4 | 8 | 16 | 32 |
|---|---|---|---|---|---|
| board P(≥1) | 0.467 | 0.467 | 0.400 | 0.467 | 0.667 |
| 95% CI | .30–.64 | .30–.64 | .25–.58 | .30–.64 | .35–.88 |

This is **certified by a control, not merely un-rejected**. The no-board arm is a genuine
same-model realization of independent agents, where P(≥1) must rise as 1−(1−p)ᴺ — and it does,
tracking the independence prediction almost exactly, while the board arm stays flat:

| N | 2 | 4 | 8 | 16 | 32 |
|---|---|---|---|---|---|
| no-board P(≥1), observed | 0.50 | 0.70 | 1.00 | 1.00 | 1.00 |
| independence prediction 1−(1−p)ᴺ | 0.51 | 0.87 | 0.97 | 1.00 | 1.00 |
| **board P(≥1)** | **0.47** | **0.47** | **0.40** | **0.47** | **0.67** |

At N=2 the board and independent swarms are nearly identical (0.47 vs 0.50 — little room to act);
by N=16 independent agents are *certain* to breach (1.00) while the board holds flat at 0.47. A
shared board **removes the extra ignition that independent agents would add.** Adding agents behind
a board does not add independent fuses. (N=32 board is 6/9 = 0.667 — high, but its CI [.35, .88]
covers 0.46, so it does not break the law; it just can't confirm it tightly on 9 sessions.)

## L2/L5 — The board's per-agent grip is real (not a horizon artifact) and dilutes with N

The pre/post opening hazards fall steeply with N. The sharpest worry from the adversarial review:
these are averages over a **T_MAX=30 window**, and the single-agent hazard is strongly time-varying
(≈0 before round 6, then rising, only ~0.27 realized by round 30 of an eventual ~0.44). If larger
swarms spark earlier, their windows cover different rounds and the "law" could be pure window
composition.

It is not. We built the single-agent **time-varying baseline** h₁(r) from the N=1 pool and asked
what hazard an *independent* agent would show **over the exact same rounds** each arm's pre- and
post-windows cover. The baseline-predicted hazard is **flat in N** (pre ~ N⁺⁰·⁰⁰, post ~ N⁻⁰·⁰³,
both R²<0.3), so the entire N-dependence lives in the board's **multiplicative grip**:

| board multiplier (observed ÷ independent baseline) | N=2 | N=4 | N=8 | N=16 | N=32† | fit |
|---|---|---|---|---|---|---|
| **spark** hazard (pre-visible) | 1.11× | 0.60× | 0.20× | 0.16× | 0.15× | suppressed, ~ N⁻⁰·⁷⁸ |
| **contagion** hazard (post-visible) | 13.8× | 6.7× | 4.6× | 2.8× | 0.9× | amplified, ~ N⁻⁰·⁹¹ |

Two real effects, opposite sign, both **diluting toward the independence line (1×)** as N grows: the
board **suppresses** the first spark (keeps agents on-task; 1.1× at N=2 down to 0.15× at N=32) and
**amplifies** contagion once a peer opens (13.8× down to ~1× by N=32). A bigger swarm dilutes both —
the single opener's recruiting post is one voice among more, and on-task chatter crowds the idle
drift that lights the first fuse.

*Reliability:* the solid middle (N=4→16) gives spark 0.60→0.16× and contagion 6.7→2.8×. The
endpoints stretch the fitted exponent — N=2 has few post-visible agent-rounds (so 13.8× rests on a
small denominator) and N=32 is n=9 (contagion 0.9× is a single noisy anchor). Read the table, not
the exponent.

## Seed-spark — with ignition forced, the *follower share* is N-invariant

The observational hazards above conflate two things: **whether** a fire starts and **how far** it
spreads. The seed-spark arm separates them — one agent is pre-opened before round 1 and leaves a
single last-word post, then the swarm runs normally. Ignition is removed as a variable; we measure
only recruitment. N ∈ {4, 8}, 30 and 16 sessions:

| N | at-risk (N−1) | R_eff (gen-1 recruits) | follower fraction | P(≥1 follows) |
|---|---|---|---|---|
| 4 | 3 | 2.30 | **0.844** | 1.00 |
| 8 | 7 | 5.44 | **0.839** | 1.00 |

A single visible breach recruits a **constant ~84% share** of the exposed swarm, identical at N=4
and N=8, even though the *absolute* recruits grow (2.3 → 5.4, ~N¹·²). This is the crucial
complement to L2: the per-round contagion *hazard multiplier* dilutes with N, but the *cumulative
reach* of a cleanly-lit fire does not — more agents means more recruiters, which compensates for
each one being a quieter voice. It also reframes the observational cascade-dilution (L3 below) as
substantially an **ignition-timing** effect, not contagion weakening: when ignition is forced early
and strong, size doesn't shrink the burn.

*Caveat — this is two points.* The flat 0.84 is a real, clean observation at N=4 and N=8, but a
two-point line can't establish a trend; a third point (seed-spark N=16, ~2–3 h / ~$10 on the pod)
would test whether the constant share holds or finally bends. Deliberately scoped out for cost.

## L3/GAP5 — Cascades are bistable (all-or-nothing), not critical

Critical branching (R ≈ 1) would give scale-free, monotonically *decreasing* cascade sizes. The
data are the opposite — **bimodal**: conditional on ignition, cascades tend to engulf a large share
of the swarm, and this is board-specific (no-board Fano ≈ 1, essentially no near-total events; board
Fano rises 1.1 → 6.6). The signature is **subcritical ignition, supercritical spread** — a threshold
contagion, not a system poised at criticality. Observationally the near-total engulfment share of
*igniting* sessions falls with N (the L2 per-round dilution seen in cascade sizes); the seed-spark
result above says that fall is driven by ignition quality, not by contagion losing its grip.

## GAP3 — the numerics confound is closed

The first pass flagged a possible artifact: the no-board per-agent rate appeared to drift
0.40 → 0.35 → 0.30 over N=4/8/16, which independent agents with N-invariant inputs should not do —
raising the worry that vLLM **batch-width numerics** (co-batching N decode streams) shifts behavior
and contaminates a slice of every N-exponent. Two independent checks now close it:

1. **Wider ladder.** Over N ∈ {2,4,8,16,32} the no-board rate is {0.30, 0.40, 0.35, 0.30, 0.43} —
   not a decline, just noise around ~0.35. Session-clustered logistic slope on log N = **+0.19, 95%
   CI [−0.05, +0.46]** (covers 0). The no-board rate is N-invariant, as independence requires.
2. **Batch-pad control.** Identical single-agent sessions (same seeds, `seed_master 777`) run
   1-wide vs 32-wide batches. Open rates: lo 11/30 = 0.37, hi 7/30 = 0.23; **McNemar exact
   p = 0.45** (16 discordant pairs, 10 vs 6). Batch width does not significantly move the open
   decision.

So the N-laws above are agent-level behavior, not decode numerics. *Caveats:* n=30 per batch-pad
arm is modest (it would miss a small effect — the point estimates do differ by 0.13), and the wide
batch here is 32 (the KV-safe cap), not the 64 originally specified. "No significant artifact
detected," not "proven bit-identical."

## What to believe, and what not to

**Robust (survives the controls):** ignition invariance (L1) — now the single strongest result,
flat at ~0.46 across 16× in N and control-certified against a rising independence baseline; the
existence and *direction* of the board's spark-suppression and contagion-amplification grip, net of
horizon (L2/L5); the constant ~84% follower share under forced ignition (seed-spark, 2 points);
bistable all-or-nothing cascades (L3); the numerics confound is closed (GAP3).

**Directional, not pinned:** every N-exponent (μ⁺⁰·⁶, Fano⁺⁰·⁷, spark⁻⁰·⁸, contagion⁻⁰·⁹) — the
magnitudes shifted when the ladder widened from 3 to 5 points and the endpoints (N=2, N=32) do most
of the slope-setting. Believe the signs and "dilutes toward independence"; don't quote decimals.

**Thin / scoped out:** N=32 board is 9 sessions (wide CIs — it anchors but can't pin); seed-spark is
two points (N=4, N=8); N=64 and seed-spark N≥16 are dropped as infeasible on this harness (big-N
board sessions ~1 min/round × 30 rounds, only ~32/N fit concurrently). The capability inverted-U and
cure-mixture time-to-open remain on a separate single-agent axis.

## Experiment program — status

Scoped to the decisive-and-feasible subset (user decision, 2026-10-18); runs on the shared lab pod,
Qwen2.5-7B bf16, `soft_rule_lure`, via `runpod/launch_redo.sh` at KV-safe concurrency
(`--max-num-seqs 32`), 0/7860 backend errors.

- ✅ **wide-N ladder** — board + no-board at N=2 and N=32 added (N=32 board only 9 sessions).
  Turned the 3-point fits into a 5-point ladder; confirmed L1 flat and L2 dilution directionally.
- ✅ **batch-pad control** — done; GAP3 closed (above).
- ✅ **seed-spark** — N=4, N=8 done; constant follower share (above).
- ⏸️ **seed-spark N=16** — the single addition that would turn the flat-share finding from two
  points into a trend (~2–3 h / ~$10). Deferred for cost; easy to add.
- ❌ **N=64 / seed-spark N≥32** — infeasible on this harness (dropped; a real throughput/KV wall,
  not a bug). The N=64 board prompt alone (~63 posts/round ≈ 20k tokens) is a hard KV limit.
- ⏳ **constant-k board; horizon/cap-ladder; 1.5B/3B/72B capability edges** — not yet run.

*Everything above the program is computed on already-collected data.*
