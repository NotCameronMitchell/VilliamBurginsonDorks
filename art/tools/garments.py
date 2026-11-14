"""
Clothes generated from each hero's own MakeHuman body, so any outfit (and any future skin)
is just data in hero_looks.py:

- A garment starts as a region of the body surface (chosen by which bone each vertex
  follows), copied, smoothed and pushed outward. Its edges (neckline, sleeves, hem, leg
  openings) are then cut with planes, so they run clean instead of following the body
  mesh's zigzag. A V-neck is two cuts after a split down the middle.
- It keeps the body's skin weights, so it moves exactly with the rig, and the body's UVs,
  so prints, numbers, buttons and patterns land in the same place on every hero.
- Skin that a garment fully covers is hidden, so nothing pokes through when animating.
- Collars, cuffs, hems and waistbands are strips laid along the garment's cut edges.
- Beards and stubble are painted into the hero's skin texture (soft edges, no gaps), which
  is also tinted toward the hero's skin color.
- Shoes are MakeHuman's (recolored); caps, glasses, sunglasses and watches are built here.

dress(rig, basemesh, model_id) is called by hero_mpfb.build() before the meshes are baked.
"""

import importlib
import math
import os
import tempfile

import bmesh
import bpy
import numpy as np
from mathutils import Vector, kdtree

import hero_looks as L
from hero_builder import Canvas, draw_digits, hexc

B = "mixamorig:"
TEXDIR = tempfile.mkdtemp(prefix="vbd_garment_tex_")
SHOES = {"sneakers": "shoes05", "leather": "shoes01", "flats": "shoes04", "boots": "shoes03"}
GOLD_METAL = 0.5  # fully metallic gold looks almost black without much to reflect (game scenes)
ARMS = ["LeftArm", "LeftForeArm", "LeftHand", "RightArm", "RightForeArm", "RightHand"]


def lin(c):
    c = np.asarray(c, dtype=float)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def sstep(e0, e1, v):
    """Smoothstep from e0 (0) to e1 (1); e1 < e0 flips it."""
    t = np.clip((v - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


# =========================================================================== body data
class Body:
    """Rest-pose facts about the MakeHuman body: positions, normals, bone weights, joints, UVs."""

    def __init__(self, rig, obj):
        self.rig, self.obj = rig, obj
        me = obj.data
        n = len(me.vertices)
        co = np.empty(n * 3)
        me.vertices.foreach_get("co", co)
        mw = np.array(obj.matrix_world)
        self.co = co.reshape(n, 3) @ mw[:3, :3].T + mw[:3, 3]
        nr = np.empty(n * 3)
        me.vertices.foreach_get("normal", nr)
        self.nrm = nr.reshape(n, 3) @ mw[:3, :3].T
        self.nrm /= np.maximum(np.linalg.norm(self.nrm, axis=1, keepdims=True), 1e-9)
        gname = {g.index: g.name for g in obj.vertex_groups}
        self.bones = [g.name for g in obj.vertex_groups if g.name.startswith(B)]
        bidx = {b: i for i, b in enumerate(self.bones)}
        self.W = np.zeros((n, len(self.bones)))
        self.groups = {}
        joint_ids = {}
        for v in me.vertices:
            for g in v.groups:
                name = gname[g.group]
                if name in bidx:
                    self.W[v.index, bidx[name]] = g.weight
                elif name.startswith("joint-"):
                    joint_ids.setdefault(name, []).append(v.index)
                else:
                    self.groups.setdefault(name, []).append(v.index)
        # MakeHuman's joint markers (small cubes at the eyes, mouth, jaw...), as points.
        self.joints = {k[6:]: self.co[ids].mean(0) for k, ids in joint_ids.items()}
        s = self.W.sum(1, keepdims=True)
        self.W = np.where(s > 0, self.W / np.maximum(s, 1e-9), 0)
        self.dom = np.array([self.bones[i] for i in self.W.argmax(1)])
        self.weighted = s[:, 0] > 0
        self.body = np.zeros(n, bool)
        self.body[self.groups.get("body", [])] = True
        rw = np.array(rig.matrix_world)
        self.bh, self.bt = {}, {}
        for b in rig.data.bones:
            self.bh[b.name] = (rw @ np.append(np.array(b.head_local), 1))[:3]
            self.bt[b.name] = (rw @ np.append(np.array(b.tail_local), 1))[:3]
        self.faces = [tuple(p.vertices) for p in me.polygons]
        self.face_mat = [p.material_index for p in me.polygons]
        uvl = me.uv_layers.active.data
        self.face_uv = [[tuple(uvl[li].uv) for li in p.loop_indices] for p in me.polygons]
        self.vert_uv = np.zeros((n, 2))
        cnt = np.zeros(n)
        for f, uvs in zip(self.faces, self.face_uv):
            for vi, uv in zip(f, uvs):
                self.vert_uv[vi] += uv
                cnt[vi] += 1
        self.vert_uv /= np.maximum(cnt, 1)[:, None]
        self.adj = [set() for _ in range(n)]
        for f in self.faces:
            for i in range(len(f)):
                a, b_ = f[i], f[(i + 1) % len(f)]
                self.adj[a].add(b_)
                self.adj[b_].add(a)
        zs = self.co[self.body, 2]
        self.height = zs.max() - zs.min()
        self.ground = zs.min()

    def j(self, bone, end="h"):
        return (self.bh if end == "h" else self.bt)[B + bone]

    def param(self, bone):
        """How far along `bone` (0 head .. 1 tail) every vertex sits."""
        h, t = self.j(bone, "h"), self.j(bone, "t")
        d = t - h
        return ((self.co - h) @ d) / max(d @ d, 1e-9)

    def is_dom(self, *bones):
        return np.isin(self.dom, [B + b for b in bones])

    def share(self, bones):
        """Each vertex's total weight on `bones` (0..1)."""
        idx = [self.bones.index(B + b) for b in bones if (B + b) in self.bones]
        return self.W[:, idx].sum(1) if idx else np.zeros(len(self.co))

    def nearest_body(self, point, sel=None):
        cand = np.where(self.body if sel is None else sel)[0]
        i = cand[np.argmin(np.linalg.norm(self.co[cand] - point, axis=1))]
        return i


# =========================================================================== regions
# Regions are generous; the plane cuts in dress() set the real edges.
def region_top(bd, sleeves, hem_z, neck_top_z):
    m = bd.is_dom("Hips", "Spine", "Spine1", "Spine2", "LeftShoulder", "RightShoulder")
    # The neck, and the throat (on men it follows the head bone): the neckline cut trims it.
    m |= bd.is_dom("Neck", "Head") & (bd.co[:, 2] <= neck_top_z)
    m &= bd.co[:, 2] >= hem_z
    for side in ("Left", "Right"):
        if sleeves in ("short", "cap", "none"):
            t_end = {"short": 0.55, "cap": 0.22, "none": 0.22}[sleeves] + 0.18
            m |= bd.is_dom(side + "Arm") & (bd.param(side + "Arm") <= t_end)
        elif sleeves == "long":
            m |= bd.is_dom(side + "Arm") | bd.is_dom(side + "ForeArm")
    return m & bd.body


def region_bottom(bd, kind, top_z):
    m = (bd.is_dom("Hips") | bd.is_dom("Spine")) & (bd.co[:, 2] <= top_z)
    for side in ("Left", "Right"):
        if kind == "shorts":
            m |= bd.is_dom(side + "UpLeg") & (bd.param(side + "UpLeg") <= 0.80)
        else:
            m |= bd.is_dom(side + "UpLeg") | bd.is_dom(side + "Leg")
    return m & bd.body


def region_head_top(bd, above_z):
    return bd.is_dom("Head") & (bd.co[:, 2] >= above_z) & bd.body


def erode(bd, mask, rings):
    keep = mask.copy()
    for _ in range(rings):
        edge = [i for i in np.where(keep)[0] if any(not keep[j] for j in bd.adj[i])]
        keep[edge] = False
    return keep


def tidy(bd, mask, rings=1):
    """Removes thin spurs from a region (erode, then grow back inside the original)."""
    core = erode(bd, mask, rings)
    for _ in range(rings):
        grow = core.copy()
        for i in np.where(core)[0]:
            for j in bd.adj[i]:
                if mask[j]:
                    grow[j] = True
        core = grow
    return core


# =========================================================================== plane cuts
# A cut is dict(co, no, where, split=False): remove what lies on the `no` side of the plane
# through `co`, among the faces picked by `where` (so a neckline cut can't touch the arms).
# where keys: xmax, zmin, zmax, ymin, ymax (box on face centers), xsign (+1 left / -1 right),
# bones (every vertex mostly on these bones), not_bones (no vertex mostly on these), share.
def where_faces(bm, obj, where):
    dl = bm.verts.layers.deform.active

    def gids(names):
        return [obj.vertex_groups[B + b].index for b in names if (B + b) in obj.vertex_groups]

    bi = gids(where["bones"]) if where.get("bones") else None
    nbi = gids(where["not_bones"]) if where.get("not_bones") else None
    thr = where.get("share", 0.5)

    def vshare(v, ids):
        if dl is None:
            return 0.0
        d = v[dl]
        tot = sum(d.values())
        return sum(d.get(i, 0.0) for i in ids) / tot if tot > 0 else 0.0

    out = []
    for f in bm.faces:
        c = f.calc_center_median()
        if "xmax" in where and abs(c.x) > where["xmax"]:
            continue
        if "zmin" in where and c.z < where["zmin"]:
            continue
        if "zmax" in where and c.z > where["zmax"]:
            continue
        if "ymin" in where and c.y < where["ymin"]:
            continue
        if "ymax" in where and c.y > where["ymax"]:
            continue
        if where.get("xsign") and c.x * where["xsign"] < 0:
            continue
        if bi is not None and not all(vshare(v, bi) > thr for v in f.verts):
            continue
        if nbi is not None and any(vshare(v, nbi) > thr for v in f.verts):
            continue
        out.append(f)
    return out


def where_verts(bd, where):
    """The same selection as where_faces, on the body's vertices."""
    m = np.ones(len(bd.co), bool)
    x, y, z = bd.co[:, 0], bd.co[:, 1], bd.co[:, 2]
    if "xmax" in where:
        m &= np.abs(x) <= where["xmax"]
    if "zmin" in where:
        m &= z >= where["zmin"]
    if "zmax" in where:
        m &= z <= where["zmax"]
    if "ymin" in where:
        m &= y >= where["ymin"]
    if "ymax" in where:
        m &= y <= where["ymax"]
    if where.get("xsign"):
        m &= x * where["xsign"] >= 0
    thr = where.get("share", 0.5)
    if where.get("bones"):
        m &= bd.share(where["bones"]) > thr
    if where.get("not_bones"):
        m &= ~(bd.share(where["not_bones"]) > thr)
    return m


def _edge_split_from_first():
    """Whether bmesh.utils.edge_split's factor counts from the vertex it's given."""
    bm = bmesh.new()
    a, b_ = bm.verts.new((0, 0, 0)), bm.verts.new((1, 0, 0))
    e = bm.edges.new((a, b_))
    _, v = bmesh.utils.edge_split(e, a, 0.25)
    ok = abs(v.co.x - 0.25) < 1e-6
    bm.free()
    return ok


_SPLIT_FROM_FIRST = None


def field_cut(bm, faces, field):
    """Removes the part of `faces` where field(points) > 0, cutting exactly along field = 0
    (a curved edge, e.g. a neckline that follows the neck all the way round)."""
    global _SPLIT_FROM_FIRST
    if not faces:
        return
    if _SPLIT_FROM_FIRST is None:
        _SPLIT_FROM_FIRST = _edge_split_from_first()
    verts = list({v for f in faces for v in f.verts})
    fv = field(np.array([tuple(v.co) for v in verts]))
    fv = np.where(np.abs(fv) < 1e-7, -1e-7, fv)  # nothing exactly on the line
    val = {v: float(x) for v, x in zip(verts, fv)}
    newv = []
    for e in list({e for f in faces for e in f.edges}):
        a, b_ = e.verts
        if a not in val or b_ not in val:
            continue
        fa, fb = val[a], val[b_]
        if (fa > 0) == (fb > 0):
            continue
        t = fa / (fa - fb)
        _, nv = bmesh.utils.edge_split(e, a, t if _SPLIT_FROM_FIRST else 1.0 - t)
        val[nv] = 0.0
        newv.append(nv)
    if newv:
        bmesh.ops.connect_verts(bm, verts=newv)
    dead = [f for f in bm.faces if all(v in val for v in f.verts) and any(val[v] > 0 for v in f.verts)]
    if dead:
        bmesh.ops.delete(bm, geom=dead, context="FACES")


def apply_cut(bm, c, faces):
    if not faces:
        return
    if "field" in c:
        field_cut(bm, faces, c["field"])
    else:
        verts = list({v for f in faces for v in f.verts})
        edges = list({e for f in faces for e in f.edges})
        no = Vector(c["no"]).normalized()
        bmesh.ops.bisect_plane(bm, geom=verts + edges + faces, dist=1e-6, plane_co=Vector(c["co"]), plane_no=no,
                               use_snap_center=False, clear_outer=not c.get("split"), clear_inner=False)
    loose_e = [e for e in bm.edges if not e.link_faces]
    if loose_e:
        bmesh.ops.delete(bm, geom=loose_e, context="EDGES")
    loose = [v for v in bm.verts if not v.link_faces]
    if loose:
        bmesh.ops.delete(bm, geom=loose, context="VERTS")


def cut_side(c, P):
    """How far past the cut each point is (> 0: removed)."""
    if "field" in c:
        return c["field"](P)
    no = np.asarray(c["no"], float)
    return (P - np.asarray(c["co"], float)) @ (no / np.linalg.norm(no))


def cut_keep(bd, c, margin=0.012):
    """Body vertices safely inside a cut (for hiding the skin a garment covers)."""
    if c.get("split"):
        return np.ones(len(bd.co), bool)
    aff = where_verts(bd, c.get("where", {}))
    return ~(aff & (cut_side(c, bd.co) > -margin))


def neckline(axis_y, z_side, front_drop, back_rise, v_depth=0.0, v_half=0.6, power=1.5):
    """A neckline as a field for field_cut: its height goes round the neck (angle 0 = the
    front), dipping `front_drop` in front and rising `back_rise` at the back, plus an
    optional V of depth `v_depth` that is `v_half` radians wide each side. Because it
    depends only on the angle, a big chest doesn't make the neckline plunge."""
    def f(P):
        th = np.arctan2(P[:, 0], -(P[:, 1] - axis_y))
        c = (1 + np.cos(th)) / 2
        h = z_side - front_drop * c ** power + back_rise * (1 - c) ** power
        if v_depth > 0:
            h = h - v_depth * np.clip(1 - np.abs(th) / v_half, 0, 1)
        return P[:, 2] - h
    return f


# =========================================================================== geometry
def make_mesh_object(name, verts, faces, uvs, weights, mats, face_mat, rig):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], faces)
    for m in mats:
        me.materials.append(m)
    if face_mat is not None:
        me.polygons.foreach_set("material_index", face_mat)
    if uvs is not None:
        uvl = me.uv_layers.new(name="UVMap")
        flat = [c for f in uvs for uv in f for c in uv]
        uvl.data.foreach_set("uv", flat)
    me.polygons.foreach_set("use_smooth", [True] * len(me.polygons))
    me.update()
    obj = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(obj)
    groups = {}
    for vi, w in enumerate(weights):
        for bone, val in w.items():
            if val > 1e-4:
                groups.setdefault(bone, {}).setdefault(round(val, 3), []).append(vi)
    for bone, byval in groups.items():
        vg = obj.vertex_groups.new(name=bone)
        for val, ids in byval.items():
            vg.add(ids, val, "REPLACE")
    obj.parent = rig
    mod = obj.modifiers.new("Armature", "ARMATURE")
    mod.object = rig
    return obj


