"""Print axis-aligned thick (wall-cut) lines in a region: python axlines.py sheet.json x0 y0 x1 y1 [width]"""
import json,collections,sys
v=json.load(open(sys.argv[1])); x0,y0,x1,y1=map(float,sys.argv[2:6]); W=float(sys.argv[6]) if len(sys.argv)>6 else 0.72
S=[s for s in v['segs'] if s[4]==W and x0<=min(s[0],s[2]) and max(s[0],s[2])<=x1 and y0<=min(s[1],s[3]) and max(s[1],s[3])<=y1]
V=collections.defaultdict(list); H=collections.defaultdict(list); O=[]
for s in S:
    if abs(s[0]-s[2])<=0.05: V[round(s[0],2)].append((round(min(s[1],s[3]),2),round(max(s[1],s[3]),2)))
    elif abs(s[1]-s[3])<=0.05: H[round(s[1],2)].append((round(min(s[0],s[2]),2),round(max(s[0],s[2]),2)))
    else: O.append([round(c,2) for c in s[:4]])
def merge(r):
    r=sorted(r); out=[list(r[0])]
    for a,b in r[1:]:
        if a<=out[-1][1]+0.05: out[-1][1]=max(out[-1][1],b)
        else: out.append([a,b])
    return out
print('V x:',); [print(' ',x,merge(V[x])) for x in sorted(V)]
print('H y:'); [print(' ',y,merge(H[y])) for y in sorted(H)]
print('oblique',O)
