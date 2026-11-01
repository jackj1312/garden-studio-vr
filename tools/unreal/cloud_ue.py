"""Unreal on a rented GPU (WORKFLOW G8), as a session you drive step by step. Epic's engine images have no SSH server
and run as a non-root user, so the pod's start command runs tools/cloud/pod_agent.py and we talk to it over RunPod's
HTTPS proxy (CORRECTIONS-LOG 136-137). Same safety as cloud_blender.py: a detached watchdog deletes the pod at the money
cap even if this shell goes away, and `down` deletes it and checks it is gone.
    ~/.runpod/venv/bin/python tools/unreal/cloud_ue.py up [--image ghcr.io/epicgames/unreal-engine:dev-slim-5.8.4] [--max-gbp 5]
    ... ping | put <local> <remote> | run "<bash>" [--wait] | status <id> | get <remote> <local> | salvage | cost | down
`down` and the watchdog (6 min before the cap) always salvage first: renders, logs, project content to renders/unreal/<date>/
and the compiled-shader cache to ~/.runpod/ue_cache, which `up` uploads to the next pod (CORRECTIONS-LOG 138).
Needs Jack's one-time access (README.md): GitHub in the EpicGames org, and RunPod registry auth named `ghcr-epic`."""
import argparse, base64, json, os, secrets, subprocess, sys, time
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "cloud"))
import cloud_blender as cb                                         # api_key(), USD_PER_GBP

REST = "https://rest.runpod.io/v1"
STATE = os.path.expanduser("~/.runpod/ue_session.json")            # pod id, token, start time, cap (never in the repo)
GPUS = ["NVIDIA GeForce RTX 4090", "NVIDIA L40S", "NVIDIA L40", "NVIDIA RTX 6000 Ada Generation", "NVIDIA RTX A6000"]
START = ('echo "$AGENT_B64" | base64 -d > /tmp/pod_agent.py; '
         'PY=$(command -v python3 || ls /home/*/UnrealEngine/Engine/Binaries/ThirdParty/Python3/Linux/bin/python3 2>/dev/null | head -1); '
         'exec "$PY" /tmp/pod_agent.py')


def H(): return {"Authorization": f"Bearer {cb.api_key()}", "Content-Type": "application/json"}
def load(): return json.load(open(STATE)) if os.path.exists(STATE) else None
def save(s): os.makedirs(os.path.dirname(STATE), exist_ok=True); json.dump(s, open(STATE, "w")); os.chmod(STATE, 0o600)
def url(s, path): return f"https://{s['pod']}-8000.proxy.runpod.net{path}"
def agent(s, method, path, **kw): return requests.request(method, url(s, path), headers={"X-Token": s["token"]}, timeout=kw.pop("timeout", 90), **kw)


def auth_id(name):
    r = requests.get(f"{REST}/containerregistryauth", headers=H(), timeout=30); r.raise_for_status()
    ids = {x["name"]: x["id"] for x in r.json()}
    if name not in ids: sys.exit(f"RunPod has no registry auth named '{name}' (README.md, Jack's one-time step)")
    return ids[name]


def delete(pod):
    for _ in range(5):
        r = requests.delete(f"{REST}/pods/{pod}", headers=H(), timeout=30)
        if r.status_code in (200, 204, 404): break
        time.sleep(5)
    for _ in range(12):
        if requests.get(f"{REST}/pods/{pod}", headers=H(), timeout=30).status_code == 404: return True
        time.sleep(5)
    return False