def weights_of(bd, vi):
    row = bd.W[vi]
    return {bd.bones[k]: float(row[k]) for k in np.nonzero(row > 1e-4)[0]}


def fix_weights(obj):
    """Gives any vertex without skin weights (a cut can make some) its nearest neighbor's."""
    me = obj.data
    have = [v.index for v in me.vertices if any(g.weight > 1e-4 for g in v.groups)]
    missing = [v.index for v in me.vertices if not any(g.weight > 1e-4 for g in v.groups)]
    if not missing or not have:
        return
    tree = kdtree.KDTree(len(have))
    for n_i, vi in enumerate(have):
        tree.insert(me.vertices[vi].co, n_i)
    tree.balance()
    for vi in missing:
        _, n_i, _ = tree.find(me.vertices[vi].co)
        for g in me.vertices[have[n_i]].groups:
            obj.vertex_groups[g.group].add([vi], g.weight, "REPLACE")


def drape(bd, used, pts, fill):
    """Fills hollows like fabric does: around each bone, every point is pushed out toward
    the fuller points near it (same slice along the bone, same side), never inward."""
    if fill <= 0:
        return pts
    out = pts.copy()
    dom = bd.dom[used]
    for bone in set(dom):
        sel = np.where(dom == bone)[0]
        if len(sel) < 12:
            continue
        h, t = bd.bh[bone], bd.bt[bone]
        d = t - h
        L2 = max(d @ d, 1e-9)
        P = pts[sel]
        s = ((P - h) @ d) / L2
        axis = h + s[:, None] * d
        R = P - axis
        r = np.linalg.norm(R, axis=1)
        dn = d / math.sqrt(L2)
        ref = np.array([0, 0, 1.0]) if abs(dn[2]) < 0.9 else np.array([0, 1.0, 0])
        e1 = np.cross(dn, ref)
        e1 /= np.linalg.norm(e1)
        e2 = np.cross(dn, e1)
        ang = np.arctan2(R @ e2, R @ e1)
        sb = np.clip(((s - s.min()) / max(1e-6, s.max() - s.min()) * 10).astype(int), 0, 9)
        ab = ((ang + math.pi) / (2 * math.pi) * 10).astype(int) % 10
        key = sb * 10 + ab
        r_new = r.copy()
        for kk in np.unique(key):
            m = key == kk
            q = np.quantile(r[m], 0.85)
            r_new[m] = np.maximum(r[m], r[m] + (q - r[m]) * fill)
        out[sel] = axis + R / np.maximum(r, 1e-9)[:, None] * r_new[:, None]
    return out


def bust_drape(bd, P):
    """Fabric over a bust spans straight across between the two fullest points and hangs
    down from them, tucking in a little toward the waist. Without this a top hugs each
    breast separately and looks shrink-wrapped. Points only ever move forward."""
    k = bd.height / 1.8
    sp, s2, nk = bd.j("Spine"), bd.j("Spine2"), bd.j("Neck")
    front = P[:, 1] < s2[1]  # characters face -Y
    band = front & (P[:, 2] > sp[2]) & (P[:, 2] < nk[2] - 0.05 * k)
    apex = {}
    for sg in (1, -1):
        m = band & (sg * P[:, 0] > 0.03 * k) & (sg * P[:, 0] < 0.13 * k)
        if m.sum() < 10:
            return P
        idx = np.where(m)[0]
        apex[sg] = P[idx[np.argmin(P[idx, 1])]]
    ya = max(apex[1][1], apex[-1][1])
    za = (apex[1][2] + apex[-1][2]) / 2
    xa = (abs(apex[1][0]) + abs(apex[-1][0])) / 2
    sternum = band & (np.abs(P[:, 0]) < 0.015 * k) & (np.abs(P[:, 2] - za) < 0.03 * k)
    if not sternum.any() or P[sternum, 1].min() - ya < 0.01 * k:
        return P  # a flat chest: nothing to bridge
    x, z = np.abs(P[:, 0]), P[:, 2]
    # The front line through both fullest points: almost straight between them, curving back
    # beyond them toward the sides.
    line = ya + 0.006 * k * (1 - np.clip(x / xa, 0, 1) ** 2)
    line = line + 0.02 * k * (np.maximum(x - xa, 0) / (0.05 * k)) ** 2
    # Below it the fabric hangs nearly straight down, tucking in more toward the waist; above
    # it the fabric goes back to following the body within a few centimeters.
    drop = np.maximum(za - z, 0)
    hang = line + np.tan(np.radians(10)) * drop + 0.03 * k * (drop / (0.25 * k)) ** 2
    target = np.where(z >= za, line, hang)
    # Round each fullest point into a dome, so the fabric doesn't tent to a point there.
    for sg in (1, -1):
        r2 = (P[:, 0] - apex[sg][0]) ** 2 + (P[:, 2] - apex[sg][2]) ** 2
        target = np.minimum(target, ya + r2 / (2 * 0.09 * k))
    w = np.where(z >= za, sstep(0.07 * k, 0.02 * k, z - za), 1.0)
    w = w * sstep(xa + 0.08 * k, xa + 0.02 * k, x) * front
    out = P.copy()
    out[:, 1] = P[:, 1] + (np.minimum(P[:, 1], target) - P[:, 1]) * w
    return out


def smooth_loops(bm, iterations=10):
    """Straightens open edges that weren't cut (the body mesh's zigzag)."""
    bverts = [v for v in bm.verts if v.is_boundary]
    for _ in range(iterations):
        new = {}
        for v in bverts:
            nb = [e.other_vert(v) for e in v.link_edges if e.is_boundary]
            if len(nb) == 2:
                new[v] = v.co * 0.5 + (nb[0].co + nb[1].co) * 0.25
        for v, c in new.items():
            v.co = c


