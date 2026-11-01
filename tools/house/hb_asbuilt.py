"""As-built layer (CONTRACT.md section 6) from a photo survey of the house (sfm/house_v1.json after audit-4): what the
client's house actually looks like where it differs from the architect's drawing. Each record is an element with
layer "as_built" and "replaces": [<drawn element ids>]; its parts carry as_built: true. The drawn elements stay
underneath (builders and inspectors keep truth-to-plans; the viewer's As-built toggle swaps them).

What it builds (generic: every window, door and fixture the survey lists, on the drawn wall it sits on):
  - the host wall again with its openings re-cut where the survey puts the frames (layer as_built, replaces the
    drawn wall and the drawn window/door fixtures in it);
  - the real frames (colour, number of lights) as fixtures in those openings;
  - the surrounds: concrete / stone jambs, heads, sills, lead strip, packer, the soldier course (Jack's own bricks,
    cut unit by unit: master/phototex/units/soldier/band.jpg);
  - fixtures: satellite dish, meter box, lights, CCTV, alarm box, plaque, mirror, doorbell, downpipes, waste pipe.
Positions along each face (x, z) are the survey's, registered into the drawing frame by spec["as_built"]["shift"];
the depth of each face is the drawn wall's (where the survey's face depth differs, as the bay does by 0.255 m, that is
reported as a question, not built)."""
import math, copy, json, os
from hb_geom import prism, merge_meshes, box, hexa
from hb_build import atom, M, sig_of, slug
from hb_walls import layer_stack


def _src(survey_path):
    return f"photo survey {os.path.basename(survey_path)} (audit-4 registration)"


class Face:
    """an existing outside wall face found for a survey item: wall atom, its Wall, u from a drawing point"""
    def __init__(self, a):
        self.a = a; self.W = a["wall"]

    def u(self, p):
        W = self.W
        return (p[0] - W.a[0]) * W.d[0] + (p[1] - W.a[1]) * W.d[1]

    def c(self, o):                       # o: depth behind the outside face (negative = proud of it)
        return self.W.c_of(o)

    def quad(self, u0, u1, o0, o1):
        W = self.W
        ca, cb = self.c(o0), self.c(o1)
        return [W.point(u0, ca), W.point(u1, ca), W.point(u1, cb), W.point(u0, cb)]

    def slab(self, u0, u1, z0, z1, o0, o1):
        u0, u1 = sorted((u0, u1)); o0, o1 = sorted((o0, o1))
        return prism(self.quad(u0, u1, o0, o1), z0, z1)

    def frame_o(self):
        """depth of the frame's outer face (as the drawn fixtures: just behind the outer leaf, 70 mm profile)"""
        L = layer_stack(self.W.ckey, self.W.t)
        core = [l for l in L if not l.get("lining")]
        return core[0]["o1"] + 0.04 - 0.035, core[0]["o1"] + 0.04


def _find_face(atoms, axis, hint, along, z, storey=None, tol=0.32):
    """outside face of an existing external wall running along `axis` ('x' or 'y') whose face is within tol of
    `hint` (the survey's face coordinate), covering `along` and z"""
    best = None
    for a in atoms:
        if a["kind"] != "wall" or a["meta"].get("category") == "demolition" or a.get("as_built"): continue
        W = a["wall"]
        if W.ckey not in ("cav_existing", "cav337_new", "solid_existing"): continue
        if storey and W.storey != storey: continue
        if axis == "x" and abs(W.d[1]) > 0.02: continue
        if axis == "y" and abs(W.d[0]) > 0.02: continue
        if not (W.z0 - 0.05 <= z <= (W.z1 if not W.profile else max(zz for _, zz in W.profile)) + 0.05): continue
        F = Face(a)
        p_face = W.point((W.ua + W.ub) / 2, W.c_of(0.0))
        fc = p_face[1] if axis == "x" else p_face[0]
        if abs(fc - hint) > tol: continue
        uu = F.u((along, fc) if axis == "x" else (fc, along))
        if not (W.ua - 0.02 <= uu <= W.ub + 0.02): continue
        d = abs(fc - hint)
        if best is None or d < best[0]: best = (d, F, fc)
    return best


def porch_primary(vid, spec):
    cfg = spec.get("as_built") or {}
    return vid in cfg.get("primary_porch", [])


