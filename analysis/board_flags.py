"""Regex first pass over posts and thoughts: awareness, give-up, folder mention, proposal to open.
Usage: python3 analysis/board_flags.py runs/pilot"""
import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from analysis.common import load_runs, first_open_per_agent  # noqa: E402

FLAGS = ["aware", "giveup", "folder", "propose", "alone"]


def main():
    root = sys.argv[1]
    per_arm = defaultdict(lambda: {"sessions": 0, "first_round": defaultdict(list), "before_open": defaultdict(int), "posts_with": defaultdict(int), "posts": 0})
    for run in load_runs(root):
        if not run["finished"]:
            continue
        a = per_arm[run["meta"]["arm"]]
        a["sessions"] += 1
        fo, t_max = first_open_per_agent(run)
        opened = [v for v in fo.values() if v]
        first_open = min(opened) if opened else None
        seen = {}
        for t in sorted(run["turns"], key=lambda x: x["round"]):
            a["posts"] += bool(t["post"])
            for fl in FLAGS:
                if t["text_flags"].get(fl):
                    a["posts_with"][fl] += 1
                    if fl not in seen:
                        seen[fl] = t["round"]
        for fl, r in seen.items():
            a["first_round"][fl].append(r)
            if first_open is None or r < first_open:
                a["before_open"][fl] += 1
    out = {}
    for arm, a in per_arm.items():
        out[arm] = {"sessions": a["sessions"], "agent_turns_with_post": a["posts"]}
        for fl in FLAGS:
            fr = a["first_round"][fl]
            out[arm][fl] = {"sessions_with_flag": len(fr), "sessions_with_flag_before_first_open": a["before_open"][fl],
                            "median_first_round": (sorted(fr)[len(fr) // 2] if fr else None), "turns_with_flag": a["posts_with"][fl]}
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