def edge_loops(bm, obj):
    """Each open edge loop as arrays: points P, surface normals N, the direction D that
    runs along the surface into the garment, and each point's skin weights W."""
    bm.normal_update()
    dl = bm.verts.layers.deform.active
    gname = {g.index: g.name for g in obj.vertex_groups}
    nxt = {}
    for e in bm.edges:
        if e.is_boundary:
            a, b_ = e.verts
            nxt.setdefault(a, []).append(b_)
            nxt.setdefault(b_, []).append(a)
    seen, loops = set(), []
    for start in list(nxt):
        if start in seen:
            continue
        loop = [start]
        seen.add(start)
        prev, cur = None, start
        while True:
            cands = [v for v in nxt[cur] if v is not prev and v not in seen]
            if not cands:
                break
            prev, cur = cur, cands[0]
            loop.append(cur)
            seen.add(cur)
        if len(loop) < 6:
            continue
        closed = any(e.other_vert(loop[-1]) is loop[0] for e in loop[-1].link_edges if e.is_boundary)
        P = np.array([tuple(v.co) for v in loop])
        N = np.array([tuple(v.normal) for v in loop])
        T = np.roll(P, -1, 0) - np.roll(P, 1, 0)
        T /= np.maximum(np.linalg.norm(T, axis=1, keepdims=True), 1e-9)
        D = np.cross(N, T)
        D /= np.maximum(np.linalg.norm(D, axis=1, keepdims=True), 1e-9)
        votes = 0.0
        for i, v in enumerate(loop):
            inner = [e.other_vert(v) for e in v.link_edges if not e.is_boundary]
            if inner:
                c = sum((u.co for u in inner), Vector()) / len(inner)
                votes += float(np.dot(np.array(tuple(c - v.co)), D[i]))
        if votes < 0:
            D = -D
        for _ in range(3):
            D = 0.5 * D + 0.25 * (np.roll(D, 1, 0) + np.roll(D, -1, 0))
            D /= np.maximum(np.linalg.norm(D, axis=1, keepdims=True), 1e-9)
        W = [{gname[k]: w for k, w in v[dl].items() if k in gname} if dl else {} for v in loop]
        loops.append(dict(P=P, N=N, D=D, W=W, closed=closed))
    return loops


def garment(bd, mask, name, offset, mat, rig, smooth=4, thickness=0.0035, loose=None, fill=0.0,
            cuts=(), edge_smooth=0, snug=None, bust=False):
    """Copies the masked body faces into a garment mesh, pushed `offset` meters outward,
    then cuts its edges. snug = (weight(points) -> 0..1, offset): where the weight is 1 the
    fabric hugs the body at that offset instead (a neckline against the neck). bust: drape
    the fabric over the chest (bust_drape). Returns (object, edge loops)."""
    mask = tidy(bd, mask)
    faces = [i for i, f in enumerate(bd.faces) if all(mask[v] for v in f)]
    used = sorted({v for i in faces for v in bd.faces[i]})
    remap = {v: k for k, v in enumerate(used)}
    used_a = np.array(used)
    pts = drape(bd, used_a, bd.co[used_a].copy(), fill)
    if bust:
        pts = bust_drape(bd, pts)
    verts = []
    for k_, v in enumerate(used):
        off = offset
        if loose is not None:
            off += loose(bd.co[v])
        verts.append(pts[k_] + bd.nrm[v] * off)
    if snug is not None:
        wfun, soff = snug
        w = np.clip(wfun(bd.co[used_a]), 0, 1)[:, None]
        tight = bd.co[used_a] + bd.nrm[used_a] * soff
        verts = list(np.array(verts) * (1 - w) + tight * w)
    fl = [tuple(remap[v] for v in bd.faces[i]) for i in faces]
    uvs = [bd.face_uv[i] for i in faces]
    wts = [weights_of(bd, v) for v in used]
    obj = make_mesh_object(name, verts, fl, uvs, wts, [mat], None, rig)
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    if smooth:  # cloth doesn't show skin detail
        inner = [v for v in bm.verts if not v.is_boundary]
        for _ in range(smooth):
            bmesh.ops.smooth_vert(bm, verts=inner, factor=0.5, use_axis_x=True, use_axis_y=True, use_axis_z=True)
    for c in cuts:
        apply_cut(bm, c, where_faces(bm, obj, c.get("where", {})))
    if edge_smooth:
        smooth_loops(bm, edge_smooth)
    if smooth:
        inner = [v for v in bm.verts if not v.is_boundary]
        bmesh.ops.smooth_vert(bm, verts=inner, factor=0.5, use_axis_x=True, use_axis_y=True, use_axis_z=True)
    loops = edge_loops(bm, obj)
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    fix_weights(obj)
    if thickness:
        sol = obj.modifiers.new("Solidify", "SOLIDIFY")
        sol.thickness = thickness
        sol.offset = -1.0
        sol.use_rim = True
        bpy.ops.object.select_all(action="DESELECT")
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        bpy.ops.object.modifier_move_to_index(modifier="Solidify", index=0)
        bpy.ops.object.modifier_apply(modifier="Solidify")
    return obj, loops


def strip(name, edge, profile, mat, rig):
    """A band laid along a garment's edge loop. profile: (along, out) offsets in meters for
    each row across the band; `along` runs over the surface into the garment (negative =
    past the edge), `out` is the height above the surface."""
    P, N, D, W = edge["P"], edge["N"], edge["D"], edge["W"]
    n, R = len(P), len(profile)
    verts, wts = [], []
    for i in range(n):
        for along, out in profile:
            verts.append(Vector(tuple(P[i] + D[i] * along + N[i] * out)))
            wts.append(W[i])
    faces = []
    for i in range(n if edge.get("closed", True) else n - 1):
        i2 = (i + 1) % n
        for r in range(R - 1):
            faces.append((i * R + r, i2 * R + r, i2 * R + r + 1, i * R + r + 1))
    # Wind the widest part of the band to face outward.
    r = int(np.argmax([abs(profile[q + 1][0] - profile[q][0]) for q in range(R - 1)]))
    a, b_, c = verts[r], verts[R + r], verts[R + r + 1]
    if (b_ - a).cross(c - b_).dot(Vector(tuple(N[0]))) * (1 if profile[r + 1][0] >= profile[r][0] else -1) < 0:
        faces = [tuple(reversed(f)) for f in faces]
    uvs = [[(0, 0), (1, 0), (1, 1), (0, 1)] for _ in faces]
    return make_mesh_object(name, verts, faces, uvs, wts, [mat], None, rig)


def hide_body(bd, mask, rings=2):
    covered = erode(bd, mask, rings)
    obj = bd.obj
    vg = obj.vertex_groups.get("vbd_hidden") or obj.vertex_groups.new(name="vbd_hidden")
    ids = np.where(covered)[0].tolist()
    if ids:
        vg.add(ids, 1.0, "REPLACE")
    if not any(m.type == "MASK" and m.vertex_group == "vbd_hidden" for m in obj.modifiers):
        m = obj.modifiers.new("Hide covered skin", "MASK")
        m.vertex_group = "vbd_hidden"
        m.invert_vertex_group = True


# Band shapes (along, out), in meters before scaling `along` by body size.
RIB_NECK = [(-0.002, -0.002), (-0.0025, 0.001), (0.0, 0.0026), (0.010, 0.0022), (0.013, 0.0010)]
RIB_NECK_THICK = [(-0.002, -0.003), (-0.003, 0.0012), (0.0, 0.0035), (0.018, 0.0030), (0.022, 0.0012)]
COLLAR = [(0.0, -0.001), (-0.016, 0.0015), (-0.019, 0.005), (-0.012, 0.008), (0.002, 0.009),
          (0.024, 0.0065), (0.030, 0.003)]
HEM = [(-0.0015, -0.002), (-0.002, 0.0008), (0.0, 0.0018), (0.010, 0.0015)]
RIB_WIDE = [(-0.002, -0.003), (-0.003, 0.001), (0.0, 0.0032), (0.038, 0.0028), (0.043, 0.001)]
CUFF = [(-0.002, -0.003), (-0.003, 0.001), (0.0, 0.0034), (0.032, 0.0030), (0.037, 0.0012)]
WAISTBAND = [(-0.002, -0.002), (-0.002, 0.001), (0.0, 0.0025), (0.035, 0.0022)]
JOGGER_CUFF = [(-0.002, -0.003), (-0.003, 0.001), (0.0, 0.0035), (0.040, 0.0032), (0.046, 0.0012)]


def scaled(profile, k):
    return [(a * k, o) for a, o in profile]


# =========================================================================== materials
def material(name, color=None, image=None, rough=0.8, metal=0.0):
    m = bpy.data.materials.new(name)
    try:
        m.use_nodes = True
    except Exception:
        pass
    bsdf = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Metallic"].default_value = metal
    if image is not None:
        tex = m.node_tree.nodes.new("ShaderNodeTexImage")
        tex.image = image
        m.node_tree.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    if color is not None:
        bsdf.inputs["Base Color"].default_value = (*lin(color), 1.0)
        m.diffuse_color = (*lin(color), 1.0)
    bsdf.inputs["Roughness"].default_value = rough
    return m


class UVFrame:
    """Maps meters on the body surface around a point to texture pixels (handles the UV
    island's rotation, mirroring and scale), for placing prints upright."""

    def __init__(self, bd, center_vi, size):
        self.S = size
        c = bd.co[center_vi]
        near = [i for i in np.argsort(np.linalg.norm(bd.co - c, axis=1))[:60] if bd.body[i]]
        P = bd.co[near][:, [0, 2]] - c[[0, 2]]  # world x (character's left) and z (up)
        U = bd.vert_uv[near] - bd.vert_uv[center_vi]
        J, *_ = np.linalg.lstsq(P, U, rcond=None)  # rows: d(uv)/dx, d(uv)/dz
        self.J = J
        self.uv0 = bd.vert_uv[center_vi]

    def px(self, x, z):
        """Texture pixel for a point x meters to the character's left and z meters up."""
        uv = self.uv0 + np.array([x, z]) @ self.J
        return uv[0] * self.S, uv[1] * self.S

    def scale(self):
        return float(np.linalg.norm(self.J[0])) * self.S  # pixels per meter (horizontal)


