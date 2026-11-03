"""Check Jack's marked site geometry in an exported setting, without Blender or a browser.

    python3 tools/house/check_setting_marks.py assets/sites/house/setting_front.glb
"""
import argparse
import json
import struct


class Setting:
    def __init__(self, path):
        with open(path, "rb") as f:
            assert f.read(4) == b"glTF"
            f.seek(12)
            length, tag = struct.unpack("<II", f.read(8))
            assert tag == 0x4e4f534a
            self.doc = json.loads(f.read(length))
            length, tag = struct.unpack("<II", f.read(8))
            assert tag == 0x004e4942
            self.bin = f.read(length)
        self.nodes = {n["name"]: n for n in self.doc["nodes"] if "mesh" in n}

    def values(self, index):
        a = self.doc["accessors"][index]
        v = self.doc["bufferViews"][a["bufferView"]]
        fmt = "<" + {5121:"B",5123:"H",5125:"I",5126:"f"}[a["componentType"]]*{"SCALAR":1,"VEC2":2,"VEC3":3,"VEC4":4}[a["type"]]
        start = a.get("byteOffset", 0) + v.get("byteOffset", 0)
        stride = v.get("byteStride", struct.calcsize(fmt))
        return [struct.unpack_from(fmt, self.bin, start+i*stride) for i in range(a["count"])]

    def primitives(self, name):
        node = self.nodes[name]
        for p in self.doc["meshes"][node["mesh"]]["primitives"]:
            t = node.get("translation", (0,0,0))
            qx,qy,qz,qw = node.get("rotation", (0,0,0,1))
            sx,sy,sz = node.get("scale", (1,1,1))
            pts = []
            for x,y,z in self.values(p["attributes"]["POSITION"]):
                x,y,z=x*sx,y*sy,z*sz
                dot = x*qx+y*qy+z*qz
                pts.append((x*(2*qw*qw-1)+2*qx*dot+2*qw*(qy*z-qz*y)+t[0],
                            y*(2*qw*qw-1)+2*qy*dot+2*qw*(qz*x-qx*z)+t[1],
                            z*(2*qw*qw-1)+2*qz*dot+2*qw*(qx*y-qy*x)+t[2]))
            yield p, pts

    def bounds(self, name):
        pts=[pt for _, values in self.primitives(name) for pt in values]
        return tuple((min(axis), max(axis)) for axis in zip(*pts))

    def triangles(self, name):
        for p,pts in self.primitives(name):
            indices = [r[0] for r in self.values(p["indices"])]
            for i in range(0,len(indices),3):
                yield self.doc["materials"][p["material"]]["name"], [pts[j] for j in indices[i:i+3]]

    def top(self, name, x, z):
        best = None
        for m, (a,b,c) in self.triangles(name):
            ax,az=b[0]-a[0],b[2]-a[2]
            bx,bz=c[0]-a[0],c[2]-a[2]
            dx,dz=x-a[0],z-a[2]
            den=ax*bz-az*bx
            if abs(den)<1e-10:
                continue
            u,v=(dx*bz-dz*bx)/den,(ax*dz-az*dx)/den
            if u>=-1e-7 and v>=-1e-7 and u+v<=1+1e-7:
                y=a[1]+u*(b[1]-a[1])+v*(c[1]-a[1])
                if best is None or y>best[0]:
                    best=(y,m)
        return best

    def transverse_path_interval(self, x):
        pieces=[]
        for _, t in self.triangles("G2_paving"):
            zz=[]
            for p,q in ((t[0],t[1]),(t[1],t[2]),(t[2],t[0])):
                if (p[0]-x)*(q[0]-x)<=0 and abs(q[0]-p[0])>1e-7:
                    zz.append(p[2]+(q[2]-p[2])*(x-p[0])/(q[0]-p[0]))
            if len(zz)==2:
                pieces.append(tuple(sorted(zz)))
        joined=[]
        for lo,hi in sorted(pieces):
            if joined and lo<=joined[-1][1]+1e-5:
                joined[-1][1]=max(joined[-1][1],hi)
            else:
                joined.append([lo,hi])
        return next(s for s in joined if s[0]<3.7<s[1])