def apply_porch_door(state_atoms, spec, notes):
    """the version builds the porch that was actually built: its door opening goes where the photo survey puts it
    (CORRECTIONS-LOG 134, Jack 1 Nov 2026: 'at the finished stage the porch is the one actually built'). Done on the
    target state before the diff, so lintel, closers, tray, staging and checks all follow the real opening."""
    cfg = spec.get("as_built") or {}
    path = os.path.expanduser(cfg.get("survey", ""))
    if not os.path.exists(path): notes.append("porch as built: survey missing"); return
    S = json.load(open(path)); door = S.get("porch", {}).get("front_door")
    if not door: return
    dx, dy, dz = cfg["shift"]
    hint = S["porch"]["side_wall_outer_x"] + dx
    y0, y1 = door["y"][0] + dy, door["y"][1] + dy; z0, z1 = door["z"][0] + dz, door["z"][1] + dz
    hit = _find_face(state_atoms, "y", hint, (y0 + y1) / 2, (z0 + z1) / 2)
    if not hit: notes.append("porch as built: no porch side wall found"); return
    dface, F, fc = hit
    ua, ub = sorted((F.u((fc, y0)), F.u((fc, y1))))
    W = F.W
    for o in W.openings:
        if o["kind"] == "door" and min(o["u1"], ub) - max(o["u0"], ua) > 0.3:
            drawn = (round(o["u0"], 3), round(o["u1"], 3), round(o["z1"], 3))
            o.update(u0=ua, u1=ub, z0=max(0.0, z0), z1=z1, conf="measured from photos", as_built_from=drawn,
                     panes=door.get("colour", "anthracite composite"))
            notes.append(f"porch door as built: u {ua:.3f}-{ub:.3f}, head {z1:.3f} (drawn u {drawn[0]}-{drawn[1]}, head {drawn[2]}); threshold survey {z0:+.3f} built at the floor")
            for a in state_atoms:
                if a["kind"] == "fixture" and a.get("op") is o:
                    a.update(frame_mat="anthracite_upvc", leaf_mat="anthracite_upvc", porch_door_as_built=True)
                    a["meta"] = dict(a["meta"], label=f"{o['id']}: {door.get('colour', '')} (as built: photo survey; 4915.2B draws a 950x2110 upvc external door)",
                                     plain_label="Front door (as it was built)", drawing=_src(path), conf="measured from photos")
                    a["provenance"] = "photo survey"
            return


def loft_rooflight(spec, notes, vid="", vkind="existing"):
    """the owner's loft conversion is not on any BDS drawing: only its front roof window is measured (photo survey,
    the same numbers the garden model uses). A primary existing element in every version (it stands today and is kept),
    labelled as the owner's conversion; the rest of the loft waits for the Quest scan. It carries no drawing spec and no
    regs mapping (id LOFT-*, regs [])."""
    cfg = spec.get("as_built") or {}; lc = spec.get("loft")
    if vkind == "existing": return []            # converted after the 2022 survey (Jack, 1 Nov 2026)
    oc = spec.get("owner_changes", {})
    owner = vid in oc.get("versions", [])
    path = os.path.expanduser(cfg.get("survey", ""))
    if not lc or not os.path.exists(path): return []
    S = json.load(open(path)); rw = S.get("main_roof", {}).get("roof_window")
    if not rw: return []
    dx, dy, dz = cfg["shift"]
    wing = next(w for w in spec["defs"]["house_before"]["wings"] if w["id"] == "main")
    pl = next(p for p in wing["planes"] if p["id"] == "front")
    t = math.tan(math.radians(pl["pitch"])); y_r, z_r = pl["p0"][1], pl["p0"][2]
    zf = lambda y: z_r - (y_r - y) * t                                  # tile-top plane of the front slope (drawn)
    nrm = (0.0, -math.sin(math.radians(pl["pitch"])), math.cos(math.radians(pl["pitch"])))
    def on(x, y, lift): return (x + nrm[0] * lift, y + nrm[1] * lift, zf(y) + nrm[2] * lift)
    (x0, x1), (y0, y1) = [v + dx for v in rw["x"]], [v + dy for v in rw["along_slope_y"]]
    def slab(xa, xb, ya, yb, l0, l1):
        return hexa([on(xa, ya, l0), on(xb, ya, l0), on(xb, yb, l0), on(xa, yb, l0), on(xa, ya, l1), on(xb, ya, l1), on(xb, yb, l1), on(xa, yb, l1)])
    fr = 0.07
    frame = merge_meshes([slab(x0, x1, y0, y0 + fr, 0.0, 0.08), slab(x0, x1, y1 - fr, y1, 0.0, 0.08),
                          slab(x0, x0 + fr, y0 + fr, y1 - fr, 0.0, 0.08), slab(x1 - fr, x1, y0 + fr, y1 - fr, 0.0, 0.08)])
    glass = slab(x0 + fr, x1 - fr, y0 + fr, y1 - fr, 0.06, 0.07)
    lab = (f"roof window in the main front slope, {abs(x1 - x0) * 1000:.0f} x {abs(y1 - y0) / math.cos(math.radians(pl['pitch'])) * 1000:.0f} mm on the slope "
           f"(anthracite frame): part of the owner's loft conversion — {lc['label']}. Position and size measured from photos [{rw.get('evidence', '')}]")
    out = []
    for nm, mesh, mat in (("frame", frame, "anthracite_upvc"), ("glass", glass, "glass")):
        m = M("rooflight", "roof", lab, "photo survey sfm/house_v1.json main_roof.roof_window (not on the BDS drawings)", "measured from photos",
              "Roof window of the loft room (your own conversion)", False)
        m.update(stage_in=1, stage_out=None, seq=0.0, seq_out=None, category="existing")
        if owner:                                 # the build starts from 2022: the owner's conversion arrives in the sequence
            st, sq = oc["loft_rooflight"]["stage"]
            m.update(stage_in=st, seq=sq, category="new", label=f"{oc['loft_rooflight']['label']}: " + lab)
        a = atom(f"LOFT-rooflight-front-{nm}", "mesh", "existing", m, sig=None, mesh=mesh, mat=mat)
        a["cat"] = m["category"]; a["no_regs"] = True; a["loft"] = True
        out.append(a)
    notes.append(f"loft: front roof window x {x0:.3f}-{x1:.3f}, y {y0:.3f}-{y1:.3f} on the drawn front slope (owner's conversion; measured from photos)")
    return out