def paint_top(bd, look_top, model_id, S=1024):
    """The texture for a top, in body-UV space: color, pattern, prints, buttons, trims."""
    col = hexc(look_top["color"])
    tp = look_top["type"]
    cv = Canvas(S, S, col)
    chest_z = bd.j("Spine2")[2] + 0.02 * bd.height
    front = bd.body & (np.abs(bd.co[:, 0]) < 0.012) & (bd.co[:, 1] < bd.j("Spine2")[1])
    cvi = bd.nearest_body(np.array([0, bd.co[front, 1].min() if front.any() else -0.1, chest_z]), front if front.any() else None)
    fr = UVFrame(bd, cvi, S)
    ppm = max(fr.scale(), 50.0)
    if look_top.get("pattern") == "dots":
        pc = hexc(look_top.get("pattern_color", "#ffffff"))
        sx = 0.026 * ppm
        yy, xx = np.mgrid[0:S, 0:S] + 0.5
        row = np.floor(yy / sx)
        xm = ((xx + (row % 2) * sx * 0.5) % sx) - sx / 2
        ym = (yy % sx) - sx / 2
        r = sx * 0.12
        cov = np.clip(r - np.hypot(xm, ym) + 0.5, 0, 1)
        for ang in (0, math.pi / 2, math.pi, 3 * math.pi / 2):
            cov = np.maximum(cov, np.clip(r * 0.7 - np.hypot(xm - math.cos(ang) * r * 1.3, ym - math.sin(ang) * r * 1.3) + 0.5, 0, 1))
        a = cov[..., None] * 0.9
        cv.a = cv.a * (1 - a) + pc * a
    if tp == "sweater":
        yy, xx = np.mgrid[0:S, 0:S] + 0.5
        sx = 0.012 * ppm
        k = (xx % sx) / sx
        val = 0.5 + 0.5 * np.cos(2 * math.pi * (yy / (sx * 0.8) + 2 * np.abs(k - 0.5)))
        cv.a = cv.a * (1 - 0.10 * val[..., None])
    if tp == "buttonup":
        for z in np.linspace(-0.22, 0.10, 6):
            x0, y0 = fr.px(0.0, z)
            cv.ellipse(x0, y0, 0.0055 * ppm, 0.0055 * ppm, np.array([0.93, 0.93, 0.96]))
        top_px, bot_px = fr.px(0, 0.14), fr.px(0, -0.30)
        cv.line([top_px, bot_px], 0.018 * ppm, col * 0.80, alpha=0.8)
        pk = [fr.px(x, z) for x, z in ((0.04, 0.03), (0.04, -0.05), (0.11, -0.05), (0.11, 0.03))]
        cv.line(pk + [pk[0]], 0.004 * ppm, col * 0.70)
    if tp == "jersey" and look_top.get("crest"):  # only when an outfit asks for one
        t0, t1 = [hexc(c) for c in (look_top.get("trim", ["#ff0000", "#00ff00"]) * 2)[:2]]
        crest = fr.px(0.085, 0.06)
        cv.ellipse(crest[0], crest[1], 0.022 * ppm, 0.026 * ppm, t0)
        cv.ellipse(crest[0], crest[1], 0.009 * ppm, 0.024 * ppm, t1)
    if look_top.get("number"):
        cx, cy = fr.px(0.0, -0.04)
        draw_digits(cv, look_top["number"], cx, cy, 0.12 * ppm, hexc(look_top.get("number_color", "#ffffff")))
    if look_top.get("print") == "cyber":
        pc = hexc(look_top.get("print_color", "#ffff00"))
        cx, cy = fr.px(0.0, -0.05)
        r = 0.07 * ppm
        hexpts = [(cx + math.cos(a) * r, cy + math.sin(a) * r) for a in np.linspace(math.pi / 6, math.pi / 6 + 2 * math.pi, 7)]
        cv.line(hexpts, 0.008 * ppm, pc)
        for i, wdt in enumerate((0.10, 0.07, 0.035)):
            cv.rect(cx - wdt * ppm / 2, cy - (0.016 + i * 0.02) * ppm, cx + wdt * ppm / 2, cy - (0.008 + i * 0.02) * ppm, pc)
        cv.rect(cx - 0.025 * ppm, cy + 0.008 * ppm, cx + 0.025 * ppm, cy + 0.034 * ppm, pc)
        cv.rect(cx - 0.015 * ppm, cy + 0.015 * ppm, cx + 0.015 * ppm, cy + 0.027 * ppm, col)
    k = bd.height / 1.8
    neck_rel = (bd.j("Neck")[2] - 0.02 * k) - chest_z  # the front of the neckline, from the chest center
    # Patterns placed by where they sit on the body (around the torso and arms).
    pat = look_top.get("pattern")
    if pat in ("stripes", "holiday", "sash", "reflective", "plaid"):
        X, Z, ok = body_maps(bd, S)
        zr = Z - chest_z
        if pat == "plaid":  # flannel: dark bands crossing both ways, with thin light lines
            pc = hexc(look_top.get("pattern_color", "#000000"))
            u, v = X / 0.09, zr / 0.09
            dark = ((u % 1) < 0.35).astype(float) + ((v % 1) < 0.35).astype(float)
            mix = (np.where(ok, dark * 0.4, 0.0))[..., None]
            cv.a = cv.a * (1 - mix) + pc * mix
            thin = ((((u + 0.6) % 1) < 0.05) | (((v + 0.6) % 1) < 0.05)) & ok
            cv.a[thin] = cv.a[thin] * 0.55 + 0.45 * np.array([0.92, 0.88, 0.8])
        elif pat == "stripes":  # bands around the chest and arms
            for i, c in enumerate(look_top.get("stripes", ["#ffffff"])):
                band = (np.abs(zr - (-0.02 - i * 0.05)) < 0.016) & ok
                cv.a[band] = hexc(c)
        elif pat == "reflective":  # hi-vis: two silver bands
            for zc in (-0.10, -0.24):
                band = (np.abs(zr - zc) < 0.018) & ok
                cv.a[band] = np.array([0.82, 0.84, 0.86])
        elif pat == "sash":  # from the left shoulder to the right hip, front and back
            d = np.abs(0.8 * X - 0.6 * zr - 0.02) < 0.035
            cv.a[d & ok] = hexc(look_top.get("pattern_color", "#e8c547"))
        elif pat == "holiday":  # an ugly sweater: zigzag band, snowflakes, little trees
            white, green = np.array([0.95, 0.95, 0.95]), np.array([0.1, 0.45, 0.2])
            zig = np.abs(zr - 0.03 - 0.025 * np.abs(((X * 25) % 2) - 1)) < 0.012
            cv.a[zig & ok] = white
            zig2 = np.abs(zr + 0.27 - 0.02 * np.abs(((X * 25 + 1) % 2) - 1)) < 0.01
            cv.a[zig2 & ok] = white
            fx, fz = ((X * 14) % 1) - 0.5, ((zr * 14) % 1) - 0.5
            flake = (np.hypot(fx, fz) < 0.12) & (zr > 0.08) & ok
            cv.a[flake] = white
            tx, tz = ((X * 12) % 1) - 0.5, (zr + 0.2) / 0.1
            tree = (tz > 0) & (tz < 1) & (np.abs(tx) < 0.35 * (1 - tz)) & ok
            cv.a[tree] = green
    if look_top.get("tie"):  # down the shirt front
        tcol = hexc(look_top["tie"])
        poly(cv, [fr.px(x, neck_rel + z) for x, z in ((-0.012, -0.004), (0.012, -0.004), (0.009, -0.03),
                                                    (-0.009, -0.03))], tcol * 0.85)
        poly(cv, [fr.px(x, neck_rel + z) for x, z in ((-0.008, -0.03), (0.008, -0.03), (0.024, -0.33), (0.0, -0.37),
                                                    (-0.024, -0.33))], tcol)
    if look_top.get("badge"):  # a name tag on the left chest
        bx, by = fr.px(0.085, 0.0)
        cv.rect(bx - 0.04 * ppm, by - 0.02 * ppm, bx + 0.04 * ppm, by + 0.02 * ppm, np.array([0.97, 0.97, 0.95]))
        cv.rect(bx - 0.04 * ppm, by - 0.02 * ppm, bx + 0.04 * ppm, by - 0.009 * ppm, hexc(look_top.get("badge_color", "#ffd23f")))
    if look_top.get("buttons"):  # jacket front
        for z in (-0.27, -0.36):
            x0, y0 = fr.px(0.0, z)
            cv.ellipse(x0, y0, 0.007 * ppm, 0.007 * ppm, col * 0.45)
    if tp == "polo":  # placket and buttons
        cv.line([fr.px(0, neck_rel), fr.px(0, neck_rel - 0.13)], 0.022 * ppm, col * 0.85)
        for z in (-0.03, -0.075, -0.115):
            x0, y0 = fr.px(0.0, neck_rel + z)
            cv.ellipse(x0, y0, 0.005 * ppm, 0.005 * ppm, np.array([0.95, 0.95, 0.95]))
    if tp == "quarterzip":  # zipper
        length = 0.55 if look_top.get("zip") == "full" else 0.2
        cv.line([fr.px(0, neck_rel + 0.02), fr.px(0, neck_rel - length)], 0.006 * ppm, np.array([0.78, 0.8, 0.82]))
        x0, y0 = fr.px(0.0, neck_rel - 0.01)
        cv.rect(x0 - 0.006 * ppm, y0 - 0.02 * ppm, x0 + 0.006 * ppm, y0, np.array([0.8, 0.82, 0.85]))
    if tp == "hoodie":  # kangaroo pocket
        pk = [fr.px(x, z) for x, z in ((-0.12, -0.24), (0.12, -0.24), (0.09, -0.36), (-0.09, -0.36))]
        poly(cv, pk, col * 0.9)
        cv.line(pk + [pk[0]], 0.004 * ppm, col * 0.7)
    if look_top.get("text"):  # block letters on the chest, maybe in a box
        txt = look_top["text"]
        hgt = 0.065
        if look_top.get("text_box"):
            w = 0.035 * len(txt) + 0.03
            poly(cv, [fr.px(x, z) for x, z in ((-w / 2, 0.055), (w / 2, 0.055), (w / 2, -0.035), (-w / 2, -0.035))],
                 hexc(look_top["text_box"]))
        draw_text(cv, fr, txt, 0.0, 0.01, hgt, hexc(look_top.get("text_color", "#ffffff")), ppm)
    cv.noise(0.012, seed=5)
    return cv.image("%s_top_%s" % (model_id, tp))


def body_maps(bd, S):
    """For each texel of a body-UV texture: the body point's x and z (meters), and whether
    any face covers it."""
    xn = (bd.co[:, 0] + 1.0) / 2.0
    zn = (bd.co[:, 2] - bd.ground + 0.05) / (bd.height + 0.1)
    X = raster_alpha(bd, np.clip(xn, 0.0001, 1), S, S)
    Z = raster_alpha(bd, np.clip(zn, 0.0001, 1), S, S)
    ok = (X > 0) & (Z > 0)
    return X * 2.0 - 1.0, Z * (bd.height + 0.1) + bd.ground - 0.05, ok


def poly(cv, pts, color):
    """Fills a polygon (pixel coordinates) on a Canvas."""
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    win = cv._win(min(xs) - 1, max(xs) + 1, min(ys) - 1, max(ys) + 1)
    if not win:
        return
    sl, xx, yy = win
    inside = np.zeros(xx.shape, bool)
    n = len(pts)
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        cond = (y1 > yy) != (y2 > yy)
        with np.errstate(divide="ignore", invalid="ignore"):
            xint = (x2 - x1) * (yy - y1) / (y2 - y1 + 1e-12) + x1
        inside ^= cond & (xx < xint)
    cv._blend(sl, inside.astype(float), color)


