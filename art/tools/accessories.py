"""
Extra props, built to fit each character's MakeHuman body (garments.py does the clothes,
caps, glasses and watches):
- **Skins:** headphones, a witch hat, a paper burger hat, a crown and cape, a work lanyard, a
  lifting belt and a coffee stirrer behind the ear.
- **Bosses and minions:** the Copilot's hood, rope belt, scythe and laptops, the chef hat,
  the apron, a spatula, a sauce bottle, a fish, a mechanical keyboard and a coffee mug.

Each prop is weighted to the bone it rides on, so it moves with the hero's animations.
Called by garments.dress() with the look's "acc" list.
"""

import math

import numpy as np
from mathutils import Vector

import garments as G
from hero_builder import hexc

B = G.B


def head_info(bd, rig):
    k = bd.height / 1.8
    head = bd.is_dom("Head") & bd.body
    P = bd.co[head]
    top = float(P[:, 2].max())
    eyes = G.eyes_of(bd)
    eye_z = float((eyes[0][2] + eyes[1][2]) / 2) if eyes else top - 0.12 * k
    upper = P[P[:, 2] > eye_z]
    cy = float(np.median(upper[:, 1])) if len(upper) else float(np.median(P[:, 1]))
    band = P[np.abs(P[:, 2] - (eye_z + 0.02 * k)) < 0.012 * k]
    half_w = float(np.abs(band[:, 0]).max()) if len(band) else 0.075 * k
    depth = float(band[:, 1].max() - band[:, 1].min()) / 2 if len(band) else 0.1 * k
    ears = bd.groups.get("ears")
    ear = {}
    for sg in (1, -1):
        e = bd.co[ears] if ears else np.zeros((0, 3))
        e = e[e[:, 0] * sg > 0]
        ear[sg] = e.mean(0) if len(e) else np.array([sg * half_w, cy + 0.01 * k, eye_z - 0.01 * k])
    # The hair (and a cap) sit above the scalp.
    hair_top = top
    for o in rig.children_recursive:
        if o.type == "MESH" and o is not bd.obj:
            cs = [o.matrix_world @ Vector(c) for c in o.bound_box]
            zc = sum(c.z for c in cs) / 8
            if zc > eye_z and abs(sum(c.x for c in cs) / 8) < 0.1 and max(c.z for c in cs) < top + 0.1:
                hair_top = max(hair_top, max(c.z for c in cs))
    return dict(top=top, hair_top=hair_top, eye_z=eye_z, cy=cy, half_w=half_w, depth=depth, ear=ear, k=k)


def mesh(name, verts, faces, mats, face_mat, weights, rig):
    uvs = [[(0, 0)] * len(f) for f in faces]
    if isinstance(weights, dict):
        weights = [weights] * len(verts)
    return G.make_mesh_object(name, verts, faces, uvs, weights, mats, face_mat, rig)


def loft(rings, closed=True):
    """Quads between consecutive rings of points (each ring the same length)."""
    verts, faces = [], []
    n = len(rings[0])
    for r in rings:
        verts.extend(r)
    for i in range(len(rings) - 1):
        for j in range(n if closed else n - 1):
            j2 = (j + 1) % n
            faces.append((i * n + j, i * n + j2, (i + 1) * n + j2, (i + 1) * n + j))
    return verts, faces


# --------------------------------------------------------------------------- props
def headphones(bd, rig, look, mid, hi):
    k = hi["k"]
    cap = "cap" in look.get("acc", [])
    top = hi["hair_top"] + (0.03 * k if cap else 0.012 * k)
    el, er = hi["ear"][1], hi["ear"][-1]
    ear_z = float((el[2] + er[2]) / 2)
    ear_y = float((el[1] + er[1]) / 2)
    hw = hi["half_w"] + 0.016 * k
    dark = G.material("%s_phones" % mid, hexc("#1c1c1e"), rough=0.45)
    accent = G.material("%s_phones_accent" % mid, hexc(look.get("phones_color", "#e74c3c")), rough=0.4)
    arc = [Vector((math.sin(t) * hw, ear_y, ear_z + 0.02 * k + (top - ear_z - 0.02 * k) * math.cos(t)))
           for t in np.linspace(-math.pi / 2, math.pi / 2, 19)]
    G.tube("%s.phones_band" % mid, arc, (0.012 * k, 0.005 * k), dark, rig, "Head", seg=8)
    for sg in (1, -1):
        c = Vector((sg * (hw + 0.004 * k), ear_y, ear_z))
        G.tube("%s.phones_cup" % mid, [c - Vector((sg * 0.012 * k, 0, 0)), c + Vector((sg * 0.022 * k, 0, 0))],
               0.038 * k, dark, rig, "Head", seg=16)
        G.tube("%s.phones_ring" % mid, [c + Vector((sg * 0.022 * k, 0, 0)), c + Vector((sg * 0.026 * k, 0, 0))],
               0.026 * k, accent, rig, "Head", seg=16)


