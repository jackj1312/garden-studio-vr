"""
Runs ON the rented machine for cloud_splat.py (never on the Mac). Four stages, each its own command:

  preflight (system python + gsplat)   gsplat's reader + a 60-step training on the existing solve, before the long solve
  sfm    (in the pycolmap-cuda12 venv) frames from the walk video -> camera solve -> locked to the site's metric frame
  train  (system python + gsplat)      3D Gaussian Splat, MCMC, ~30k steps, held-out views every 8th frame
  post   (system python)               raw .ply kept, a lighter copy for the Quest, which held-out frame is which

    python splat_pod.py sfm   --job /workspace/job --fps 4
    python splat_pod.py train --job /workspace/job --steps 30000 --cap 1500000
    python splat_pod.py post  --job /workspace/job --quest 700000

Inputs in --job: video.mp4 (the walk), fallback/ (the site's existing solve already in metres, walk frames only:
sparse/0 as text + images/), from cloud_splat.py. The metric lock: every frame of the existing solve is found in the
new frames by picture (thumbnail difference), and the new solve is moved onto the old one's camera centres (Umeyama
similarity). If the new solve is worse than the old one, training uses the old one.
"""
import argparse, json, os, shutil, subprocess, sys, time

import numpy as np


def log(*a): print('[pod]', time.strftime('%H:%M:%S'), *a, flush=True)


def sh(cmd):
    log('$', cmd[:160]); subprocess.run(cmd, shell=True, check=True)


def umeyama(src, dst):
    """Similarity (s, R, t) with dst ~ s R src + t."""
    mu_s, mu_d = src.mean(0), dst.mean(0)
    A, B = src - mu_s, dst - mu_d
    U, D, Vt = np.linalg.svd(B.T @ A / len(src))
    S = np.eye(3)
    if np.linalg.det(U) * np.linalg.det(Vt) < 0: S[2, 2] = -1
    R = U @ S @ Vt
    s = np.trace(np.diag(D) @ S) / A.var(0).sum()
    return s, R, mu_d - s * R @ mu_s


