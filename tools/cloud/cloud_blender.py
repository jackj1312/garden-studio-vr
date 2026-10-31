"""
Render a product's 3D shots (a Blender script) on rented RunPod GPUs and bring the frames home. Same pattern as
siteconcept-site-universe/universe/cloud/runpod_job.py (rent, upload, install Blender, run, download) with
cloud_render.py's safety: a watchdog deletes the machine past --max-min minutes or about --max-gbp pounds, the machine is
deleted in a finally (also on Ctrl-C / SIGTERM / SIGHUP) and the API is asked afterwards that it is gone.

    ~/.runpod/venv/bin/python scripts/cloud_blender.py nx1-ad [--gpus 2] [--samples 128] [--frames 30,100]
        [--shots hero,lid,end] [--max-min 45] [--max-gbp 1.0]

FAN-OUT (Jack, 18 Oct 2026): --pods N rents N separate machines AT ONCE (each --gpus GPUs) and splits the frames across
every GPU of every machine (interleaved), so wall-clock time divides by N for about the same money (billing is per
second; each machine adds ~1-2 min of setup). --cloud COMMUNITY (the default) rents Community Cloud first (an RTX 4090 is
~$0.34/h there vs ~$0.89/h Secure; research 18 Oct 2026: best Cycles performance per dollar), falling back to SECURE.
--max-gbp is the cap for the WHOLE run, split across the machines. Only 'multi' jobs fan out; bakes stay on one machine.
    e.g. the MR L.A film: ... cloud_blender.py mrla-film --bundle <dir> --pods 8 --gpus 1 --extra "--shots all" --max-gbp 4

For nx1-ad: uploads blender/nx1_jar.py and public/clients/nx1-ad/media/label.png (made by blender/nx1_label.py from
their label photo), renders each shot with one Blender process per GPU (frames interleaved), and downloads
public/clients/nx1-ad/media/3d/<shot>/####.jpg (gitignored, like all client media). Frames already at home are kept;
--frames renders a check list instead into out/nx1-ad/cloud-check/. Needs ~/.runpod/api_key (never printed) and
~/.ssh/runpod_ed25519.
"""
import tempfile, argparse, io, os, re, shlex, signal, sys, tarfile, threading, time

import paramiko
import runpod

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))   # garden-studio-vr root
BLENDER_VERSION = '5.2.2'
BLENDER_URL = f'https://download.blender.org/release/Blender5.2/blender-{BLENDER_VERSION}-linux-x64.tar.xz'
# a host that gets an error page from blender.org (18 Oct 2026) tries a mirror instead
BLENDER_MIRROR = f'https://mirrors.ocf.berkeley.edu/blender/release/Blender5.2/blender-{BLENDER_VERSION}-linux-x64.tar.xz'
IMAGE = 'runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04'
GPUS = ['NVIDIA GeForce RTX 4090', 'NVIDIA RTX 6000 Ada Generation', 'NVIDIA L40S', 'NVIDIA GeForce RTX 3090', 'NVIDIA RTX A6000',
        'NVIDIA L40', 'NVIDIA RTX A5000', 'NVIDIA RTX 4000 Ada Generation']
