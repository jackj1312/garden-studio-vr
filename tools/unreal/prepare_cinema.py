"""Transfer the approved browser rehearsal poses exactly into Unreal coordinates."""
import json
from pathlib import Path
p=Path('out/unreal-house/golden/bundle/scene.json');scene=json.loads(p.read_text())
poses=json.load(open('renders/unreal/house-stills/camera-preview-v3-open/poses.json'));v=json.load(open('tools/unreal/house-cinema.json'))['video']
assert len(poses)==v['fps']*v['seconds']
scene['video']={k:v[k] for k in ['fps','seconds','res','hfov_deg']}
scene['video']['keys']=[dict(t=p['t'],pos_cm=[100*p['eye'][i] for i in [0,2,1]],pitch=p['rotation'][0],yaw=-90-p['rotation'][1]) for p in poses]
for name,eye,aim,focal in [('Lounge',[3.10,1.5,-1.5],[1.1,1,-3.3],21),('Fire_check',[1.4,.70,-2.31],[.4,.34,-2.31],35),('Window_check',[2.4,1.45,-1.15],[1.75,1.02,-.25],35),('Hob_check',[7.4,1.6,-5.8],[8.29,1.1,-5.92],30),('Alcove_check',[1.7,1.2,-3.8],[.355,1.1,-3.68],32),('Garden_ground',[4.4,.65,17.5],[4.,-.20,15.7],30)]:
 scene['cameras']=[c for c in scene['cameras'] if c['name']!=name]
 delta=[b-a for a,b in zip(eye,aim)]
 scene['cameras'].append(dict(name=name,pos_cm=[100*eye[i] for i in [0,2,1]],fwd=[delta[i] for i in [0,2,1]],up=[0,0,1],focal_mm=focal,sensor_w_mm=36,sensor_h_mm=20.25,w=1920,h=1080))
p.write_text(json.dumps(scene))
print('Exact approved route:',len(poses),'keys')