def up(a):
    if load(): sys.exit("a session is already up: run `down` first")
    token = secrets.token_urlsafe(24)
    env = {"AGENT_TOKEN": token, "AGENT_WORK": "/tmp/job", "NVIDIA_DRIVER_CAPABILITIES": "all",
           "AGENT_B64": base64.b64encode(open(os.path.join(HERE, "..", "cloud", "pod_agent.py"), "rb").read()).decode()}
    body = {"name": "studio-unreal", "imageName": a.image, "gpuTypeIds": GPUS, "gpuTypePriority": "custom", "gpuCount": 1,
            "cloudType": a.cloud, "containerDiskInGb": 140, "volumeInGb": 0, "ports": ["8000/http"], "env": env,
            "containerRegistryAuthId": auth_id(a.auth), "dockerEntrypoint": ["/bin/bash", "-c"], "dockerStartCmd": [START],
            "supportPublicIp": False, "minRAMPerGPU": 24}
    r = requests.post(f"{REST}/pods", headers=H(), json=body, timeout=60)
    if r.status_code >= 300: sys.exit(f"create failed {r.status_code}: {r.text[:300]}")
    pod = r.json(); rate = float(pod.get("costPerHr") or 0.9)
    cap_min = min(a.max_min, a.max_gbp * cb.USD_PER_GBP / max(rate, 0.1) * 60)
    s = {"pod": pod["id"], "token": token, "t0": time.time(), "rate": rate, "cap_min": cap_min, "image": a.image}
    save(s)
    # the watchdog: its own process, outlives this shell; deletes the pod at the cap
    subprocess.Popen([sys.executable, os.path.abspath(__file__), "watchdog", pod["id"], str(cap_min * 60)],
                     stdout=open(os.path.expanduser("~/.runpod/ue_watchdog.log"), "a"), stderr=subprocess.STDOUT, start_new_session=True)
    print(f"rented {pod['id']} at ${rate}/h; hard cap {cap_min:.0f} min (£{a.max_gbp}); waiting for the engine image to pull")
    t = time.time()
    while time.time() - t < a.wait_min * 60:
        try:
            p = agent(s, "GET", "/ping", timeout=20)
            if p.status_code == 200:
                print("agent up after %.1f min:" % ((time.time() - t) / 60), json.dumps(p.json(), indent=1)); restore(s); return
        except requests.RequestException: pass
        time.sleep(20)
    print(f"no agent after {a.wait_min} min (image pull or start failed): deleting"); a.no_salvage = True; down(a)


def watchdog(pod, secs):
    deadline = time.time() + float(secs)                           # secs = time left until the money cap
    time.sleep(max(0, deadline - time.time() - 360))
    s = load()
    if s and s.get("pod") == pod:                                  # still up near the cap: save the work first
        print(time.ctime(), "near the cap: salvaging", flush=True); salvage(s)
        time.sleep(max(0, deadline - time.time()))
        if (load() or {}).get("pod") == pod:
            print(time.ctime(), "cap reached: deleting", pod, delete(pod), flush=True); os.remove(STATE)


def need():
    s = load()
    if not s: sys.exit("no session: run `up` first")
    return s


def cost(a=None):
    s = need(); mins = (time.time() - s["t0"]) / 60; usd = mins / 60 * s["rate"]
    print(f"{s['pod']}: {mins:.1f} min, about ${usd:.2f} (~£{usd / cb.USD_PER_GBP:.2f}) of the £{s['cap_min'] * s['rate'] / 60 / cb.USD_PER_GBP:.2f} cap")


CACHE = os.path.expanduser("~/.runpod/ue_cache")                  # the shader/derived-data cache, reused by the next pod
RESULTS = "renders/unreal"                                          # every salvage lands in a dated folder here
# Unreal 5.8 keeps compiled shaders in ZenServer's store and the user's local DDC, not where UE-LocalDataCachePath points
DDC_PATHS = "home/ue4/.config/Epic/UnrealEngine/Common/DerivedDataCache home/ue4/.config/Epic/UnrealEngine/Common/Zen/Data"   # LogZenServiceInstance: data dir (CORRECTIONS-LOG 146)


def fetch(s, remote, local):
    with agent(s, "GET", f"/download?path={remote}", stream=True, timeout=900) as resp:
        if resp.status_code != 200: return False
        os.makedirs(os.path.dirname(local), exist_ok=True)
        with open(local, "wb") as f:
            for chunk in resp.iter_content(1 << 20): f.write(chunk)
    return True


def salvage(s):
    """Bring home everything paid for, whatever state the run is in: renders, logs, the built project content, and the
    compiled-shader cache (the slow part of a first run), so a failure never wastes the money spent before it."""
    stamp = time.strftime("%Y%m%d-%H%M"); dest = os.path.join(RESULTS, stamp); ok = []
    try:
        j = agent(s, "POST", "/run", data=(
            "cd /tmp/job && tar -cf /tmp/job/results.tar --ignore-failed-read out run-*.log project/Saved/Logs project/Content "
            "project/Config 2>/dev/null; pkill -f zenserver; sleep 2; tar -cf /tmp/job/ddc.tar --ignore-failed-read -C / " + DDC_PATHS +
            " 2>/dev/null; ls -la /tmp/job/ddc.tar; echo packed").encode()).json()
        for _ in range(60):
            if agent(s, "GET", f"/status?id={j['id']}").json()["done"]: break
            time.sleep(5)
        if fetch(s, "/tmp/job/results.tar", os.path.join(dest, "results.tar")):
            subprocess.run(["tar", "-xf", "results.tar"], cwd=dest); ok.append(f"results -> {dest}")
        if fetch(s, "/tmp/job/ddc.tar", os.path.join(CACHE, "ddc.tar.part")):
            os.replace(os.path.join(CACHE, "ddc.tar.part"), os.path.join(CACHE, "ddc.tar")); ok.append("shader cache -> ~/.runpod/ue_cache")
    except Exception as e:
        print("salvage incomplete:", str(e)[:200])
    print("salvaged:", "; ".join(ok) or "nothing (agent unreachable)"); return ok