KEY = os.path.expanduser('~/.ssh/runpod_ed25519')
USD_PER_GBP = 1.27
MIN_MBPS = 200                  # rent() asks for machines with at least this download and upload first
JOBS = {  # slug -> (script, {remote name: local path}, script args)
    'nx1-ad': ('blender/nx1_jar.py', {'label.png': 'public/clients/nx1-ad/media/label.png'}, '--label label.png'),
}
# single jobs: one Blender process (a fluid bake can't be split across GPUs), its own args, PNG frames into `dest`
SINGLE = {
    # Garden VR: Jack's front garden rebuilt from its measured plan, light baked (Cycles) into light maps for the
    # headset, desktop + Quest GLBs exported, proof stills from the walk-video cameras. Bundle: tools/cloud/garden_bundle.sh
    'garden-bake': {'script': 'tools/cloud/garden_cloud.py', 'args': '', 'dest': 'assets/sites/front-garden-model/cloud', 'ext': 'png', 'blend': True},
    # the feed-drip ink pour with a touch of viscosity (a cohesive pool on landing), finer grid; ~1-2 h of CPU bake
    # water-thin: bakes in minutes
    'ink-pour': {'script': 'blender/ink_pour.py', 'args': '--res 256 --frames 1-44 --samples 128', 'dest': 'public/fx/ink-pour', 'ext': 'png'},
    # any FOOH .blend made self-contained by blender/bundle_blend.py: final composite over the plate + checks + MP4
    'fooh': {'script': 'blender/fooh_render.py', 'args': '--plate assets/plate.mp4 --mode final', 'dest': 'ad-mockups/fooh/cloud', 'ext': 'png', 'blend': True},  # progress = CG frames (final/cg/*.png)
    # any self-contained .blend (bundle_blend.py): its animation as JPEG frames
    'blend-frames': {'script': 'blender/render_frames.py', 'args': '', 'dest': 'out/blend-frames', 'ext': 'jpg', 'blend': True},
    # bake-then-render: a Mantaflow liquid baked inside a bundled .blend, candidate frames turned into static meshes,
    # quick Cycles previews (PNG) + the .blend with the meshes (tests_streams.blend); the final still then goes through
    # blend-frames. MR L.A perfume test still B (the stream into the 50ml).
    'stream-bake': {'script': 'blender/mrla-perfume/stream_bake.py', 'args': '', 'dest': 'ad-mockups/mrla/perfume/tests/bake', 'ext': 'png', 'blend': True},
    # THE MR L.A FILM: the pour's stream (FLIP, every frame -> stream.abc) baked inside a bundle of tests_b2_final.blend
    'mrla-film-stream': {'script': 'blender/mrla-perfume/film/film_stream_bake.py', 'args': '', 'dest': 'out/mrla-film/bake', 'ext': 'png', 'blend': True, 'cpu': True},
    # THE MR L.A FILM: the 24-scents -> hero splash (SH08c_Splash), FLIP res 320 + spray/foam/bubbles baked in a bundle of
    # film.blend (one CPU-bound Blender; Mantaflow does not use the GPU); brings home cache/{config,mesh,particles} + checks
    'mrla-film-splash': {'script': 'blender/mrla-perfume/film/film_splash_bake.py', 'args': '--res 320', 'dest': 'out/mrla-film/splash-bake', 'ext': 'png', 'blend': True, 'cpu': True, 'resumable': True},
    # THE MR L.A FILM: renders shots of a bundled film.blend (one scene per shot): --extra "--stills SH01:30,SH02:70" or
    # "--shots SH01,SH02" for the full frames; multi: one Blender per GPU, frames interleaved
    'mrla-film': {'script': 'blender/mrla-perfume/film/film_render.py', 'args': '', 'dest': 'out/mrla-film/render', 'ext': 'jpg', 'blend': True, 'multi': True},
    'ink-pour-thick': {'script': 'blender/ink_pour.py', 'args': '--res 256 --frames 1-44 --samples 128 --visc 3e-6', 'dest': 'public/fx/ink-pour-thick', 'ext': 'png'},
}


def log(*a): print('[cloud-blender]', *a, flush=True)


def api_key():
    p = os.path.expanduser('~/.runpod/api_key')
    k = os.environ.get('RUNPOD_API_KEY') or (open(p).read().strip() if os.path.exists(p) else '')
    if not k: sys.exit('No RunPod API key in ~/.runpod/api_key')
    return k