def witch_hat(bd, rig, look, mid, hi):
    k = hi["k"]
    base_z = hi["hair_top"] - 0.03 * k
    cy = hi["cy"] + 0.01 * k
    black = G.material("%s_witch" % mid, hexc(look.get("hat_color", "#1b1424")), rough=0.85)
    band = G.material("%s_witch_band" % mid, hexc("#8e44ad"), rough=0.6)
    n = 20
    rings = []
    for i in range(9):
        t = i / 8
        r = 0.115 * k * (1 - t) ** 1.15 + 0.004 * k
        z = base_z + 0.36 * k * t
        y = cy + 0.11 * k * t * t
        rings.append([Vector((math.cos(a) * r, y + math.sin(a) * r, z)) for a in np.linspace(0, 2 * math.pi, n, endpoint=False)])
    v, f = loft(rings)
    mesh("%s.witch_cone" % mid, v, f, [black], None, {B + "Head": 1.0}, rig)
    # Brim: a wide flat ring, a little wavy.
    rings = []
    for r in (0.095 * k, 0.17 * k, 0.25 * k):
        rings.append([Vector((math.cos(a) * r, cy + math.sin(a) * r * 0.95,
                              base_z - 0.004 * k - (0.012 * k * (r / (0.25 * k)) ** 2) * (1 + 0.3 * math.sin(3 * a))))
                      for a in np.linspace(0, 2 * math.pi, 28, endpoint=False)])
    v, f = loft(rings)
    mesh("%s.witch_brim" % mid, v, f, [black], None, {B + "Head": 1.0}, rig)
    ring = [Vector((math.cos(a) * 0.112 * k, cy + math.sin(a) * 0.112 * k, base_z + 0.018 * k))
            for a in np.linspace(0, 2 * math.pi, 24, endpoint=False)]
    G.tube("%s.witch_band" % mid, ring, (0.004 * k, 0.016 * k), band, rig, "Head", closed=True, seg=6)


def paper_hat(bd, rig, look, mid, hi):
    """A folded paper burger-joint hat."""
    k = hi["k"]
    z0 = hi["hair_top"] - 0.04 * k
    cy = hi["cy"]
    rx, ry = hi["half_w"] * 0.8, 0.105 * k
    white = G.material("%s_paper" % mid, hexc("#f5f5f0"), rough=0.9)
    red = G.material("%s_paper_band" % mid, hexc(look.get("hat_band", "#d62828")), rough=0.8)
    n = 28
    angs = np.linspace(0, 2 * math.pi, n, endpoint=False)
    bottom = [Vector((math.cos(a) * rx, cy + math.sin(a) * ry, z0)) for a in angs]
    mid_r = [Vector((math.cos(a) * rx * 0.75, cy + math.sin(a) * ry * 0.97, z0 + 0.022 * k)) for a in angs]
    ridge = [Vector((math.cos(a) * 0.004 * k, cy + math.sin(a) * ry * 0.9, z0 + 0.08 * k * (1 - 0.25 * abs(math.sin(a)) ** 4)))
             for a in angs]
    v, f = loft([bottom, mid_r, ridge])
    fm = [1] * n + [0] * n
    mesh("%s.paper_hat" % mid, v, f, [white, red], fm, {B + "Head": 1.0}, rig)


def crown(bd, rig, look, mid, hi):
    k = hi["k"]
    z0 = hi["hair_top"] - 0.03 * k
    cy = hi["cy"]
    rx, ry = hi["half_w"] * 0.95, hi["depth"] * 0.9
    gold = G.material("%s_crown" % mid, hexc("#e2b23c"), rough=0.25, metal=1.0)
    gem = G.material("%s_gem" % mid, hexc("#c0392b"), rough=0.1)
    ring = [Vector((math.cos(a) * rx, cy + math.sin(a) * ry, z0)) for a in np.linspace(0, 2 * math.pi, 28, endpoint=False)]
    G.tube("%s.crown_band" % mid, ring, (0.004 * k, 0.012 * k), gold, rig, "Head", closed=True, seg=6)
    for i in range(8):
        a = i * 2 * math.pi / 8 - math.pi / 2
        base = Vector((math.cos(a) * rx, cy + math.sin(a) * ry, z0 + 0.008 * k))
        tip = base + Vector((math.cos(a) * 0.006 * k, math.sin(a) * 0.006 * k, 0.05 * k))
        G.tube("%s.crown_spike" % mid, [base, tip], (0.012 * k, 0.004 * k), gold, rig, "Head", seg=4)
        G.tube("%s.crown_gem" % mid, [tip, tip + Vector((0, 0, 0.008 * k))], 0.006 * k, gem, rig, "Head", seg=8)


def cape(bd, rig, look, mid, hi):
    k = hi["k"]
    nh = bd.j("Neck")
    knee = bd.j("LeftLeg")[2]
    col = G.material("%s_cape" % mid, hexc(look.get("cape_color", "#5b2a86")), rough=0.7)
    trim = G.material("%s_cape_trim" % mid, hexc("#e2b23c"), rough=0.3, metal=1.0)
    rows, cols = 10, 9
    back = bd.body & (bd.co[:, 1] > bd.j("Spine1")[1] - 0.02 * k)

    def back_y(x, z):
        near = back & (np.abs(bd.co[:, 0] - x) < 0.05 * k) & (np.abs(bd.co[:, 2] - z) < 0.05 * k)
        return float(bd.co[near, 1].max()) if near.any() else float(bd.j("Spine1")[1] + 0.1 * k)

    grid = []
    for i in range(rows):
        t = i / (rows - 1)
        z = (nh[2] - 0.01 * k) * (1 - t) + (knee + 0.05 * k) * t
        half = 0.15 * k * (1 - t) + 0.26 * k * t
        row = []
        for j in range(cols):
            x = -half + 2 * half * j / (cols - 1)
            y = back_y(x * 0.8, z) + 0.025 * k + 0.07 * k * t * t
            row.append(Vector((x, y, z)))
        grid.append(row)
    v, f = loft(grid, closed=False)
    wts = []
    for i in range(rows):
        t = i / (rows - 1)
        w = {B + "Spine2": max(0.0, 1 - 2.2 * t), B + "Spine1": max(0.0, 1 - abs(t - 0.45) * 2.5),
             B + "Hips": max(0.0, (t - 0.35) * 1.6)}
        s = sum(w.values())
        wts.extend([{kk: vv / s for kk, vv in w.items() if vv > 0}] * cols)
    mesh("%s.cape" % mid, v, f, [col], None, wts, rig)
    G.tube("%s.cape_trim" % mid, grid[-1], 0.006 * k, trim, rig, "Hips", seg=6)
    G.tube("%s.cape_clasp" % mid, [grid[0][0] + Vector((0, -0.03 * k, 0)), grid[0][-1] + Vector((0, -0.03 * k, 0))],
           0.006 * k, trim, rig, "Spine2", seg=6)