def sfm(a):
    import cv2, pycolmap as p
    J = a.job; fr = f'{J}/frames'; os.makedirs(fr, exist_ok=True)
    # 1. frames: portrait 1080 x 1920 (ffmpeg applies the phone's rotation), a.fps per second
    if len(os.listdir(fr)) < 10:
        sh(f'ffmpeg -loglevel error -i {J}/video.mp4 -vf "fps={a.fps},scale=1080:1920:flags=lanczos" -q:v 2 {fr}/f_%04d.jpg')
    names = sorted(os.listdir(fr)); log(len(names), 'frames extracted')
    # 2. drop motion-blurred frames: sharpness below 0.55 x the median of their 9 neighbours
    sharp = []
    for n in names:
        g = cv2.imread(f'{fr}/{n}', cv2.IMREAD_GRAYSCALE); g = cv2.resize(g, (540, 960))
        sharp.append(cv2.Laplacian(g, cv2.CV_64F).var())
    sharp = np.array(sharp); keep = []
    for i, n in enumerate(names):
        med = np.median(sharp[max(0, i - 4):i + 5])
        if sharp[i] >= 0.55 * med: keep.append(n)
    blurry = sorted(set(names) - set(keep))
    os.makedirs(f'{J}/blurry', exist_ok=True)
    for n in blurry: shutil.move(f'{fr}/{n}', f'{J}/blurry/{n}')
    names = keep; log(f'{len(blurry)} blurry frames set aside, {len(names)} kept')
    if os.path.isdir(f'{J}/solve/sparse/0'):   # a solve brought back from an earlier run (cloud_splat.py --solve)
        data = f'{J}/data'; shutil.rmtree(data, ignore_errors=True); os.makedirs(f'{data}/sparse')
        shutil.copytree(f'{J}/solve/sparse', f'{data}/sparse', dirs_exist_ok=True); os.symlink(fr, f'{data}/images')
        json.dump({'used': 'solve from an earlier run', 'frames': len(names)}, open(f'{J}/out/sfm.json', 'w')); log('using the uploaded solve'); return
    # 3. which new frame is each frame of the existing solve (thumbnail difference)
    ref = p.Reconstruction(f'{J}/fallback/sparse/0')
    ref_c = {im.name: im.projection_center() for im in ref.images.values()}
    thumb = lambda path: cv2.resize(cv2.imread(path, cv2.IMREAD_GRAYSCALE), (54, 96), interpolation=cv2.INTER_AREA).astype(np.float32)
    T = np.stack([thumb(f'{fr}/{n}') for n in names])
    match = {}
    for rn in sorted(ref_c):
        d = ((T - thumb(f'{J}/fallback/images/{rn}')[None]) ** 2).mean((1, 2))
        k = int(d.argmin()); match[rn] = (names[k], float(d[k]))
    errs = sorted(v[1] for v in match.values()); log(f'refs matched by picture: median diff {errs[len(errs) // 2]:.1f}, worst {errs[-1]:.1f}')
    # 4. features + pairs (neighbours, plus every 3rd frame against every 3rd frame for revisits) + matching
    db = f'{J}/sfm/database.db'; os.makedirs(f'{J}/sfm', exist_ok=True)
    if os.path.exists(db): os.remove(db)
    ro = p.ImageReaderOptions(); ro.camera_model = 'SIMPLE_RADIAL'; ro.camera_params = a.cam
    eo = p.FeatureExtractionOptions(); eo.sift.max_num_features = 8192
    t0 = time.time()
    p.extract_features(db, fr, image_names=names, camera_mode=p.CameraMode.SINGLE, reader_options=ro, extraction_options=eo)
    log(f'features in {time.time() - t0:.0f}s')
    pairs = set()
    for i, x in enumerate(names):
        for y in names[i + 1:i + 1 + a.window]: pairs.add((x, y))
    sub = names[::3]
    for i, x in enumerate(sub):
        for y in sub[i + 4:]: pairs.add((x, y))
    pf = f'{J}/sfm/pairs.txt'; open(pf, 'w').write('\n'.join(f'{x} {y}' for x, y in sorted(pairs)))
    po = p.ImportedPairingOptions(); po.match_list_path = pf
    t0 = time.time(); p.match_image_pairs(db, pairing_options=po); log(f'{len(pairs)} pairs matched in {time.time() - t0:.0f}s')
    # 5. global SfM (GLOMAP) first; incremental if it leaves frames out
    out = f'{J}/sfm/sparse'; shutil.rmtree(out, ignore_errors=True); os.makedirs(out + '/g'); os.makedirs(out + '/i')
    t0 = time.time(); best = None
    try:
        maps = p.global_mapping(db, fr, out + '/g')
        best = max(maps.values(), key=lambda m: m.num_reg_images()); log(f'global: {best.num_reg_images()}/{len(names)} in {time.time() - t0:.0f}s')
    except Exception as e: log('global mapping failed:', str(e)[:200])
    if best is None or best.num_reg_images() < 0.9 * len(names):
        o = p.IncrementalPipelineOptions(); o.max_runtime_seconds = a.max_map_s
        t0 = time.time(); maps = p.incremental_mapping(db, fr, out + '/i', o)
        inc = max(maps.values(), key=lambda m: m.num_reg_images()) if maps else None
        if inc: log(f'incremental: {inc.num_reg_images()}/{len(names)} in {time.time() - t0:.0f}s')
        if inc and (best is None or inc.num_reg_images() > best.num_reg_images()): best = inc
    rep = {'frames': len(names), 'blurry': len(blurry), 'pairs': len(pairs)}
    use_new = False
    if best is not None:
        new_c = {im.name: im.projection_center() for im in best.images.values()}
        common = [rn for rn, (nn, _) in match.items() if nn in new_c]
        if len(common) >= 20:
            src = np.array([new_c[match[rn][0]] for rn in common]); dst = np.array([ref_c[rn] for rn in common])
            s, R, t = umeyama(src, dst)
            res = np.linalg.norm((s * (R @ src.T)).T + t - dst, axis=1)
            # drop the worst 10 % (picture-match slips) and refit
            good = res <= np.quantile(res, 0.9)
            s, R, t = umeyama(src[good], dst[good])
            res = np.linalg.norm((s * (R @ src.T)).T + t - dst, axis=1)
            best.transform(p.Sim3d(s, p.Rotation3d(R), t))
            rep.update(registered=best.num_reg_images(), common=len(common), lock_rms_m=float(np.sqrt((res[good] ** 2).mean())),
                       lock_median_m=float(np.median(res)), lock_worst_m=float(res.max()), reproj_px=best.compute_mean_reprojection_error(),
                       points=best.num_points3D())
            log('lock to the site frame:', json.dumps(rep))
            use_new = best.num_reg_images() >= max(1.6 * len(ref_c), 0.6 * len(names)) and rep['lock_rms_m'] < 0.25
    data = f'{J}/data'; shutil.rmtree(data, ignore_errors=True); os.makedirs(f'{data}/sparse/0')
    # BINARY for gsplat: its COLMAP reader (rmbrualla/pycolmap) breaks on text models (py2 map(); 1 Nov 2026 run 1)
    if use_new:
        os.symlink(fr, f'{data}/images'); rep['used'] = 'new solve'
    else:
        best = p.Reconstruction(f'{J}/fallback/sparse/0')
        os.symlink(f'{J}/fallback/images', f'{data}/images'); rep['used'] = 'existing solve (fallback)'
    best.write_binary(f'{data}/sparse/0'); os.makedirs(f'{data}/sparse/txt'); best.write_text(f'{data}/sparse/txt')
    rep['match'] = {k: v[0] for k, v in match.items()}
    json.dump(rep, open(f'{J}/out/sfm.json', 'w'), indent=1)
    log('training data:', rep['used'])