FONT5x7 = {
    "A": ["01110", "10001", "10001", "11111", "10001", "10001", "10001"],
    "B": ["11110", "10001", "10001", "11110", "10001", "10001", "11110"],
    "C": ["01111", "10000", "10000", "10000", "10000", "10000", "01111"],
    "D": ["11110", "10001", "10001", "10001", "10001", "10001", "11110"],
    "E": ["11111", "10000", "10000", "11110", "10000", "10000", "11111"],
    "F": ["11111", "10000", "10000", "11110", "10000", "10000", "10000"],
    "G": ["01111", "10000", "10000", "10011", "10001", "10001", "01111"],
    "H": ["10001", "10001", "10001", "11111", "10001", "10001", "10001"],
    "I": ["11111", "00100", "00100", "00100", "00100", "00100", "11111"],
    "K": ["10001", "10010", "10100", "11000", "10100", "10010", "10001"],
    "L": ["10000", "10000", "10000", "10000", "10000", "10000", "11111"],
    "M": ["10001", "11011", "10101", "10101", "10001", "10001", "10001"],
    "N": ["10001", "11001", "10101", "10011", "10001", "10001", "10001"],
    "O": ["01110", "10001", "10001", "10001", "10001", "10001", "01110"],
    "P": ["11110", "10001", "10001", "11110", "10000", "10000", "10000"],
    "R": ["11110", "10001", "10001", "11110", "10100", "10010", "10001"],
    "S": ["01111", "10000", "10000", "01110", "00001", "00001", "11110"],
    "T": ["11111", "00100", "00100", "00100", "00100", "00100", "00100"],
    "U": ["10001", "10001", "10001", "10001", "10001", "10001", "01110"],
    "V": ["10001", "10001", "10001", "10001", "10001", "01010", "00100"],
    "W": ["10001", "10001", "10001", "10101", "10101", "10101", "01010"],
    "Y": ["10001", "10001", "01010", "00100", "00100", "00100", "00100"],
}


def draw_text(cv, fr, text, x0, z0, hgt, color, ppm):
    """Block capitals centered at (x0, z0) meters on the body; hgt = letter height."""
    cell = hgt / 7.0
    width = len(text) * 6 * cell - cell
    left = x0 - width / 2  # someone facing the hero reads from their left: the hero's right, -x
    for i, ch in enumerate(text.upper()):
        rows = FONT5x7.get(ch)
        if rows is None:
            continue
        for r, row in enumerate(rows):
            for c, bit in enumerate(row):
                if bit == "1":
                    cx = left + (i * 6 + c + 0.5) * cell
                    cz = z0 + hgt / 2 - (r + 0.5) * cell
                    px, py = fr.px(cx, cz)
                    hw = cell * ppm * 0.62  # cells overlap a little, so strokes are solid
                    cv.rect(px - hw, py - hw, px + hw, py + hw, color)


def plain_texture(name, color, noise=0.02, S=256):
    cv = Canvas(S, S, hexc(color))
    cv.noise(noise, seed=9)
    return cv.image(name)


# =========================================================================== skin texture
def eyes_of(bd):
    """(left eye, right eye) centers from MakeHuman's eye joint markers."""
    le, re = bd.joints.get("l-eye"), bd.joints.get("r-eye")
    if le is None or re is None:
        return None
    if le[0] < re[0]:  # "l" is the character's left (+x)
        le, re = re, le
    return le, re


def skin_material(bd):
    counts = {}
    for f, mi in zip(bd.faces, bd.face_mat):
        if all(bd.body[v] for v in f):
            counts[mi] = counts.get(mi, 0) + 1
    if not counts:
        return None
    idx = max(counts, key=counts.get)
    slots = bd.obj.material_slots
    return slots[idx].material if idx < len(slots) else None


def beard_alpha(bd, look):
    """Per-vertex beard coverage (0..1) for a short boxed beard or stubble: mustache under
    the nose, a cheek line rising to the sideburns at the ears, along the jaw underneath,
    never on the lips or the neck. Landmarks come from MakeHuman's "lips" and "ears" vertex
    groups and its chin ("jaw") joint. (MakeHuman's "mouth" joint is not at the mouth.)"""
    face = look.get("face", {})
    kind = face.get("beard", "none")
    if kind not in ("short", "stubble", "mustache"):
        return None
    eyes = eyes_of(bd)
    lips = bd.groups.get("lips")
    if eyes is None or not lips:
        return None
    k = bd.height / 1.8
    Lp = bd.co[lips]
    mz = float(np.median(Lp[:, 2]))
    my = float(Lp[:, 1].min())
    mw = float(np.abs(Lp[:, 0]).max())
    ears = bd.groups.get("ears")
    eye_z = 0.5 * (eyes[0][2] + eyes[1][2])
    ear_y = float(bd.co[ears][:, 1].min()) if ears else 0.5 * (eyes[0][1] + eyes[1][1]) + 0.07 * k
    chin = bd.joints.get("jaw")
    chin_zr = (float(chin[2]) - mz) if chin is not None else -0.027 * k
    ax = np.abs(bd.co[:, 0])
    yr = bd.co[:, 1] - my
    zr = bd.co[:, 2] - mz
    # Upper edge: under the nose in the middle, rising across the cheeks to the sideburns.
    z_top = k * (0.012 + 0.004 * sstep(0.024 * k, 0.016 * k, ax)) + np.maximum(0.0, ax - 0.032 * k) * 1.0
    z_top = np.minimum(z_top, eye_z - mz - 0.035 * k)
    a = sstep(z_top + 0.003 * k, z_top - 0.003 * k, zr)
    # Back edge: the front of the ears.
    yb = ear_y - my - 0.004 * k
    a *= sstep(yb + 0.004 * k, yb - 0.006 * k, yr)
    # Under the chin, then up along the jaw toward the ears; never down the neck.
    y_back = max(yb, 0.06 * k)
    t = np.clip((yr - 0.03 * k) / max(y_back - 0.03 * k, 1e-3), 0, 1)
    z_low = (chin_zr - 0.03 * k) * (1 - t) + (-0.022 * k) * t
    a *= sstep(z_low - 0.004 * k, z_low + 0.005 * k, zr)
    # Not on the lips.
    e = (ax / (mw + 0.003 * k)) ** 2 + (zr / (0.0095 * k)) ** 2
    a *= np.where(yr < 0.02 * k, sstep(0.8, 1.3, e), 1.0)
    a *= (bd.is_dom("Head", "Neck") & bd.body).astype(float)
    if kind == "mustache":  # just the upper lip: above the lips, under the nose, at the front
        a *= sstep(0.0, 0.004 * k, zr) * sstep(0.042 * k, 0.03 * k, ax) * sstep(0.03 * k, 0.018 * k, yr)
    return a * (0.42 if kind == "stubble" else 0.95)


def raster_alpha(bd, valpha, W, H):
    """Paints per-vertex values into texture space (body UVs), interpolated across faces."""
    A = np.zeros((H, W), np.float32)
    for fi, f in enumerate(bd.faces):
        av = valpha[list(f)]
        if av.max() < 0.005 or not all(bd.body[v] for v in f):
            continue
        uvs = np.array(bd.face_uv[fi]) * [W, H]
        tris = ((0, 1, 2), (0, 2, 3)) if len(f) == 4 else ((0, 1, 2),)
        for tri in tris:
            P = uvs[list(tri)]
            a3 = av[list(tri)]
            x0, y0 = np.maximum(np.floor(P.min(0)).astype(int) - 1, 0)
            x1, y1 = np.minimum(np.ceil(P.max(0)).astype(int) + 1, [W - 1, H - 1])
            if x1 < x0 or y1 < y0:
                continue
            ys, xs = np.mgrid[y0:y1 + 1, x0:x1 + 1]
            px, py = xs + 0.5, ys + 0.5
            (ax_, ay_), (bx_, by_), (cx_, cy_) = P
            den = (by_ - cy_) * (ax_ - cx_) + (cx_ - bx_) * (ay_ - cy_)
            if abs(den) < 1e-9:
                continue
            l1 = ((by_ - cy_) * (px - cx_) + (cx_ - bx_) * (py - cy_)) / den
            l2 = ((cy_ - ay_) * (px - cx_) + (ax_ - cx_) * (py - cy_)) / den
            l3 = 1 - l1 - l2
            tol = -1.5 / max(1.0, abs(den) ** 0.5)
            inside = (l1 >= tol) & (l2 >= tol) & (l3 >= tol)
            val = np.clip(l1 * a3[0] + l2 * a3[1] + l3 * a3[2], 0, 1)
            yy, xx = ys[inside], xs[inside]
            A[yy, xx] = np.maximum(A[yy, xx], val[inside])
    return A


def skin_texture(bd, look, model_id, tint=0.3):
    """The hero's own copy of the skin texture: tinted toward look["skin"], with any beard
    or stubble painted in."""
    import hero_mpfb
    mat = skin_material(bd)
    node, img = hero_mpfb.base_color_image(mat)
    if img is None:
        return
    W, H = img.size
    if max(W, H) > 2048:
        img.scale(2048, 2048)
        W, H = img.size
    px = np.empty(W * H * 4, np.float32)
    img.pixels.foreach_get(px)
    px = px.reshape(H, W, 4)
    rgb = px[..., :3].copy()
    if look.get("skin") and tint > 0:
        tgt = hexc(look["skin"]).astype(np.float32)
        lum = rgb @ np.array([0.299, 0.587, 0.114], np.float32)
        valid = px[..., 3] > 0.5
        mean = float(lum[valid].mean()) if valid.any() else float(lum.mean())
        rgb = rgb * (1 - tint) + tgt[None, None, :] * (lum / max(mean, 1e-3))[..., None] * tint
    av = beard_alpha(bd, look)
    if av is not None and av.max() > 0.01:
        A = raster_alpha(bd, av, W, H)
        ys, xs = np.nonzero(A > 0.002)
        if len(ys):
            y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
            sub = A[y0:y1, x0:x1]
            rng = np.random.default_rng(11)
            nz = rng.random(sub.shape).astype(np.float32)
            nz = (nz + np.roll(nz, 1, 0) + np.roll(nz, -1, 0) + np.roll(nz, 2, 0)) / 4.0  # short strands
            face = look.get("face", {})
            col = hexc(face.get("beard_color", look["hair"]["color"])).astype(np.float32)
            a = np.clip(sub * (0.8 + 0.4 * (nz - 0.5) * 2), 0, 1)[..., None]
            shade = (0.75 + 0.5 * nz)[..., None]
            rgb[y0:y1, x0:x1] = rgb[y0:y1, x0:x1] * (1 - a) + col * shade * a
    px[..., :3] = np.clip(rgb, 0, 1)
    new = bpy.data.images.new("%s_skin" % model_id, W, H, alpha=True)
    new.pixels.foreach_set(px.ravel())
    new.filepath_raw = os.path.join(TEXDIR, "%s_skin.png" % model_id)
    new.file_format = "PNG"
    new.save()
    node.image = new


