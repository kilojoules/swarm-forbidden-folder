"""CLI runner: python -m harness.run --arm N1-pool --sessions 30 --backend ollama --base-url http://localhost:11434 --model qwen3:8b --out runs/pilot"""
import argparse
import concurrent.futures
import json
import os
import re
import sys
import threading
import time

from . import config, prompts, sandbox
from .backends import make_backend
from .session import Session, SessionConfig

_print_lock = threading.Lock()


def log(msg):
    with _print_lock:
        sys.stderr.write(time.strftime("%H:%M:%S ") + msg + "\n")
        sys.stderr.flush()


def slug(s):
    return re.sub(r"[^A-Za-z0-9.-]+", "_", s)


def session_finished(out_dir, n):
    p = os.path.join(out_dir, "closing.jsonl")
    if not os.path.exists(p):
        return False
    with open(p) as f:
        return sum(1 for l in f if l.strip()) >= n


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", required=True, choices=sorted(config.ARMS))
    ap.add_argument("--variant", default="base", choices=sorted(prompts.VARIANTS), help="prompt pressure/lure variant (PILOT.md 5)")
    ap.add_argument("--poison", default="none", choices=["none", "none_roster", "silent", "lastword"],
                    help="opening poisons the agent: silent=vanish, lastword=one final post then dark, none_roster=roster shown but no poison, none=original")
    ap.add_argument("--stop-on-open", action="store_true", help="end the session at the first open (efficient time-to-open survival runs)")
    ap.add_argument("--sessions", type=int, required=True)
    ap.add_argument("--backend", choices=["ollama", "vllm"], required=True)
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--out", default="runs")
    ap.add_argument("--parallel-sessions", type=int, default=4)
    ap.add_argument("--T-max", type=int, default=None, help="override T_MAX (changes the prompt!)")
    ap.add_argument("--seed-master", type=int, default=20260912)
    ap.add_argument("--max-tokens", type=int, default=None, help="default 1024 non-thinking, 4096 thinking")
    ap.add_argument("--no-structured", action="store_true", help="do not send a JSON schema; rely on lenient parsing")
    ap.add_argument("--think", choices=["auto", "on", "off"], default="auto")
    ap.add_argument("--sandbox", choices=["auto", "seatbelt", "setpriv", "none"], default="auto")
    ap.add_argument("--start-index", type=int, default=0)
    ap.add_argument("--force", action="store_true", help="rerun finished sessions (deletes nothing; writes a fresh dir suffix)")
    ap.add_argument("--timeout", type=int, default=1800, help="HTTP timeout per model call, seconds")
    ap.add_argument("--num-ctx", type=int, default=config.NUM_CTX_OLLAMA, help="Ollama context window (vLLM uses --max-model-len)")
    args = ap.parse_args(argv)

    arm = config.ARMS[args.arm]
    t_max = args.T_max or arm.get("T_MAX", config.T_MAX)
    preset = config.preset_for(args.model)
    if args.think != "auto":
        preset["think"] = args.think == "on"
    max_tokens = args.max_tokens or (config.MAX_TOKENS_THINKING if preset.get("think") else config.MAX_TOKENS_PLAIN)
    sb = sandbox.default_mode() if args.sandbox == "auto" else args.sandbox
    if sb == "none" and args.sandbox == "auto":
        sys.exit("no sandbox available (need /usr/bin/sandbox-exec on macOS, or root + setpriv on Linux); pass --sandbox none to run unsandboxed on purpose")
    sandbox.prewarm_matplotlib()
    backend = make_backend(args.backend, args.base_url, args.model, num_ctx=args.num_ctx, timeout=args.timeout)
    out_root = os.path.abspath(os.path.join(args.out, args.arm))
    os.makedirs(out_root, exist_ok=True)
    log("arm={} N={} board={} T_MAX={} variant={} poison={} model={} backend={} preset={} max_tokens={} structured={} sandbox={}".format(
        args.arm, arm["N"], arm["board"], t_max, args.variant, args.poison, args.model, args.backend, preset, max_tokens, not args.no_structured, sb))

    jobs = []
    for i in range(args.start_index, args.start_index + args.sessions):
        vtag = "" if args.variant == "base" else "__v-{}".format(args.variant)
        ptag = "" if args.poison == "none" else "__p-{}".format(args.poison)
        run_id = "{}__{}{}{}__s{}__{:03d}".format(args.arm, slug(args.model), vtag, ptag, args.seed_master, i)
        out_dir = os.path.join(out_root, run_id)
        if session_finished(out_dir, arm["N"]) and not args.force:
            log("skip finished {}".format(run_id))
            continue
        if args.force and os.path.exists(out_dir):
            run_id = "{}__rerun{}".format(run_id, int(time.time()))   # fresh run_id => fresh canary, seeds, ids
            out_dir = os.path.join(out_root, run_id)
        cfg = SessionConfig(run_id=run_id, arm=args.arm, N=arm["N"], board=arm["board"], T_MAX=t_max,
                            model=args.model, backend_kind=args.backend, preset=preset, max_tokens=max_tokens,
                            structured=not args.no_structured, seed_master=args.seed_master, out_dir=out_dir,
                            sandbox_mode=sb, variant=args.variant, poison=args.poison, stop_on_open=args.stop_on_open)
        jobs.append(cfg)

    def run_one(cfg):
        try:
            return Session(cfg, backend, log=log).run()
        except Exception as e:
            log("[{}] FAILED: {!r}".format(cfg.run_id, e))
            return {"run_id": cfg.run_id, "error": repr(e)}

    t0 = time.time()
    results = []
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.parallel_sessions) as ex:
            for res in ex.map(run_one, jobs):
                results.append(res)
                log("session done: {}".format(json.dumps(res)))
    except KeyboardInterrupt:
        log("interrupted; partial sessions resume from their last complete round on rerun")
        sys.stderr.flush()
        os._exit(130)
    summary = {"arm": args.arm, "model": args.model, "sessions": len(results),
               "sessions_with_open": sum(1 for r in results if any(o[1] for o in r.get("opens", []))),
               "failed": sum(1 for r in results if "error" in r), "elapsed_s": round(time.time() - t0, 1)}
    with open(os.path.join(out_root, "summary_{}.json".format(int(t0))), "w") as f:
        json.dump({"summary": summary, "results": results}, f, indent=1)
    log("SUMMARY " + json.dumps(summary))
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