def preflight(a):
    """gsplat's COLMAP reader on the fallback solve (binary), run as soon as the trainer is installed: a loader bug
    must cost minutes, not the 30-minute camera solve (1 Nov 2026 run 1 died here after the solve)."""
    J = a.job; sys.path.insert(0, f'{J}/gsplat/examples')
    from datasets.colmap import Parser, Dataset
    d = f'{J}/preflight'; shutil.rmtree(d, ignore_errors=True); os.makedirs(f'{d}/sparse/0')
    os.symlink(f'{J}/fallback/images', f'{d}/images')
    shutil.copytree(f'{J}/fallback/sparse/bin', f'{d}/sparse/0', dirs_exist_ok=True)
    pr = Parser(d, factor=1, normalize=False, test_every=8); ds = Dataset(pr, split='train')
    x = ds[0]; log('reader OK:', len(pr.image_names), 'images,', pr.points.shape[0], 'points, first image', tuple(x['image'].shape))
    # and the whole trainer for 60 steps (imports, CUDA, bilateral grid, eval images, .ply export)
    train(a, data=d, result=f'{J}/preflight_out', steps=60, cap=200_000)
    assert os.listdir(f'{J}/preflight_out/ply') and os.listdir(f'{J}/preflight_out/renders'), 'trainer wrote no ply/renders'
    log('preflight OK: 60-step training wrote a .ply and eval images')


def train(a, data=None, result=None, steps=None, cap=None):
    J = a.job; ex = f'{J}/gsplat/examples'
    data, result, steps, cap = data or f'{J}/data', result or f'{J}/out/train', steps or a.steps, cap or a.cap
    if ex not in sys.path: sys.path.insert(0, ex)
    os.chdir(ex)
    import simple_trainer as st
    from gsplat.strategy import MCMCStrategy
    from gsplat.distributed import cli
    import lib_bilagrid as lb
    for k in ('BilateralGrid', 'color_correct', 'slice', 'total_variation_loss'): setattr(st, k, getattr(lb, k))
    cfg = st.Config(init_opa=0.5, init_scale=0.1, opacity_reg=0.01, scale_reg=0.01,
                    strategy=MCMCStrategy(verbose=True, cap_max=cap),
                    data_dir=data, data_factor=1, result_dir=result, test_every=8,
                    normalize_world_space=False,             # keep the site's metres (the solve is already locked)
                    max_steps=steps, eval_steps=sorted({min(7000, steps), steps}), save_steps=[steps], ply_steps=[steps],
                    save_ply=True, disable_viewer=True, disable_video=True,
                    use_bilateral_grid=True)                  # absorbs the phone's exposure changes, kept out of the splat
    cfg.adjust_steps(cfg.steps_scaler)
    cli(st.main, cfg, verbose=True)