def rent(n, cloud='COMMUNITY', tag=''):
    """Rents one machine with n GPUs: the GPUS list in order (RTX 4090 first), Community Cloud first when asked, then
    Secure. Raises if nothing is free (the caller decides whether that ends the run)."""
    pub = open(KEY + '.pub').read().strip()
    order = ['COMMUNITY', 'SECURE'] if cloud == 'COMMUNITY' else [cloud]
    # fast links first (18 Oct 2026: a Community machine in Taiwan moved 1 GB at 0.25 MB/s; transfers, not renders, set
    # the pace), then any link
    for bw in (MIN_MBPS, None):
        for ct in order:
            for gpu in GPUS:
                try:
                    pod = runpod.create_pod(name='siteconcept-blender' + tag, image_name=IMAGE, gpu_type_id=gpu, gpu_count=n, cloud_type=ct,
                                            support_public_ip=True, start_ssh=True, container_disk_in_gb=40, ports='22/tcp', env={'PUBLIC_KEY': pub},
                                            min_download=bw, min_upload=bw)
                    if pod and pod.get('id'):
                        log(tag, 'rented', n, 'x', gpu, ct, f'(link {bw}+ Mbps)' if bw else '(any link)', pod['id']); return pod['id'], gpu
                except Exception as e:
                    log(tag, 'no', n, 'x', gpu, ct, f'{bw}+ Mbps' if bw else '', '-', str(e)[:70])
    raise RuntimeError('no GPU machine free right now (Community or Secure)')


CPU_INSTANCES = ['cpu5c-32-64', 'cpu3c-32-64', 'cpu5c-16-32', 'cpu3c-16-32']
CPU_IMAGE = 'runpod/base:1.4.0-ubuntu2204'


def rent_cpu(tag='', disk_gb=80, skip_cpu=False):
    """A many-core CPU machine for simulations (Mantaflow is CPU-bound; a GPU card is wasted money on a bake).
    Its /workspace is a pod volume, so a STOPPED machine keeps the bake cache and can resume."""
    pub = open(KEY + '.pub').read().strip()
    for inst in ([] if skip_cpu else CPU_INSTANCES):
        try:
            pod = runpod.create_pod(name='siteconcept-blender' + tag, image_name=CPU_IMAGE, instance_id=inst, cloud_type='SECURE',
                                    start_ssh=True, container_disk_in_gb=20, volume_in_gb=disk_gb, volume_mount_path='/workspace',
                                    ports='22/tcp', env={'PUBLIC_KEY': pub})
            if pod and pod.get('id'):
                log(tag, 'rented CPU', inst, pod['id']); return pod['id'], inst
        except Exception as e:
            log(tag, 'no', inst, '-', str(e)[:70])
    # no CPU machine: a GPU machine with at least 16 vCPUs (the GPU idles; the simulation uses the cores)
    for ct in ('COMMUNITY', 'SECURE'):
        for gpu in GPUS:
            try:
                pod = runpod.create_pod(name='siteconcept-blender' + tag, image_name=IMAGE, gpu_type_id=gpu, gpu_count=1, cloud_type=ct,
                                        min_vcpu_count=16, support_public_ip=True, start_ssh=True, container_disk_in_gb=20,
                                        volume_in_gb=disk_gb, volume_mount_path='/workspace', ports='22/tcp', env={'PUBLIC_KEY': pub})
                if pod and pod.get('id'):
                    log(tag, 'rented', gpu, ct, '(16+ vCPUs, for the simulation)', pod['id']); return pod['id'], gpu
            except Exception as e:
                log(tag, 'no', gpu, ct, '16 vCPU -', str(e)[:60])
    raise RuntimeError('no machine with 16+ vCPUs free right now')


def stop(pod_id):
    """Pauses a machine but keeps its /workspace volume (a resumable bake's cache). Small storage charge only."""
    for _ in range(5):
        try: runpod.stop_pod(pod_id); return True
        except Exception as e: log('stop failed, retrying:', str(e)[:120]); time.sleep(5)
    return False


