#!/bin/bash
# Publishes the pipeline document (docs/pipeline/) to ~/Desktop/Garden Studio Pipeline/ and rebuilds its PDF.
# Run after ANY change to a stage, a tool, a link or a picture in the document (Claude and Codex both).
set -e
SRC="$(cd "$(dirname "$0")/../.." && pwd)/docs/pipeline"
DST="$HOME/Desktop/Garden Studio Pipeline"
# Preserve guide assets from concurrent worktrees; publish updates without pruning unrelated files.
mkdir -p "$DST"; rsync -a --exclude "*.pdf" "$SRC/" "$DST/"
CH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
[ -x "$CH" ] && "$CH" --headless=new --disable-gpu --no-pdf-header-footer --virtual-time-budget=8000 \
  --print-to-pdf="$DST/Garden Studio Pipeline.pdf" "file://$DST/Garden Studio Pipeline.html" 2>/dev/null
echo "published: $DST"
