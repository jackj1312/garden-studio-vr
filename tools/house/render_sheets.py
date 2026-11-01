#!/usr/bin/env python3
"""Render architect PDF sheets to PNG for the board's PLANS tab (src/house/viewer.js, CONTRACT.md "sheets.json").

    python3 tools/house/render_sheets.py <site> <sheet.pdf> [more.pdf …] [--dpi 100] [--max 4096]

Writes assets/sites/<site>/sheets/<pdf stem>_p<page>.png (one per page, longest side capped at --max px so a
headset can hold it) and merges them into assets/sites/<site>/sheets.json:

    { "contract": 1,
      "sheets": [ { "drawing": "<pdf stem> p<page>", "image": "sheets/<file>.png", "width": W, "height": H, "pdf": "<name>" } ],
      "crops":  { "<element id>": { "drawing": "<sheet drawing>", "rect": [x, y, w, h] } } }

The tracer (tools/plan/trace_drawing.py or the generator) adds the per-element "crops" in the PNG's pixel space;
existing crops are kept. Rename a sheet's "drawing" to the reference the extras use (e.g. "4915.3A section A-A")
so a part's `drawing` finds it. Light work: macOS PDFKit through a tiny Swift script (no Python PDF library
needed), one page at a time."""
import json, os, subprocess, sys, tempfile

ROOT = os.path.realpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
SWIFT = r'''
import Foundation
import PDFKit
import AppKit
let a = CommandLine.arguments
let doc = PDFDocument(url: URL(fileURLWithPath: a[1]))!
let out = a[2], stem = a[3], dpi = Double(a[4])!, cap = Double(a[5])!
for i in 0..<doc.pageCount {
  let page = doc.page(at: i)!
  let box = page.bounds(for: .mediaBox)
  var s = dpi / 72.0
  s = min(s, cap / max(box.width, box.height))
  let w = Int(box.width * s), h = Int(box.height * s)
  let rep = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: w, pixelsHigh: h, bitsPerSample: 8, samplesPerPixel: 4,
                             hasAlpha: true, isPlanar: false, colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0)!
  NSGraphicsContext.saveGraphicsState()
  let ctx = NSGraphicsContext(bitmapImageRep: rep)!
  NSGraphicsContext.current = ctx
  ctx.cgContext.setFillColor(CGColor(red: 1, green: 1, blue: 1, alpha: 1))
  ctx.cgContext.fill(CGRect(x: 0, y: 0, width: w, height: h))
  ctx.cgContext.scaleBy(x: s, y: s)
  page.draw(with: .mediaBox, to: ctx.cgContext)
  NSGraphicsContext.restoreGraphicsState()
  let name = "\(stem)_p\(i + 1).png"
  try! rep.representation(using: .png, properties: [:])!.write(to: URL(fileURLWithPath: out + "/" + name))
  print("\(name) \(w) \(h)")
}
'''


def main():
    args = sys.argv[1:]
    if len(args) < 2:
        sys.exit(__doc__)
    dpi, cap = 100.0, 4096.0
    if "--dpi" in args:
        i = args.index("--dpi"); dpi = float(args[i + 1]); del args[i:i + 2]
    if "--max" in args:
        i = args.index("--max"); cap = float(args[i + 1]); del args[i:i + 2]
    site, pdfs = args[0], args[1:]
    site_dir = os.path.join(ROOT, "assets", "sites", site)
    out = os.path.join(site_dir, "sheets")
    os.makedirs(out, exist_ok=True)
    index_path = os.path.join(site_dir, "sheets.json")
    index = json.load(open(index_path)) if os.path.isfile(index_path) else {"contract": 1, "sheets": [], "crops": {}}
    with tempfile.TemporaryDirectory() as tmp:
        script = os.path.join(tmp, "render.swift")
        open(script, "w").write(SWIFT)
        for pdf in pdfs:
            stem = os.path.splitext(os.path.basename(pdf))[0].replace(" ", "_")
            r = subprocess.run(["nice", "-n", "10", "swift", script, os.path.abspath(pdf), out, stem, str(dpi), str(cap)],
                               capture_output=True, text=True)
            if r.returncode:
                print(r.stderr[-800:], file=sys.stderr); sys.exit(r.returncode)
            for line in r.stdout.split("\n"):
                if not line.strip():
                    continue
                name, w, h = line.rsplit(" ", 2)
                entry = {"drawing": f"{stem} p{name.rsplit('_p', 1)[1][:-4]}", "image": f"sheets/{name}",
                         "width": int(w), "height": int(h), "pdf": os.path.basename(pdf)}
                index["sheets"] = [s for s in index["sheets"] if s["image"] != entry["image"]] + [entry]
                print(f"render_sheets: {entry['image']} {w}x{h}")
    json.dump(index, open(index_path, "w"), indent=1)
    print(f"render_sheets: {len(index['sheets'])} sheets in {os.path.relpath(index_path, ROOT)}")


if __name__ == "__main__":
    main()