def recolor_brows(rig, look, model_id):
    import hero_mpfb
    col = look.get("face", {}).get("brows")
    if not col:
        return
    for o in rig.children_recursive:
        if o.type == "MESH" and "eyebrow" in o.name.lower():
            for slot in o.material_slots:
                hero_mpfb.colorize(slot.material, col, keep=0.1, name="%s_brows" % model_id)


# =========================================================================== accessories
def tube(name, pts, radius, mat, rig, bone, closed=False, seg=8, sq=2.0):
    verts, faces = [], []
    n = len(pts)
    for i, p in enumerate(pts):
        a = pts[i - 1] if (closed or i > 0) else pts[i]
        b_ = pts[(i + 1) % n] if (closed or i < n - 1) else pts[i]
        t = (Vector(b_) - Vector(a)).normalized()
        ref = Vector((0, 0, 1)) if abs(t.z) < 0.9 else Vector((1, 0, 0))
        x = t.cross(ref).normalized()
        y = t.cross(x).normalized()
        rx, ry = radius if isinstance(radius, tuple) else (radius, radius)
        for q in range(seg):
            ang = 2 * math.pi * q / seg
            c, s = math.cos(ang), math.sin(ang)
            e = 2.0 / sq
            verts.append(Vector(p) + x * math.copysign(abs(c) ** e, c) * rx + y * math.copysign(abs(s) ** e, s) * ry)
    rng = range(n) if closed else range(n - 1)
    for i in rng:
        i2 = (i + 1) % n
        for q in range(seg):
            q2 = (q + 1) % seg
            faces.append((i * seg + q, i2 * seg + q, i2 * seg + q2, i * seg + q2))
    if not closed:
        verts.append(Vector(pts[0]))
        verts.append(Vector(pts[-1]))
        c0, c1 = len(verts) - 2, len(verts) - 1
        for q in range(seg):
            q2 = (q + 1) % seg
            faces.append((q2, q, c0))
            faces.append(((n - 1) * seg + q, (n - 1) * seg + q2, c1))
    wts = [{B + bone: 1.0}] * len(verts)
    uvs = [[(0, 0)] * len(f) for f in faces]
    return make_mesh_object(name, verts, faces, uvs, wts, [mat], None, rig)


def add_accessories(bd, rig, look, model_id):
    acc = look.get("acc", [])
    Hm = bd.height
    k = Hm / 1.8
    eyes = eyes_of(bd)
    if "cap" in acc:
        eye_z = eyes[0][2] if eyes else bd.j("Head")[2] + 0.5 * (bd.j("Head", "t")[2] - bd.j("Head")[2])
        brow_z = eye_z + 0.032 * k
        mask = region_head_top(bd, brow_z - 0.05 * k)
        upper = mask & (bd.co[:, 2] >= brow_z)
        front = bd.co[upper][np.argmin(bd.co[upper][:, 1])]
        # The cap's rim: just above the brows in front, a little lower at the back.
        rim = dict(co=(0.0, front[1], brow_z), no=(0.0, -0.1, -1.0), where=dict(zmin=brow_z - 0.1 * k))
        capc = look.get("cap", {})
        capm = material("%s_cap" % model_id, hexc(capc.get("color", "#16161a")), rough=0.75)
        cap, cap_edges = garment(bd, mask, "%s.cap" % model_id, 0.022 * k, capm, rig, smooth=4, thickness=0.004,
                                 cuts=[rim])
        if capc.get("front"):  # a trucker cap: a different front panel
            cap.data.materials.append(material("%s_cap_front" % model_id, hexc(capc["front"]), rough=0.8))
            ymid = float(np.median(bd.co[mask][:, 1]))
            for p in cap.data.polygons:
                if p.center.y < ymid - 0.01 * k:
                    p.material_index = 1
        for e in cap_edges:
            strip("%s.cap_band" % model_id, e, scaled([(-0.002, -0.002), (-0.002, 0.001), (0.0, 0.002), (0.012, 0.0015)], k),
                  capm, rig)
        y0, z0 = front[1] - 0.004, brow_z + 0.005
        hw = 0.085 * k
        pts, rad = [], []
        for t in np.linspace(0, 1, 6):
            pts.append(Vector((0, y0 - 0.075 * t * k, z0 - 0.012 * t * t)))
            rad.append((hw * (1 - 0.45 * t ** 1.6), 0.004))
        verts, faces = [], []
        for i, (p, (rx, ry)) in enumerate(zip(pts, rad)):
            for q in range(10):
                a = 2 * math.pi * q / 10
                verts.append(p + Vector((math.cos(a) * rx, 0, math.sin(a) * ry)))
        for i in range(len(pts) - 1):
            for q in range(10):
                q2 = (q + 1) % 10
                faces.append((i * 10 + q, i * 10 + q2, (i + 1) * 10 + q2, (i + 1) * 10 + q))
        make_mesh_object("%s.cap_brim" % model_id, verts, faces, [[(0, 0)] * 4 for _ in faces],
                         [{B + "Head": 1.0}] * len(verts), [capm], None, rig)
    if "visor" in acc:  # a sun visor: a band around the head and a brim in front, no crown
        eye_z = eyes[0][2] if eyes else bd.j("Head")[2] + 0.5 * (bd.j("Head", "t")[2] - bd.j("Head")[2])
        band_z = eye_z + 0.045 * k
        sl = bd.is_dom("Head") & bd.body & (np.abs(bd.co[:, 2] - band_z) < 0.012 * k)
        P = bd.co[sl]
        cx, cy = float(P[:, 0].mean()), float(P[:, 1].mean())
        rx = float(np.abs(P[:, 0] - cx).max()) + 0.02 * k
        ry = float(np.abs(P[:, 1] - cy).max()) + 0.02 * k
        vm = material("%s_visor" % model_id, hexc(look.get("visor_color", "#ffcc33")), rough=0.6)
        ring = [Vector((cx + math.cos(a) * rx, cy + math.sin(a) * ry, band_z)) for a in np.linspace(0, 2 * math.pi, 28, endpoint=False)]
        tube("%s.visor_band" % model_id, ring, (0.0035 * k, 0.02 * k), vm, rig, "Head", closed=True, seg=6, sq=6.0)
        y0, z0 = cy - ry + 0.002, band_z - 0.012 * k
        hw = 0.085 * k
        pts, rad = [], []
        for t in np.linspace(0, 1, 6):
            pts.append(Vector((cx, y0 - 0.08 * t * k, z0 - 0.01 * t * t)))
            rad.append((hw * (1 - 0.45 * t ** 1.6), 0.004))
        verts, faces = [], []
        for p, (rx_, ry_) in zip(pts, rad):
            for q in range(10):
                a = 2 * math.pi * q / 10
                verts.append(p + Vector((math.cos(a) * rx_, 0, math.sin(a) * ry_)))
        for i in range(len(pts) - 1):
            for q in range(10):
                q2 = (q + 1) % 10
                faces.append((i * 10 + q, i * 10 + q2, (i + 1) * 10 + q2, (i + 1) * 10 + q))
        make_mesh_object("%s.visor_brim" % model_id, verts, faces, [[(0, 0)] * 4 for _ in faces],
                         [{B + "Head": 1.0}] * len(verts), [vm], None, rig)
    if eyes and ("glasses" in acc or "sunglasses" in acc):
        le, re = (Vector(eyes[0]), Vector(eyes[1]))
        sun = "sunglasses" in acc
        fm = material("%s_frame" % model_id, hexc("#151515" if sun else look.get("glasses_color", "#8a72b4")),
                      rough=0.35)
        lens = material("%s_lens" % model_id, hexc("#101216"), rough=0.1)
        w = (0.026 if sun else 0.028) * k
        hgt = (0.019 if sun else 0.021) * k
        fwd = -0.024 * k
        rim_r = 0.0016 if sun else 0.0024
        for c in (le, re):
            cc = Vector(c) + Vector((0, fwd, 0.0))
            ring = [cc + Vector((math.copysign(abs(math.cos(a)) ** 0.5, math.cos(a)) * w, 0,
                                 math.copysign(abs(math.sin(a)) ** 0.5, math.sin(a)) * hgt))
                    for a in np.linspace(0, 2 * math.pi, 20, endpoint=False)]
            tube("%s.frame" % model_id, ring, rim_r, fm, rig, "Head", closed=True, seg=6)
            if sun:
                lv = [cc + Vector((math.copysign(abs(math.cos(a)) ** 0.5, math.cos(a)) * w * 0.98, 0.001,
                                   math.copysign(abs(math.sin(a)) ** 0.5, math.sin(a)) * hgt * 0.98))
                      for a in np.linspace(0, 2 * math.pi, 20, endpoint=False)]
                ctr = len(lv)
                verts = lv + [cc + Vector((0, 0.0015, 0))]
                faces = [(i, (i + 1) % ctr, ctr) for i in range(ctr)]
                make_mesh_object("%s.lens" % model_id, verts, faces, [[(0, 0)] * 3 for _ in faces],
                                 [{B + "Head": 1.0}] * len(verts), [lens], None, rig)
            sg = 1 if c[0] > 0 else -1
            ear = Vector((c[0] + sg * 0.025 * k, c[1] + 0.09 * k, c[2] - 0.004))
            tube("%s.temple" % model_id, [cc + Vector((sg * w, 0, 0.004)), ear], rim_r * 0.85, fm, rig, "Head")
        tube("%s.bridge" % model_id, [re + Vector((w * 0.9, fwd, 0.005)), le + Vector((-w * 0.9, fwd, 0.005))],
             rim_r, fm, rig, "Head")
    if "watch" in acc:
        wr = Vector(bd.j("LeftHand"))
        el = Vector(bd.j("LeftForeArm"))
        d = (wr - el).normalized()
        c = wr - d * 0.035 * k
        near = np.linalg.norm(bd.co - np.array(c), axis=1) < 0.04
        r = float(np.median(np.linalg.norm(np.cross(bd.co[near] - np.array(c), np.array(d)), axis=1))) if near.any() else 0.028
        ref = Vector((0, 0, 1)) if abs(d.z) < 0.9 else Vector((0, 1, 0))
        x = d.cross(ref).normalized()
        y = d.cross(x).normalized()
        ring = [c + (x * math.cos(a) + y * math.sin(a)) * (r + 0.004) for a in np.linspace(0, 2 * math.pi, 16, endpoint=False)]
        wm = material("%s_watch" % model_id, hexc("#1c1c1e"), rough=0.4)
        tube("%s.watch" % model_id, ring, (0.0025, 0.007), wm, rig, "LeftForeArm", closed=True, seg=6)
        face_c = c + y * (r + 0.006)
        tube("%s.watch_face" % model_id, [face_c - y * 0.002, face_c + y * 0.003], 0.010,
             material("%s_watch_face" % model_id, hexc("#3a4a5a"), rough=0.2), rig, "LeftForeArm", seg=12)


