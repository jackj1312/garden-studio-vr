"""Package a completed local camera rehearsal using the tested player template."""
import json,re,sys
from pathlib import Path
root=Path(__file__).resolve().parents[2]
out=root/sys.argv[1]
spec=json.loads((root/'tools/unreal/house-cinema.json').read_text())['video']
poses=json.loads((out/'poses.json').read_text())
assert len(poses)==spec['seconds']*spec['fps'],'Capture must finish before packaging'
assert all((out/f'{p["frame"]:04d}.jpg').is_file() for p in poses)
template=root/'renders/unreal/house-stills/camera-preview-v2/index.html'
s=template.read_text().replace('10 seconds · same planned lens and camera height',f'{spec["seconds"]} seconds · {spec["hfov_deg"]}° horizontal wide-angle lens · revised hallway route')
a=s.index('const poses=')+len('const poses=');b=s.index(',v=document.querySelector',a);s=s[:a]+json.dumps(poses)+s[b:]
points=' '.join(f'{30+p["eye"][0]*32},{300+p["eye"][2]*32}' for p in poses)
s=re.sub(r'<polyline points="[^"]*"',f'<polyline points="{points}"',s,count=1)
buttons='<div>'+''.join(f'<button data-t="{b["t"]}">{b["label"]}</button>' for b in spec['beats'])+'</div>'
s=re.sub(r'<div><button data-t=.*?</div>',lambda _:buttons,s,count=1,flags=re.S)
s=s.replace('stove flames, candle flicker and cooking steam','stove flames, the new window candle and candle flicker, and cooking steam')
(out/'index.html').write_text(s)
(out/'check.json').write_text(json.dumps({'frames':len(poses),'fps':spec['fps'],'seconds':spec['seconds'],'hfov':spec['hfov_deg'],'camera_lens':'about 20 mm full-frame','door':'living entrance opened before capture','effects':'planned Unreal effects absent'},indent=2))
print('Player prepared:',out/'index.html')
