"""Create, wait for, and tear down a vLLM pod on RunPod.
  python3 runpod/pod.py create --model Qwen/Qwen3-8B --gpu "NVIDIA H100 80GB HBM3" --cloud COMMUNITY --name swarm-core
  python3 runpod/pod.py wait <pod_id>          # prints the base URL when /v1/models answers
  python3 runpod/pod.py status <pod_id>
  python3 runpod/pod.py stop <pod_id> | terminate <pod_id>
"""
import argparse
import json
import os
import re
import sys
import time

import requests
import runpod

VLLM_IMAGE = os.environ.get("VLLM_IMAGE", "vllm/vllm-openai:latest")


def api_key():
    k = os.environ.get("RUNPOD_API_KEY")
    if k:
        return k
    p = os.path.expanduser("~/.runpod/config.toml")
    if os.path.exists(p):
        m = re.search(r"apikey\s*=\s*['\"]?([^'\"\n]+)", open(p).read(), re.I)
        if m:
            return m.group(1).strip()
    sys.exit("no RunPod API key: set RUNPOD_API_KEY or run `runpodctl doctor`")


def reasoning_parser(model):
    m = model.lower()
    if "deepseek-r1" in m or "deepseek_r1" in m:
        return "deepseek_r1"
    if "gpt-oss" in m:
        return "openai_gptoss"
    if "qwen3" in m:
        return "qwen3"
    return None


def docker_args(model, max_len, thinking, quantization=None):
    args = ["--model", model, "--served-model-name", model, "--host", "0.0.0.0", "--port", "8000",
            "--max-model-len", str(max_len), "--enable-prefix-caching", "--gpu-memory-utilization", "0.92",
            "--max-num-seqs", "128", "--dtype", "auto"]
    if quantization:
        args += ["--quantization", quantization]
    rp = reasoning_parser(model)
    if thinking and rp:
        args += ["--reasoning-parser", rp]
    return " ".join(args)


def create(a):
    runpod.api_key = api_key()
    thinking = reasoning_parser(a.model) is not None
    pod = runpod.create_pod(
        name=a.name, image_name=VLLM_IMAGE, gpu_type_id=a.gpu, cloud_type=a.cloud, gpu_count=1,
        volume_in_gb=a.volume_gb, container_disk_in_gb=a.disk_gb, volume_mount_path="/root/.cache/huggingface",
        ports="8000/http,22/tcp", docker_args=docker_args(a.model, a.max_len, thinking, a.quantization),
        env={"HF_HUB_ENABLE_HF_TRANSFER": "1", "VLLM_LOGGING_LEVEL": "INFO"},
    )
    print(json.dumps({"pod_id": pod["id"], "name": a.name, "gpu": a.gpu, "cloud": a.cloud, "image": VLLM_IMAGE,
                      "docker_args": docker_args(a.model, a.max_len, thinking, a.quantization)}))
    return pod["id"]


def base_url(pod_id):
    return "https://{}-8000.proxy.runpod.net".format(pod_id)


def wait(a):
    runpod.api_key = api_key()
    url = base_url(a.pod_id)
    t0 = time.time()
    last = ""
    while time.time() - t0 < a.timeout:
        try:
            pod = runpod.get_pod(a.pod_id)
            st = pod.get("desiredStatus") or pod.get("status")
        except Exception as e:
            st = "api-error {}".format(e)
        try:
            r = requests.get(url + "/v1/models", timeout=10)
            if r.status_code == 200 and "data" in r.json():
                sys.stderr.write("\nready after {:.0f}s: {}\n".format(time.time() - t0, r.json()["data"][0]["id"]))
                print(url)
                return
            last = "http {}".format(r.status_code)
        except Exception as e:
            last = type(e).__name__
        sys.stderr.write("\rwaiting ({:.0f}s) pod={} endpoint={}   ".format(time.time() - t0, st, last))
        time.sleep(15)
    sys.exit("\ntimeout waiting for {}".format(url))


def status(a):
    runpod.api_key = api_key()
    print(json.dumps(runpod.get_pod(a.pod_id), indent=1))


def stop(a):
    runpod.api_key = api_key()
    print(json.dumps(runpod.stop_pod(a.pod_id)))


def terminate(a):
    runpod.api_key = api_key()
    print(json.dumps(runpod.terminate_pod(a.pod_id)))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("create")
    c.add_argument("--model", default="Qwen/Qwen3-8B")
    c.add_argument("--gpu", default="NVIDIA H100 80GB HBM3")
    c.add_argument("--cloud", default="COMMUNITY", choices=["COMMUNITY", "SECURE"])
    c.add_argument("--name", default="swarm-vllm")
    c.add_argument("--max-len", type=int, default=32768)
    c.add_argument("--quantization", default=None, help="e.g. fp8 (halves weight memory for large models)")
    c.add_argument("--volume-gb", type=int, default=60)
    c.add_argument("--disk-gb", type=int, default=30)
    c.set_defaults(fn=create)
    w = sub.add_parser("wait"); w.add_argument("pod_id"); w.add_argument("--timeout", type=int, default=1800); w.set_defaults(fn=wait)
    s = sub.add_parser("status"); s.add_argument("pod_id"); s.set_defaults(fn=status)
    st = sub.add_parser("stop"); st.add_argument("pod_id"); st.set_defaults(fn=stop)
    t = sub.add_parser("terminate"); t.add_argument("pod_id"); t.set_defaults(fn=terminate)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
