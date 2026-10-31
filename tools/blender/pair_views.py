"""Side-by-side of real frames and model renders from the same camera (WORKFLOW G6).
    ~/splat/bin/python tools/blender/pair_views.py <render_dir> <frames_dir> <out.jpg> frame,frame,..."""
import sys, os
from PIL import Image, ImageDraw, ImageFont
rd, fd, out, frames = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4].split(",")
f = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 18)
pairs = []
for fr in frames:
    m = Image.open(os.path.join(rd, fr.replace(".jpg", ".png"))).convert("RGB")
    r = Image.open(os.path.join(fd, fr)).convert("RGB").resize(m.size)
    p = Image.new("RGB", (m.width * 2 + 8, m.height + 30), (18, 18, 18)); p.paste(r, (0, 30)); p.paste(m, (m.width + 8, 30))
    ImageDraw.Draw(p).text((6, 5), f"{fr}: real | model (v2 mockup)", fill=(240, 240, 240), font=f); pairs.append(p)
cols = 3 if len(pairs) > 4 else 2; W = max(p.width for p in pairs); H = max(p.height for p in pairs)
sheet = Image.new("RGB", (cols * W, ((len(pairs) + cols - 1) // cols) * H), (10, 10, 10))
for i, p in enumerate(pairs): sheet.paste(p, ((i % cols) * W, (i // cols) * H))
sheet.thumbnail((3000, 3000)); sheet.save(out, quality=88); print(out, sheet.size)