def audit(path):
    g=Setting(path)
    report={}
    lo,hi=g.transverse_path_interval(4.964)
    report["path_m"]=[round(lo,4),round(hi,4),round(hi-lo,4)]
    assert abs(hi-lo-.900)<.00005 and abs(lo-3.209489)<.0001 and abs(hi-4.109489)<.0001, report
    assert g.top("G2_house_bed",4.964,lo-.01)
    assert not g.top("G2_house_bed",4.964,lo+.01)
    bench=min(g.bounds(n)[2][0] for n in g.nodes if n.startswith("Bench_") and not n.startswith("Bench_stone_"))
    report["bench_clearance_mm"]=round(1000*(bench-2.665),1)
    assert 12<report["bench_clearance_mm"]<18, report
    report["rear_post_to_gutter_mm"]=[round(1000*(g.bounds("Perg_post_"+n)[2][0]-2.725),1) for n in ("3","4")]
    assert all(8<gap<12 for gap in report["rear_post_to_gutter_mm"]),report
    assert abs(g.bounds("Perg_post_0")[2][0]-4.495)<.002, report
    bb=g.bounds("G2_lawn_kerb_terminal")
    report["corner_cut_mm"]=round((bb[2][1]-bb[2][0])*1000,1)
    assert abs(bb[2][0]-g.bounds("G2_border_foot_to_fence")[2][1])<.0002
    assert abs(bb[2][1]-g.bounds("G2_lawn_kerb")[2][0])<.0002
    assert abs(g.top("G2_lawn_kerb_terminal",7.689,6.133)[0]+.225)<.001
    assert "Shed_front" not in g.nodes
    left,right=g.bounds("Shed_door_left"),g.bounds("Shed_door_right")
    report["shed_leaf_widths_mm"]=[round(1000*(a[0][1]-a[0][0]),1) for a in (left,right)]
    assert all(300<v<600 for v in report["shed_leaf_widths_mm"])
    assert .004<right[0][0]-left[0][1]<.006
    assert g.bounds("Shed_door_latch_grip")[2][1]>left[2][1]+.040
    for n in ("Shed_door_left","Shed_door_right","Shed_front_siding_house","Shed_front_siding_fence"):
        assert all(g.doc['materials'][p["material"]]["name"]=="FG_shed_red_gltf" and "TEXCOORD_0" in p["attributes"]
                   for p,_ in g.primitives(n)),n
    hedges=sorted(g.bounds(n)[0] for n in g.nodes if n.startswith("B_street_hedge"))
    report["street_hedge_x_m"]=[[round(q,3) for q in span] for span in hedges]
    assert len(hedges)==3 and abs(hedges[1][0]-hedges[0][1]-1.10)<.002
    assert abs(hedges[2][0]-5.63)<.002 and hedges[2][1]>=8.63
    assert hedges[2][0]-hedges[1][1]>3.
    tests=[(.20,21.74,"concrete"),(.20,22.03,"FG_road"),(.20,23.14,"turf"),
           (-.90,23.14,"turf"),(3.25,23.14,"FG_pavement")]
    report["transition"]=[g.top("G2_pavement",x,z)[1] for x,z,_ in tests]
    assert all(expected.lower() in result.lower() for (_,_,expected),result in zip(tests,report["transition"])),report
    uv_error = 0
    for pr, pts in g.primitives("G2_pavement"):
        if g.doc["materials"][pr["material"]]["name"] != "FG_pavement_gltf":
            continue
        uv = g.values(pr["attributes"]["TEXCOORD_0"])
        for (x,_,z),(u,v) in zip(pts,uv):
            uv_error = max(uv_error, abs(u-(x-4.63)/1.8), abs(v-(1+(z-3.09)/1.8)))
    report["untouched_pavement_uv_error"] = round(uv_error, 6)
    assert uv_error < .0001, report
    assert "grey" in g.top("G2_paving",.20,21.65)[1]
    plant_materials=set()
    for n in g.nodes:
        if n.startswith(("Plant2_door_shrub_", "Plant2_house_")):
            for p,_ in g.primitives(n):
                m=g.doc["materials"][p["material"]]
                assert "TEXCOORD_0" in p["attributes"] and "baseColorTexture" in m["pbrMetallicRoughness"] and "normalTexture" in m, n
                plant_materials.add(m["name"])
    report["botanical_materials"]=sorted(plant_materials)
    assert len(plant_materials)>=3, report
    for soil in ("G2_house_bed","G2_hedge_soil"):
        for p,_ in g.primitives(soil):
            m=g.doc["materials"][p["material"]]
            assert m["name"]=="FG_mulch_gltf" and "normalTexture" in m and "baseColorTexture" in m["pbrMetallicRoughness"],soil
    return report


if __name__=="__main__":
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("setting")
    print(json.dumps(audit(ap.parse_args().setting),indent=2))
