# Garden Studio furnishing kit

Author in metres, X width, Y depth, Z up, front −Y. The exported glTF faces +Z. Its pivot is the bottom centre of its measured footprint. The studio spec faces −Z at zero yaw, so a studio spec placement adds 180° about up when placing a kit model.

`studio.make` builds the component construction sizes. `studio.make_at_size` reconstructs the parts against a requested finished envelope and checks the result to 1 mm. Accessories and cloth are included in the measured envelope. A size incompatible with the item's construction raises an error. Root scale is one. `materials.json` records original geometry/colour authorship, reviewed CC0 texture URLs, licence URLs, metric repeats and digests.

Run from the project root. Use an empty headless Blender process for each command.

```sh
Blender --background --factory-startup -t 2 --python-exit-code 1 --python tools/library/kit/check_sizes.py
Blender --background --factory-startup -t 2 --python-exit-code 1 --python tools/library/kit/export.py
Blender --background --factory-startup -t 2 --python-exit-code 1 --python tools/library/kit/export.py -- --id modern.sofa
python3 tools/https-serve.py 8450 127.0.0.1
node tools/library/kit/thumbnails.cjs
python3 tools/library/kit/check.py
python3 tools/library/kit/contact_sheet.py tools/library/kit/contact-sheet.jpg
```

The thumbnail script uses Puppeteer Core and local Chrome. Set `PUPPETEER_CORE` or `CHROME` for an existing installation. Product images are photographed from the exported meshes, with one neutral studio, front three-quarter lens and contact floor. A changed mesh, shared texture or lighting rig invalidates its photograph. Models reference shared texture files. Common fittings have one catalogue identity and their `compatibleStyles` list supplies the style filter.
