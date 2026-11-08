"""Render a region of a PDF sheet (displayed page points) at high dpi with a 10pt grid labelled in sheet points."""
import fitz,sys,glob,os,cv2,numpy as np
S=os.environ.get('DRAWINGS_DIR', os.path.expanduser('~/Desktop/23 Battle Road/sources/bds-originals'))  # folder of the sheet PDFs
n,x0,y0,x1,y1,out=sys.argv[1],*map(float,sys.argv[2:6]),sys.argv[6]; z=float(sys.argv[7]) if len(sys.argv)>7 else 6
p=fitz.open(glob.glob(S+f'/{n} *.pdf')[0])[0]
pix=p.get_pixmap(matrix=fitz.Matrix(z,z),clip=fitz.Rect(x0,y0,x1,y1))
img=np.frombuffer(pix.samples,np.uint8).reshape(pix.h,pix.w,pix.n)[:,:,:3].copy()
for g in range(int(x0//10*10)+10,int(x1),10):
    X=int((g-x0)*z); cv2.line(img,(X,0),(X,img.shape[0]),(255,180,180) if g%50 else (255,0,255),1)
    if g%50==0: cv2.putText(img,str(g),(X+2,14),0,0.45,(200,0,200),1)
for g in range(int(y0//10*10)+10,int(y1),10):
    Y=int((g-y0)*z); cv2.line(img,(0,Y),(img.shape[1],Y),(255,180,180) if g%50 else (255,0,255),1)
    if g%50==0: cv2.putText(img,str(g),(2,Y-3),0,0.45,(200,0,200),1)
cv2.imwrite(out,img[:,:,::-1]); print(img.shape)
