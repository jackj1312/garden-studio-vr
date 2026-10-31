"""Run the Unreal step on a rented GPU (WORKFLOW G8). Same safety as tools/cloud/cloud_blender.py: hard money cap,
watchdog, the pod is deleted in a finally and checked gone.
    ~/.runpod/venv/bin/python tools/unreal/cloud_ue.py --usd out/unreal --site assets/sites/front-garden-model \
        [--image ghcr.io/epicgames/unreal-engine:dev-slim-5.8] [--auth ghcr-epic] [--max-gbp 5] [--max-min 120]
Needs Jack's one-time access (README.md): GitHub linked to Epic, and RunPod registry auth named `ghcr-epic`."""
import argparse, os, sys, tarfile, tempfile, threading
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "cloud"))
import runpod, cloud_blender as cb

ap = argparse.ArgumentParser()
ap.add_argument("--usd", required=True); ap.add_argument("--site", required=True)
ap.add_argument("--image", default="ghcr.io/epicgames/unreal-engine:dev-slim-5.8")
ap.add_argument("--auth", default="ghcr-epic"); ap.add_argument("--max-gbp", type=float, default=5.0); ap.add_argument("--max-min", type=float, default=120)
ap.add_argument("--dest", default="renders/front-garden/unreal")
a = ap.parse_args()
runpod.api_key = cb.api_key()
auths = {x.get("name"): x.get("id") for x in (runpod.get_container_registry_auths() if hasattr(runpod, "get_container_registry_auths") else [])}
if a.auth not in auths:
    sys.exit(f"RunPod has no registry auth named '{a.auth}' yet: see tools/unreal/README.md (Jack's one-time step)")
pack = os.path.join(tempfile.gettempdir(), f"ue-job-{os.getpid()}.tgz")
with tarfile.open(pack, "w:gz", compresslevel=1) as t:
    t.add(a.usd, arcname="usd"); t.add(os.path.join(a.site, "site.json"), arcname="site.json")
    t.add(os.path.join(a.site, "refs.json"), arcname="cams.json")
    t.add(os.path.join(os.path.dirname(os.path.abspath(__file__)), "garden_ue.py"), arcname="garden_ue.py")
pub = open(cb.KEY + ".pub").read().strip(); pod_id = None
try:
    for gpu in ("NVIDIA GeForce RTX 4090", "NVIDIA L40", "NVIDIA L40S", "NVIDIA RTX A6000"):
        try:
            pod = runpod.create_pod(name="garden-unreal", image_name=a.image, gpu_type_id=gpu, gpu_count=1, cloud_type="COMMUNITY",
                                    container_registry_auth_id=auths[a.auth], support_public_ip=True, start_ssh=True,
                                    container_disk_in_gb=80, ports="22/tcp", env={"PUBLIC_KEY": pub})
            pod_id = pod["id"]; print("rented", gpu, pod_id); break
        except Exception as e:
            print("no", gpu, str(e)[:80])
    if not pod_id: sys.exit("no GPU free")
    rate = (runpod.get_pod(pod_id) or {}).get("costPerHr", 0.9)
    cap_min = min(a.max_min, a.max_gbp * cb.USD_PER_GBP / max(rate, 0.1) * 60)
    print(f"${rate}/h; hard cap {cap_min:.0f} min")
    timer = threading.Timer(cap_min * 60, lambda: cb.terminate(pod_id)); timer.daemon = True; timer.start()
    ip, port = cb.ssh_address(pod_id, timeout=1800); c = cb.connect(ip, port)
    sftp = c.open_sftp(); cb.run(c, "mkdir -p /job/out"); sftp.put(pack, "/job/job.tgz"); cb.run(c, "cd /job && tar -xzf job.tgz")
    cb.run(c, "cd /job && UE=$(ls -d /home/ue*/UnrealEngine 2>/dev/null | head -1); echo engine $UE; "
              "$UE/Engine/Binaries/Linux/UnrealEditor-Cmd -run=pythonscript "
              "-script=\"/job/garden_ue.py --usd /job/usd/garden.usdc --site /job/site.json --cams /job/cams.json --out /job/out\" "
              "-RenderOffscreen -unattended -nosplash 2>&1 | tail -40")
    os.makedirs(a.dest, exist_ok=True); cb.run(c, "cd /job/out && tar -cf /job/out.tar .", quiet=True)
    sftp.get("/job/out.tar", os.path.join(a.dest, "out.tar"))
    with tarfile.open(os.path.join(a.dest, "out.tar")) as t: t.extractall(a.dest)
    print("downloaded to", a.dest)
finally:
    if pod_id: print("deleted", cb.terminate(pod_id), "gone", cb.gone(pod_id))
