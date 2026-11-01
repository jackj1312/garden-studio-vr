"""
Train a 3D Gaussian Splat of a site ("as it is today") from its walk video on a rented RunPod GPU, and bring home the
raw .ply, web-compressed copies (.sog / .compressed.ply, full and Quest-light) and held-out matched views. Same safety as
cloud_blender.py (whose rent / SSH / delete helpers it reuses): a watchdog deletes the machine past the money cap, the
machine is deleted in a finally (also on Ctrl-C / SIGTERM / SIGHUP), and the API is asked afterwards that it is gone.
Nothing heavy runs on the Mac: it only packs the existing solve (walk frames, in metres) and uploads.

    ~/.runpod/venv/bin/python tools/cloud/cloud_splat.py --site ~/Desktop/garden-scans/front-garden \
        --video ~/Desktop/garden-scans/20494.mp4 --max-gbp 2.0 [--fps 4] [--steps 30000] [--cap 1500000]

--site needs sfm2/sparse/0 (COLMAP), sfm2/images, sfm2/aligned.json (scale, R, t into the site's metres). Results land in
<site>/splat-test/ (private, never in the repo). The pod side is tools/cloud/splat_pod.sh + splat_pod.py.
"""
import argparse, json, os, shlex, signal, subprocess, sys, tarfile, tempfile, threading, time

import runpod

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cloud_blender as cb   # rent, ssh_address, connect, out_, terminate, gone, api_key, KEY, USD_PER_GBP

HERE = os.path.dirname(os.path.abspath(__file__))
SPLAT_PY = os.path.expanduser('~/splat/bin/python')   # has pycolmap (light work only: rewrite a text model)

PREP = r'''
import json, sys, numpy as np, pycolmap
site, out = sys.argv[1], sys.argv[2]
r = pycolmap.Reconstruction(f'{site}/sfm2/sparse/0'); d = json.load(open(f'{site}/sfm2/aligned.json'))
r.transform(pycolmap.Sim3d(d['scale'], pycolmap.Rotation3d(np.array(d['R'])), np.array(d['t'])))
for im in list(r.images.values()):
    if not im.name.startswith('walk'): r.deregister_frame(im.frame_id)   # stills are months older: not "today"
r.write_text(out)
import os; b = os.path.join(os.path.dirname(out), 'bin'); os.makedirs(b, exist_ok=True); r.write_binary(b)
print(r.num_reg_images(), 'walk frames in metres')
'''


def log(*a): print('[cloud-splat]', *a, flush=True)


def scp(port, ip, src, dst, up=True):
    o = ['-P', str(port), '-i', cb.KEY, '-o', 'StrictHostKeyChecking=no', '-o', 'UserKnownHostsFile=/dev/null', '-o', 'LogLevel=ERROR',
         '-o', 'ServerAliveInterval=30', '-q']
    a, b = (src, f'root@{ip}:{dst}') if up else (f'root@{ip}:{src}', dst)
    subprocess.run(['scp', *o, a, b], check=True)


