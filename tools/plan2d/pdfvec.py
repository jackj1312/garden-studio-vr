"""Extract vector line segments + text from an architect PDF sheet (PyMuPDF). Coordinates in PDF points, y down."""
import fitz, json, sys, os
def extract(pdf, out):
    d=fitz.open(pdf); p=d[0]; M=p.rotation_matrix  # -> displayed (rotated) page coords
    T=lambda q: fitz.Point(q)*M
    segs=[]; fills=[]; arcs=[]
    for i,dr in enumerate(p.get_drawings()):
        w=dr.get('width') or 0; col=dr.get('color'); fill=dr.get('fill')
        for it in dr['items']:
            if it[0]=='l':
                a,b=T(it[1]),T(it[2]); segs.append([round(a.x,3),round(a.y,3),round(b.x,3),round(b.y,3),round(w,3),i])
            elif it[0]=='re':
                r=fitz.Rect(it[1])*M; r.normalize()
                for (a,b) in [((r.x0,r.y0),(r.x1,r.y0)),((r.x1,r.y0),(r.x1,r.y1)),((r.x1,r.y1),(r.x0,r.y1)),((r.x0,r.y1),(r.x0,r.y0))]:
                    segs.append([round(a[0],3),round(a[1],3),round(b[0],3),round(b[1],3),round(w,3),i])
            elif it[0]=='c':
                a,b=T(it[1]),T(it[4]); segs.append([round(a.x,3),round(a.y,3),round(b.x,3),round(b.y,3),round(w,3),-i-1])  # curve chord (arcs: door swings)
        cpts=[]
        for it in dr['items']:
            if it[0]=='c':
                P0,P1,P2,P3=[T(q) for q in it[1:5]]
                for t in (0.0,0.25,0.5,0.75,1.0):
                    a=(1-t)**3; b=3*(1-t)**2*t; c=3*(1-t)*t*t; d=t**3
                    cpts.append([round(a*P0.x+b*P1.x+c*P2.x+d*P3.x,3),round(a*P0.y+b*P1.y+c*P2.y+d*P3.y,3)])
        if len(cpts)>=5: arcs.append({'id':i,'width':round(w,3),'pts':cpts})
        if fill is not None: fills.append([i,[round(c,3) for c in fill], [round(v,2) for v in (dr['rect']*M)]])
    words=[]
    for w in p.get_text('words'):
        r=fitz.Rect(w[:4])*M; r.normalize(); words.append([round(r.x0,2),round(r.y0,2),round(r.x1,2),round(r.y1,2),w[4]])
    json.dump({'pdf':pdf,'page_pt':[p.rect.width,p.rect.height],'note':'coords = displayed page points (rotation applied), y down','segs':segs,'fills':fills,'arcs':arcs,'words':words},open(out,'w'))
    print(os.path.basename(pdf),len(segs),'segs',len(fills),'fills',len(words),'words')
if __name__=='__main__':
    extract(sys.argv[1],sys.argv[2])