def lanyard(bd, rig, look, mid, hi):
    k = hi["k"]
    nh = bd.j("Neck")
    z = nh[2] + 0.004 * k
    ring = bd.body & (np.abs(bd.co[:, 2] - z) < 0.012 * k) & (np.abs(bd.co[:, 0]) < 0.09 * k)
    pts = bd.co[ring]
    cy = float(pts[:, 1].mean()) if len(pts) else nh[1]
    rx = float(np.abs(pts[:, 0]).max()) + 0.012 * k if len(pts) else 0.06 * k
    ry = float(np.abs(pts[:, 1] - cy).max()) + 0.012 * k if len(pts) else 0.06 * k
    strap = G.material("%s_lanyard" % mid, hexc(look.get("lanyard_color", "#1f4e8c")), rough=0.6)
    chest_z = bd.j("Spine2")[2] + 0.01 * k
    front = bd.body & (np.abs(bd.co[:, 0]) < 0.02 * k) & (np.abs(bd.co[:, 2] - chest_z) < 0.03 * k)
    fy = float(bd.co[front, 1].min()) - 0.032 * k if front.any() else cy - 0.15 * k
    badge_top = Vector((0, fy, chest_z - 0.03 * k))
    loop = []
    for a in np.linspace(math.radians(-60), math.radians(240), 22):  # around the back of the neck
        loop.append(Vector((math.cos(a) * rx, cy - math.sin(a) * ry * -1.0, z + 0.01 * k * math.sin(a))))
    path = [badge_top + Vector((0.012 * k, 0, 0))] + loop + [badge_top - Vector((0.012 * k, 0, 0))]
    G.tube("%s.lanyard" % mid, path, 0.0032 * k, strap, rig, "Spine2", seg=6)
    white = G.material("%s_badge" % mid, hexc("#f4f4f4"), rough=0.4)
    blue = G.material("%s_badge_top" % mid, hexc(look.get("lanyard_color", "#1f4e8c")), rough=0.4)
    c = badge_top - Vector((0, 0.002, 0.045 * k))
    G.tube("%s.badge" % mid, [c - Vector((0, 0, 0.038 * k)), c + Vector((0, 0, 0.038 * k))], (0.028 * k, 0.003 * k),
           white, rig, "Spine2", seg=4, sq=8.0)
    G.tube("%s.badge_top" % mid, [c + Vector((0, -0.0035, 0.024 * k)), c + Vector((0, -0.0035, 0.036 * k))],
           (0.026 * k, 0.001 * k), blue, rig, "Spine2", seg=4, sq=8.0)


def belt(bd, rig, look, mid, hi):
    k = hi["k"]
    hips_z, spine_z = bd.j("Hips")[2], bd.j("Spine1")[2]
    z = hips_z + 0.45 * (spine_z - hips_z)
    sl = bd.body & (np.abs(bd.co[:, 2] - z) < 0.015 * k) & bd.is_dom("Hips", "Spine", "Spine1")
    P = bd.co[sl]
    cx, cy = float(P[:, 0].mean()), float(P[:, 1].mean())
    ang = np.arctan2(P[:, 1] - cy, P[:, 0] - cx)
    rad = np.hypot(P[:, 0] - cx, P[:, 1] - cy)
    bins = 36
    r = np.zeros(bins)
    for i in range(bins):
        a0 = -math.pi + i * 2 * math.pi / bins
        m = (ang >= a0) & (ang < a0 + 2 * math.pi / bins)
        r[i] = rad[m].max() if m.any() else np.nan
    good = ~np.isnan(r)
    r = np.interp(np.arange(bins), np.where(good)[0], r[good], period=bins)
    r = (r + np.roll(r, 1) + np.roll(r, -1)) / 3 + 0.03 * k
    leather = G.material("%s_belt" % mid, hexc("#3b2416"), rough=0.6)
    metal = G.material("%s_buckle" % mid, hexc("#c9ccd1"), rough=0.25, metal=1.0)
    rings = []
    for dz in (-0.055 * k, 0.055 * k):
        rings.append([Vector((cx + math.cos(-math.pi + (i + 0.5) * 2 * math.pi / bins) * r[i],
                              cy + math.sin(-math.pi + (i + 0.5) * 2 * math.pi / bins) * r[i], z + dz))
                      for i in range(bins)])
    v, f = loft(rings)
    mesh("%s.belt" % mid, v, f, [leather], None, {B + "Hips": 0.5, B + "Spine": 0.5}, rig)
    fi = int(np.argmin([math.sin(-math.pi + (i + 0.5) * 2 * math.pi / bins) for i in range(bins)]))
    fp = Vector((cx, cy - r[fi] - 0.004 * k, z))
    G.tube("%s.buckle" % mid, [fp - Vector((0, 0, 0.04 * k)), fp + Vector((0, 0, 0.04 * k))], (0.035 * k, 0.005 * k),
           metal, rig, "Hips", seg=4, sq=8.0)


