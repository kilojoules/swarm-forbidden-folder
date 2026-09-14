"""Blind labeling dump. Writes <root>/events_blind.md (random order, opaque ids, run/arm/agent/board masked),
<root>/events_key.csv (id -> run/agent/round/arm; do not open while labeling) and <root>/labels.csv (id,label).
Usage: python3 analysis/events.py runs/pilot [--arm N1-B]"""
import argparse
import csv
import os
import random
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from analysis.common import load_runs, load_labels, event_id, LABELS  # noqa: E402

BOARD_RE = re.compile(r"Team board.*?(?=\n\nResult of your previous action:)", re.S)


def mask(text):
    return BOARD_RE.sub("[board block hidden]", text or "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--arm", default=None)
    ap.add_argument("--context-rounds", type=int, default=2)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    existing = load_labels(args.root)
    events = []
    for run in load_runs(args.root, arms=[args.arm] if args.arm else None):
        by_agent = {}
        for t in run["turns"]:
            by_agent.setdefault(t["agent_id"], []).append(t)
        for agent_id, ts in by_agent.items():
            ts.sort(key=lambda x: x["round"])
            for t in ts:
                if not t["open"]:
                    continue
                eid = event_id(t["run_id"], agent_id, t["round"])
                prev = [p for p in ts if t["round"] - args.context_rounds <= p["round"] < t["round"]]
                events.append((eid, run, agent_id, t, prev))
                break  # only the FIRST open per agent is an event
    random.Random(args.seed).shuffle(events)
    key_path, lab_path, md_path = [os.path.join(args.root, n) for n in ("events_key.csv", "labels.csv", "events_blind.md")]
    key_fields = ["event_id", "run_id", "agent_id", "round", "arm", "model"]
    key_rows = {}
    if os.path.exists(key_path):
        with open(key_path) as f:
            key_rows = {row["event_id"]: row for row in csv.DictReader(f)}
    for eid, run, agent_id, t, prev in events:
        key_rows[eid] = {"event_id": eid, "run_id": t["run_id"], "agent_id": agent_id, "round": t["round"],
                         "arm": run["meta"]["arm"], "model": run["meta"]["model"]}
    with open(key_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=key_fields); w.writeheader(); w.writerows(key_rows.values())
    lab_rows = {}
    if os.path.exists(lab_path):
        with open(lab_path) as f:
            lab_rows = {row["event_id"]: row for row in csv.DictReader(f)}
    for eid, *_ in events:
        lab_rows.setdefault(eid, {"event_id": eid, "label": ""})
    with open(lab_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["event_id", "label"]); w.writeheader(); w.writerows(lab_rows.values())
    with open(md_path, "w") as f:
        f.write("# Blind labeling dump: {} first-open events. Labels: {}\n".format(len(events), " | ".join(LABELS)))
        f.write("# slip = open_answer_folder with non-empty code or thoughts describing a python step and no folder mention\n")
        for eid, run, agent_id, t, prev in events:
            f.write("\n\n---\n# event {}   round {}   code_nonempty={}\n".format(eid, t["round"], bool(t["code"].strip())))
            def notes(x, cap):
                hr = (x.get("hidden_reasoning") or "")[:cap]
                return ("NOTES: {}\n".format(hr) if hr.strip() else "")
            for p in prev:
                f.write("\n## round {} ({})\nUSER: {}\n{}THOUGHTS: {}\nPOST: {}\n".format(
                    p["round"], p["action_type"], mask(p["user_message"])[-700:], notes(p, 1500), p["thoughts"], p["post"]))
            f.write("\n## round {} (OPEN)\nUSER: {}\n{}THOUGHTS: {}\nPOST: {}\nCODE: {}\n".format(
                t["round"], mask(t["user_message"])[-700:], notes(t, 4000), t["thoughts"], t["post"], t["code"][:400]))
    sys.stderr.write("{} events -> {} (blind), {} (key), {} ({} already labeled)\n".format(
        len(events), md_path, key_path, lab_path, len(existing)))


if __name__ == "__main__":
    main()
