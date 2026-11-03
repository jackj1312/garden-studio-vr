"""Signed cabinet support lines in the viewer's X/Z plan. All dimensions in metres."""
import math


def base_units(items, room):
    return [it for it in items if it["room"] == room and it["asset"].get("kind") == "kitchen_unit"
            and 0 < it["size_mm"][2] < 1400]


def frame(it):
    yaw = math.radians(it["yaw_deg"])
    return (math.cos(yaw), -math.sin(yaw)), (math.sin(yaw), math.cos(yaw))


def dot(a, b):
    return sum(x*y for x,y in zip(a,b))


def board_support(item, units, items=()):
    x, _, z = item["position_m"]
    host = min(units, key=lambda u:math.hypot(x-u["position_m"][0], z-u["position_m"][2]))
    _, back = frame(host)
    cx, _, cz = host["position_m"]
    thickness = item["size_mm"][1]/1000
    height = item["size_mm"][2]/1000
    # The board bears on the room-facing finished strip. A low upstand supports
    # it at the top edge; a full-height hob splash supports it at its upper back.
    support_height=height;finish_depth=0
    for splash in items:
        if splash["room"]!=item["room"] or not splash["asset"].get("hob_splash"):continue
        for section in splash_segments(splash,units):
            if abs(section["yaw"]-host["yaw_deg"])>.01:continue
            along,_=frame(host)
            if abs(dot((x-section["x"],z-section["z"]),along))>section["width"]/2:continue
            support_height=min(support_height,section["height"]);finish_depth=splash["size_mm"][1]/1000
    lean=math.radians(6)
    rear_clearance=finish_depth+thickness/(2*math.cos(lean))+support_height*math.tan(lean)
    offset = host["size_mm"][1]/2000 - rear_clearance - dot((x-cx,z-cz),back)
    return host, [x+offset*back[0],item["position_m"][1],z+offset*back[1]]


def splash_segments(item, units):
    """Join the backs at their true corner and divide the hob wall without coplanar faces."""
    thickness = item["size_mm"][1]/1000
    groups = {}
    for u in units:
        x,y,z=u["position_m"]; w,d,h=[v/1000 for v in u["size_mm"]]
        along,back=frame(u)
        line=dot((x,z),back)+d/2-thickness/2
        key=(round(u["yaw_deg"]%360,2),round(line,3),round(y+h,3))
        group=groups.setdefault(key,dict(along=along,back=back,line=line,height=y+h,yaw=u["yaw_deg"], spans=[]))
        s=dot((x,z),along);group["spans"].append([s-w/2,s+w/2])
    runs=[]
    for g in groups.values():
        for lo,hi in sorted(g["spans"]):
            if runs and runs[-1]["group"] is g and lo<=runs[-1]["hi"]+.004:
                runs[-1]["hi"]=max(runs[-1]["hi"],hi)
            else:runs.append(dict(group=g,lo=lo,hi=hi))
    # A blind-corner base has a worktop all the way back to the other wall.
    # Extend one linear slab to that intersection and butt its partner onto it.
    for i,a in enumerate(runs):
        for b in runs[i+1:]:
            g,k=a["group"],b["group"]
            if abs(dot(g["along"],k["along"]))>.001:continue
            centre=[g["back"][j]*g["line"]+k["back"][j]*k["line"] for j in (0,1)]
            ends=[]
            for r in (a,b):
                station=dot(centre,r["group"]["along"])
                edge=min(("lo","hi"),key=lambda e:abs(r[e]-station))
                ends.append((r,edge,station))
            if any(abs(r[e]-s)>.62 for r,e,s in ends):continue
            for n,(r,e,s) in enumerate(ends):
                outward=1 if e=="hi" else -1
                r[e]=s+outward*(thickness/2 if n==0 else -thickness/2)
    segments=[]
    hob=item["asset"]["hob_splash"]
    for r in runs:
        g,lo,hi=r["group"],r["lo"],r["hi"]
        low=item["size_mm"][2]/1000
        spans=[(lo,hi,low)]
        if abs(g["along"][1])>.999:
            za,zb=sorted(dot((0,z),g["along"]) for z in hob["z"])
            if lo<=za<zb<=hi:spans=[(lo,za,low),(za,zb,hob["height_mm"]/1000),(zb,hi,low)]
        for start,end,h in spans:
            if end-start<.001:continue
            s=(start+end)/2
            x,z=[g["along"][j]*s+g["back"][j]*g["line"] for j in (0,1)]
            segments.append(dict(x=x,z=z,base=g["height"],width=end-start,height=h,yaw=g["yaw"]))
    return segments


def rail_drape(length,radius):
    """Free drops, plus the half-turn round the bar, sum to the cut cloth length."""
    free=length-math.pi*radius
    return free*.55,free*.45