def restore(s):
    """Seed a new pod with the last run's shader cache so it does not pay for the same compile twice."""
    p = os.path.join(CACHE, "ddc.tar")
    if not os.path.exists(p): print("no saved shader cache yet"); return
    with open(p, "rb") as f: agent(s, "PUT", "/upload?path=/tmp/job/ddc.tar", data=f, timeout=1800)
    j = agent(s, "POST", "/run", data=b"tar -xf /tmp/job/ddc.tar -C / && rm /tmp/job/ddc.tar && du -sh /home/ue4/.config/Epic/UnrealEngine/Common/Zen/Data /home/ue4/.config/Epic/UnrealEngine/Common/DerivedDataCache").json()
    print("shader cache restored (job %s)" % j["id"])


def down(a=None):
    s = load()
    if not s: print("no session"); return
    if not getattr(a, "no_salvage", False): salvage(s)
    cost(); print("deleted", s["pod"], "gone:", delete(s["pod"])); os.remove(STATE)


def main():
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd", required=True)
    u = sub.add_parser("up"); u.add_argument("--image", default="ghcr.io/epicgames/unreal-engine:dev-slim-5.8.4")
    u.add_argument("--auth", default="ghcr-epic"); u.add_argument("--cloud", default="SECURE", choices=["SECURE", "COMMUNITY"])
    u.add_argument("--max-gbp", type=float, default=5.0); u.add_argument("--max-min", type=float, default=150)
    u.add_argument("--wait-min", type=float, default=40)
    sub.add_parser("ping"); sub.add_parser("cost"); sub.add_parser("salvage")
    d = sub.add_parser("down"); d.add_argument("--no-salvage", action="store_true")
    p = sub.add_parser("put"); p.add_argument("local"); p.add_argument("remote")
    g = sub.add_parser("get"); g.add_argument("remote"); g.add_argument("local")
    r = sub.add_parser("run"); r.add_argument("command"); r.add_argument("--wait", action="store_true")
    st = sub.add_parser("status"); st.add_argument("id"); st.add_argument("--tail", type=int, default=40)
    w = sub.add_parser("watchdog"); w.add_argument("pod"); w.add_argument("secs")
    a = ap.parse_args()
    if a.cmd == "up": return up(a)
    if a.cmd == "watchdog": return watchdog(a.pod, a.secs)
    if a.cmd == "down": return down(a)
    if a.cmd == "cost": return cost(a)
    s = need()
    if a.cmd == "salvage": salvage(s)
    elif a.cmd == "ping": print(json.dumps(agent(s, "GET", "/ping").json(), indent=1))
    elif a.cmd == "put":
        with open(a.local, "rb") as f: print(agent(s, "PUT", f"/upload?path={a.remote}", data=f, timeout=600).json())
    elif a.cmd == "get":
        with agent(s, "GET", f"/download?path={a.remote}", stream=True, timeout=600) as resp, open(a.local, "wb") as f:
            resp.raise_for_status()
            for chunk in resp.iter_content(1 << 20): f.write(chunk)
        print("saved", a.local, os.path.getsize(a.local), "bytes")
    elif a.cmd == "run":
        j = agent(s, "POST", "/run", data=a.command.encode()).json(); print("job", j["id"])
        while a.wait:
            time.sleep(15); st = agent(s, "GET", f"/status?id={j['id']}&tail=15").json()
            if st["done"]: print(st["tail"]); print("exit", st["code"]); break
    elif a.cmd == "status":
        st = agent(s, "GET", f"/status?id={a.id}&tail={a.tail}").json(); print(st["tail"]); print("done", st["done"], "exit", st["code"])
    cost()


if __name__ == "__main__":
    main()