def stirrer(bd, rig, look, mid, hi):
    k = hi["k"]
    e = Vector(tuple(hi["ear"][-1]))  # behind the right ear
    wood = G.material("%s_stirrer" % mid, hexc("#c8a165"), rough=0.8)
    a = e + Vector((-0.012 * k, 0.012 * k, 0.03 * k))
    b = e + Vector((-0.014 * k, -0.035 * k, -0.035 * k))
    G.tube("%s.stirrer" % mid, [a, b], (0.0035 * k, 0.0012 * k), wood, rig, "Head", seg=4, sq=8.0)


def radii_around(P, cx, cy, bins=72):
    """How far P reaches from (cx, cy) in each of `bins` directions, by angle from the front
    (-y) toward his left (+x); empty directions are filled in, then smoothed. None if P is
    empty."""
    if len(P) == 0:
        return None
    ang = np.arctan2(P[:, 0] - cx, -(P[:, 1] - cy))
    rad = np.hypot(P[:, 0] - cx, P[:, 1] - cy)
    idx = ((ang + math.pi) / (2 * math.pi) * bins).astype(int) % bins
    r = np.full(bins, np.nan)
    for i in range(bins):
        m = idx == i
        if m.any():
            r[i] = rad[m].max()
    good = ~np.isnan(r)
    r = np.interp(np.arange(bins), np.where(good)[0], r[good], period=bins)
    for _ in range(2):
        r = (r + np.roll(r, 1) + np.roll(r, -1)) / 3
    return r


def radius_at(r, theta):
    """radii_around()'s reach at angle theta (radians from the front), interpolated."""
    bins = len(r)
    f = (theta + math.pi) / (2 * math.pi) * bins - 0.5
    i0 = int(math.floor(f))
    w = f - i0
    return float(r[i0 % bins] * (1 - w) + r[(i0 + 1) % bins] * w)


def thicken(obj, thickness):
    """Gives a sheet real thickness (a Solidify, applied under the armature)."""
    import bpy
    sol = obj.modifiers.new("Solidify", "SOLIDIFY")
    sol.thickness = thickness
    sol.offset = -1.0
    sol.use_rim = True
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.modifier_move_to_index(modifier="Solidify", index=0)
    bpy.ops.object.modifier_apply(modifier="Solidify")


