"""Measure changes between two complete sets of the three studio camera frames.

Pass the two existing directories and optional filename prefixes (e.g. off-/on-).
The pictures stay at native resolution. The caller decides what changes are intended.
"""
import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image


def read(path):
    with Image.open(path) as source:
        return np.asarray(source.convert("RGB"), dtype=np.float32)


def compare(left, right):
    if left.shape != right.shape:
        raise ValueError(f"Unmatched frame sizes {left.shape} and {right.shape}")
    delta = np.abs(left - right)
    return {
        "size": [left.shape[1], left.shape[0]],
        "mean_rgb_error_255": round(float(delta.mean()), 4),
        "p99_max_channel_error_255": round(float(np.percentile(delta.max(axis=2), 99)), 2),
        "percent_pixels_max_error_over_12": round(float(100 * (delta.max(axis=2) > 12).mean()), 3),
        "exact_pixels_percent": round(float(100 * np.all(delta == 0, axis=2).mean()), 3),
        "before_mean_rgb": np.round(left.mean(axis=(0, 1)), 2).tolist(),
        "after_mean_rgb": np.round(right.mean(axis=(0, 1)), 2).tolist(),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("before", type=Path)
    ap.add_argument("after", type=Path)
    ap.add_argument("--prefix-before", default="")
    ap.add_argument("--prefix-after", default="")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    result = {}
    for name in ("kitchen-diner", "lounge", "front-garden"):
        a = args.before / (args.prefix_before + name + ".jpg")
        b = args.after / (args.prefix_after + name + ".jpg")
        result[name] = compare(read(a), read(b))
    report = json.dumps(result, indent=2) + "\n"
    if args.out:
        args.out.write_text(report)
    print(report, end="")


if __name__ == "__main__":
    main()