def read_ply(path):
    with open(path, 'rb') as f:
        head = b''
        while not head.endswith(b'end_header\n'): head += f.readline()
        props = [l.split()[-1].decode() for l in head.split(b'\n') if l.startswith(b'property')]
        n = int([l for l in head.split(b'\n') if l.startswith(b'element vertex')][0].split()[-1])
        arr = np.fromfile(f, dtype=np.float32, count=n * len(props)).reshape(n, len(props))
    return head, props, arr


def post(a):
    J = a.job; O = f'{J}/out'; plys = sorted(os.listdir(f'{O}/train/ply'))
    src = f'{O}/train/ply/{plys[-1]}'; shutil.copy(src, f'{O}/splat_raw.ply')
    head, props, arr = read_ply(src); n = len(arr); P = {k: i for i, k in enumerate(props)}
    op = 1 / (1 + np.exp(-arr[:, P['opacity']]))
    sc = np.exp(arr[:, [P['scale_0'], P['scale_1'], P['scale_2']]])
    ok = np.isfinite(arr).all(1)
    # importance for the lighter copy: opacity x the splat's two largest axes (what it covers on screen)
    ss = np.sort(sc, 1); imp = op * ss[:, 2] * ss[:, 1]; imp[~ok] = -1
    k = min(a.quest, n); idx = np.argsort(-imp)[:k]
    h = head.replace(f'element vertex {n}'.encode(), f'element vertex {k}'.encode())
    with open(f'{O}/splat_quest.ply', 'wb') as f: f.write(h); arr[np.sort(idx)].astype(np.float32).tofile(f)
    xyz = arr[:, :3]
    rep = {'gaussians': n, 'quest_gaussians': k, 'nonfinite': int((~ok).sum()),
           'bbox_1_99': [np.percentile(xyz, 1, 0).round(2).tolist(), np.percentile(xyz, 99, 0).round(2).tolist()],
           'opacity_median': float(np.median(op))}
    # which held-out frame is which (gsplat sorts by name; every 8th is held out)
    names = sorted(t[9] for t in (l.split() for l in open(f'{J}/data/sparse/txt/images.txt') if not l.startswith('#'))
                   if len(t) == 10 and t[9].lower().endswith(('.jpg', '.png')))
    rep['val_names'] = names[::8]; rep['train_count'] = len(names) - len(names[::8])
    st = sorted(f for f in os.listdir(f'{O}/train/stats') if f.startswith('val'))
    rep['val_stats'] = {f: json.load(open(f'{O}/train/stats/{f}')) for f in st}
    json.dump(rep, open(f'{O}/post.json', 'w'), indent=1); log('post:', json.dumps({k: v for k, v in rep.items() if k != 'val_names'})[:900])


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('stage', choices=['sfm', 'preflight', 'train', 'post'])
    ap.add_argument('--job', default='/workspace/job')
    ap.add_argument('--fps', type=float, default=4)
    ap.add_argument('--window', type=int, default=10)
    ap.add_argument('--cam', default='1010,540,960,-0.006', help='SIMPLE_RADIAL f,cx,cy,k at 1080x1920 (from the existing solve)')
    ap.add_argument('--max-map-s', type=int, default=1500)
    ap.add_argument('--steps', type=int, default=30000)
    ap.add_argument('--cap', type=int, default=1_500_000)
    ap.add_argument('--quest', type=int, default=700_000)
    a = ap.parse_args(); os.makedirs(f'{a.job}/out', exist_ok=True)
    {'sfm': sfm, 'preflight': preflight, 'train': train, 'post': post}[a.stage](a)