def hood(bd, rig, look, mid, hi):
    """A raised reaper's hood, lofted from rings around the head and neck: roomy, rising to a
    soft point at the back, its brow jutting out past the face so the face sits in its
    shadow, and draped over the shoulders. The face and throat stay open."""
    import bmesh
    k = hi["k"]
    eye_z, top, cy = hi["eye_z"], hi["top"], hi["cy"]
    neck_z = float(bd.j("Neck")[2])
    chin = bd.joints.get("jaw")
    chin_z = float(chin[2]) if chin is not None else eye_z - 0.09 * k
    near = bd.body & bd.is_dom("Head", "Neck", "Spine2", "LeftShoulder", "RightShoulder")
    # Rings from the shoulders up: (height, half-angle of the face opening in degrees, how far
    # the opening's edge juts forward, room left around the body, skin weights). The opening
    # runs on down to the neck, and the drape's hem rises toward the front (lift), so the
    # hood ends in rounded corners there rather than flaps.
    levels = [
        (neck_z - 0.045 * k, 46, 0.0, 0.05, {"Spine2": 1.0}),
        (neck_z + 0.005 * k, 40, 0.01, 0.055, {"Spine2": 0.55, "Neck": 0.45}),
        (chin_z - 0.025 * k, 42, 0.025, 0.06, {"Neck": 0.5, "Head": 0.5}),
        (chin_z + 0.02 * k, 50, 0.04, 0.055, {"Head": 0.85, "Neck": 0.15}),
        ((chin_z + eye_z) / 2, 56, 0.05, 0.05, {"Head": 1.0}),
        (eye_z, 56, 0.058, 0.05, {"Head": 1.0}),
        (eye_z + 0.045 * k, 48, 0.064, 0.05, {"Head": 1.0}),
        (eye_z + 0.085 * k, 28, 0.06, 0.05, {"Head": 1.0}),
        (top - 0.015 * k, 0, 0.035, 0.05, {"Head": 1.0}),
    ]
    n = 41
    rings, wts = [], []
    last = None
    for li, (z, gap, jut, room, w) in enumerate(levels):
        sl = near & (np.abs(bd.co[:, 2] - z) < 0.015 * k)
        P = bd.co[sl]
        ccy = float((P[:, 1].min() + P[:, 1].max()) / 2) if len(P) else cy
        r = radii_around(P, 0.0, ccy)
        if r is None:
            r, ccy = last
        last = (r, ccy)
        ring = []
        for j in range(n):
            th = math.radians(gap + (360 - 2 * gap) * j / (n - 1))
            rr = radius_at(r, th if th <= math.pi else th - 2 * math.pi) + room * k
            front = max(0.0, math.cos(th))
            lift = 0.045 * k * front ** 2 if li == 0 else 0.0
            ring.append(Vector((math.sin(th) * rr, ccy - math.cos(th) * rr - jut * k * front, z + lift)))
        rings.append(ring)
        wts.append({B + b: v for b, v in w.items()})
    # Over the top of the head the hood narrows and leans back to a soft point.
    r, ccy = last
    for dz, scale, back, jut in ((0.035, 0.74, 0.03, 0.015), (0.062, 0.42, 0.075, 0.0)):
        ring = []
        for j in range(n):
            th = math.radians(360 * j / (n - 1))
            rr = (radius_at(r, th if th <= math.pi else th - 2 * math.pi) + 0.05 * k) * scale
            ring.append(Vector((math.sin(th) * rr, ccy + back * k - math.cos(th) * rr - jut * k * max(0.0, math.cos(th)),
                                top + dz * k)))
        rings.append(ring)
        wts.append({B + "Head": 1.0})
    tip = Vector((0.0, ccy + 0.17 * k, top + 0.055 * k))
    verts, faces = loft(rings, closed=False)
    t0 = len(verts)
    verts.append(tip)
    o = (len(rings) - 1) * n
    faces += [(o + j, o + j + 1, t0) for j in range(n - 1)]
    vw = [w for w in wts for _ in range(n)] + [{B + "Head": 1.0}]
    col = G.material("%s_hood" % mid, hexc(look.get("hood_color", "#141428")), rough=0.9)
    obj = mesh("%s.hood" % mid, verts, faces, [col], None, vw, rig)
    bm = bmesh.new()  # close the seam where the closed rings meet in front
    bm.from_mesh(obj.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    G.smooth_loops(bm, 4)  # round off the corners of the openings
    for _ in range(2):  # soften the rings into cloth (the open edges stay put)
        inner = [v for v in bm.verts if not v.is_boundary]
        bmesh.ops.smooth_vert(bm, verts=inner, factor=0.5, use_axis_x=True, use_axis_y=True, use_axis_z=True)
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    thicken(obj, 0.012 * k)


def cord(bd, rig, look, mid, hi):
    """A rope belt over a robe, tied in front at his left with two knotted ends hanging."""
    k = hi["k"]
    hips_z, spine_z = bd.j("Hips")[2], bd.j("Spine1")[2]
    z = hips_z + 0.45 * (spine_z - hips_z) - 0.016 * k  # over the robe's waist seam
    sl = bd.body & (np.abs(bd.co[:, 2] - z) < 0.015 * k) & bd.is_dom("Hips", "Spine", "Spine1")
    pts = bd.co[sl]
    cx, cy = float(pts[:, 0].mean()), float(pts[:, 1].mean())
    r = radii_around(pts, cx, cy)
    rope = G.material("%s_cord" % mid, hexc(look.get("cord_color", "#4a4a6a")), rough=0.95)
    parts = Parts()
    ring = []
    for th in np.linspace(-math.pi, math.pi, 49):
        rr = radius_at(r, th) + 0.045 * k
        ring.append(Vector((cx + math.sin(th) * rr, cy - math.cos(th) * rr, z)))
    parts.taper(ring, [(0.008 * k, 0.008 * k)] * len(ring), rope, seg=8)
    th = math.radians(28)  # the knot, a little to his left of center
    rr = radius_at(r, th) + 0.05 * k
    knot = Vector((cx + math.sin(th) * rr, cy - math.cos(th) * rr, z))
    parts.taper([knot - Vector((0, 0.004 * k, 0)), knot + Vector((0, -0.024 * k, 0))],
                [(0.017 * k, 0.017 * k), (0.012 * k, 0.012 * k)], rope, seg=10)
    for dx, length in ((-0.012, 0.3), (0.016, 0.24)):  # the two hanging ends, each with a knot
        a = knot + Vector((dx * k, -0.012 * k, -0.01 * k))
        b = a + Vector((dx * 0.4 * k, -0.045 * k, -length * k))
        parts.taper([a, (a + b) / 2, b], [(0.007 * k, 0.007 * k)] * 3, rope, seg=8)
        parts.taper([b + Vector((0, 0, 0.012 * k)), b - Vector((0, 0, 0.014 * k))],
                    [(0.012 * k, 0.012 * k), (0.009 * k, 0.009 * k)], rope, seg=8)
    return mesh("%s.cord" % mid, parts.verts, parts.faces, parts.mats, parts.fmat,
                {B + "Hips": 0.5, B + "Spine": 0.5}, rig)


def chef_hat(bd, rig, look, mid, hi):
    """A tall, puffy chef's toque."""
    k = hi["k"]
    z0 = hi["hair_top"] - 0.035 * k
    cy = hi["cy"]
    rx, ry = hi["half_w"] * 1.02, hi["depth"] * 1.05
    white = G.material("%s_chef_hat" % mid, hexc("#fafafa"), rough=0.92)
    angs = np.linspace(0, 2 * math.pi, 32, endpoint=False)
    rings = []
    for s, dz, puff in ((1.0, 0.0, 0.0), (1.0, 0.06, 0.0), (1.1, 0.085, 0.05), (1.24, 0.14, 0.07), (1.22, 0.19, 0.07),
                        (1.02, 0.225, 0.05), (0.6, 0.243, 0.02), (0.06, 0.248, 0.0)):
        rings.append([Vector((math.cos(a) * rx * s * (1 + puff * math.sin(6 * a)),
                              cy + math.sin(a) * ry * s * (1 + puff * math.sin(6 * a)), z0 + dz * k)) for a in angs])
    v, f = loft(rings)
    mesh("%s.chef_hat" % mid, v, f, [white], None, {B + "Head": 1.0}, rig)


def apron(bd, rig, look, mid, hi):
    """A bib apron: over the chest, hanging flat across both legs to the knees, with a neck
    strap and waist ties."""
    k = hi["k"]
    col = G.material("%s_apron" % mid, hexc(look.get("apron_color", "#ffffff")), rough=0.85)
    hips_z, spine_z = bd.j("Hips")[2], bd.j("Spine1")[2]
    waist = hips_z + 0.45 * (spine_z - hips_z)
    chest = bd.j("Spine2")[2] + 0.03 * k
    knee = bd.j("LeftLeg")[2] + 0.05 * k
    front = bd.body & (bd.co[:, 1] < bd.j("Spine")[1])

    def front_y(x, z, w):
        near = front & (np.abs(bd.co[:, 0] - x) < w) & (np.abs(bd.co[:, 2] - z) < 0.035 * k)
        return float(bd.co[near, 1].min()) if near.any() else None

    rows, cols = 13, 9
    grid, wts = [], []
    for i in range(rows):
        t = i / (rows - 1)
        z = chest + (knee - chest) * t
        bib = z > waist
        half = (0.1 if bib else 0.16 + 0.03 * (waist - z) / max(waist - knee, 1e-3)) * k
        xs = [-half + 2 * half * j / (cols - 1) for j in range(cols)]
        ys = [front_y(x, z, 0.05 * k) for x in xs]
        valid = [y for y in ys if y is not None] or [float(bd.j("Hips")[1]) - 0.12 * k]
        if bib:  # follows the chest
            ys = [(y if y is not None else max(valid)) - 0.034 * k for y in ys]
        else:  # hangs flat and straight from the belly, across both legs
            ys = [min(valid) - 0.03 * k - 0.012 * k * t] * cols
        grid.append([Vector((x, y, z)) for x, y in zip(xs, ys)])
        for x in xs:
            if bib:
                w = {B + "Spine2": max(0.0, (z - waist) / max(chest - waist, 1e-3)), B + "Spine1": 0.5}
            else:
                leg = B + ("LeftUpLeg" if x > 0 else "RightUpLeg")
                s = min(1.0, (waist - z) / max(waist - knee, 1e-3)) * 0.45 * min(1.0, abs(x) / (0.08 * k))
                w = {B + "Hips": 1.0 - s, leg: s}
            tot = sum(w.values())
            wts.append({kk: vv / tot for kk, vv in w.items() if vv > 0})
    v, f = loft(grid, closed=False)
    obj = mesh("%s.apron" % mid, v, f, [col], None, wts, rig)
    sol = obj.modifiers.new("Solidify", "SOLIDIFY")
    sol.thickness = 0.004
    sol.use_rim = True
    import bpy
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.modifier_apply(modifier="Solidify")
    # A strap around the back of the neck, and ties around the waist.
    nh = bd.j("Neck")
    nz = nh[2] + 0.01 * k
    ring = bd.body & (np.abs(bd.co[:, 2] - nz) < 0.012 * k) & (np.abs(bd.co[:, 0]) < 0.09 * k)
    P = bd.co[ring]
    ncy = float(P[:, 1].mean()) if len(P) else nh[1]
    nrx = (float(np.abs(P[:, 0]).max()) if len(P) else 0.06 * k) + 0.014 * k
    nry = (float(np.abs(P[:, 1] - ncy).max()) if len(P) else 0.06 * k) + 0.014 * k
    strap = [grid[0][0]] + [Vector((math.cos(a) * nrx, ncy + math.sin(a) * nry, nz)) for a in np.linspace(math.radians(200), math.radians(-20), 14)] + [grid[0][-1]]
    G.tube("%s.apron_strap" % mid, strap, (0.012 * k, 0.003 * k), col, rig, "Spine2", seg=6, sq=6.0)
    wz = waist + 0.02 * k
    sl = bd.body & (np.abs(bd.co[:, 2] - wz) < 0.015 * k)
    P = bd.co[sl]
    wcx, wcy = float(P[:, 0].mean()), float(P[:, 1].mean())
    wrx = float(np.abs(P[:, 0] - wcx).max()) + 0.03 * k
    wry = float(np.abs(P[:, 1] - wcy).max()) + 0.03 * k
    tie = [Vector((wcx + math.cos(a) * wrx, wcy + math.sin(a) * wry, wz)) for a in np.linspace(math.radians(210), math.radians(-30), 20)]
    G.tube("%s.apron_tie" % mid, tie, (0.003 * k, 0.012 * k), col, rig, "Spine", seg=6, sq=6.0)


# --------------------------------------------------------------------------- hand-held props
def grip(bd, side):
    """Where a fist holds things in the rest pose: the grip point, the direction to the
    fingers, the thumb side (a held stick runs this way) and the palm normal."""
    h, t = Vector(tuple(bd.j(side + "Hand"))), Vector(tuple(bd.j(side + "Hand", "t")))
    along = (t - h).normalized()
    th = bd.bh.get(B + side + "HandThumb1")
    thumb = Vector((0.0, -1.0, 0.0))
    if th is not None:
        tv = Vector(tuple(th)) - h
        tv = tv - along * tv.dot(along)
        if tv.length > 1e-4:
            thumb = tv.normalized()
    return h + (t - h) * 0.55, along, thumb, along.cross(thumb).normalized()


class Parts:
    """Collects boxes and tapered tubes into one mesh (one object per prop)."""

    def __init__(self):
        self.verts, self.faces, self.fmat, self.mats = [], [], [], []

    def _mat(self, m):
        if m not in self.mats:
            self.mats.append(m)
        return self.mats.index(m)

    def box(self, c, ax, ay, az, sx, sy, sz, m):
        """A box centered at c, half-sizes sx, sy, sz along the axes ax, ay, az."""
        o = len(self.verts)
        self.verts += [c + ax * (sx * i) + ay * (sy * j) + az * (sz * l) for i in (-1, 1) for j in (-1, 1) for l in (-1, 1)]
        for f in ((0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)):
            self.faces.append(tuple(o + i for i in f))
            self.fmat.append(self._mat(m))

    def taper(self, pts, radii, m, up=None, seg=10):
        """A capped tube along pts; radii[i] = (rx, ry), with ry along `up` if given."""
        o, n = len(self.verts), seg
        for i, p in enumerate(pts):
            t = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
            if up is not None:
                y = (up - t * up.dot(t)).normalized()
            else:
                ref = Vector((0, 0, 1)) if abs(t.z) < 0.9 else Vector((1, 0, 0))
                y = t.cross(ref).cross(t).normalized()
            x = t.cross(y).normalized()
            rx, ry = radii[i]
            self.verts += [p + x * (math.cos(q) * rx) + y * (math.sin(q) * ry)
                           for q in np.linspace(0, 2 * math.pi, n, endpoint=False)]
        mi = self._mat(m)
        for i in range(len(pts) - 1):
            for q in range(n):
                q2 = (q + 1) % n
                self.faces.append((o + i * n + q, o + i * n + q2, o + (i + 1) * n + q2, o + (i + 1) * n + q))
                self.fmat.append(mi)
        self.verts += [pts[0], pts[-1]]
        c0, c1, last = len(self.verts) - 2, len(self.verts) - 1, o + (len(pts) - 1) * n
        for q in range(n):
            q2 = (q + 1) % n
            self.faces += [(o + q2, o + q, c0), (last + q, last + q2, c1)]
            self.fmat += [mi, mi]

    def rod(self, a, b, r, m, seg=8):
        self.taper([a, b], [(r, r), (r, r)], m, seg=seg)

    def make(self, name, rig, bone):
        return mesh(name, self.verts, self.faces, self.mats, self.fmat, {B + bone: 1.0}, rig)


def scythe(bd, rig, look, mid, hi):
    k = hi["k"]
    g, along, thumb, palm = grip(bd, "Right")
    wood = G.material("%s_scythe_pole" % mid, hexc("#2b2233"), rough=0.6)
    steel = G.material("%s_scythe_blade" % mid, hexc(look.get("blade_color", "#cfe8ff")), rough=0.2, metal=0.8)
    P = Parts()
    top = g + thumb * 1.25 * k
    P.rod(g - thumb * 0.55 * k, top, 0.014 * k, wood)
    P.rod(top - thumb * 0.04 * k, top + thumb * 0.03 * k, 0.022 * k, steel)  # the collar
    pts, rad = [], []
    for i in range(10):  # the blade sweeps out from the top and curves down to a point
        a = i / 9
        pts.append(top + palm * (0.62 * k * a) - thumb * (0.24 * k * a * a))
        rad.append((0.004 * k, 0.055 * k * (1 - a) ** 0.8 + 0.002 * k))
    P.taper(pts, rad, steel, up=thumb, seg=8)
    P.make("%s.scythe" % mid, rig, "RightHand")


def laptop(bd, rig, look, mid, hi):
    """A closed laptop, held by its edge."""
    k = hi["k"]
    g, along, thumb, palm = grip(bd, "Left")
    shell = G.material("%s_laptop" % mid, hexc(look.get("laptop_color", "#8a8f98")), rough=0.35, metal=0.6)
    logo = G.material("%s_laptop_logo" % mid, hexc("#7fd4ff"), rough=0.3)
    P = Parts()
    c = g + along * 0.12 * k
    P.box(c, thumb, along, palm, 0.165 * k, 0.115 * k, 0.011 * k, shell)
    P.box(c + palm * 0.0115 * k, thumb, along, palm, 0.022 * k, 0.022 * k, 0.001 * k, logo)
    P.make("%s.laptop" % mid, rig, "LeftHand")


def floating_laptop(bd, rig, look, mid, hi):
    """The Copilot Pro's second laptop: open, its screen glowing, hovering by his left
    shoulder. It rides the chest bone, so it sways along with him."""
    k = hi["k"]
    sh = Vector(tuple(bd.j("LeftArm")))
    c = Vector((sh.x + 0.22 * k, sh.y - 0.05 * k, sh.z + 0.2 * k))
    yaw = math.radians(-18)  # the screen turns a little toward his middle
    X = Vector((math.cos(yaw), math.sin(yaw), 0.0))
    Y = Vector((-math.sin(yaw), math.cos(yaw), 0.0))  # toward the back
    Z = Vector((0.0, 0.0, 1.0))
    t = math.radians(8)  # the screen leans back a little
    U = (Z * math.cos(t) + Y * math.sin(t)).normalized()
    N = X.cross(U).normalized()  # the screen's front
    shell = G.material("%s_laptop2" % mid, hexc(look.get("laptop_color", "#8a8f98")), rough=0.35, metal=0.6)
    deck = G.material("%s_laptop2_keys" % mid, hexc("#2d3436"), rough=0.6)
    screen = G.glow_material("%s_laptop2_screen" % mid, look.get("eye_glow", "#7fd4ff"), 2.5)
    P = Parts()
    P.box(c, X, Y, Z, 0.15 * k, 0.105 * k, 0.008 * k, shell)
    P.box(c + Z * 0.0085 * k - Y * 0.02 * k, X, Y, Z, 0.125 * k, 0.055 * k, 0.001 * k, deck)
    hinge = c + Y * 0.105 * k + Z * 0.004 * k
    cs = hinge + U * 0.105 * k
    P.box(cs, X, U, N, 0.15 * k, 0.105 * k, 0.006 * k, shell)
    P.box(cs + N * 0.0065 * k, X, U, N, 0.135 * k, 0.09 * k, 0.001 * k, screen)
    P.make("%s.laptop2" % mid, rig, "Spine2")


def spatula(bd, rig, look, mid, hi):
    k = hi["k"]
    g, along, thumb, palm = grip(bd, "Right")
    handle = G.material("%s_spatula_handle" % mid, hexc("#1c1c1e"), rough=0.5)
    steel = G.material("%s_spatula" % mid, hexc("#c9ccd1"), rough=0.25, metal=1.0)
    P = Parts()
    P.rod(g - thumb * 0.06 * k, g + thumb * 0.2 * k, 0.012 * k, handle)
    P.rod(g + thumb * 0.2 * k, g + thumb * 0.27 * k, 0.005 * k, steel, seg=6)
    P.box(g + thumb * 0.33 * k, palm, thumb, along, 0.05 * k, 0.065 * k, 0.003 * k, steel)
    P.make("%s.spatula" % mid, rig, "RightHand")


def bottle(bd, rig, look, mid, hi):
    """A squeeze bottle of the Village Sauce."""
    k = hi["k"]
    g, along, thumb, palm = grip(bd, "Right")
    sauce = G.material("%s_bottle" % mid, hexc(look.get("bottle_color", "#ffb627")), rough=0.3)
    cap = G.material("%s_bottle_cap" % mid, hexc("#c0392b"), rough=0.4)
    P = Parts()
    P.taper([g - thumb * 0.09 * k, g + thumb * 0.08 * k, g + thumb * 0.1 * k],
            [(0.04 * k, 0.04 * k), (0.04 * k, 0.04 * k), (0.03 * k, 0.03 * k)], sauce, seg=14)
    P.taper([g + thumb * 0.1 * k, g + thumb * 0.13 * k, g + thumb * 0.19 * k],
            [(0.024 * k, 0.024 * k), (0.02 * k, 0.02 * k), (0.004 * k, 0.004 * k)], cap, seg=10)
    P.make("%s.bottle" % mid, rig, "RightHand")


def fish(bd, rig, look, mid, hi):
    """A whole fish, held by the tail."""
    k = hi["k"]
    g, along, thumb, palm = grip(bd, "Right")
    skin = G.material("%s_fish" % mid, hexc("#9fb8c6"), rough=0.3, metal=0.3)
    fin = G.material("%s_fish_fin" % mid, hexc("#6f8fa0"), rough=0.4)
    eye = G.material("%s_fish_eye" % mid, hexc("#111111"), rough=0.2)
    P = Parts()
    pts, rad = [], []
    for i in range(10):  # the tail at the fist, the body hanging below it (a big one: it reads in battle)
        a = i / 9
        pts.append(g + along * (0.08 * k + 0.46 * k * a))
        s = math.sin(math.pi * min(0.98, 0.15 + a * 0.85)) ** 0.7
        rad.append((0.009 * k + 0.032 * k * s, 0.014 * k + 0.075 * k * s))
    P.taper(pts, rad, skin, up=thumb, seg=10)
    P.box(g + along * 0.04 * k, along, thumb, palm, 0.045 * k, 0.07 * k, 0.004 * k, fin)  # the tail fin
    for sg in (1, -1):
        P.box(pts[-2] + palm * sg * 0.03 * k, thumb, along, palm, 0.009 * k, 0.009 * k, 0.004 * k, eye)
    P.make("%s.fish" % mid, rig, "RightHand")


def keyboard(bd, rig, look, mid, hi):
    """A clacky mechanical keyboard, held like a club."""
    k = hi["k"]
    g, along, thumb, palm = grip(bd, "Left")
    case = G.material("%s_keyboard" % mid, hexc("#2d3436"), rough=0.5)
    keys = G.material("%s_keys" % mid, hexc("#dfe6e9"), rough=0.6)
    accent = G.material("%s_keys_accent" % mid, hexc("#e17055"), rough=0.6)
    P = Parts()
    c = g + thumb * 0.17 * k
    P.box(c, thumb, palm, along, 0.22 * k, 0.012 * k, 0.07 * k, case)
    for i in range(10):
        for j in range(3):
            kc = c + thumb * ((i - 4.5) * 0.04 * k) + along * ((j - 1) * 0.04 * k) + palm * 0.016 * k
            P.box(kc, thumb, palm, along, 0.016 * k, 0.005 * k, 0.016 * k, accent if (i, j) == (9, 0) else keys)
    P.make("%s.keyboard" % mid, rig, "LeftHand")


def mug(bd, rig, look, mid, hi):
    k = hi["k"]
    g, along, thumb, palm = grip(bd, "Right")
    cup = G.material("%s_mug" % mid, hexc(look.get("mug_color", "#ffffff")), rough=0.3)
    coffee = G.material("%s_coffee" % mid, hexc("#3b2416"), rough=0.2)
    P = Parts()
    c = g + palm * 0.06 * k
    P.rod(c - thumb * 0.045 * k, c + thumb * 0.05 * k, 0.04 * k, cup, seg=14)
    P.rod(c + thumb * 0.05 * k, c + thumb * 0.052 * k, 0.034 * k, coffee, seg=14)
    arc = [c - palm * (0.04 * k + 0.022 * k * math.cos(a)) + thumb * (0.028 * k * math.sin(a))
           for a in np.linspace(-math.pi / 2, math.pi / 2, 8)]
    P.taper(arc, [(0.007 * k, 0.007 * k)] * len(arc), cup, seg=6)
    P.make("%s.mug" % mid, rig, "RightHand")


PROPS = {"headphones": headphones, "witch_hat": witch_hat, "paper_hat": paper_hat, "crown": crown,
         "cape": cape, "lanyard": lanyard, "belt": belt, "stirrer": stirrer,
         "hood": hood, "chef_hat": chef_hat, "apron": apron, "scythe": scythe, "laptop": laptop,
         "floating_laptop": floating_laptop, "cord": cord,
         "spatula": spatula, "bottle": bottle, "fish": fish, "keyboard": keyboard, "mug": mug}


def add(bd, rig, look, mid):
    acc = [a for a in look.get("acc", []) if a in PROPS]
    if not acc:
        return
    hi = head_info(bd, rig)
    for a in acc:
        PROPS[a](bd, rig, look, mid, hi)
