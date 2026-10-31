#!/bin/zsh
# Turn a folder of phone photos and videos of a garden into a textured mesh.
#
#   tools/reconstruct-garden.sh <folder> [detail] [fps]
#
#   folder   photos (.jpg/.heic) and videos (.mov/.mp4) straight off the phone
#   detail   preview | reduced | medium | full | raw     (default full)
#   fps      frames pulled from each video per second    (default 2)
#
# Writes <folder>/images (every still, plus video frames) and
# <folder>/garden-<detail>.usdz. Everything stays on this Mac.
set -e
SRC="${1:?folder of photos and videos}"
DETAIL="${2:-full}"
FPS="${3:-2}"
HERE="$(cd "$(dirname "$0")" && pwd)"
FFMPEG="$HOME/splat/lib/python3.13/site-packages/imageio_ffmpeg/binaries/ffmpeg-macos-aarch64-v7.1"
IMG="$SRC/images"
mkdir -p "$IMG"

n=0
for f in "$SRC"/*.(jpg|jpeg|JPG|JPEG|heic|HEIC|png|PNG)(N); do
  base="${f:t:r}"
  case "${f:e:l}" in
    heic) sips -s format jpeg "$f" --out "$IMG/$base.jpg" >/dev/null ;;
    *)    cp "$f" "$IMG/$base.${f:e}" ;;
  esac
  n=$((n+1))
done
echo "stills: $n"

for v in "$SRC"/*.(mov|MOV|mp4|MP4|m4v)(N); do
  base="${v:t:r}"
  # frames at full resolution; the phone's own exposure, no rescale
  "$FFMPEG" -hide_banner -loglevel error -i "$v" -vf "fps=$FPS" -q:v 2 "$IMG/${base}_%04d.jpg"
  echo "video $base: $(ls "$IMG" | grep -c "^${base}_") frames"
done

total=$(ls "$IMG" | wc -l | tr -d ' ')
echo "images for reconstruction: $total"
OUT="$SRC/garden-$DETAIL.usdz"
echo "reconstructing at $DETAIL → $OUT"
time "$HERE/photogrammetry/scan" "$IMG" "$OUT" "$DETAIL"
ls -la "$OUT"
