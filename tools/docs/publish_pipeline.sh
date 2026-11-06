#!/bin/bash
# Publishes the pipeline document (docs/pipeline/) to ~/Desktop/Garden Studio Pipeline/ and rebuilds its PDF.
# Run after ANY change to a stage, a tool, a link or a picture in the document (Claude and Codex both).
set -e
SRC="$(cd "$(dirname "$0")/../.." && pwd)/docs/pipeline"
DST="$HOME/Desktop/Garden Studio Pipeline"
# Preserve guide assets from concurrent worktrees; publish updates without pruning unrelated files.
python3 "$(dirname "$0")/copy_pipeline.py" "$SRC" "$DST"
python3 "$(dirname "$0")/print_pipeline.py" "$SRC/Garden Studio Pipeline.html" "$DST/Garden Studio Pipeline.pdf"
echo "published: $DST"
