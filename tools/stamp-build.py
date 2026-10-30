#!/usr/bin/env python3
"""Stamp a build id onto every module import and asset URL.

Browsers cache aggressively and GitHub Pages serves max-age=600, so
without this a headset keeps running yesterday's JavaScript for ten
minutes after a deploy. Run it before every commit.
"""
import pathlib, re, subprocess, sys

root = pathlib.Path(__file__).resolve().parent.parent
build = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                       cwd=root, capture_output=True, text=True).stdout.strip() or "dev"
build += "-" + subprocess.run(["date", "+%H%M"], capture_output=True, text=True).stdout.strip()

changed = []

idx = root / "index.html"
t = idx.read_text()
t2 = re.sub(r'src="src/app\.js(\?v=[^"]*)?"', f'src="src/app.js?v={build}"', t)
if t2 != t:
    idx.write_text(t2); changed.append("index.html")

for f in sorted((root / "src").glob("*.js")):
    t = f.read_text()
    t2 = re.sub(r'(from\s+"\./[A-Za-z0-9_\-]+\.js)(\?v=[^"]*)?"', rf'\1?v={build}"', t)
    t2 = re.sub(r'(export const BUILD = ")[^"]*(")', rf'\g<1>{build}\g<2>', t2)
    if t2 != t:
        f.write_text(t2); changed.append(f"src/{f.name}")

print(f"build {build}")
print("stamped:", ", ".join(changed) if changed else "nothing")
