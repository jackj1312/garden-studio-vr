#!/bin/bash
# Runs ON the rented machine (started by cloud_splat.py, detached, logging to /root/job.log). Installs the tools while
# the walk video is still uploading, then: camera solve -> splat training -> post -> web compression.
# Args are passed through from cloud_splat.py: FPS STEPS CAP QUEST
set -eo pipefail
J=/workspace/job; cd $J; mkdir -p out
FPS=${1:-4}; STEPS=${2:-30000}; CAP=${3:-1500000}; QUEST=${4:-700000}
say(){ echo "[pod $(date +%H:%M:%S)] $*"; }
ARCH=$(nvidia-smi --query-gpu=compute_cap --format=csv,noheader | head -1)
export TORCH_CUDA_ARCH_LIST="$ARCH" MAX_JOBS=$(nproc) PIP_ROOT_USER_ACTION=ignore
say "GPU $(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader | head -1), sm $ARCH, $(nproc) CPUs"

# trainer stack (system python, the image's torch) in the background, gsplat's CUDA compiled for this card only
(
  set -e
  pip install -q --no-build-isolation ninja "numpy<2" viser "imageio[ffmpeg]" scikit-learn tqdm "torchmetrics[image]" \
      opencv-python-headless "tyro>=0.8.8" Pillow tensorboard tensorly pyyaml matplotlib splines rich packaging
  pip install -q --no-build-isolation "git+https://github.com/rmbrualla/pycolmap@cc7ea4b7301720ac29287dbe450952511b32125e" \
      "git+https://github.com/nerfstudio-project/nerfview@4538024fe0d15fd1a0e4d760f3695fc44ca72787" \
      "git+https://github.com/rahul-goel/fused-ssim@328dc9836f513d00c4b5bc38fe30478b4435cbb5"
  BUILD_NO_CUDA=1 pip install -q --no-build-isolation gsplat==1.5.3
  [ -d gsplat ] || git clone -q --depth 1 --branch v1.5.3 https://github.com/nerfstudio-project/gsplat.git
  python -c "from gsplat.cuda._backend import _C; print('gsplat CUDA ready', _C is not None)"
) > /root/trainer_setup.log 2>&1 &
TRAINER=$!

# web compression tool (node + splat-transform), also in the background
(
  set -e
  cd /workspace; [ -x node/bin/node ] || (curl -fsSL https://nodejs.org/dist/v22.11.0/node-v22.11.0-linux-x64.tar.xz | tar -xJ && mv node-v22.11.0-linux-x64 node)
  export PATH=/workspace/node/bin:$PATH; npm install -g -s @playcanvas/splat-transform@3.10.1
  splat-transform --version || true
) > /root/node_setup.log 2>&1 &
NODE=$!

say "installing ffmpeg + the camera-solve venv"
(apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq ffmpeg libsm6 libice6 libxext6 libgl1 libegl1 libxrender1 libglib2.0-0 >/dev/null) || true   # pycolmap needs the X libs (1 Nov 2026)
python -m venv /workspace/sfmenv
/workspace/sfmenv/bin/pip install -q pycolmap-cuda12==4.2.1 "numpy<3" opencv-python-headless
/workspace/sfmenv/bin/python -c "import pycolmap; print('pycolmap', pycolmap.__version__, 'cuda', pycolmap.has_cuda)" || true

say "preflight: gsplat's reader on the existing solve (before the long camera solve)"
wait $TRAINER || { tail -40 /root/trainer_setup.log; say "TRAINER INSTALL FAILED"; exit 3; }
tail -1 /root/trainer_setup.log
python $J/splat_pod.py preflight --job $J > /root/preflight.log 2>&1 || { tail -30 /root/preflight.log; say "PREFLIGHT FAILED"; exit 5; }
grep "preflight OK" /root/preflight.log || true

say "waiting for the walk video"
while [ ! -f $J/video.done ]; do sleep 5; done
say "video here: $(du -h $J/video.mp4 | cut -f1)"

/workspace/sfmenv/bin/python $J/splat_pod.py sfm --job $J --fps $FPS > /root/sfm.log 2>&1 || { grep -v "^I20" /root/sfm.log | tail -30; say "SFM FAILED"; exit 2; }
grep "^\[pod\]" /root/sfm.log || true

say "training $STEPS steps, cap $CAP gaussians"
python $J/splat_pod.py train --job $J --steps $STEPS --cap $CAP > /root/train.log 2>&1 || { tail -40 /root/train.log; say "TRAIN FAILED"; exit 4; }
grep -a -E "Parser|PSNR|Step:|num_GS" /root/train.log | tail -8 || true
python $J/splat_pod.py post --job $J --quest $QUEST

wait $NODE || { tail -20 /root/node_setup.log; say "node install failed; raw .ply only"; }
export PATH=/workspace/node/bin:$PATH
cd $J/out
for v in raw quest; do
  splat-transform -w splat_$v.ply splat_$v.sog > /root/st_$v.log 2>&1 && say "sog $v: $(du -h splat_$v.sog | cut -f1)" || { tail -5 /root/st_$v.log; say "sog $v failed"; }
  splat-transform -w splat_$v.ply splat_$v.compressed.ply > /root/stc_$v.log 2>&1 && say "compressed.ply $v: $(du -h splat_$v.compressed.ply | cut -f1)" || { tail -5 /root/stc_$v.log; say "compressed.ply $v failed"; }
done
mkdir -p val && python -c "
import glob, os; from PIL import Image
for f in sorted(glob.glob('train/renders/val_step*.png')):
    Image.open(f).convert('RGB').save('val/' + os.path.basename(f)[:-4] + '.jpg', quality=92)
" || true
cp train/stats/*.json . 2>/dev/null || true
du -sh $J/out/* | sort -h | tail -12
say "JOB DONE"
