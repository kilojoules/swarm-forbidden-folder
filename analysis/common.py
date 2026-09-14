"""Shared loaders for the analysis scripts."""
import csv
import glob
import hashlib
import json
import os

DELIBERATE = ("deliberate-acknowledged", "deliberate-rationalized")
LABELS = ("deliberate-acknowledged", "deliberate-rationalized", "untracked", "exploratory", "slip")


def event_id(run_id, agent_id, rnd):
    return hashlib.sha1("{}|{}|{}".format(run_id, agent_id, rnd).encode()).hexdigest()[:10]


def load_runs(root, arms=None, model=None):
    """Yield dicts {meta, turns(list), board(list), closing(list), probe(list), dir, finished} per session."""
    for meta_path in sorted(glob.glob(os.path.join(root, "*", "*", "meta.json"))):
        d = os.path.dirname(meta_path)
        meta = json.load(open(meta_path))
        if arms and meta["arm"] not in arms:
            continue
        if model and meta["model"] != model:
            continue

        def rd(name):
            p = os.path.join(d, name)
            out = []
            if os.path.exists(p):
                for l in open(p):
                    if not l.strip():
                        continue
                    try:
                        out.append(json.loads(l))
                    except ValueError:
                        pass   # truncated trailing line from a crash; the harness drops it on resume
            return out
        probe = json.load(open(os.path.join(d, "probe.json"))) if os.path.exists(os.path.join(d, "probe.json")) else []
        closing = rd("closing.jsonl")
        yield {"meta": meta, "turns": rd("turns.jsonl"), "board": rd("board.jsonl"), "closing": closing,
               "probe": probe, "dir": d, "finished": len(closing) >= meta.get("N", 1)}


def load_labels(root, filename=None):
    """labels.csv (event_id,label) joined through events_key.csv (event_id,run_id,agent_id,round,arm).
    Returns {(run_id, agent_id, round): label}. filename overrides labels.csv (e.g. labels_judge.csv for a first pass)."""
    filename = filename or os.environ.get("SWARM_LABELS", "labels.csv")
    lp, kp = os.path.join(root, filename), os.path.join(root, "events_key.csv")
    if not (os.path.exists(lp) and os.path.exists(kp)):
        return {}
    key = {}
    with open(kp) as f:
        for row in csv.DictReader(f):
            key[row["event_id"]] = (row["run_id"], row["agent_id"], int(row["round"]))
    out = {}
    with open(lp) as f:
        for row in csv.DictReader(f):
            lab = (row.get("label") or "").strip()
            if lab and lab not in LABELS:
                raise ValueError("labels.csv: unknown label {!r} for event {}; allowed: {}".format(lab, row["event_id"], ", ".join(LABELS)))
            if lab and row["event_id"] in key:
                out[key[row["event_id"]]] = lab
    return out


def unlabeled_first_opens(run, labels):
    """(run_id, agent_id, round) of first-open events that have no label yet."""
    fo, _ = first_open_per_agent(run)
    rid = run["meta"]["run_id"]
    return [(rid, a, r) for a, r in fo.items() if r is not None and (labels or {}).get((rid, a, r)) is None]


def first_open_per_agent(run, labels=None, deliberate_only=False):
    """Event = an agent's FIRST open of any class (later opens are re-reads). Returns ({agent_id: round|None}, T_MAX).
    With deliberate_only, an agent whose first open is not labeled deliberate is a non-event (competing risk)."""
    t_max = run["meta"]["T_MAX"]
    out = {a: None for a in run["meta"]["agent_ids"]}
    seen = set()
    for t in sorted(run["turns"], key=lambda x: (x["round"], x["exec_position"])):
        a = t["agent_id"]
        if not t["open"] or a in seen:
            continue
        seen.add(a)
        if deliberate_only:
            if (labels or {}).get((t["run_id"], a, t["round"])) in DELIBERATE:
                out[a] = t["round"]
        else:
            out[a] = t["round"]
    return out, t_max


def cdf(times, t_max):
    """P(first open by r) for r = 0..t_max from a list of rounds / None (censored at t_max)."""
    n = len(times)
    return [sum(1 for t in times if t is not None and t <= r) / n if n else 0.0 for r in range(t_max + 1)]


def logrank(times_a, times_b, t_max):
    """Two-sample log-rank test with administrative censoring at t_max. Returns (chi2, p, O_a, E_a)."""
    from scipy.stats import chi2 as chi2dist
    O, E, V = 0.0, 0.0, 0.0
    for r in range(1, t_max + 1):
        na = sum(1 for t in times_a if t is None or t >= r)
        nb = sum(1 for t in times_b if t is None or t >= r)
        da = sum(1 for t in times_a if t == r)
        db = sum(1 for t in times_b if t == r)
        n, d = na + nb, da + db
        if n < 2 or d == 0:
            continue
        O += da
        E += d * na / n
        V += d * (na / n) * (nb / n) * (n - d) / (n - 1)
    if V == 0:
        return 0.0, 1.0, O, E
    stat = (O - E) ** 2 / V
    return stat, float(chi2dist.sf(stat, 1)), O, E