def as_built(vb, spec, notes):
    cfg = spec.get("as_built")
    if not cfg or vb.v["id"] not in cfg.get("versions", []): return [], []
    path = os.path.expanduser(cfg["survey"])
    if not os.path.exists(path):
        notes.append(f"as-built survey missing: {path}"); return [], []
    S = json.load(open(path))
    dx, dy, dz = cfg["shift"]
    X = lambda x: x + dx; Y = lambda y: y + dy; Z = lambda z: z + dz
    src = _src(path)
    atoms = vb.atoms
    out, questions = [], []
    rebuilt = {}                                           # drawn wall id -> (as-built wall atom, replaced fixture ids)

    def meta_for(host, group, label, plain, collide=False, conf="measured from photos"):
        m = M(group, host["meta"]["storey"], label, src, conf, plain, collide)
        for k in ("stage_in", "stage_out", "seq", "seq_out"):
            m[k] = host["meta"].get(k)
        m["category"] = host["meta"].get("category", "existing")
        if m["stage_in"] is None: m["stage_in"] = 1
        if m["seq"] is None: m["seq"] = 0.0
        return m

    def ab(a, replaces):
        a["provenance"] = "photo survey"
        if porch_primary(vb.v["id"], spec) and a["id"].startswith(("AB-X-porch", "AB-S-porch")):
            a["provenance"] = "owner / as built, not on drawings"; a["no_regs"] = True
            a["meta"] = dict(a["meta"], label=a["meta"]["label"] + " [by owner / as built, not on drawings]")
            PF_ = spec["staging"].get("porch_finish", {})
            st_, sq_ = PF_.get("step" if "step" in a["id"] else "fixtures", [a["meta"].get("stage_in", 1), 0.7])
            a["meta"] = dict(a["meta"], stage_in=st_, seq=sq_, stage_out=None, seq_out=None, category="new")
            a["cat"] = "new"
            return a
        a["as_built"] = dict(replaces=sorted(set(replaces)))
        a["cat"] = a["meta"]["category"]
        return a

    def rebuild(F):
        """the host wall again (layer as_built), its openings to be re-cut"""
        a = F.a
        if a["id"] in rebuilt: return rebuilt[a["id"]]
        W2 = copy.copy(a["wall"])
        W2.id = "AB-" + a["wall"].id
        W2.openings = [dict(o) for o in a["wall"].openings]
        W2.holes = list(a["wall"].holes)
        a2 = dict(a); a2["id"] = "AB-" + a["id"]; a2["wall"] = W2
        a2["meta"] = dict(a["meta"], label=a["meta"]["label"] + " — openings as built (photo survey)", drawing=src, conf="measured from photos")
        a2.pop("as_built", None)
        rec = dict(atom=a2, Face=Face(a2), replaces=[a["id"]])
        rebuilt[a["id"]] = rec
        return rec

    def fixtures_in(F, u0, u1, z0, z1):
        """drawn fixtures of this wall whose opening overlaps the range"""
        hits = []
        for f in atoms:
            if f["kind"] != "fixture" or f.get("as_built"): continue
            if f["wall"] is not F.W and f["wall"].id.split("~")[0] != F.W.id.split("~")[0]: continue
            o = f["op"]
            if min(o["u1"], u1) - max(o["u0"], u0) > 0.05 and min(o["z1"], z1) - max(o["z0"], z0) > 0.05: hits.append(f)
        return hits

    # ------------------------------------------------------------ windows and the front door
    items = []
    for wing, hint_key in (("left_wing", "face_y"), ("right_wing", "face_y")):
        Wg = S.get(wing, {})
        for w in Wg.get("windows", []):
            items.append(("window", wing, Y(Wg[hint_key]), w))
    door = S.get("porch", {}).get("front_door")
    primary = porch_primary(vb.v["id"], spec)
    PF = spec["staging"].get("porch_finish", {})
    if door and not primary: items.append(("door", "porch", X(S["porch"]["side_wall_outer_x"]), door))
    for kind, wing, hint, w in items:
        if kind == "window":
            x0, x1, z0, z1 = X(w["frame"][0]), X(w["frame"][1]), Z(w["frame"][2]), Z(w["frame"][3])
            hit = _find_face(atoms, "x", hint, (x0 + x1) / 2, (z0 + z1) / 2)
        else:
            y0, y1 = Y(door["y"][0]), Y(door["y"][1]); z0, z1 = Z(door["z"][0]), Z(door["z"][1])
            hit = _find_face(atoms, "y", hint, (y0 + y1) / 2, (z0 + z1) / 2)
        if not hit:
            notes.append(f"as-built: no drawn wall for {w.get('id', kind)}"); continue
        dface, F0, fc = hit
        if dface > 0.05:
            questions.append(dict(id=f"Q-asbuilt-face-{slug(w.get('id', kind))}", text=f"{w.get('id', 'front door')}: the photo survey puts this face "
                                  f"{dface * 1000:.0f} mm from the drawn wall face ({fc:+.3f} drawn vs {hint:+.3f} surveyed). The as-built layer keeps the "
                                  "drawn depth and uses the survey only along the face: which is right?", surveyed=round(hint, 3), drawn=round(fc, 3)))
        rec = rebuild(F0)
        F = rec["Face"]; W2 = F.W
        if kind == "window":
            ua, ub = sorted((F.u((x0, fc)), F.u((x1, fc))))
        else:
            ua, ub = sorted((F.u((fc, y0)), F.u((fc, y1))))
            if z0 < 0.0:          # the door can't stand below the floor it opens onto: survey z registration (+-0.1) noted
                questions.append(dict(id="Q-asbuilt-door-threshold", text=f"Front door: the survey's threshold reads {z0:+.3f} (below the drawn "
                                      f"porch floor 0.000); built from the floor, head {z1:+.3f} as surveyed (drawn head 2.110).", surveyed=round(z0, 3)))
                z0 = 0.0
        drawn = fixtures_in(F0, ua, ub, z0, z1)
        rec["replaces"] += [f["id"] for f in drawn]
        # re-cut: drop the drawn openings this frame replaces, add the surveyed one
        ids = {f["op"]["id"] for f in drawn}
        W2.openings = [o for o in W2.openings if o["id"] not in ids]
        oid = (w.get("id") or "front-door") + " (as built)"
        n = int(w.get("panes", 1))
        packer = 0.025 if w.get("packer_z") else 0.0
        op = dict(id=oid, kind=kind, u0=ua, u1=ub, z0=z0, z1=z1 + packer, panes=f"{n}-light", conf="measured from photos", src=src)
        W2.openings.append(op)
        opf = dict(op, z1=z1)
        jm = w.get("jamb_m", 0.07)
        colour = w.get("colour", "anthracite uPVC")
        fm = M("window" if kind == "window" else "door", W2.storey,
               f"{oid}: {colour}, {n} light{'s' if n > 1 else ''}" + (f"; {w.get('surround')}" if w.get("surround") else "") + f" [{w.get('evidence', door.get('evidence', '') if kind == 'door' else '')}]",
               src, "measured from photos", "Window (as it is today)" if kind == "window" else "Front door (as it is today)", False)
        for k in ("stage_in", "stage_out", "seq", "seq_out", "category"): fm[k] = rec["atom"]["meta"].get(k)
        fo0, fo1 = F.frame_o()
        fx = atom(f"AB-F-{slug(W2.id)}-{slug(oid)}", "fixture", "window" if kind == "window" else "door", fm, sig=None, wall=W2, op=opf,
                  c_plane=F.c((fo0 + fo1) / 2), nlights=n if kind == "window" else 1, internal=False,
                  frame_mat="anthracite_upvc", leaf_mat="anthracite_upvc" if kind == "door" else None, sill_mat="anthracite_upvc",
                  rooms=[(r_["name"], r_["poly"]) for r_ in vb.state.get("rooms", []) if r_.get("storey") == W2.storey])   # row 191: the window board needs the room
        out.append(ab(fx, rec["replaces"]))
        host = rec["atom"]
        parts = []                                           # (mesh, mat, group, label, plain)
        uj0, uj1 = ua - jm, ub + jm
        if kind == "window":
            head = w.get("head")
            stone = "stone" in (w.get("surround", "") + str(head))
            smat = "cream_stone" if (stone or "cream" in w.get("surround", "")) else "buff_concrete"
            surround_txt = w.get("surround", "")
            # jambs: 5 mm proud of the brick face, plus a 10 mm return lining the reveal to the frame
            # row 179: jambs, sill and head never share a face plane where they overlap (they z-fought at the corners): a stone
            # sill runs under the jambs; a sill band runs between them
            stone_sill = "first" in w["id"].lower() or "stone sill" in surround_txt or "cream stone" in surround_txt
            for (pa, pb, ra, rb) in ((uj0, ua, ua, ua + 0.01), (ub, uj1, ub - 0.01, ub)):
                parts.append((F.slab(pa, pb, z0 if stone_sill else z0 - (0.05 if not stone else 0.07), z1 + packer, -0.005, 0.0), smat, "jamb"))
                parts.append((F.slab(ra, rb, z0, z1 + packer, 0.0, fo0 - 0.002), smat, "jamb return"))   # up to the opening head (row 179: a 25 mm slot over the return)
            # sill under the frame
            if stone_sill:
                parts.append((F.slab(uj0 - 0.03, uj1 + 0.03, z0 - 0.07, z0, -0.035, 0.0), "cream_stone", "stone sill"))
            else:
                parts.append((F.slab(ua, ub, z0 - 0.05, z0, -0.005, 0.0), smat, "sill band under the sill board"))
            top = z1 + packer
            if w.get("head") == "concrete_lead":
                hz0, hz1 = Z(w["head_z"][0]), Z(w["head_z"][1])
                ls = w["lead_strip"]
                hu0, hu1 = sorted((F.u((X(ls["x"][0]), fc)), F.u((X(ls["x"][1]), fc))))
                pz0, pz1 = Z(w["packer_z"][0]), Z(w["packer_z"][1])
                parts.append((F.slab(ua + 0.01, ub - 0.01, pz0, pz1, 0.02, fo0 - 0.002), "packer", "packer over the frame (recessed, between the jamb returns)"))
                parts.append((F.slab(hu0, hu1, pz1, hz1, -0.005, 0.0), "buff_concrete", "concrete head"))
                parts.append((F.slab(hu0, hu1, Z(ls["z"][0]), Z(ls["z"][1]), -0.005 - ls.get("thick_m", 0.003), -0.005), "lead", "lead strip over the head"))
                top, su0, su1 = hz1, hu0, hu1
            elif w.get("lintel") and "2.22-2.30" in w.get("lintel", ""):
                hz1 = Z(2.30)
                parts.append((F.slab(uj0 - 0.10, uj1 + 0.10, z1 + packer, hz1, -0.005, 0.0), smat, "stone lintel"))
                top, su0, su1 = hz1, uj0 - 0.10, uj1 + 0.10
            else:                                            # head band up to the soffit (upstairs)
                soffit = Z(S.get("eaves", {}).get("soffit_z", 4.68))
                parts.append((F.slab(uj0, uj1, z1 + packer, soffit, -0.005, 0.0), smat, "head band up to the soffit"))
                su0 = None
            if "soldier" in (w.get("above") or "") and su0 is not None:
                m = F.slab(su0, su1, top, top + 0.22, -0.004, 0.0)
                parts.append((m, "soldier_brick", "soldier course of the house's own bricks", ("band", top, su0, F)))
            for pt in parts:
                mesh, mat, what = pt[0], pt[1], pt[2]
                pm = meta_for(host, "wall_outer", f"{oid} — {what}: {surround_txt or w.get('above', '')}".strip(), "Window surround (as it is today)")
                a = atom(f"AB-S-{slug(W2.id)}-{slug(oid)}-{slug(what)}", "mesh", "existing", pm, sig=None, mesh=mesh, mat=mat)
                if len(pt) > 3: a["uv_band"] = (pt[3][1], pt[3][2], pt[3][3].W.d)
                out.append(ab(a, rec["replaces"]))
        else:
            # door furniture: lever handle and letter plate (black)
            ul = ub - 0.09 if F.W.d[1] > 0 else ua + 0.09
            hm = merge_meshes([F.slab(ul - 0.06, ul + 0.06, 1.0, 1.03, -0.07, fo0 - 0.01),
                               F.slab((ua + ub) / 2 - 0.15, (ua + ub) / 2 + 0.15, 0.75, 0.80, fo0 - 0.012, fo0 - 0.002)])
            pm = meta_for(host, "door", "front door furniture: black lever handle and letter plate (photo survey)", "Door handle and letter plate")
            out.append(ab(atom(f"AB-S-{slug(W2.id)}-door-furniture", "mesh", "existing", pm, sig=None, mesh=hm, mat="black_metal"), rec["replaces"]))
    for rid, rec in rebuilt.items():
        out.append(ab(rec["atom"], rec["replaces"]))
    if door and primary:                                     # the built porch door's furniture, with the door
        h = _find_face(atoms, "y", X(S["porch"]["side_wall_outer_x"]), Y(sum(door["y"]) / 2), 1.0)
        if h:
            F = h[1]
            fx = next((f for f in atoms if f["kind"] == "fixture" and f.get("porch_door_as_built")), None)
            if fx:
                o = fx["op"]; ua, ub = o["u0"], o["u1"]; fo0, fo1 = F.frame_o()
                ul = ub - 0.09 if F.W.d[1] > 0 else ua + 0.09
                hm = merge_meshes([F.slab(ul - 0.06, ul + 0.06, 1.0, 1.03, -0.07, fo0 - 0.01),
                                   F.slab((ua + ub) / 2 - 0.15, (ua + ub) / 2 + 0.15, 0.75, 0.80, fo0 - 0.012, fo0 - 0.002)])
                st, sq = PF.get("door", [fx["meta"].get("stage_in", 1), 0.9])
                pm = M("door", "ground", "front door furniture: black lever handle and letter plate (photo survey)", src, "measured from photos", "Door handle and letter plate")
                pm.update(stage_in=st, stage_out=None, seq=min(0.99, sq + 0.02), seq_out=None, category="new")
                a = atom("AB-S-porch-door-furniture", "mesh", "existing", pm, sig=None, mesh=hm, mat="black_metal"); a["cat"] = "new"
                a["door_furniture_of"] = fx["id"]
                out.append(a)

    # ------------------------------------------------------------ fixtures on the faces
    def fix(fid, F, u0, u1, z0, z1, o0, o1, mat, label, plain, group="fitting", extra=None):
        pm = meta_for(F.a, group, label, plain)
        mesh = F.slab(u0, u1, z0, z1, o0, o1)
        if extra: mesh = merge_meshes([mesh] + extra)
        out.append(ab(atom(f"AB-X-{slug(fid)}", "mesh", "existing", pm, sig=None, mesh=mesh, mat=mat), []))

    def pipe_v(F, u, z0, z1, off, r=0.034, n=8):
        W = F.W
        c0 = F.c(-off)
        cx, cy = W.point(u, c0)
        poly = [(cx + r * math.cos(2 * math.pi * i / n), cy + r * math.sin(2 * math.pi * i / n)) for i in range(n)]
        return prism(poly, z0, z1)

    def face_for(wing, x=None, y=None, z=1.0):
        if wing == "left_wing": h = _find_face(atoms, "x", Y(S["left_wing"]["face_y"]), X(x), Z(z))
        elif wing == "right_wing": h = _find_face(atoms, "x", Y(S["right_wing"]["face_y"]), X(x), Z(z))
        elif wing == "porch_side": h = _find_face(atoms, "y", X(S["porch"]["side_wall_outer_x"]), Y(y), Z(z))
        elif wing == "porch_front": h = _find_face(atoms, "x", Y(S["porch"]["front_y"]), X(x), Z(z))
        elif wing == "bay_side": h = _find_face(atoms, "y", X(S["right_wing"]["x"][1]), Y(y), Z(z))
        else: h = None
        return h

    ground = -0.25
    for wing in ("left_wing", "right_wing"):
        for f in S.get(wing, {}).get("fixtures", []):
            fid, ev = f["id"], f.get("evidence", "")
            if not f.get("fixed", True): continue
            lab = f"{fid.replace('_', ' ')} ({f.get('colour', '')}) — photo survey [{ev}]"
            if "box" in f:
                bx0, bx1, bz0, bz1 = f["box"]
                h = face_for(wing, x=(bx0 + bx1) / 2, z=(bz0 + bz1) / 2)
                if not h: continue
                F = h[1]; fc = h[2]
                u0, u1 = sorted((F.u((X(bx0), fc)), F.u((X(bx1), fc))))
                proud = f.get("proud", 0.012)
                mat = "upvc_white" if f.get("colour", "").startswith("white") else "black_metal"
                plain = {"meter_box": "Meter box", "decorative_metal_panel": "Decorative metal panel", "decorative_metal_panel_2": "Decorative metal panel"}.get(fid, "Fixture on the wall")
                fix(f"{wing}-{fid}", F, u0, u1, Z(bz0), Z(bz1), -proud, 0.0, mat, lab, plain)
            elif fid == "satellite_dish":
                cxs, czs = f["centre"]
                h = face_for(wing, x=cxs, z=czs)
                if not h: continue
                F = h[1]; fc = h[2]; u = F.u((X(cxs), fc)); zc = Z(czs)
                r = f["size"] / 2; so = f.get("stand_off", 0.24)
                # dish: a shallow 12-sided disc facing the road, tilted up 25 deg, on a bracket arm to the wall
                W = F.W; n = 12; tilt = math.radians(25)
                c_d = F.c(-so)
                V = []; Fc = []
                for k_ in range(n):
                    t_ = 2 * math.pi * k_ / n
                    du, dzz = r * math.cos(t_), r * math.sin(t_)
                    for off in (0.0, 0.03):
                        cc = c_d + W.out * (off - dzz * math.sin(tilt))
                        p2 = W.point(u + du, cc)
                        V.append((p2[0], p2[1], zc + dzz * math.cos(tilt)))
                Fc.append(tuple(2 * k_ for k_ in range(n))[::-1]); Fc.append(tuple(2 * k_ + 1 for k_ in range(n)))
                for k_ in range(n):
                    a_, b_ = 2 * k_, 2 * ((k_ + 1) % n)
                    Fc.append((a_, b_, b_ + 1, a_ + 1))
                arm = F.slab(u - 0.02, u + 0.02, zc - r - 0.02, zc - r + 0.02, -so, 0.0)
                plate = F.slab(u - 0.08, u + 0.08, zc - r - 0.12, zc - r + 0.08, -0.012, 0.0)
                pm = meta_for(F.a, "fitting", lab, "Satellite dish")
                out.append(ab(atom(f"AB-X-{wing}-dish", "mesh", "existing", pm, sig=None, mesh=merge_meshes([(V, Fc), arm, plate]), mat="dish"), []))
            elif fid in ("waste_pipe", "downpipe"):
                xs = f["x"]
                if fid == "downpipe" and "side wall" in f.get("where", ""):
                    h = face_for("bay_side", y=f.get("y", 0.78), z=1.0)
                    if not h: continue
                    F = h[1]; fc = h[2]
                    yy = Y(f.get("y", 0.78))
                    # along the side wall: the survey's distance back from the bay's front corner, on the drawn corner
                    corner = Y(S["right_wing"]["face_y"])
                    hb = _find_face(atoms, "x", corner, X(S["right_wing"]["x"][1]) - 0.3, 1.0)
                    drawn_corner = hb[2] if hb else corner
                    u = F.u((fc, drawn_corner + (yy - corner)))
                else:
                    h = face_for(wing, x=xs, z=1.0)
                    if not h: continue
                    F = h[1]; fc = h[2]; u = F.u((X(xs), fc))
                ztop = Z(f["top_z"]) if f.get("top_z") else Z(S.get("eaves", {}).get("fascia", [4.66, 4.86])[0])
                ms = [pipe_v(F, u, ground, ztop, 0.06)]
                ms.append(F.slab(u - 0.034, u + 0.034, ztop - 0.07, ztop, -0.06, 0.0))         # the bend / offset into the wall
                pm = meta_for(F.a, "drain", lab, "Rain-water pipe" if fid == "downpipe" else "Waste pipe from the house")
                out.append(ab(atom(f"AB-X-{wing}-{fid}", "mesh", "existing", pm, sig=None, mesh=merge_meshes(ms), mat="black_upvc"), []))
            elif "x" in f and "z" in f:
                h = face_for(wing, x=f["x"], z=f["z"])
                if not h: continue
                F = h[1]; fc = h[2]; u = F.u((X(f["x"]), fc)); zc = Z(f["z"])
                sz = {"led_floodlight": (0.20, 0.15, 0.06), "cctv_bullet": (0.07, 0.07, 0.18), "low_wall_light": (0.10, 0.18, 0.08),
                      "alarm_bell_box": (f.get("size", [0.25, 0.33])[0], f.get("size", [0.25, 0.33])[1], 0.08)}.get(fid, (0.1, 0.1, 0.05))
                mat = "upvc_white" if f.get("colour", "").startswith("white") else "black_metal"
                plain = {"led_floodlight": "Security light", "cctv_bullet": "CCTV camera", "low_wall_light": "Wall light", "alarm_bell_box": "Alarm box"}.get(fid, "Fixture")
                fix(f"{wing}-{fid}", F, u - sz[0] / 2, u + sz[0] / 2, zc - sz[1] / 2, zc + sz[1] / 2, -sz[2], 0.0, mat, lab, plain)
    # porch
    P = S.get("porch", {})
    mir = P.get("mirror")
    if mir:
        bx0, bx1, bz0, bz1 = mir["box"]
        h = face_for("porch_front", x=(bx0 + bx1) / 2, z=(bz0 + bz1) / 2)
        if h:
            F = h[1]; fc = h[2]
            u0, u1 = sorted((F.u((X(bx0), fc)), F.u((X(bx1), fc))))
            z0, z1 = Z(bz0), Z(bz1); pr = mir.get("proud", 0.03); fw = 0.035
            frame = [F.slab(u0, u1, z0, z0 + fw, -pr, 0), F.slab(u0, u1, z1 - fw, z1, -pr, 0), F.slab(u0, u0 + fw, z0, z1, -pr, 0), F.slab(u1 - fw, u1, z0, z1, -pr, 0)]
            nv = mir.get("bars", {}).get("vertical", 3)
            for k_ in range(1, nv + 1):
                uu = u0 + (u1 - u0) * k_ / (nv + 1); frame.append(F.slab(uu - 0.008, uu + 0.008, z0 + fw, z1 - fw, -pr, -pr + 0.012))
            for zz in mir.get("bars", {}).get("horizontal_z", []):
                frame.append(F.slab(u0 + fw, u1 - fw, Z(zz) - 0.008, Z(zz) + 0.008, -pr, -pr + 0.012))
            pm = meta_for(F.a, "fitting", f"arched garden mirror on the porch front (not a window): black metal frame and glazing bars, "
                                         f"pointed arch heads not modelled — photo survey [{mir.get('evidence', '')}]", "Garden mirror on the wall")
            out.append(ab(atom("AB-X-porch-mirror-frame", "mesh", "existing", pm, sig=None, mesh=merge_meshes(frame), mat="black_metal"), []))
            out.append(ab(atom("AB-X-porch-mirror-glass", "mesh", "existing", dict(pm), sig=None,
                               mesh=F.slab(u0 + fw, u1 - fw, z0 + fw, z1 - fw, -pr + 0.012, -0.004), mat="mirror"), []))
    for f in P.get("fixtures", []):
        if not f.get("fixed", True): continue
        fid = f["id"]; lab = f"{fid.replace('_', ' ')} — photo survey [{f.get('evidence', '')}]"
        if fid == "house_number_plaque":
            h = face_for("porch_side", y=sum(f["y"]) / 2, z=sum(f["z"]) / 2)
            if not h: continue
            F = h[1]; fc = h[2]
            u0, u1 = sorted((F.u((fc, Y(f["y"][0]))), F.u((fc, Y(f["y"][1])))))
            fix("porch-plaque", F, u0, u1, Z(f["z"][0]), Z(f["z"][1]), -0.025, -0.015, "slate", lab + " " + f.get("colour", ""), "House number plaque",
                extra=[F.slab(u0 + 0.02, u0 + 0.03, Z(f["z"][0]) + 0.02, Z(f["z"][0]) + 0.03, -0.015, 0.0),
                       F.slab(u1 - 0.03, u1 - 0.02, Z(f["z"][0]) + 0.02, Z(f["z"][0]) + 0.03, -0.015, 0.0)])
        elif fid == "video_doorbell":
            h = face_for("porch_side", y=f["y"], z=f["z"])
            if not h: continue
            F = h[1]; fc = h[2]; u = F.u((fc, Y(f["y"])))
            fix("porch-doorbell", F, u - 0.03, u + 0.03, Z(f["z"]) - 0.065, Z(f["z"]) + 0.065, -0.03, 0.0, "black_metal", lab, "Video doorbell")
        elif fid == "downpipe":
            h = face_for("porch_front", x=f["x"], z=1.0)
            if not h: continue
            F = h[1]; fc = h[2]; u = F.u((X(f["x"]), fc))
            ztop = Z(P.get("roof", {}).get("fascia", [1.96, 2.18])[0])
            pm = meta_for(F.a, "drain", lab, "Rain-water pipe")
            out.append(ab(atom("AB-X-porch-downpipe", "mesh", "existing", pm, sig=None, mesh=pipe_v(F, u, ground, ztop, 0.06), mat="black_upvc"), []))
        elif fid == "cctv_camera":
            h = face_for("porch_front", x=f["x"], z=1.0)
            if not h: continue
            F = h[1]; fc = h[2]; u = F.u((X(f["x"]), fc))
            fix("porch-cctv", F, u - 0.05, u + 0.05, Z(f["z"]) - 0.07, Z(f["z"]), -0.12, 0.0, "upvc_white", lab, "CCTV camera")
    st = P.get("step")
    if st:
        h = face_for("porch_side", y=sum(st["y"]) / 2, z=0.5)
        if h:
            F = h[1]
            x0, x1 = X(st["x"][0]), X(st["x"][1]); y0, y1 = Y(st["y"][0]), Y(st["y"][1])
            pm = meta_for(F.a, "fitting", f"front step: top {Z(st['top_z']):+.3f} — photo survey [{st.get('evidence', '')}]", "Front step", collide=True)
            out.append(ab(atom("AB-X-porch-step", "mesh", "existing", pm, sig=None,
                               mesh=box(min(x0, x1), max(x0, x1) - 0.004, min(y0, y1), max(y0, y1), ground, max(Z(st["top_z"]), ground + 0.02)), mat="concrete"), []))
    return out, questions