def main():
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    signal.signal(signal.SIGHUP, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    ap = argparse.ArgumentParser()
    ap.add_argument('--site', required=True)
    ap.add_argument('--video', required=True)
    ap.add_argument('--max-gbp', type=float, default=2.0)
    ap.add_argument('--fps', type=float, default=4)
    ap.add_argument('--steps', type=int, default=30000)
    ap.add_argument('--cap', type=int, default=1_500_000)
    ap.add_argument('--quest', type=int, default=700_000)
    ap.add_argument('--solve', default='', help='a data/sparse folder brought home by an earlier run (skips the camera solve)')
    ap.add_argument('--cloud', default='COMMUNITY', choices=['COMMUNITY', 'SECURE'])
    a = ap.parse_args()
    site = os.path.abspath(os.path.expanduser(a.site)); video = os.path.abspath(os.path.expanduser(a.video))
    dest = os.path.join(site, 'splat-test'); os.makedirs(dest, exist_ok=True)
    runpod.api_key = cb.api_key()

    # 1. pack the existing solve (walk frames only, already in metres) + the pod scripts
    tmp = tempfile.mkdtemp(prefix='splat-'); fb = os.path.join(tmp, 'fallback'); os.makedirs(f'{fb}/sparse/0')
    print(subprocess.run([SPLAT_PY, '-c', PREP, site, f'{fb}/sparse/0'], check=True, capture_output=True, text=True).stdout.strip())
    names = [l.split()[9] for l in open(f'{fb}/sparse/0/images.txt') if not l.startswith('#') and len(l.split()) == 10]
    pack = os.path.join(tmp, 'bundle.tgz')
    with tarfile.open(pack, 'w:gz', compresslevel=1) as t:
        for f in ('splat_pod.py', 'splat_pod.sh'): t.add(os.path.join(HERE, f), arcname=f)
        t.add(f'{fb}/sparse', arcname='fallback/sparse')
        for n in names: t.add(f'{site}/sfm2/images/{n}', arcname=f'fallback/images/{n}')
        if a.solve: t.add(os.path.abspath(os.path.expanduser(a.solve)), arcname='solve/sparse')
    log('bundle', os.path.getsize(pack) >> 20, 'MB;', len(names), 'frames of the existing solve; video', os.path.getsize(video) >> 20, 'MB')

    pod_id, gpu = cb.rent(1, a.cloud, '-splat')
    t0 = time.time(); ok = False
    usd_h = float((runpod.get_pod(pod_id) or {}).get('costPerHr') or 0) or 0.69
    cap_min = a.max_gbp * cb.USD_PER_GBP / usd_h * 60
    log(f'{gpu} ${usd_h:.2f}/h; hard cap {cap_min:.0f} min (£{a.max_gbp})')
    capped = threading.Event()
    def watchdog(): capped.set(); log(f'CAP REACHED ({cap_min:.0f} min): deleting the machine'); cb.terminate(pod_id)
    timer = threading.Timer(cap_min * 60, watchdog); timer.daemon = True; timer.start()
    try:
        ip, port = cb.ssh_address(pod_id); c = cb.connect(ip, port); log('connected', f'{time.time() - t0:.0f}s')
        cb.out_(c, 'mkdir -p /workspace/job')
        tu = time.time(); scp(port, ip, pack, '/workspace/job/bundle.tgz'); log(f'bundle up in {time.time() - tu:.0f}s')
        cb.out_(c, 'cd /workspace/job && tar -xzf bundle.tgz && chmod +x splat_pod.sh')
        cmd = f'cd /workspace/job && ./splat_pod.sh {a.fps} {a.steps} {a.cap} {a.quest} > /root/job.log 2>&1; echo $? > /root/job.exit'
        cb.out_(c, f'setsid nohup bash -c {shlex.quote(cmd)} > /dev/null 2>&1 < /dev/null & echo started')
        log('job started; uploading the walk video alongside the installs')
        up = {}
        def upload():
            try:
                tv = time.time(); scp(port, ip, video, '/workspace/job/video.part')
                up['s'] = time.time() - tv
                cb.out_(c2, 'mv /workspace/job/video.part /workspace/job/video.mp4 && touch /workspace/job/video.done')
            except Exception as e: up['err'] = str(e)
        c2 = cb.connect(ip, port)
        th = threading.Thread(target=upload, daemon=True); th.start()
        seen = 0; said_up = False
        while True:
            time.sleep(30)
            if capped.is_set(): raise RuntimeError('cap reached')
            try:
                lines = cb.out_(c, 'cat /root/job.log 2>/dev/null').splitlines()
                ex = cb.out_(c, 'cat /root/job.exit 2>/dev/null').strip()
                prog = cb.out_(c, "tail -c 400 /root/train.log 2>/dev/null | tr '\\r' '\\n' | grep -a -o '[0-9]*/[0-9]* \\[[^]]*\\]' | tail -1").strip()
            except Exception as e:
                log('connection dropped, reconnecting:', str(e)[:80]); c = cb.connect(ip, port); continue
            for l in lines[seen:]: print('  |', l[:220], flush=True)
            seen = len(lines)
            mins = (time.time() - t0) / 60
            if 's' in up and not said_up: log(f'video up in {up["s"] / 60:.1f} min'); said_up = True
            if 'err' in up: raise RuntimeError('video upload failed: ' + up['err'][:200])
            if prog: log(f'training {prog}  ·  {mins:.0f} min, ~£{usd_h * mins / 60 / cb.USD_PER_GBP:.2f}')
            if ex:
                if ex != '0': raise RuntimeError(f'pod job failed (exit {ex})')
                break
        # 2. bring it home: everything in out/ except checkpoints and the duplicate .ply, plus the new solve
        cb.out_(c, 'cd /workspace/job && tar --exclude=out/train/ckpts --exclude=out/train/ply --exclude=out/train/renders '
                   '--exclude=out/train/tb -cf /workspace/out.tar out data/sparse')
        log('downloading', cb.out_(c, 'du -h /workspace/out.tar | cut -f1').strip())
        td = time.time(); tar = os.path.join(dest, '.download.tar'); scp(port, ip, '/workspace/out.tar', tar, up=False)
        with tarfile.open(tar) as t: t.extractall(dest)
        os.remove(tar); log(f'downloaded in {time.time() - td:.0f}s ->', dest); ok = True
    except Exception as e:
        log('FAILED:', 'cap reached' if capped.is_set() else str(e)[:400])
        try: print(cb.out_(c, 'tail -60 /root/job.log; tail -30 /root/trainer_setup.log'))
        except Exception: pass
        # salvage before the machine goes: the camera solve and logs cost real time to make (run 1 lost a 30-min solve)
        if not capped.is_set():
            try:
                cb.out_(c, 'cd /workspace/job && tar --exclude=out/train/ckpts -cf /workspace/salvage.tar data/sparse out /root/*.log 2>/dev/null; ls -la /workspace/salvage.tar')
                sv = os.path.join(dest, f'salvage-{time.strftime("%H%M")}'); os.makedirs(sv, exist_ok=True)
                scp(port, ip, '/workspace/salvage.tar', os.path.join(sv, 'salvage.tar'), up=False); log('salvaged solve + logs ->', sv)
            except Exception as e2: log('salvage failed:', str(e2)[:120])
    finally:
        timer.cancel(); mins = (time.time() - t0) / 60
        okd = cb.terminate(pod_id); verified = cb.gone(pod_id)
        log(f'{gpu}: machine {"deleted" if okd else "NOT DELETED"}; API check: {"gone" if verified else "STILL LISTED - delete it at runpod.io/console/pods: " + pod_id}')
        usd = usd_h * mins / 60
        log(f'elapsed {mins:.1f} min, about ${usd:.2f} (~£{usd / cb.USD_PER_GBP:.2f})')
        json.dump({'pod': pod_id, 'gpu': gpu, 'usd_h': usd_h, 'minutes': mins, 'usd': usd, 'gbp': usd / cb.USD_PER_GBP, 'ok': ok},
                  open(os.path.join(dest, f'cost-{time.strftime("%Y%m%d-%H%M")}.json'), 'w'))
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