# =========================================================================== shoes
def add_shoes(rig, basemesh, look, model_id):
    mod = importlib.import_module("bl_ext.vbd.mpfb.services")
    sh = look["shoes"]
    asset = SHOES.get(sh["type"], "shoes05")
    path = mod.AssetService.find_asset_absolute_path(asset + ".mhclo", "clothes")
    if not path:
        return
    obj = mod.HumanService.add_mhclo_asset(path, basemesh, asset_type="Clothes", subdiv_levels=0, material_type="MAKESKIN")
    if obj is None:
        return
    obj.parent = rig
    import hero_mpfb
    for slot in obj.material_slots:
        hero_mpfb.colorize(slot.material, sh["color"], keep=0.0, name="%s_shoes" % model_id)


# =========================================================================== outfit
def dress(rig, basemesh, model_id, look=None):
    """Dresses the hero in their hero_looks.py outfit (or `look`, for skins)."""
    look = look or L.look(model_id)
    add_shoes(rig, basemesh, look, model_id)
    # Bake the body shape first, so garments follow the hero's actual figure.
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active = basemesh
    basemesh.select_set(True)
    if basemesh.data.shape_keys:
        bpy.ops.object.shape_key_remove(all=True, apply_mix=True)
    bpy.context.view_layer.update()
    bd = Body(rig, basemesh)
    bd.female = look.get("sex") == "f"  # tops drape over the bust (bust_drape)
    Hm = bd.height
    k = Hm / 1.8
    skin_texture(bd, look, model_id, tint=look.get("skin_tint", 0.3))
    recolor_brows(rig, look, model_id)
    top, bottom = look["top"], look["bottom"]
    tt, bt = top["type"], bottom["type"]
    hips_z, spine_z = bd.j("Hips")[2], bd.j("Spine1")[2]
    waist_z = hips_z + 0.45 * (spine_z - hips_z)
    hem_z = hips_z + 0.02 * k
    covered = np.zeros(len(bd.co), bool)
    # ---------------------------------------------------------------- bottoms (under the top)
    gold = bottom.get("material") == "gold"
    bmat = material("%s_bottom" % model_id, image=plain_texture("%s_bottom" % model_id, bottom["color"]),
                    rough=0.38 if gold else 0.85, metal=GOLD_METAL if gold else 0.0)
    if bt in ("skirt", "robe"):
        z_top = waist_z
        robe = bt == "robe"  # a robe falls to the ankles, flaring less
        z_hem = (bd.j("LeftFoot")[2] + 0.05 * k) if robe else (bd.j("LeftLeg")[2] - 0.06 * k)
        skirt_r0 = None
        legs = bd.is_dom("Hips", "LeftUpLeg", "RightUpLeg") & bd.body & (bd.co[:, 2] <= z_top) & (bd.co[:, 2] >= z_hem)
        pts = bd.co[legs]
        cy = float(np.median(pts[:, 1]))
        rings, n_r, seg = [], 8, 28
        for i in range(n_r):
            t = i / (n_r - 1)
            z = z_top - (z_top - z_hem) * t
            band_pts = bd.co[bd.body & (np.abs(bd.co[:, 2] - z) < 0.012) & (np.abs(bd.co[:, 0]) < 0.25 * k)]
            r0 = float(np.percentile(np.hypot(band_pts[:, 0], band_pts[:, 1] - cy), 95)) if len(band_pts) else 0.15 * k
            if skirt_r0 is None:
                skirt_r0 = r0
            r = max(r0 + 0.01 * k, skirt_r0) * (1 + (0.32 if robe else 0.55) * t ** 1.3)
            rings.append([(math.cos(a) * r, cy + math.sin(a) * r * 0.85, z) for a in np.linspace(0, 2 * math.pi, seg, endpoint=False)])
        verts = [v for ring in rings for v in ring]
        faces = []
        for i in range(n_r - 1):
            for j in range(seg):
                j2 = (j + 1) % seg
                faces.append((i * seg + j, i * seg + j2, (i + 1) * seg + j2, (i + 1) * seg + j))
        tree = kdtree.KDTree(int(bd.body.sum()))
        idx = np.where(bd.body)[0]
        for n_i, vi in enumerate(idx):
            tree.insert(bd.co[vi], n_i)
        tree.balance()
        wts = []
        for v in verts:
            _, n_i, _ = tree.find(v)
            w = weights_of(bd, idx[n_i])
            t = (z_top - v[2]) / max(1e-6, z_top - z_hem)
            mixed = {kk: vv * t * 0.7 for kk, vv in w.items()}
            mixed[B + "Hips"] = mixed.get(B + "Hips", 0.0) + (1 - t * 0.7)
            s = sum(mixed.values())
            wts.append({kk: vv / s for kk, vv in mixed.items()} if s else {B + "Hips": 1.0})
        uvs = [[(0, 0), (1, 0), (1, 1), (0, 1)] for _ in faces]
        sk = make_mesh_object("%s.skirt" % model_id, verts, faces, uvs, wts, [bmat], None, rig)
        sol = sk.modifiers.new("Solidify", "SOLIDIFY")
        sol.thickness = 0.004
        sol.use_rim = True
        bpy.context.view_layer.objects.active = sk
        bpy.ops.object.modifier_move_to_index(modifier="Solidify", index=0)
        bpy.ops.object.modifier_apply(modifier="Solidify")
    else:
        # The waistband stops just above the top's hem, so the top always covers it.
        top_z = (hem_z + 0.03 * k) if tt != "tank" else waist_z
        mask = region_bottom(bd, bt, top_z + 0.06 * k)
        cuts = [dict(co=(0.0, 0.0, top_z), no=(0.0, 0.0, 1.0), where=dict(xmax=0.32 * k, zmin=top_z - 0.15 * k))]
        for side in ("Left", "Right"):
            if bt == "shorts":
                bone, t = side + "UpLeg", 0.62
            else:
                bone, t = side + "Leg", {"pants": 0.93, "joggers": 0.90, "leggings": 0.95}.get(bt, 0.93)
            h, tl = bd.j(bone), bd.j(bone, "t")
            cuts.append(dict(co=h + t * (tl - h), no=tl - h,
                             where=dict(bones=[side + "UpLeg", side + "Leg", side + "Foot"])))
        off = {"joggers": 0.013, "pants": 0.009, "shorts": 0.012, "leggings": 0.003}.get(bt, 0.009) * k
        fill = {"joggers": 0.85, "pants": 0.65, "shorts": 0.75, "leggings": 0.1}.get(bt, 0.6)

        def loose(p):
            if bt in ("joggers", "shorts"):
                return 0.006 * k * float(np.clip((hips_z - p[2]) / (0.3 * Hm), 0, 1))
            return 0.0

        def waist_snug(P):  # under the top's hem the bottoms hug the body, so the top always covers them
            return sstep(top_z - 0.12 * k, top_z - 0.04 * k, P[:, 2])

        obj, edges = garment(bd, mask, "%s.%s" % (model_id, bt), off, bmat, rig, loose=loose, fill=fill, smooth=5,
                             cuts=cuts, snug=(waist_snug, 0.003 * k))
        keep = np.ones(len(bd.co), bool)
        for c in cuts:
            keep &= cut_keep(bd, c)
        covered |= mask & keep
        cuff = material("%s_bottom_hem" % model_id, hexc(bottom["color"]) * 0.88, rough=0.85)
        for e in edges:
            if e["P"][:, 2].mean() < hips_z - 0.1 * k:  # leg openings
                if bt == "leggings":
                    continue
                prof = JOGGER_CUFF if bt == "joggers" else HEM
            else:
                prof = WAISTBAND
            strip("%s.%s_band" % (model_id, bt), e, scaled(prof, k), cuff, rig)
    # ---------------------------------------------------------------- tops (a shirt under a jacket...)
    if look.get("under"):
        covered |= build_top(bd, rig, look["under"], model_id + "_under", hem_z, waist_z, under=True)
    covered |= build_top(bd, rig, top, model_id, hem_z, waist_z, over=bool(look.get("under")))
    hide_body(bd, covered, rings=2)
    add_accessories(bd, rig, look, model_id)
    import accessories
    accessories.add(bd, rig, look, model_id)
    if look.get("eye_glow"):
        glow_eyes(rig, look["eye_glow"], model_id)
    if look.get("ghost"):
        ghostify(rig)