def ssh_address(pod_id, timeout=600):
    t0 = time.time()
    while time.time() - t0 < timeout:
        pod = runpod.get_pod(pod_id) or {}
        for p in ((pod.get('runtime') or {}).get('ports') or []):
            if p.get('privatePort') == 22 and p.get('isIpPublic'): return p['ip'], p['publicPort']
        time.sleep(5)
    raise TimeoutError('the machine never opened SSH')


def connect(ip, port):
    for _ in range(40):
        try:
            c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            c.connect(ip, port=port, username='root', key_filename=KEY, timeout=15, banner_timeout=30)
            c.get_transport().set_keepalive(30); return c
        except Exception:
            time.sleep(5)
    raise TimeoutError('could not log in to the machine')


def run(c, cmd, quiet=False):
    chan = c.get_transport().open_session(); chan.get_pty(); chan.exec_command(f'bash -o pipefail -c {shlex.quote(cmd)}')
    for line in chan.makefile('r'):
        if not quiet: print('  |', line.rstrip()[:200], flush=True)
    code = chan.recv_exit_status()
    if code: raise RuntimeError(f'remote command failed ({code}): {cmd[:80]}')


def out_(c, cmd):
    _, o, _ = c.exec_command(cmd, timeout=60); return o.read().decode()


def terminate(pod_id):
    for _ in range(5):
        try: runpod.terminate_pod(pod_id); return True
        except Exception as e:
            if 'not found' in str(e).lower(): return True
            log('delete failed, retrying:', str(e)[:120]); time.sleep(5)
    return False


def gone(pod_id):
    for _ in range(12):
        try:
            if pod_id not in [p['id'] for p in (runpod.get_pods() or [])]: return True
        except Exception: pass
        time.sleep(5)
    return False


