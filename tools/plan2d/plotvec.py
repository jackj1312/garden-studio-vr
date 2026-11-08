"""Plot vector segments of a sheet region by line width, for inspection. usage: plotvec.py sheet.json x0 y0 x1 y1 out.png [scale px/pt] [widths...]"""
import json,sys,cv2,numpy as np
v=json.load(open(sys.argv[1])); x0,y0,x1,y1=map(float,sys.argv[2:6]); out=sys.argv[6]; k=float(sys.argv[7]) if len(sys.argv)>7 else 4
ws=[float(a) for a in sys.argv[8:]] or None
img=np.full((int((y1-y0)*k),int((x1-x0)*k),3),255,np.uint8)
cols={0.12:(200,200,200),0.24:(0,160,0),0.72:(0,0,0),0.48:(255,0,0),0:(0,0,255)}
for s in v['segs']:
    if not (x0<=min(s[0],s[2]) and max(s[0],s[2])<=x1 and y0<=min(s[1],s[3]) and max(s[1],s[3])<=y1): continue
    if ws and s[4] not in ws: continue
    c=cols.get(s[4],(255,0,255)); 
    cv2.line(img,(int((s[0]-x0)*k),int((s[1]-y0)*k)),(int((s[2]-x0)*k),int((s[3]-y0)*k)),c,2 if s[4]>=0.48 else 1)
for w in v['words']:
    if x0<=w[0]<=x1 and y0<=w[1]<=y1: cv2.putText(img,w[4],(int((w[0]-x0)*k),int((w[3]-y0)*k)),cv2.FONT_HERSHEY_SIMPLEX,0.35*k/3,(0,0,200),1)
# grid every 10pt
for gx in range(int(x0//50*50),int(x1),50): cv2.line(img,(int((gx-x0)*k),0),(int((gx-x0)*k),img.shape[0]),(230,200,255),1); cv2.putText(img,str(gx),(int((gx-x0)*k)+2,12),0,0.4,(150,0,150),1)
for gy in range(int(y0//50*50),int(y1),50): cv2.line(img,(0,int((gy-y0)*k)),(img.shape[1],int((gy-y0)*k)),(230,200,255),1); cv2.putText(img,str(gy),(2,int((gy-y0)*k)-2),0,0.4,(150,0,150),1)
cv2.imwrite(out,img); print(img.shape)