def glow_material(name, color, strength=6.0):
    """A material that glows in the color (emission, which the glTF export keeps)."""
    m = material(name, hexc(color), rough=0.3)
    bsdf = next((n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if bsdf is not None:
        for nm in ("Emission Color", "Emission"):
            if nm in bsdf.inputs:
                bsdf.inputs[nm].default_value = (*lin(hexc(color)), 1.0)
        if "Emission Strength" in bsdf.inputs:
            bsdf.inputs["Emission Strength"].default_value = strength
    return m


def glow_eyes(rig, color, model_id, strength=6.0):
    """Eyes that glow (the Copilot's, under the hood)."""
    m = glow_material("%s_eye_glow" % model_id, color, strength)
    for o in rig.children_recursive:
        if o.type == "MESH" and "high-poly" in o.name.lower():  # MakeHuman's eyes
            for i in range(len(o.material_slots)):
                o.material_slots[i].material = m


# Top types: (default sleeves, neckline (front dip, back rise, V depth, V half-width in
# radians), offset from the body, fill, thick ribbed edges). Lengths are times k.
TOP_STYLE = {
    "tee": ("short", (0.03, 0.01, 0.0, 0.6), 0.016, 0.65, False),
    "jersey": ("short", (0.03, 0.01, 0.05, 0.6), 0.017, 0.7, False),
    "buttonup": ("short", (0.025, 0.012, 0.0, 0.6), 0.018, 0.75, False),
    "polo": ("short", (0.025, 0.012, 0.0, 0.6), 0.017, 0.7, False),
    "sweatshirt": ("long", (0.03, 0.01, 0.0, 0.6), 0.020, 0.9, True),
    "sweater": ("long", (0.03, 0.01, 0.0, 0.6), 0.022, 0.9, True),
    "hoodie": ("long", (0.035, 0.01, 0.0, 0.6), 0.024, 0.92, True),
    "quarterzip": ("long", (0.02, 0.015, 0.0, 0.6), 0.021, 0.88, True),
    "jacket": ("long", (0.03, 0.012, 0.17, 0.85), 0.028, 0.92, False),
    "vest": ("none", (0.03, 0.01, 0.12, 0.7), 0.034, 0.9, False),
    "tank": ("none", (0.085, -0.03, 0.0, 0.6), 0.014, 0.55, False),
    "dress": ("cap", (0.04, 0.0, 0.0, 0.6), 0.010, 0.45, False),
    "robe": ("long", (0.045, 0.0, 0.0, 0.6), 0.03, 0.95, False),  # with a "robe" bottom down to the ankles
}
POLO_COLLAR = [(0.0, -0.001), (-0.012, 0.0015), (-0.015, 0.004), (-0.009, 0.006), (0.002, 0.007), (0.018, 0.005),
               (0.022, 0.0025)]
STAND = [(0.0, -0.001), (-0.006, 0.0022), (-0.026, 0.0042), (-0.03, 0.002)]
LAPEL = [(-0.004, 0.001), (-0.002, 0.0065), (0.04, 0.007), (0.05, 0.003)]
HOOD = [(-0.01, 0.0), (-0.03, 0.03), (0.0, 0.07), (0.06, 0.08), (0.11, 0.05), (0.14, 0.01)]


def sub_edge(edge, keep):
    """The longest run of an edge loop where keep is True, as an open edge."""
    n = len(keep)
    if keep.all() or not keep.any():
        return None
    start = int(np.argmax(~keep))  # rotate so the loop starts outside the run
    order = np.roll(np.arange(n), -start)
    k2 = keep[order]
    best, cur, best_rng = 0, 0, (0, 0)
    for i, v in enumerate(k2):
        cur = cur + 1 if v else 0
        if cur > best:
            best, best_rng = cur, (i - cur + 1, i + 1)
    idx = order[best_rng[0]:best_rng[1]]
    if len(idx) < 3:
        return None
    return dict(P=edge["P"][idx], N=edge["N"][idx], D=edge["D"][idx], W=[edge["W"][i] for i in idx], closed=False)


def build_top(bd, rig, top, name, hem_z, waist_z, under=False, over=False):
    """Makes one top (shirt, hoodie, jacket...). Returns the body vertices it covers."""
    Hm = bd.height
    k = Hm / 1.8
    tt = top["type"]
    st = TOP_STYLE.get(tt, TOP_STYLE["tee"])
    sleeves = {"dress": "cap", "tank": "none", "vest": "none"}.get(tt, top.get("sleeves", st[0]))
    hips_z = bd.j("Hips")[2]
    # A robe's top ends at the waist, where its skirt starts (a rope belt covers the seam).
    top_hem = {"dress": waist_z - 0.02 * k, "jacket": hips_z - 0.05 * k, "robe": waist_z - 0.02 * k}.get(tt, hem_z)
    nh = bd.j("Neck")
    z_side = nh[2] + 0.012 * Hm
    fd, br, vd, vh = st[1]
    neck_f = neckline(nh[1], z_side, fd * k, br * k, v_depth=vd * k, v_half=vh)
    tmask = region_top(bd, sleeves, top_hem - 0.05 * k, z_side + 0.05 * k)
    cuts = [dict(field=neck_f, where=dict(xmax=0.14 * k, zmin=z_side - 0.3 * k, not_bones=ARMS))]

    def neck_snug(P):  # the neckline hugs the neck instead of standing off it
        r = np.hypot(P[:, 0], P[:, 1] - nh[1])
        return sstep(-0.07 * k, -0.02 * k, neck_f(P)) * sstep(0.15 * k, 0.10 * k, r)
    for side in ("Left", "Right"):
        if sleeves == "none":
            continue
        bone, t = {"short": (side + "Arm", 0.55), "cap": (side + "Arm", 0.22),
                   "long": (side + "ForeArm", 0.86 if tt == "jacket" else 0.92)}[sleeves]
        h, tl = bd.j(bone), bd.j(bone, "t")
        cuts.append(dict(co=h + t * (tl - h), no=tl - h,
                         where=dict(bones=[side + "Arm", side + "ForeArm", side + "Hand"], share=0.45)))
    cuts.append(dict(co=(0.0, 0.0, top_hem), no=(0.0, 0.0, -1.0),
                     where=dict(xmax=0.32 * k, zmax=top_hem + 0.12 * k, not_bones=ARMS)))
    if sleeves == "none":
        for side, sg in (("Left", 1), ("Right", -1)):
            sh = bd.j(side + "Arm")

            def armhole(P, sh=sh, sg=sg):  # an oval around the arm's root, plus the arm itself
                c = sh + np.array([sg * 0.01 * k, 0.0, -0.05 * k])
                r = np.array([0.07, 0.085, 0.11]) * k
                inside = (1 - (((P - c) / r) ** 2).sum(1)) * 0.035 * k
                beyond = sg * (P[:, 0] - sh[0]) - 0.02 * k
                return np.maximum(inside, beyond)
            cuts.append(dict(field=armhole, where=dict(xsign=sg, zmin=sh[2] - 0.3 * k)))
    gold = top.get("material") == "gold"
    timg = paint_top(bd, top, name)
    tmat = material("%s_top" % name, image=timg, rough=0.38 if gold else 0.85, metal=GOLD_METAL if gold else 0.0)
    off = st[2] * k * (0.6 if under else 1.0) + (0.006 * k if over else 0.0)
    tobj, tedges = garment(bd, tmask, "%s.%s" % (name, tt), off, tmat, rig, fill=st[3], smooth=5, cuts=cuts,
                           snug=(neck_snug, (0.003 if under else 0.004 + (0.004 if over else 0.0)) * k),
                           bust=getattr(bd, "female", False))
    keep = np.ones(len(bd.co), bool)
    for c in cuts:
        keep &= cut_keep(bd, c)
    covered = tmask & keep
    base = hexc(top["color"])
    rib = material("%s_rib" % name, base * 0.9, rough=0.38 if gold else 0.9, metal=GOLD_METAL if gold else 0.0)
    hem_m = material("%s_hem" % name, base * 0.94, rough=0.38 if gold else 0.85, metal=GOLD_METAL if gold else 0.0)
    trims = top.get("trim")
    trim_m = [material("%s_trim%d" % (name, i), hexc(c), rough=0.7) for i, c in enumerate(trims)] if trims else []
    thick = st[4]
    for e in tedges:
        P = e["P"]
        zc, xc = P[:, 2].mean(), np.abs(P[:, 0]).mean()
        is_neck = zc > bd.j("Spine2")[2] - (0.12 * k if vd > 0.1 else 0.0) and xc < 0.09 * k
        is_hem = zc < bd.j("Spine")[2] and P[:, 0].min() < 0 < P[:, 0].max()
        if is_neck:
            if tt == "buttonup":
                strip("%s.collar" % name, e, scaled(COLLAR, k), material("%s_collar" % name, base * 0.97, rough=0.85), rig)
            elif tt == "polo":
                strip("%s.collar" % name, e, scaled(POLO_COLLAR, k), trim_m[0] if trim_m else hem_m, rig)
            elif tt == "quarterzip":
                strip("%s.collar" % name, e, scaled(STAND, k), rib, rig)
            elif tt == "jacket":
                strip("%s.lapels" % name, e, scaled(LAPEL, k), hem_m, rig)
            elif tt == "vest":
                strip("%s.edge" % name, e, scaled(HEM, k), hem_m, rig)
            elif trim_m:
                strip("%s.collar" % name, e, scaled(RIB_NECK, k), trim_m[0], rig)
                if len(trim_m) > 1 and trims[1] != trims[0]:
                    strip("%s.collar_stripe" % name, e, scaled([(0.004, 0.0029), (0.008, 0.0029)], k), trim_m[1], rig)
            else:
                strip("%s.collar" % name, e, scaled(RIB_NECK_THICK if thick else RIB_NECK, k), rib, rig)
            if tt == "hoodie":
                back = sub_edge(e, e["P"][:, 1] > nh[1] - 0.01 * k)
                if back is not None:
                    strip("%s.hood" % name, back, scaled(HOOD, k), material("%s_hood" % name, base * 0.85, rough=0.9), rig)
                front_z = float(P[np.argmin(P[:, 1]), 2])
                for sg in (1, -1):
                    x0 = sg * 0.035 * k
                    y0 = float(P[np.argmin(np.abs(P[:, 0] - x0) + (P[:, 1] > nh[1]) * 9), 1]) - 0.006 * k
                    tube("%s.string" % name, [Vector((x0, y0, front_z - 0.005)), Vector((x0 * 1.1, y0 - 0.004, front_z - 0.13 * k))],
                         0.0028 * k, material("%s_string" % name, hexc("#f2f2f2"), rough=0.8), rig, "Spine2", seg=6)
        elif is_hem:
            strip("%s.hem" % name, e, scaled(RIB_WIDE if thick else HEM, k), rib if thick else hem_m, rig)
        else:  # sleeves and armholes
            if thick and sleeves == "long":
                strip("%s.cuff" % name, e, scaled(CUFF, k), rib, rig)
            else:
                strip("%s.sleeve_hem" % name, e, scaled(HEM, k), trim_m[0] if trim_m else hem_m, rig)
    return covered


def ghostify(rig):
    """The ghost skin: every material pale, glowing blue and see-through."""
    done = set()
    for o in rig.children_recursive:
        if o.type != "MESH":
            continue
        for slot in o.material_slots:
            m = slot.material
            if m is None or m.name in done or not m.use_nodes:
                continue
            done.add(m.name)
            nt = m.node_tree
            bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
            if bsdf is None:
                continue
            tint = (0.55, 0.85, 1.0, 1.0)
            src = bsdf.inputs["Base Color"].links[0].from_socket if bsdf.inputs["Base Color"].links else None
            if src is not None:
                try:  # Blender 4/5 "Mix" node in color mode; the glTF exporter reads texture x color
                    mul = nt.nodes.new("ShaderNodeMix")
                    mul.data_type = "RGBA"
                    mul.blend_type = "MULTIPLY"
                    mul.inputs[0].default_value = 1.0
                    mul.inputs[7].default_value = tint
                    nt.links.new(src, mul.inputs[6])
                    nt.links.new(mul.outputs[2], bsdf.inputs["Base Color"])
                except Exception:
                    mul = nt.nodes.new("ShaderNodeMixRGB")
                    mul.blend_type = "MULTIPLY"
                    mul.inputs[0].default_value = 1.0
                    mul.inputs[2].default_value = tint
                    nt.links.new(src, mul.inputs[1])
                    nt.links.new(mul.outputs[0], bsdf.inputs["Base Color"])
            else:
                bsdf.inputs["Base Color"].default_value = tint
            for nm in ("Emission Color", "Emission"):
                if nm in bsdf.inputs:
                    bsdf.inputs[nm].default_value = (0.35, 0.75, 1.0, 1.0)
            if "Emission Strength" in bsdf.inputs:
                bsdf.inputs["Emission Strength"].default_value = 0.8
            if not bsdf.inputs["Alpha"].links:
                bsdf.inputs["Alpha"].default_value = 0.6
            # Front faces only: a see-through, double-sided surface shows its own back through
            # the front and looks inside out (the glTF export makes it single-sided too).
            # Hair, brows and lashes are thin cards, so they keep both sides.
            cards = any(s in m.name.lower() for s in ("hair", "brow", "lash"))
            for attr, val in (("blend_method", "BLEND"), ("surface_render_method", "BLENDED"),
                              ("use_backface_culling", not cards)):
                try:
                    setattr(m, attr, val)
                except Exception:
                    pass