def main():
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    signal.signal(signal.SIGHUP, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    ap = argparse.ArgumentParser()
    ap.add_argument('slug', choices=list(JOBS) + list(SINGLE))
    ap.add_argument('--gpus', type=int, default=2)
    ap.add_argument('--samples', type=int, default=128)
    ap.add_argument('--shots', default='hero,lid,end')
    ap.add_argument('--frames', default='', help='a check list, e.g. "30,100" (rendered for every shot), into out/<slug>/cloud-check/')
    ap.add_argument('--max-min', type=float, default=45)
    ap.add_argument('--max-gbp', type=float, default=1.0)
    ap.add_argument('--bundle', default='', help='fooh: the bundle dir made by blender/bundle_blend.py (scene.blend + assets/)')
    ap.add_argument('--dest', default='', help='where the results land (default per job)')
    ap.add_argument('--extra', default='', help='extra args for the job script, e.g. "--frames 1-150 --samples 64"')
    ap.add_argument('--pods', type=int, default=1, help='machines rented at once (multi jobs only); frames split across all of them')
    ap.add_argument('--gpu-for-sim', action='store_true', help='simulations: skip the CPU-only machines (slow to start tonight) and take a 16+ vCPU GPU machine')
    ap.add_argument('--seed-from', default='', help='POD:SRC:DST[:a,b]: before the job, that running machine hands SRC (only '
                    'subfolders a,b if given) straight to this one at DST, with a one-off key (never via the Mac: 18 Oct 2026, a 1 GB '
                    'splash cache crawled home from Taiwan at 0.25 MB/s while the machine uploaded at 66 MB/s)')
    ap.add_argument('--seed-link', default='', help='a symlink made to DST after seeding, e.g. the path the scene reads')
    ap.add_argument('--cloud', default='COMMUNITY', choices=['COMMUNITY', 'SECURE'], help='COMMUNITY first (cheaper), falling back to SECURE')
    a = ap.parse_args()
    runpod.api_key = api_key()

    one = SINGLE.get(a.slug)
    if one:
        script, assets, sargs = one['script'], {}, one['args']
        if not one.get('multi'): a.gpus = 1
    else: script, assets, sargs = JOBS[a.slug]
    ext = one['ext'] if one else 'jpg'
    check = bool(a.frames) and not one
    if one and one.get('blend') and not a.bundle: sys.exit('this job needs --bundle <dir> (blender/bundle_blend.py)')
    if a.extra: sargs += ' ' + a.extra
    if one and one.get('resumable') and 'cache_resumable = True' not in open(os.path.join(ROOT, script)).read():
        sys.exit(f'refusing: {script} is a simulation bake but does not set cache_resumable = True (a stopped bake would be lost)')
    dest = os.path.abspath(a.dest) if a.dest else os.path.join(ROOT, one['dest']) if one else os.path.join(ROOT, 'out', a.slug, 'cloud-check') if check else os.path.join(ROOT, 'public', 'clients', a.slug, 'media', '3d')
    # the bundle is packed to a file on disk and streamed up (an in-memory bundle of a GB would strain the 8 GB Mac)
    pack = os.path.join(tempfile.gettempdir(), f'siteconcept-bundle-{os.getpid()}.tgz')
    with tarfile.open(pack, mode='w:gz', compresslevel=1) as t:
        t.add(os.path.join(ROOT, script), arcname=os.path.basename(script))
        for name, local in assets.items(): t.add(os.path.join(ROOT, local), arcname=name)
        if one and one.get('blend'):
            for name in os.listdir(a.bundle): t.add(os.path.join(a.bundle, name), arcname=name)
    log('bundle', os.path.getsize(pack) >> 10, 'KB')
    import atexit; atexit.register(lambda: os.path.exists(pack) and os.remove(pack))

    pods = max(1, a.pods) if (one and one.get('multi')) or not one else 1
    workers = pods * a.gpus
    lock = threading.Lock(); results = []

    def machine(k):
        tag = f'[{k + 1}/{pods}]' if pods > 1 else ''
        def say(*m): log(tag, *m)
        try:
            pod_id, gpu = rent_cpu(tag, skip_cpu=a.gpu_for_sim) if (one and one.get('cpu')) else rent(a.gpus, a.cloud, tag)
        except Exception as e:
            say('FAILED to rent:', str(e)[:120]); results.append((k, False, 0.0)); return
        t0 = time.time()
        usd_h = float((runpod.get_pod(pod_id) or {}).get('costPerHr') or 0) or 0.69 * a.gpus
        cap_min = min(a.max_min, (a.max_gbp / pods) * USD_PER_GBP / usd_h * 60)
        say(f'${usd_h:.2f}/h; hard cap {cap_min:.0f} min')
        capped = threading.Event()

        keep = bool(one and one.get('resumable'))

        def watchdog():
            capped.set()
            if keep:
                say(f'CAP REACHED ({cap_min:.0f} min): PAUSING the machine (its bake cache is kept; re-run to resume): {pod_id}'); stop(pod_id)
            else:
                say(f'CAP REACHED ({cap_min:.0f} min): deleting the machine'); terminate(pod_id)
        timer = threading.Timer(cap_min * 60, watchdog); timer.daemon = True; timer.start()
        ok_run = False
        try:
            ip, port = ssh_address(pod_id); c = connect(ip, port); say('connected', f'{time.time() - t0:.0f}s')
            run(c, 'mkdir -p /workspace/job && ((command -v xz >/dev/null && ldconfig -p | grep -q libXi.so.6) || '
                   '(apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq xz-utils libx11-6 libxi6 libxxf86vm1 libxfixes3 libxrender1 libgl1 libxkbcommon0 libsm6 libice6 libegl1 >/dev/null))', quiet=True)
            sftp = c.open_sftp()
            tu = time.time(); sftp.put(pack, '/workspace/job/bundle.tgz'); say(f'bundle up in {time.time() - tu:.0f}s')
            run(c, f'cd /workspace && ( [ -x blender/blender ] || ( ( curl -fsSL --retry 3 {BLENDER_URL} -o b.tar.xz || curl -fsSL --retry 3 {BLENDER_MIRROR} -o b.tar.xz ) && tar -xf b.tar.xz && mv blender-{BLENDER_VERSION}-linux-x64 blender && rm b.tar.xz ) ) '
                   '&& cd /workspace/job && tar -xzf bundle.tgz && ' + ('echo "$(nproc) CPUs"; nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null || true' if (one and one.get('cpu')) else 'nvidia-smi --query-gpu=name,memory.total --format=csv,noheader'), quiet=pods > 1)
            say('blender ready', f'{time.time() - t0:.0f}s')
            if a.seed_from:
                sp, src, dst, *sub = a.seed_from.split(':')
                paths = ' '.join(shlex.quote(x) for x in (sub[0].split(',') if sub else ['.']))
                sc_ = connect(*ssh_address(sp, timeout=60))
                # a one-off key made on the source machine and trusted only by this new one; both machines are deleted after
                out_(sc_, 'rm -f /root/xfer /root/xfer.pub; ssh-keygen -q -t ed25519 -N "" -f /root/xfer')
                pubk = out_(sc_, 'cat /root/xfer.pub').strip()
                out_(c, f'mkdir -p /root/.ssh {dst} && echo {shlex.quote(pubk)} >> /root/.ssh/authorized_keys')
                ts = time.time()
                _, o, e = sc_.exec_command(f'tar -C {src} -cf - {paths} | ssh -i /root/xfer -p {port} -o StrictHostKeyChecking=no '
                                           f'-o UserKnownHostsFile=/dev/null -o LogLevel=ERROR root@{ip} "tar -C {dst} -xf -" && echo SEEDED', timeout=3600)
                res = o.read().decode()
                out_(sc_, 'rm -f /root/xfer /root/xfer.pub'); sc_.close()
                out_(c, f'grep -vF {shlex.quote(pubk.split()[1])} /root/.ssh/authorized_keys > /tmp/ak; cat /tmp/ak > /root/.ssh/authorized_keys')
                if 'SEEDED' not in res: raise RuntimeError('seeding failed: ' + e.read().decode()[:300])
                if a.seed_link: out_(c, f'ln -sfn {dst} {a.seed_link}')
                say(f'seeded {dst} ({out_(c, f"du -sh {dst} | cut -f1").strip()}) from {sp} in {time.time() - ts:.0f}s')
            fr = f' --frames {a.frames}' if check else ''
            for i in range(a.gpus):  # one Blender per GPU; frames interleaved across EVERY GPU of every machine
                w = k * a.gpus + i
                rest = (f' --every {workers} --offset {w}' if one.get('multi') else '') if one else f' --shots {a.shots} --samples {a.samples} --every {workers} --offset {w}{fr}'
                blend = ' scene.blend' if one and one.get('blend') else ''
                cmd = (f'cd /workspace/job && CUDA_VISIBLE_DEVICES={i} /workspace/blender/blender -b --factory-startup{blend} --python-exit-code 1 --python {os.path.basename(script)} -- '
                       f'{sargs} --out /workspace/out{rest} > /root/r{i}.log 2>&1; echo $? > /root/r{i}.exit')
                out_(c, f'setsid nohup bash -c {shlex.quote(cmd)} > /dev/null 2>&1 < /dev/null & echo started')
            say(f'rendering on {a.gpus} GPU(s)')
            last = -1; tr = time.time()
            while True:
                try:
                    n = int(out_(c, f'find /workspace/out -maxdepth 3 -name "*.{ext}" 2>/dev/null | wc -l').strip() or 0)
                    ex = [out_(c, f'cat /root/r{i}.exit 2>/dev/null').strip() for i in range(a.gpus)]
                except Exception as e:
                    say('connection dropped, reconnecting:', str(e)[:80]); c = connect(ip, port); continue
                if one and one.get('cpu'):
                    try:
                        m = int(out_(c, "find /workspace/out -path '*/data/*' -name 'fluid_data_*' 2>/dev/null | wc -l").strip() or 0)
                        tot = re.search(r'frames \((\d+), (\d+)\)', out_(c, 'head -c 4000 /root/r0.log'))
                        if tot and m and m != getattr(machine, '_m', -1):
                            T = int(tot.group(2)) - int(tot.group(1)) + 1; el = (time.time() - tr) / 60
                            proj = el / m * T
                            say(f'bake {m}/{T} frames, {el:.0f} min so far, projected {proj:.0f} min of {cap_min:.0f} min cap' + ('  WARNING: will pass the cap' if proj > cap_min * 0.95 else ''))
                            machine._m = m
                    except Exception: pass
                if n != last:
                    el = time.time() - tr
                    say(f'{n} frames ({el / max(n, 1):.1f} s a frame on this machine) {time.time() - t0:.0f}s'); last = n
                if all(e != '' for e in ex):
                    if any(e not in ('0', '2') for e in ex):
                        print(out_(c, 'tail -30 /root/r0.log'))
                        raise RuntimeError(f'blender failed: exits {ex}')
                    break
                time.sleep(15)
            say('rendered', f'{time.time() - tr:.0f}s')
            if not n: print(out_(c, 'tail -30 /root/r0.log')); raise RuntimeError('no frames rendered')
            run(c, 'cd /workspace/out && tar --exclude=./_cache --exclude=./cache/data --exclude=./cache/guiding --exclude=./cache/noise -cf /workspace/out.tar .', quiet=True)
            sftp = c.open_sftp(); os.makedirs(dest, exist_ok=True)
            tmp = os.path.join(dest, f'.download-{k}.tar')       # streamed to disk, never held in memory (8 GB Mac)
            sftp.get('/workspace/out.tar', tmp)
            size = os.path.getsize(tmp)
            with lock:  # every machine's frames land in the same folder
                with tarfile.open(tmp) as t: t.extractall(dest)
            os.remove(tmp)
            say('downloaded', size >> 20, 'MB ->', dest); ok_run = True
            ck = os.path.join(dest, 'checks.json')
            if os.path.exists(ck) and pods == 1: say('checks:', open(ck).read()[:600])
        except Exception as e:
            say('FAILED:', 'cap reached' if capped.is_set() else str(e)[:300])
        finally:
            timer.cancel()
            mins = (time.time() - t0) / 60
            if keep and not ok_run:
                stop(pod_id)
                say(f'machine PAUSED with its bake cache kept ({pod_id}). Resume: start it at runpod.io/console/pods and re-run, or delete it there to stop the small storage charge.')
            else:
                okd = terminate(pod_id); verified = gone(pod_id)
                say(f'{a.gpus} x {gpu}: machine {"deleted" if okd else "NOT DELETED"}; API check: {"gone" if verified else "STILL LISTED - delete it at runpod.io/console/pods: " + pod_id}')
            usd = usd_h * mins / 60
            say(f'elapsed {mins:.1f} min, about ${usd:.2f} (~£{usd / USD_PER_GBP:.2f})')
            results.append((k, ok_run, usd))

    t_all = time.time()
    threads = [threading.Thread(target=machine, args=(k,), daemon=True) for k in range(pods)]
    try:
        for th in threads: th.start(); time.sleep(2)   # stagger the rentals a little
        for th in threads: th.join()
    except KeyboardInterrupt:
        log('interrupted: every machine is deleted by its own finally'); raise
    total = sum(r[2] for r in results); good = sum(1 for r in results if r[1])
    log(f'ALL DONE: {good}/{pods} machines delivered; {((time.time() - t_all) / 60):.1f} min wall-clock; about ${total:.2f} (~£{total / USD_PER_GBP:.2f}) in total')
    if good < pods:
        log('some frames are missing: re-run the same command; frames already at home are kept by the job scripts that skip done frames')
        sys.exit(1)


if __name__ == '__main__':
    main()
