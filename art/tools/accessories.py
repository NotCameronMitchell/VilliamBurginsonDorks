"""
Extra props for hero skins, built to fit each hero's MakeHuman body (garments.py does the
clothes, caps, glasses and watches): headphones, a witch hat, a paper burger hat, a crown and
cape, a work lanyard, a lifting belt and a coffee stirrer behind the ear.

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


PROPS = {"headphones": headphones, "witch_hat": witch_hat, "paper_hat": paper_hat, "crown": crown,
         "cape": cape, "lanyard": lanyard, "belt": belt, "stirrer": stirrer}


def add(bd, rig, look, mid):
    acc = [a for a in look.get("acc", []) if a in PROPS]
    if not acc:
        return
    hi = head_info(bd, rig)
    for a in acc:
        PROPS[a](bd, rig, look, mid, hi)
