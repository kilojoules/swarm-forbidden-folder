"""Render a session's shared-board conversation as readable markdown, with open/leak markers.
Usage: python results/render_board.py <session_dir> <out.md> "<caption>" """
import json, os, sys
def render(d, out, caption):
    meta=json.load(open(os.path.join(d,"meta.json")))
    ids=meta["agent_ids"]; short={a:"A%02d"%(i+1) for i,a in enumerate(ids)}
    canary=meta.get("canary","")
    firsts={}
    for l in open(os.path.join(d,"turns.jsonl")):
        t=json.loads(l)
        if t["open"] and t["agent_id"] not in firsts: firsts[t["agent_id"]]=t["round"]
    board={}
    for l in open(os.path.join(d,"board.jsonl")):
        p=json.loads(l); board.setdefault(p["round"],[]).append(p)
    lines=[]
    lines.append("# Board log — %s"%caption)
    lines.append("")
    lines.append("`%s`  "%meta["run_id"])
    lines.append("model **%s**, N=%d, board=%s, poison=%s. Agents renamed A01..A%02d; the folder-open"
                 " tool is `open_answer_folder`."%(meta["model"],meta["N"],meta["board"],meta.get("poison","none"),meta["N"]))
    op=[(short[a],r) for a,r in sorted(firsts.items(),key=lambda x:x[1])]
    lines.append("")
    lines.append("**Openers (round):** %s"%(", ".join("%s(r%d)"%(a,r) for a,r in op) if op else "none"))
    lines.append("")
    lines.append("---")
    for r in range(1, meta["T_MAX"]+1):
        posts=board.get(r,[])
        opened_this=[short[a] for a,rr in firsts.items() if rr==r]
        if not posts and not opened_this: continue
        lines.append("")
        lines.append("### round %d"%r)
        for p in posts:
            a=short[p["agent_id"]]
            mark=""
            if firsts.get(p["agent_id"])==r: mark=" **← opens the folder this round**"
            if canary and canary in p["text"]: mark+=" **[CANARY LEAKED TO BOARD]**"
            lines.append("- **%s:** %s%s"%(a, p["text"], mark))
        # note openers who left no post this round (e.g., silent poison)
        silent_openers=[a for a in opened_this if a not in [short[p["agent_id"]] for p in posts]]
        for a in silent_openers:
            lines.append("- *%s opened the folder and went dark (no message).*"%a)
    open(out,"w").write("\n".join(lines)+"\n")
    print("wrote",out,"(%d openers)"%len(firsts))
if __name__=="__main__":
    render(sys.argv[1].rstrip("/")+"/", sys.argv[2], sys.argv[3])
