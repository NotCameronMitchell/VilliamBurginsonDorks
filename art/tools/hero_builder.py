"""
Builds a detailed, stylized hero in Blender from hero_looks.py, with no 3D AI service:

- a smooth body lofted from cross-sections (torso, neck, arms, hands, legs, shoes), with cuffs
  and hems where clothes end
- a head with an anime-style face painted on: from a Gemini portrait of the person when
  art/heroes/<id>/face.jpg exists (hero_looks "face_image"), otherwise drawn from scratch
- hair built from a cap plus locks, in the person's style and color
- clothes with patterns, collars, prints and numbers, and accessories (cap, glasses, watch)
- a Mixamo-named skeleton, with every vertex's weights set from where its part sits

hero_assemble.py calls build(model_id), then retargets the Kimodo motions and exports it.
"""

import math
import os
import tempfile

import bpy
import numpy as np
from mathutils import Vector

import hero_looks as L
import hero_specs as H

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
PFX = "mixamorig:"
TEXDIR = tempfile.mkdtemp(prefix="vbd_tex_")


# =========================================================================== small helpers
def hexc(h):
    return np.array([int(h[i:i + 2], 16) / 255.0 for i in (1, 3, 5)])


def lin(c):
    c = np.asarray(c, dtype=float)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def sstep(e0, e1, x):
    if e1 == e0:
        return 1.0 if x >= e1 else 0.0
    t = min(1.0, max(0.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


def lerp_table(table, x):
    """Piecewise-linear lookup in [(x, value...)] (sorted by x); returns a tuple."""
    if x <= table[0][0]:
        return table[0][1:]
    for a, b in zip(table, table[1:]):
        if x <= b[0]:
            t = (x - a[0]) / (b[0] - a[0])
            return tuple(av + (bv - av) * t for av, bv in zip(a[1:], b[1:]))
    return table[-1][1:]


def frame_for(t, up):
    """Right-handed frame (x, y) around tangent t, with y as close to `up` as possible."""
    t = t.normalized()
    y = up - t * up.dot(t)
    if y.length < 1e-6:
        y = Vector((1, 0, 0)) - t * t.x
    y.normalize()
    return y.cross(t), y


def wnorm(w):
    s = sum(w.values())
    return {k: v / s for k, v in w.items() if v > 1e-5} if s > 0 else w


def chain_w(s, segs, blend):
    """Weights along a chain of bones: segs = [(bone, s0, s1)], blended over +-blend at joints."""
    w = {}
    n = len(segs)
    for j, (bone, s0, s1) in enumerate(segs):
        lo = sstep(s0 - blend, s0 + blend, s) if j > 0 else 1.0
        hi = 1.0 - sstep(s1 - blend, s1 + blend, s) if j < n - 1 else 1.0
        if lo * hi > 1e-5:
            w[bone] = w.get(bone, 0.0) + lo * hi
    return wnorm(w)


def mix_w(a, b, t):
    out = {k: v * (1 - t) for k, v in a.items()}
    for k, v in b.items():
        out[k] = out.get(k, 0.0) + v * t
    return wnorm(out)


# =========================================================================== mesh data
class MeshData:
    """Vertices with bone weights, and faces with a material key and per-corner UVs."""

    def __init__(self):
        self.co, self.w, self.faces = [], [], []

    def v(self, co, w):
        self.co.append(Vector(co))
        self.w.append(w)
        return len(self.co) - 1

    def f(self, idx, mat, uv):
        self.faces.append((tuple(idx), mat, list(uv)))


class Ring:
    def __init__(self, c, x, y, rx, yf, yb=None, sq=2.0):
        self.c, self.x, self.y = Vector(c), Vector(x), Vector(y)
        self.rx, self.yf = rx, yf
        self.yb = yf if yb is None else yb
        self.sq = sq

    def point(self, th):
        c, s = math.cos(th), math.sin(th)
        e = 2.0 / self.sq
        px = math.copysign(abs(c) ** e, c) * self.rx
        py = math.copysign(abs(s) ** e, s) * (self.yf if s < 0 else self.yb)
        return self.c + self.x * px + self.y * py


def rings_along(points, radii, up, sq=2.0):
    """Rings for a path of points; radii = [(rx, yf, yb)]. Front (-y) is the yf side."""
    out = []
    for i, p in enumerate(points):
        a = points[max(0, i - 1)]
        b = points[min(len(points) - 1, i + 1)]
        x, y = frame_for(Vector(b) - Vector(a), up)
        rx, yf, yb = radii[i]
        out.append(Ring(p, x, y, rx, yf, yb, sq))
    return out


def loft(md, rings, seg, mat, wfn, v_scale=1.0, cap0=False, cap1=False, tip=0.0):
    """Skins rings into a tube. mat: key or fn(i, k). wfn(i, co) -> weights.
    UVs: u around (front center at u=0.75), v along the path * v_scale."""
    idx, vs = [], [0.0]
    for i in range(1, len(rings)):
        vs.append(vs[-1] + (rings[i].c - rings[i - 1].c).length)
    for i, r in enumerate(rings):
        row = []
        for k in range(seg):
            co = r.point(2 * math.pi * k / seg)
            row.append(md.v(co, wfn(i, co)))
        idx.append(row)
    for i in range(len(rings) - 1):
        for k in range(seg):
            k2 = (k + 1) % seg
            u0, u1 = k / seg, (k + 1) / seg
            v0, v1 = vs[i] * v_scale, vs[i + 1] * v_scale
            m = mat(i, k) if callable(mat) else mat
            md.f((idx[i][k], idx[i][k2], idx[i + 1][k2], idx[i + 1][k]), m,
                 [(u0, v0), (u1, v0), (u1, v1), (u0, v1)])
    for end, (cond, sign) in enumerate(((cap0, -1), (cap1, 1))):
        if not cond:
            continue
        i = 0 if end == 0 else len(rings) - 1
        r = rings[i]
        t = r.x.cross(r.y)
        c = r.c + t * sign * tip
        ci = md.v(c, wfn(i, c))
        m = mat(min(i, len(rings) - 2), 0) if callable(mat) else mat
        vv = vs[i] * v_scale
        for k in range(seg):
            k2 = (k + 1) % seg
            tri = (idx[i][k], idx[i][k2], ci) if sign > 0 else (idx[i][k2], idx[i][k], ci)
            md.f(tri, m, [(k / seg, vv), ((k + 1) / seg, vv), ((k + 0.5) / seg, vv + 0.01)])
    return idx


def loop_loft(md, path, rx, ry, seg, mat, wfn, up=Vector((0, 0, 1)), sq=2.0):
    """A tube around a closed path (collars, cuffs, frames, watch bands)."""
    n = len(path)
    rings = []
    for i in range(n):
        t = Vector(path[(i + 1) % n]) - Vector(path[i - 1])
        x, y = frame_for(t, up)
        rings.append(Ring(path[i], x, y, rx, ry, ry, sq))
    idx = []
    for r in rings:
        idx.append([md.v(r.point(2 * math.pi * k / seg), wfn(0, r.c)) for k in range(seg)])
    for i in range(n):
        i2 = (i + 1) % n
        for k in range(seg):
            k2 = (k + 1) % seg
            md.f((idx[i][k], idx[i][k2], idx[i2][k2], idx[i2][k]), mat,
                 [(k / seg, i / n), ((k + 1) / seg, i / n), ((k + 1) / seg, (i + 1) / n), (k / seg, (i + 1) / n)])


# =========================================================================== textures
class Canvas:
    """A float sRGB image to paint on (row 0 is the bottom, like Blender images)."""

    def __init__(self, w, h, color):
        self.w, self.h = w, h
        self.a = np.empty((h, w, 3))
        self.a[:] = color

    def _win(self, x0, x1, y0, y1):
        x0, x1 = max(0, int(x0)), min(self.w, int(math.ceil(x1)))
        y0, y1 = max(0, int(y0)), min(self.h, int(math.ceil(y1)))
        if x0 >= x1 or y0 >= y1:
            return None
        yy, xx = np.mgrid[y0:y1, x0:x1] + 0.5
        return (slice(y0, y1), slice(x0, x1)), xx, yy

    def _blend(self, sl, alpha, color):
        a = np.clip(alpha, 0, 1)[..., None]
        self.a[sl] = self.a[sl] * (1 - a) + np.asarray(color) * a

    def ellipse(self, cx, cy, rx, ry, color, alpha=1.0, soft=1.0, angle=0.0, grad=None):
        pad = max(rx, ry) + 3
        win = self._win(cx - pad, cx + pad, cy - pad, cy + pad)
        if not win:
            return
        sl, xx, yy = win
        ca, sa = math.cos(angle), math.sin(angle)
        dx, dy = xx - cx, yy - cy
        u, v = (dx * ca + dy * sa) / rx, (-dx * sa + dy * ca) / ry
        d = np.sqrt(u * u + v * v)
        cov = np.clip(0.5 - (d - 1) * min(rx, ry) / soft, 0, 1) * alpha
        col = color
        if grad is not None:  # vertical gradient: (top color, bottom color)
            t = np.clip((v + 1) / 2, 0, 1)[..., None]
            col = np.asarray(grad[1]) * (1 - t) + np.asarray(grad[0]) * t
            a = cov[..., None]
            self.a[sl] = self.a[sl] * (1 - a) + col * a
            return
        self._blend(sl, cov, col)

    def line(self, pts, width, color, alpha=1.0, soft=1.0, taper=False):
        pts = [np.array(p, dtype=float) for p in pts]
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        pad = width + 3
        win = self._win(min(xs) - pad, max(xs) + pad, min(ys) - pad, max(ys) + pad)
        if not win:
            return
        sl, xx, yy = win
        best = np.full(xx.shape, 1e9)
        wid = np.full(xx.shape, width / 2)
        n = len(pts) - 1
        for i in range(n):
            a, b = pts[i], pts[i + 1]
            ab = b - a
            L2 = max(1e-9, ab.dot(ab))
            t = np.clip(((xx - a[0]) * ab[0] + (yy - a[1]) * ab[1]) / L2, 0, 1)
            d = np.hypot(xx - (a[0] + t * ab[0]), yy - (a[1] + t * ab[1]))
            closer = d < best
            best = np.where(closer, d, best)
            if taper:
                g = (i + t) / n  # 0..1 along the line: thick in the middle, thin at the ends
                wid = np.where(closer, width / 2 * (0.25 + 0.75 * np.sin(np.pi * g)), wid)
        cov = np.clip(0.5 - (best - wid) / soft, 0, 1) * alpha
        self._blend(sl, cov, color)

    def rect(self, x0, y0, x1, y1, color, alpha=1.0):
        win = self._win(x0, x1, y0, y1)
        if win:
            self._blend(win[0], np.full(win[1].shape, alpha), color)

    def noise(self, amount, scale=1.0, seed=1):
        rng = np.random.default_rng(seed)
        n = rng.standard_normal((self.h, self.w, 1)) * amount
        self.a = np.clip(self.a * (1 + n * scale), 0, 1)

    def image(self, name):
        h, w = self.h, self.w
        rgba = np.concatenate([np.clip(self.a, 0, 1), np.ones((h, w, 1))], axis=2).astype(np.float32)
        img = bpy.data.images.new(name, w, h, alpha=False)
        img.pixels.foreach_set(rgba.ravel())
        path = os.path.join(TEXDIR, name + ".png")
        img.filepath_raw = path
        img.file_format = "PNG"
        img.save()
        return img


SEGS = {  # 7-segment digits: a b c d e f g
    "0": "abcdef", "1": "bc", "2": "abged", "3": "abgcd", "4": "fgbc", "5": "afgcd",
    "6": "afgedc", "7": "abc", "8": "abcdefg", "9": "abcfgd",
}


def draw_digits(cv, text, cx, cy, hgt, color):
    wd, th = hgt * 0.55, hgt * 0.14
    gap = wd * 0.35
    total = len(text) * wd + (len(text) - 1) * gap
    x = cx - total / 2
    for ch in text:
        segs = SEGS.get(ch, "")
        x0, x1, y0, y1, ym = x, x + wd, cy - hgt / 2, cy + hgt / 2, cy
        boxes = {"a": (x0, y1 - th, x1, y1), "g": (x0, ym - th / 2, x1, ym + th / 2), "d": (x0, y0, x1, y0 + th),
                 "f": (x0, ym, x0 + th, y1), "b": (x1 - th, ym, x1, y1), "e": (x0, y0, x0 + th, ym),
                 "c": (x1 - th, y0, x1, ym)}
        for s in segs:
            cv.rect(*boxes[s], color)
        x += wd + gap


# =========================================================================== the hero
class Hero:
    def __init__(self, model_id):
        self.id = model_id
        self.look = L.look(model_id)
        self.H = H.spec(model_id)["height"]
        lk = self.look
        self.f = lk.get("sex") == "f"
        self.bulk = lk.get("build", 1.0)
        self.muscle = bool(lk.get("muscle"))
        self.md = MeshData()
        self.mats = {}
        self.skeleton()

    # ------------------------------------------------------------------ proportions
    def skeleton(self):
        Hm, lk = self.H, self.look
        heads = lk.get("heads", 6.0)
        self.h = h = Hm / heads
        self.chin = Hm - h
        self.neck_base = self.chin - 0.034 * Hm
        self.sh_z = self.neck_base - 0.016 * Hm
        lf = 0.50 - (6.2 - heads) * 0.022
        self.hip_z = lf * Hm
        self.crotch = self.hip_z - 0.022 * Hm
        self.knee_z = 0.53 * self.hip_z
        self.ankle_z = 0.095 * self.hip_z
        b = self.bulk
        shoulder_mul = 1.32 if self.muscle else 1.0
        self.sh_x = (0.092 if self.f else 0.104) * Hm * (0.6 + 0.4 * b) * shoulder_mul
        self.hip_x = (0.056 if self.f else 0.052) * Hm * (0.7 + 0.3 * b)
        arm_scale = (heads / 6.2) ** 0.25
        self.l_up, self.l_fore, self.l_hand = 0.172 * Hm * arm_scale, 0.148 * Hm * arm_scale, 0.088 * Hm * arm_scale
        ang = math.radians(47)
        self.arm_dir = {s: Vector((sg * math.cos(ang), 0.04, -math.sin(ang))).normalized()
                        for s, sg in (("Left", 1), ("Right", -1))}
        self.yc = -0.012 * Hm  # head sits a little forward
        self.waist_z = self.hip_z + 0.43 * (self.sh_z - self.hip_z) * 0.62
        J = {}
        z_sp = self.hip_z + 0.16 * (self.sh_z - self.hip_z)
        z_sp1 = self.hip_z + 0.42 * (self.sh_z - self.hip_z)
        z_sp2 = self.hip_z + 0.66 * (self.sh_z - self.hip_z)
        self.z_sp, self.z_sp1, self.z_sp2 = z_sp, z_sp1, z_sp2
        J["Hips"] = (Vector((0, 0, self.hip_z)), Vector((0, 0, z_sp)))
        J["Spine"] = (Vector((0, 0, z_sp)), Vector((0, 0, z_sp1)))
        J["Spine1"] = (Vector((0, 0, z_sp1)), Vector((0, 0, z_sp2)))
        J["Spine2"] = (Vector((0, 0, z_sp2)), Vector((0, 0, self.neck_base)))
        J["Neck"] = (Vector((0, 0, self.neck_base)), Vector((0, self.yc * 0.6, self.chin + 0.12 * h)))
        J["Head"] = (Vector((0, self.yc * 0.6, self.chin + 0.12 * h)), Vector((0, self.yc, Hm)))
        self.arm = {}
        for s, sg in (("Left", 1), ("Right", -1)):
            d = self.arm_dir[s]
            sh = Vector((sg * self.sh_x, 0.0, self.sh_z))
            el = sh + d * self.l_up
            wr = el + d * self.l_fore
            tip = wr + d * self.l_hand
            self.arm[s] = (sh, el, wr, tip)
            J[s + "Shoulder"] = (Vector((sg * 0.022 * Hm, 0, self.sh_z + 0.004 * Hm)), sh)
            J[s + "Arm"] = (sh, el)
            J[s + "ForeArm"] = (el, wr)
            J[s + "Hand"] = (wr, tip)
            hip = Vector((sg * self.hip_x, 0.0, self.hip_z))
            knee = Vector((sg * self.hip_x * 0.95, -0.006 * Hm, self.knee_z))
            ankle = Vector((sg * self.hip_x * 0.92, 0.004 * Hm, self.ankle_z))
            ball = Vector((ankle.x, -0.075 * Hm, 0.018 * Hm))
            toe = Vector((ankle.x, -0.115 * Hm, 0.018 * Hm))
            J[s + "UpLeg"] = (hip, knee)
            J[s + "Leg"] = (knee, ankle)
            J[s + "Foot"] = (ankle, ball)
            J[s + "ToeBase"] = (ball, toe)
        self.J = J

    # ------------------------------------------------------------------ materials
    def mat(self, key, color=None, image=None, rough=0.75, metal=0.0):
        if key in self.mats:
            return key
        m = bpy.data.materials.new("%s_%s" % (self.id, key))
        try:
            m.use_nodes = True
        except Exception:
            pass
        nt = m.node_tree
        bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
        base = color if color is not None else (0.8, 0.8, 0.8)
        if image is not None:
            tex = nt.nodes.new("ShaderNodeTexImage")
            tex.image = image
            nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
            base = np.asarray(image.pixels[:4][:3]) if color is None else color
        else:
            bsdf.inputs["Base Color"].default_value = (*lin(base), 1.0)
        bsdf.inputs["Roughness"].default_value = rough
        bsdf.inputs["Metallic"].default_value = metal
        m.diffuse_color = (*lin(base), 1.0)
        self.mats[key] = m
        return key

    # ------------------------------------------------------------------ body
    def torso(self):
        Hm, b, f = self.H, self.bulk, self.f
        mus = self.muscle
        z0, z1 = self.crotch, self.neck_base
        if f:
            prof = [(0.00, .068, .054, .064), (0.10, .098, .066, .084), (0.25, .094, .064, .076),
                    (0.42, .074, .058, .056), (0.58, .082, .080, .056), (0.72, .088, .084, .058),
                    (0.86, .093, .060, .056), (0.95, .080, .046, .048), (1.00, .046, .036, .038)]
        else:
            prof = [(0.00, .070, .055, .064), (0.10, .093, .064, .076), (0.25, .088, .062, .068),
                    (0.42, .084, .062, .059), (0.58, .094, .071, .060), (0.72, .103, .075, .062),
                    (0.86, .108, .063, .060), (0.95, .090, .048, .050), (1.00, .050, .040, .042)]
        rings = []
        self.torso_rings = []
        for t, w, yf, yb in prof:
            z = z0 + (z1 - z0) * t
            wm = (0.65 + 0.35 * b)
            if mus and t > 0.5:
                wm *= 1.0 + 0.30 * sstep(0.5, 0.86, t)
            dm = 0.55 + 0.45 * b
            if mus and t > 0.5:
                dm *= 1.0 + 0.22 * sstep(0.5, 0.8, t)
            rings.append(Ring((0, 0, z), (1, 0, 0), (0, 1, 0), w * Hm * wm, yf * Hm * dm, yb * Hm * dm, 2.6))
            self.torso_rings.append((z, w * Hm * wm))
        self.waist_z = z0 + (z1 - z0) * 0.40
        top = self.look["top"]["type"]
        bottom_key, top_key = "bottom", "top"
        hem_t = 0.38 if top not in ("dress",) else 0.30

        def mat(i, k):
            return top_key if prof[i][0] >= hem_t - 1e-6 else bottom_key

        def wfn(i, co):
            w = chain_w(co.z, [(PFX + "Hips", -9, self.z_sp), (PFX + "Spine", self.z_sp, self.z_sp1),
                               (PFX + "Spine1", self.z_sp1, self.z_sp2), (PFX + "Spine2", self.z_sp2, 99)],
                        0.03 * Hm)
            wmax = rings[i].rx
            side = "Left" if co.x > 0 else "Right"
            ws = sstep(0.55 * wmax, 0.98 * wmax, abs(co.x)) * sstep(self.sh_z - 0.06 * Hm, self.sh_z, co.z) * 0.75
            if ws > 0:
                w = mix_w(w, {PFX + side + "Shoulder": 1.0}, ws)
            return w

        loft(self.md, rings, 16, mat, wfn, v_scale=1.0 / (z1 - z0), cap0=True, cap1=True, tip=0.01 * Hm)
        # Untucked tops get a hem lip at the waist; skirts and dresses a waist seam.
        if top in ("tee", "buttonup", "sweatshirt", "sweater", "jersey", "tank"):
            zh = z0 + (z1 - z0) * hem_t
            w = lerp_table([(p[0], p[1], p[2], p[3]) for p in prof], hem_t)
            wm = (0.65 + 0.35 * b)
            dm = 0.55 + 0.45 * b
            path = [Vector((math.cos(a) * w[0] * Hm * wm * 1.035, math.sin(a) * (w[1] if math.sin(a) < 0 else w[2]) * Hm * dm * 1.04, zh))
                    for a in np.linspace(0, 2 * math.pi, 24, endpoint=False)]
            band = "top_rib" if top in ("sweatshirt", "sweater") else "top"
            loop_loft(self.md, path, 0.006 * Hm, 0.012 * Hm, 6, band,
                      lambda i, co: chain_w(co.z, [(PFX + "Hips", -9, self.z_sp), (PFX + "Spine", self.z_sp, 99)], 0.03 * Hm))

    def neck(self):
        Hm = self.H
        r = (0.026 if self.f else 0.030) * Hm * (0.8 + 0.2 * self.bulk) * (1.25 if self.muscle else 1.0)
        pts = [Vector((0, 0, self.neck_base - 0.03 * Hm)), Vector((0, self.yc * 0.3, self.neck_base + 0.01 * Hm)),
               Vector((0, self.yc * 0.6, self.chin + 0.02 * Hm)), Vector((0, self.yc * 0.7, self.chin + 0.10 * self.h))]
        rad = [(r * 1.15, r * 1.1, r * 1.1), (r, r, r), (r * 0.95, r * 0.95, r * 0.95), (r * 0.9, r * 0.9, r * 0.9)]
        rings = rings_along(pts, rad, Vector((0, 1, 0)))

        def wfn(i, co):
            return chain_w(co.z, [(PFX + "Neck", -9, self.chin), (PFX + "Head", self.chin, 99)], 0.02 * Hm)

        loft(self.md, rings, 10, "skin", wfn, v_scale=2.0)

    def arm_part(self, side):
        Hm = self.H
        sg = 1 if side == "Left" else -1
        sh, el, wr, tip = self.arm[side]
        d = self.arm_dir[side]
        fm = 0.86 if self.f else 1.0
        m = fm * (0.75 + 0.25 * self.bulk)
        mus = 1.55 if self.muscle else 1.0
        # (s along the arm from the shoulder joint, radius)
        lu, lf = self.l_up, self.l_fore
        prof = [(-0.035 * Hm, .038 * mus), (0.0, .038 * mus), (0.04 * Hm, .036 * mus), (0.45 * lu, .032 * mus),
                (lu - 0.02 * Hm, .027 * (1 + (mus - 1) * 0.5)), (lu, .025 * (1 + (mus - 1) * 0.4)),
                (lu + 0.035 * Hm, .028 * (1 + (mus - 1) * 0.6)), (lu + 0.6 * lf, .024), (lu + lf - 0.005 * Hm, .019)]
        top = self.look["top"]
        sleeve = top.get("sleeves", "short")
        s_end = {"short": 0.55 * lu, "long": lu + lf - 0.012 * Hm, "none": -1.0}[sleeve]
        if top["type"] == "dress":
            s_end = 0.28 * lu
        pts, rad, mats = [], [], []
        for s, r in prof:
            pts.append(sh + d * s)
            rr = r * Hm * m
            rad.append((rr, rr, rr))
        # Sleeve hem: a lip where the sleeve ends.
        if s_end > 0:
            ins = []
            for s, mul in ((s_end - 0.008 * Hm, 1.0), (s_end - 0.002 * Hm, 1.13), (s_end + 0.004 * Hm, 1.08), (s_end + 0.008 * Hm, 0.97)):
                ins.append((s, mul))
            merged = sorted([(s, r * Hm * m, "x") for s, r in prof] + [(s, None, mul) for s, mul in ins], key=lambda e: e[0])
            pts, rad = [], []
            ps = [s for s, _ in prof]
            rs = [r * Hm * m for _, r in prof]
            for s, r, mul in merged:
                if r is None:
                    rr = float(np.interp(s, ps, rs)) * mul
                else:
                    rr = r
                pts.append(sh + d * s)
                rad.append((rr, rr, rr))
            svals = [e[0] for e in merged]
        else:
            svals = [s for s, _ in prof]
        hem_key = "trim0" if top["type"] == "jersey" else ("top_rib" if top["type"] in ("sweatshirt", "sweater") else "sleeve")

        def mat(i, k):
            s_mid = 0.5 * (svals[i] + svals[i + 1])
            if s_end > 0 and s_end - 0.006 * Hm < s_mid < s_end + 0.006 * Hm:
                return hem_key
            return "sleeve" if s_mid < s_end else "skin"

        def wfn(i, co):
            s = (co - sh).dot(d)
            return chain_w(s, [(PFX + side + "Shoulder", -9, 0.0), (PFX + side + "Arm", 0.0, lu),
                               (PFX + side + "ForeArm", lu, 99)], 0.03 * Hm)

        rings = rings_along(pts, rad, Vector((0, 1, 0)))
        loft(self.md, rings, 10, mat, wfn, v_scale=3.0, cap0=True, cap1=True, tip=0.004 * Hm)
        self.hand(side, wr, d)

    def hand(self, side, wr, d):
        Hm = self.H
        sc = (0.88 if self.f else 1.0) * (1.15 if self.muscle else 1.0)
        x, y = frame_for(d, Vector((0, 1, 0)))
        # Palm then a mitten of fingers; flat side faces the thigh.
        pts = [wr - d * 0.004 * Hm, wr + d * 0.012 * Hm, wr + d * 0.040 * Hm, wr + d * 0.056 * Hm,
               wr + d * 0.078 * Hm, wr + d * 0.092 * Hm]
        rad = [(0.012, 0.016, 0.016), (0.011, 0.020, 0.020), (0.011, 0.022, 0.022), (0.010, 0.021, 0.021),
               (0.008, 0.017, 0.017), (0.006, 0.012, 0.012)]
        rad = [(a * Hm * sc, b_ * Hm * sc, c * Hm * sc) for a, b_, c in rad]
        rings = rings_along(pts, rad, Vector((0, 1, 0)), sq=2.4)
        wh = {PFX + side + "Hand": 1.0}
        loft(self.md, rings, 10, "skin", lambda i, co: wh, cap1=True, tip=0.004 * Hm)
        # Thumb, along the front edge.
        base = wr + d * 0.016 * Hm - y * 0.016 * Hm * sc
        tdir = (d * 0.55 - y * 0.55 - x * 0.25).normalized()
        tp = [base, base + tdir * 0.018 * Hm * sc, base + tdir * 0.034 * Hm * sc]
        tr = [(0.0085, 0.0085, 0.0085), (0.0075, 0.0075, 0.0075), (0.0060, 0.0060, 0.0060)]
        tr = [(a * Hm * sc, b_ * Hm * sc, c * Hm * sc) for a, b_, c in tr]
        loft(self.md, rings_along(tp, tr, Vector((0, 0, 1))), 8, "skin", lambda i, co: wh, cap1=True, tip=0.004 * Hm)

    def leg_part(self, side):
        Hm = self.H
        hip, knee = self.J[side + "UpLeg"]
        _, ankle = self.J[side + "Leg"]
        L1, L2 = (knee - hip).length, (ankle - knee).length
        fm = 1.04 if self.f else 1.0
        m = fm * (0.75 + 0.25 * self.bulk)
        bt = self.look["bottom"]["type"]
        bag = {"joggers": 1.12, "pants": 1.05, "shorts": 1.07, "leggings": 0.97, "skirt": 1.0}.get(bt, 1.0)
        prof = [(-0.05 * Hm, .060), (0.0, .058), (0.06 * Hm, .053), (0.5 * L1, .047), (L1 - 0.02 * Hm, .037),
                (L1, .035), (L1 + 0.05 * Hm, .039), (L1 + 0.55 * L2, .031), (L1 + L2 - 0.01 * Hm, .024),
                (L1 + L2 + 0.02 * Hm, .023)]
        hem = {"shorts": 0.62 * L1, "skirt": -1.0, "pants": L1 + L2 - 0.015 * Hm, "joggers": L1 + L2 - 0.02 * Hm,
               "leggings": L1 + L2}[bt]
        clothed_mul = bag
        pts, rad, svals = [], [], []

        def point_at(s):
            if s <= L1:
                return hip + (knee - hip).normalized() * s
            return knee + (ankle - knee).normalized() * (s - L1)

        entries = [(s, r) for s, r in prof]
        if bt in ("shorts",):
            entries += [(hem - 0.01 * Hm, None), (hem - 0.002 * Hm, "lip"), (hem + 0.006 * Hm, "in")]
        if bt == "joggers":
            entries += [(hem - 0.05 * Hm, None), (hem - 0.035 * Hm, "cuff")]
        entries.sort(key=lambda e: e[0])
        ps = [s for s, _ in prof]
        rs = [r * Hm * m for _, r in prof]
        for s, r in entries:
            base = float(np.interp(s, ps, rs))
            clothed = s < hem
            mul = clothed_mul if clothed else 1.0
            if r == "lip":
                mul = clothed_mul * 1.10
            elif r == "in":
                mul = 0.98
            elif r == "cuff":
                mul = clothed_mul * 0.92
            pts.append(point_at(s))
            rr = base * mul
            rad.append((rr, rr, rr))
            svals.append(s)

        def mat(i, k):
            s_mid = 0.5 * (svals[i] + svals[i + 1])
            if bt == "skirt":
                return "skin" if s_mid > 0.2 * L1 else "bottom"
            return "bottom" if s_mid < hem else "skin"

        def wfn(i, co):
            s = (co - hip).dot((knee - hip).normalized()) if co.z > knee.z else L1 + (co - knee).dot((ankle - knee).normalized())
            w = chain_w(s, [(PFX + side + "UpLeg", -9, L1), (PFX + side + "Leg", L1, L1 + L2),
                            (PFX + side + "Foot", L1 + L2, 99)], 0.035 * Hm)
            if s < 0.02 * Hm:
                w = mix_w(w, {PFX + "Hips": 1.0}, 0.5 * sstep(0.02 * Hm, -0.04 * Hm, s))
            return w

        rings = rings_along(pts, rad, Vector((0, 1, 0)))
        loft(self.md, rings, 10, mat, wfn, v_scale=3.0, cap0=True, cap1=True, tip=0.004 * Hm)
        self.shoe(side, ankle)

    def shoe(self, side, ankle):
        Hm = self.H
        st = self.look["shoes"]["type"]
        low = st == "flats"
        sc = (0.9 if self.f else 1.0)
        x0 = ankle.x
        # Along the foot, heel (+y) to toe (-y): (y, half width, bottom, top) in Hm units
        prof = [(0.030, .026, .000, .050), (0.020, .032, .000, .062), (-0.010, .035, .000, .060),
                (-0.045, .038, .000, .048), (-0.080, .037, .000, .036), (-0.105, .030, .000, .028),
                (-0.118, .018, .002, .018)]
        if low:
            prof = [(y, w * 0.9, b_, t_ * 0.62) for y, w, b_, t_ in prof]
        pts, rad = [], []
        sole_h = 0.012 * Hm if st == "sneakers" else 0.007 * Hm
        for y, w, b_, t_ in prof:
            zb, zt = b_ * Hm + sole_h, t_ * Hm * sc + sole_h * 0.5
            pts.append(Vector((x0, y * Hm * sc, 0.5 * (zb + zt))))
            rad.append((w * Hm * sc, 0.5 * (zt - zb), 0.5 * (zt - zb)))
        rings = rings_along(pts, rad, Vector((0, 0, 1)), sq=2.6)
        ball_y = self.J[side + "ToeBase"][0].y

        def wfn(i, co):
            t = sstep(ball_y + 0.02 * Hm, ball_y - 0.02 * Hm, co.y)
            return wnorm({PFX + side + "Foot": 1 - t, PFX + side + "ToeBase": t})

        loft(self.md, rings, 12, "shoe", wfn, v_scale=4.0, cap0=True, cap1=True, tip=0.006 * Hm)
        # Sole: a flat slab a bit wider than the shoe.
        sp = [Vector((x0, y * Hm * sc, sole_h * 0.5)) for y, *_ in prof]
        sr = [(w * Hm * sc * 1.06, sole_h * 0.55, sole_h * 0.55) for _, w, *_ in prof]
        loft(self.md, rings_along(sp, sr, Vector((0, 0, 1)), sq=3.0), 12, "sole", wfn, v_scale=4.0,
             cap0=True, cap1=True, tip=0.004 * Hm)

    def skirt(self):
        Hm = self.H
        z0 = self.waist_z
        z1 = self.knee_z - 0.05 * Hm
        tw = [r for z, r in self.torso_rings]
        tz = [z for z, r in self.torso_rings]
        rings = []
        n = 7
        for i in range(n):
            t = i / (n - 1)
            z = z0 + (z1 - z0) * t
            base = float(np.interp(z0, tz, tw))
            w = base * (1.0 + 0.95 * t ** 1.3) + 0.01 * Hm * t
            rings.append(Ring((0, 0.004 * Hm * t, z), (1, 0, 0), (0, -1, 0), w, w * 0.82, w * 0.86, 2.2))

        def wfn(i, co):
            t = sstep(z0, z1, co.z) if z1 < z0 else sstep(z0, z1, co.z)
            t = (z0 - co.z) / max(1e-6, (z0 - z1))
            side = "Left" if co.x > 0 else "Right"
            sidew = sstep(0.0, 0.08 * Hm, abs(co.x))
            return mix_w({PFX + "Hips": 1.0}, {PFX + side + "UpLeg": 1.0}, 0.65 * sstep(0.15, 1.0, t) * sidew)

        # Rings go downward, so swap y to keep faces pointing out.
        loft(self.md, rings, 18, "bottom", wfn, v_scale=2.0)
        # An inner copy, so the skirt is visible from below too.
        inner = [Ring(r.c, r.x, Vector((0, 1, 0)), r.rx * 0.97, r.yb * 0.97, r.yf * 0.97, r.sq) for r in rings]
        loft(self.md, inner, 18, "bottom", wfn, v_scale=2.0)

    # ------------------------------------------------------------------ head
    HEAD_M = [(0.00, .10, .10, .04), (0.06, .20, .20, .13), (0.16, .29, .27, .22), (0.30, .355, .32, .30),
              (0.45, .375, .335, .355), (0.60, .38, .33, .38), (0.74, .36, .30, .37), (0.86, .30, .24, .31),
              (0.95, .19, .15, .20), (0.995, .05, .04, .05)]
    HEAD_F = [(0.00, .09, .09, .04), (0.06, .18, .19, .12), (0.16, .27, .26, .21), (0.30, .345, .315, .30),
              (0.45, .372, .335, .355), (0.60, .38, .33, .38), (0.74, .362, .30, .37), (0.86, .305, .245, .31),
              (0.95, .195, .155, .205), (0.995, .05, .04, .05)]

    def head_prof(self, zf):
        tab = self.HEAD_F if self.f else self.HEAD_M
        w, yf, yb = lerp_table(tab, zf)
        jaw = self.look.get("jaw", 1.0)
        if zf < 0.35:
            w *= 1.0 + (jaw - 1.0) * (1 - zf / 0.35)
        return w * self.h, yf * self.h, yb * self.h

    def head_point(self, phi, zf, out=0.0):
        """Head surface point at angle phi (0 = front, +90 deg = character's left) and height zf."""
        w, yf, yb = self.head_prof(zf)
        c = math.cos(phi)
        x = math.sin(phi) * (w + out)
        y = -(yf + out) * c if c > 0 else -(yb + out) * c
        return Vector((x, self.yc + y, self.chin + zf * self.h))

    def head_normal(self, phi, zf):
        p0 = self.head_point(phi, zf)
        radial = Vector((p0.x, p0.y - self.yc, 0))
        if radial.length < 1e-6:
            return Vector((0, 0, 1))
        radial.normalize()
        up = sstep(0.75, 1.0, zf)
        return (radial * (1 - up) + Vector((0, 0, 1)) * up).normalized()

    def head(self):
        h = self.h
        zfs = [0.0, 0.03, 0.08, 0.16, 0.24, 0.32, 0.40, 0.48, 0.56, 0.64, 0.72, 0.80, 0.87, 0.93, 0.97, 0.995]
        seg = 24
        md = self.md
        idx = []
        wh = {PFX + "Head": 1.0}
        W = self.head_prof(0.6)[0]
        for zf in zfs:
            row = []
            for k in range(seg):
                phi = math.pi * 2 * k / seg  # 0 = front
                row.append(md.v(self.head_point(phi, zf), wh))
            idx.append(row)
        self.face_W = W

        def face_uv(vi):
            co = md.co[vi]
            return (0.5 + co.x / (2 * W), (co.z - self.chin) / h)

        for j in range(len(zfs) - 1):
            for k in range(seg):
                k2 = (k + 1) % seg
                # phi runs counterclockwise seen from above, like the lofts, so this winding faces out.
                q = (idx[j][k], idx[j][k2], idx[j + 1][k2], idx[j + 1][k])
                phim = math.pi * 2 * (k + 0.5) / seg
                front = math.cos(phim) > 0.30 and zfs[j] < 0.80
                if front:
                    md.f(q, "face", [face_uv(v) for v in q])
                else:
                    md.f(q, "skin", [(k / seg, zfs[j]), (k2 / seg, zfs[j]), (k2 / seg, zfs[j + 1]), (k / seg, zfs[j + 1])])
        top = md.v(self.head_point(0, 1.0), wh)
        for k in range(seg):
            k2 = (k + 1) % seg
            md.f((idx[-1][k], idx[-1][k2], top), "skin", [(0, 1), (0, 1), (0, 1)])
        bot = md.v(self.head_point(0, -0.01) + Vector((0, 0.02 * h, 0)), wh)
        for k in range(seg):
            k2 = (k + 1) % seg
            md.f((idx[0][k2], idx[0][k], bot), "skin", [(0, 0), (0, 0), (0, 0)])
        # Ears
        for sg in (1, -1):
            c = self.head_point(sg * math.radians(92), 0.44) + Vector((0, 0.03 * h, 0))
            pts = [c + Vector((0, 0, z * h)) for z in (-0.07, -0.035, 0.0, 0.04, 0.075)]
            rr = [(0.012, 0.025, 0.020), (0.022, 0.045, 0.040), (0.026, 0.052, 0.046), (0.022, 0.045, 0.040),
                  (0.010, 0.022, 0.018)]
            rad = [(a * h, b_ * h, c_ * h) for a, b_, c_ in rr]
            loft(md, rings_along(pts, rad, Vector((0, 1, 0))), 8, "skin", lambda i, co: wh, cap0=True, cap1=True)

    def eye_pos(self, side):
        """Where an eye sits on the face texture (u, v) and in the world."""
        sg = 1 if side == "Left" else -1
        ex = 0.150 * self.h * sg
        ez = 0.43
        return (0.5 + ex / (2 * self.face_W), ez), self.head_point(math.asin(max(-1, min(1, ex / self.head_prof(ez)[0]))), ez)

    # ------------------------------------------------------------------ hair
    HAIRLINES = {
        "short": [(0, .79), (30, .77), (55, .70), (80, .60), (110, .52), (150, .36), (180, .32)],
        "receding": [(0, .845), (15, .86), (32, .905), (52, .80), (80, .62), (110, .52), (150, .36), (180, .32)],
        "full": [(0, .77), (30, .75), (55, .69), (80, .58), (110, .50), (150, .34), (180, .30)],
        "long": [(0, .80), (12, .80), (40, .72), (70, .55), (95, .42), (140, .30), (180, .28)],
        "capped": [(0, .70), (40, .66), (80, .56), (110, .48), (150, .34), (180, .30)],
    }

    def hairline(self, style, phi):
        tab = self.HAIRLINES.get({"quiff": "full", "wavy": "full", "longwavy": "long"}.get(style, style),
                                 self.HAIRLINES["short"])
        return lerp_table(tab, abs(math.degrees((phi + math.pi) % (2 * math.pi) - math.pi)))[0]

    def hair(self):
        hs = self.look["hair"]
        style = hs["style"]
        h = self.h
        md = self.md
        wh = {PFX + "Head": 1.0}
        K, J = 28, 9
        thick0 = {"quiff": 0.035, "wavy": 0.045, "full": 0.05, "long": 0.035, "longwavy": 0.045}.get(style, 0.03) * h
        cols = []
        for k in range(K):
            phi = 2 * math.pi * k / K
            hl = self.hairline(style, phi)
            col = []
            for j in range(J):
                t = j / (J - 1)
                zf = hl + (0.985 - hl) * (1 - (1 - t) ** 1.6)
                out = thick0 * (0.35 + 0.65 * sstep(0.0, 0.5, t)) + 0.012 * h * t
                col.append(md.v(self.head_point(phi, zf, out), wh))
            cols.append(col)
        for k in range(K):
            k2 = (k + 1) % K
            for j in range(J - 1):
                q = (cols[k][j], cols[k2][j], cols[k2][j + 1], cols[k][j + 1])
                md.f(q, "hair", [(k / K, j / J), (k2 / K, j / J), (k2 / K, (j + 1) / J), (k / K, (j + 1) / J)])
        crown = md.v(self.head_point(0, 1.0, thick0 + 0.012 * h), wh)
        for k in range(K):
            md.f((cols[k][-1], cols[(k + 1) % K][-1], crown), "hair", [(0, 1), (0, 1), (0, 1)])
        # Underside of the cap edge, so it isn't paper-thin at the hairline.
        inner = [md.v(self.head_point(2 * math.pi * k / K, self.hairline(style, 2 * math.pi * k / K) + 0.02, -0.005 * h), wh) for k in range(K)]
        for k in range(K):
            k2 = (k + 1) % K
            md.f((cols[k2][0], cols[k][0], inner[k], inner[k2]), "hair", [(0, 0), (0, 0), (0, 0), (0, 0)])
        rng = np.random.default_rng(7)

        def lock(phi, zf, dirv, length, width, thick, bend=None, wave=0.0, waves=2.0, lo_w=None, n=7):
            root = self.head_point(phi, zf, thick0 * 0.6)
            nrm = self.head_normal(phi, zf)
            dirv = Vector(dirv).normalized()
            bend = Vector(bend) if bend is not None else Vector((0, 0, 0))
            side = dirv.cross(nrm)
            side = side.normalized() if side.length > 1e-6 else Vector((1, 0, 0))
            pts, rad = [], []
            for i in range(n):
                t = i / (n - 1)
                p = root + dirv * length * t + bend * length * t * t
                if wave:
                    p += side * math.sin(t * math.pi * waves) * wave * t
                pts.append(p)
                taper = (1 - t) ** 0.75 + 0.06
                rad.append((width * taper, thick * taper, thick * taper))
            rings = rings_along(pts, rad, nrm)
            loft(md, rings, 6, "hair", lo_w or (lambda i, co: wh), v_scale=1.0 / max(1e-6, length), cap1=True,
                 tip=0.004 * h)

        def long_w(i, co):
            t = sstep(self.chin, self.sh_z - 0.10 * self.H, co.z)
            return mix_w(wh, {PFX + "Spine2": 1.0}, 0.7 * (1 - t) if co.z < self.chin else 0.0)

        if style == "quiff":
            for a in np.linspace(-38, 38, 9):
                ph = math.radians(a)
                lock(ph, 0.78, (math.sin(ph) * 0.25, 0.55, 1.0), 0.30 * h, 0.075 * h, 0.035 * h, bend=(0, 0.45, -0.15))
            for a in np.linspace(-60, 60, 7):
                ph = math.radians(a)
                lock(ph, 0.90, (math.sin(ph) * 0.3, 1.0, 0.35), 0.26 * h, 0.08 * h, 0.03 * h, bend=(0, 0.2, -0.35))
        elif style == "wavy":
            for a in np.linspace(-150, 150, 15):
                ph = math.radians(a)
                lock(ph, 0.80 + 0.06 * math.cos(ph), (math.sin(ph) * 0.4, 0.9, 0.45), 0.30 * h, 0.085 * h, 0.035 * h,
                     bend=(0, 0.15, -0.55), wave=0.03 * h, waves=2.5)
            for a in np.linspace(-30, 30, 5):
                ph = math.radians(a)
                lock(ph, 0.80, (math.sin(ph) * 0.3, 0.4, 1.0), 0.22 * h, 0.075 * h, 0.035 * h, bend=(0, 0.5, -0.1))
        elif style in ("short", "receding"):
            zbase = 0.90 if style == "receding" else 0.84
            for a in np.linspace(-45, 45, 7):
                ph = math.radians(a)
                lock(ph, zbase, (math.sin(ph) * 0.4 + 0.15, -0.1, 1.0), 0.13 * h, 0.07 * h, 0.03 * h, bend=(0.1, -0.2, -0.4))
            for a in np.linspace(-120, 120, 9):
                ph = math.radians(a)
                lock(ph, 0.93, (math.sin(ph), 0.6, 0.3), 0.14 * h, 0.08 * h, 0.025 * h, bend=(0, 0.1, -0.5))
        elif style == "full":
            for a in np.linspace(-35, 45, 8):
                ph = math.radians(a)
                lock(ph, 0.80, (0.55, -0.35, 0.55), 0.24 * h, 0.08 * h, 0.04 * h, bend=(0.2, -0.3, -0.55))
            for a in np.linspace(-150, 150, 13):
                ph = math.radians(a)
                lock(ph, 0.86, (math.sin(ph) * 0.5, 0.8, 0.6), 0.26 * h, 0.09 * h, 0.04 * h, bend=(0, 0.1, -0.6))
        elif style == "capped":
            for a in (-100, -80, 80, 100, 140, -140, 180):
                ph = math.radians(a)
                lock(ph, 0.58, (math.sin(ph) * 0.3, 0.2, -1.0), 0.08 * h, 0.07 * h, 0.02 * h)
        elif style in ("long", "longwavy"):
            wavy = style == "longwavy"
            wv = 0.035 * h if wavy else 0.0
            vol = 1.18 if wavy else 1.0
            drop = (self.chin + 0.02 * self.H) - (self.sh_z - 0.20 * self.H)
            # Back curtain: wide locks from the crown down the back.
            for a in np.linspace(105, 255, 9):
                ph = math.radians(a)
                zf = 0.62 + 0.15 * abs(math.cos(ph))
                root = self.head_point(ph, zf, thick0)
                length = (root.z - (self.sh_z - 0.18 * self.H))
                outward = Vector((math.sin(ph) * 0.18, 0.25, 0))
                lock(ph, zf, (outward.x, outward.y, -1.0), length, 0.11 * h * vol, 0.035 * h * vol,
                     bend=(math.sin(ph) * 0.1, 0.12, 0), wave=wv, waves=3.0, lo_w=long_w)
            # Side curtains framing the face, over the shoulders.
            for sg in (1, -1):
                for a, ln in ((68, 1.0), (88, 1.05), (108, 1.0)):
                    ph = math.radians(sg * a)
                    lock(ph, 0.62, (sg * 0.35, -0.12 if a < 90 else 0.05, -1.0), drop * ln, 0.10 * h * vol,
                         0.035 * h * vol, bend=(sg * 0.12, -0.10, 0), wave=wv, waves=3.0, lo_w=long_w)
                ph = math.radians(sg * 18)
                lock(ph, 0.84, (sg * 0.55, -0.35, -0.5), 0.40 * h, 0.09 * h * vol, 0.03 * h, bend=(sg * 0.15, 0, -0.4),
                     wave=wv * 0.6)
            # Top volume with a middle part.
            for sg in (1, -1):
                for a in np.linspace(10, 150, 6):
                    ph = math.radians(sg * a)
                    lock(ph, 0.95, (math.sin(ph) * 0.9, 0.4 * math.copysign(1, -math.cos(ph)) + 0.2, 0.05),
                         0.22 * h, 0.09 * h, 0.03 * h, bend=(0, 0, -0.6))
        del rng

    # ------------------------------------------------------------------ clothes details
    def collar(self):
        top = self.look["top"]
        tp = top["type"]
        Hm = self.H
        z = self.neck_base + 0.004 * Hm
        r0 = (0.033 if not self.f else 0.030) * Hm * (0.85 + 0.15 * self.bulk) * (1.25 if self.muscle else 1.0)
        w = {PFX + "Spine2": 0.5, PFX + "Neck": 0.5}
        if tp in ("tank", "dress"):
            return
        if tp == "jersey":  # V-neck trim in two colors
            for j, (key, off) in enumerate((("trim0", 0.0), ("trim1", 0.006 * Hm))):
                path = []
                for a in np.linspace(0, 2 * math.pi, 28, endpoint=False):
                    front = max(0.0, -math.sin(a))
                    rr = r0 * 1.12 + off
                    path.append(Vector((math.cos(a) * rr, math.sin(a) * rr * 0.9 - front * 0.004 * Hm,
                                        z - 0.045 * Hm * front ** 3 - off * 0.6)))
                loop_loft(self.md, path, 0.0045 * Hm, 0.0065 * Hm, 6, key, lambda i, co: w)
            return
        hgt = {"buttonup": 0.016, "tee": 0.006, "sweatshirt": 0.009, "sweater": 0.011}.get(tp, 0.007) * Hm
        key = "top_rib" if tp in ("sweatshirt", "sweater") else "top"
        path = []
        for a in np.linspace(0, 2 * math.pi, 28, endpoint=False):
            front = max(0.0, -math.sin(a))
            dip = 0.010 * Hm * front ** 2 if tp != "buttonup" else 0.022 * Hm * front ** 4
            path.append(Vector((math.cos(a) * r0 * 1.08, math.sin(a) * r0 * 1.0, z - dip + hgt * 0.4)))
        loop_loft(self.md, path, 0.004 * Hm, hgt, 6, key, lambda i, co: w)

    def accessories(self):
        acc = self.look.get("acc", [])
        Hm, h = self.H, self.h
        wh = {PFX + "Head": 1.0}
        if "watch" in acc:
            sh, el, wr, tip = self.arm["Left"]
            d = self.arm_dir["Left"]
            c = wr - d * 0.018 * Hm
            x, y = frame_for(d, Vector((0, 1, 0)))
            rr = 0.021 * Hm * (0.75 + 0.25 * self.bulk)
            path = [c + (x * math.cos(a) + y * math.sin(a)) * rr for a in np.linspace(0, 2 * math.pi, 16, endpoint=False)]
            loop_loft(self.md, path, 0.003 * Hm, 0.007 * Hm, 6, "watch", lambda i, co: {PFX + "LeftForeArm": 1.0}, up=d)
            face_c = c + x * (rr + 0.004 * Hm)
            pts = [face_c - x * 0.003 * Hm, face_c + x * 0.004 * Hm]
            loft(self.md, rings_along(pts, [(0.009 * Hm, 0.009 * Hm, 0.009 * Hm)] * 2, d), 10, "watch_face",
                 lambda i, co: {PFX + "LeftForeArm": 1.0}, cap0=True, cap1=True)
        if "cap" in acc:
            rings = []
            for zf in (0.60, 0.70, 0.80, 0.88, 0.94, 0.985):
                w, yf, yb = self.head_prof(zf)
                o = 0.055 * h
                rings.append(Ring((0, self.yc, self.chin + zf * h + 0.01 * h), (1, 0, 0), (0, 1, 0), w + o, yf + o, yb + o, 2.0))
            loft(self.md, rings, 24, "cap", lambda i, co: wh, cap1=True, tip=0.02 * h)
            # Brim
            w, yf, yb = self.head_prof(0.60)
            y0 = self.yc - yf - 0.04 * h
            z0 = self.chin + 0.61 * h
            pts, rad = [], []
            for t in np.linspace(0, 1, 6):
                pts.append(Vector((0, y0 - 0.34 * h * t, z0 - 0.05 * h * t * t)))
                ww = (w + 0.06 * h) * (1 - 0.45 * t ** 1.6)
                rad.append((ww, 0.010 * h, 0.010 * h))
            loft(self.md, rings_along(pts, rad, Vector((0, 0, 1)), sq=2.2), 16, "cap", lambda i, co: wh,
                 cap0=True, cap1=True, tip=0.003 * h)
            # Button on top and a small logo on the front.
            tp = Vector((0, self.yc, self.chin + 1.0 * h + 0.05 * h))
            loft(self.md, rings_along([tp, tp + Vector((0, 0, 0.02 * h))], [(0.025 * h,) * 3] * 2, Vector((0, 1, 0))),
                 8, "cap", lambda i, co: wh, cap1=True)
            lg = self.head_point(0, 0.76, 0.062 * h)
            loft(self.md, rings_along([lg + Vector((0, 0.004 * h, 0)), lg - Vector((0, 0.004 * h, 0))],
                                      [(0.05 * h, 0.04 * h, 0.04 * h)] * 2, Vector((0, 0, 1))), 12, "logo", lambda i, co: wh,
                 cap0=True, cap1=True)
        if "sunglasses" in acc or "glasses" in acc:
            sun = "sunglasses" in acc
            for side in ("Left", "Right"):
                (u, v), p = self.eye_pos(side)
                c = p + Vector((0, -0.045 * h, 0.005 * h))
                if sun:
                    pts = [c + Vector((0, 0.006 * h, 0)), c - Vector((0, 0.006 * h, 0))]
                    loft(self.md, rings_along(pts, [(0.085 * h, 0.07 * h, 0.07 * h)] * 2, Vector((0, 0, 1)), sq=3.2),
                         14, "lens", lambda i, co: wh, cap0=True, cap1=True)
                else:
                    path = []
                    for a in np.linspace(0, 2 * math.pi, 20, endpoint=False):
                        cx, cz = math.cos(a), math.sin(a)
                        e = 0.6
                        path.append(c + Vector((math.copysign(abs(cx) ** e, cx) * 0.085 * h, 0,
                                                math.copysign(abs(cz) ** e, cz) * 0.065 * h)))
                    loop_loft(self.md, path, 0.010 * h, 0.010 * h, 6, "frame", lambda i, co: wh, up=Vector((0, -1, 0)))
                # Temple arm back to the ear
                sg = 1 if side == "Left" else -1
                a0 = c + Vector((sg * 0.085 * h, 0, 0.02 * h))
                ear = self.head_point(sg * math.radians(88), 0.50, 0.01 * h)
                loft(self.md, rings_along([a0, ear], [(0.008 * h,) * 3] * 2, Vector((0, 0, 1))), 6, "frame",
                     lambda i, co: wh, cap0=True, cap1=True)
            (_, _), pl = self.eye_pos("Left")
            (_, _), pr = self.eye_pos("Right")
            mid = (pl + pr) / 2 + Vector((0, -0.05 * h, 0.02 * h))
            br = [pr + Vector((0.08 * h, -0.045 * h, 0.02 * h)), mid, pl + Vector((-0.08 * h, -0.045 * h, 0.02 * h))]
            loft(self.md, rings_along(br, [(0.009 * h,) * 3] * 3, Vector((0, 0, 1))), 6, "frame", lambda i, co: wh,
                 cap0=True, cap1=True)

    # ------------------------------------------------------------------ textures
    def face_texture(self):
        S = 1024
        lk = self.look
        skin = hexc(lk["skin"])
        cv = Canvas(S, S, skin)
        W, h = self.face_W, self.h
        U = lambda x: (0.5 + x / (2 * W)) * S  # noqa: E731
        V = lambda zf: zf * S  # noqa: E731
        px_u = S / (2 * W)  # pixels per meter across
        px_v = S / h
        img_path = os.path.join(ROOT, "art", "heroes", self.id if self.id in L.LOOKS else
                                L.FORM_LOOKS[self.id][0], "face.jpg")
        fi = lk.get("face_image")
        if fi and os.path.exists(img_path):
            self.paste_face(cv, img_path, fi, U, V)
            return cv
        face = lk.get("face", {})
        # Soft cheek warmth
        for sg in (1, -1):
            cv.ellipse(U(sg * 0.20 * h), V(0.29), 0.07 * h * px_u, 0.045 * h * px_v, skin * 0.93 + np.array([0.07, 0.0, 0.0]),
                       alpha=0.35 if face.get("blush") else 0.15, soft=40)
        # Beard / stubble
        beard = face.get("beard", "none")
        if beard != "none":
            bc = hexc(face.get("beard_color", lk["hair"]["color"]))
            strong = 0.9 if beard == "short" else 0.28
            lay = Canvas(S, S, (0, 0, 0))
            cov = np.zeros((S, S))
            yy, xx = np.mgrid[0:S, 0:S] + 0.5
            zf = yy / S
            xm = (xx / S - 0.5) * 2 * W / h
            jaw = (zf < 0.30) & (np.abs(xm) < 0.36 - 0.5 * np.maximum(0, 0.12 - zf))
            mouth_hole = ((np.abs(xm) < 0.07) & (np.abs(zf - 0.20) < 0.022))
            cov = np.where(jaw & ~mouth_hole, 1.0, 0.0)
            cov *= np.clip((0.30 - zf) / 0.05, 0, 1)
            cov *= np.clip((0.36 - np.abs(xm)) / 0.06, 0, 1)
            rng = np.random.default_rng(3)
            grain = rng.random((S, S))
            cov = cov * (0.75 + 0.25 * grain) * strong
            a = cov[..., None]
            cv.a = cv.a * (1 - a) + bc * a
            del lay
        # Nose
        cv.ellipse(U(0.008 * h), V(0.300), 0.020 * h * px_u, 0.012 * h * px_v, skin * 0.82, alpha=0.45, soft=10)
        cv.ellipse(U(-0.004 * h), V(0.318), 0.008 * h * px_u, 0.010 * h * px_v, np.minimum(skin * 1.08, 1), alpha=0.5, soft=6)
        # Mouth
        mouth = face.get("mouth", "smile")
        lipc = np.array([0.45, 0.16, 0.16])
        mw = 0.075 * h
        if mouth == "grin":
            pts = []
            for t in np.linspace(-1, 1, 15):
                pts.append((U(t * mw), V(0.205 - 0.035 * (1 - t * t))))
            # Filled open smile: dark mouth, teeth band, outline
            yy, xx = np.mgrid[0:S, 0:S] + 0.5
            tx = (xx - U(0)) / (mw * px_u)
            ty = (yy - V(0.205)) / (0.035 * h * px_v)
            inside = (np.abs(tx) <= 1) & (ty <= 0) & (ty >= -(1 - tx * tx))
            cv.a[inside] = np.array([0.36, 0.09, 0.10])
            teeth = inside & (ty > -0.38)
            cv.a[teeth] = np.array([0.98, 0.97, 0.95])
            cv.line([(U(-mw), V(0.205)), (U(mw), V(0.205))], 0.006 * h * px_v, lipc * 0.8)
            cv.line(pts, 0.006 * h * px_v, lipc * 0.8)
        elif mouth == "smirk":
            pts = [(U(t * mw), V(0.205 - 0.016 * (1 - t * t) + 0.012 * t)) for t in np.linspace(-1, 1, 13)]
            cv.line(pts, 0.010 * h * px_v, lipc, taper=True)
        else:
            pts = [(U(t * mw * 0.9), V(0.205 - 0.02 * (1 - t * t))) for t in np.linspace(-1, 1, 13)]
            cv.line(pts, 0.010 * h * px_v, lipc, taper=True)
        # Eyes
        eyec = hexc(lk.get("eyes", "#5a4030"))
        browc = hexc(face.get("brows", lk["hair"]["color"]))
        for side in ("Left", "Right"):
            sg = 1 if side == "Left" else -1
            (u, v), _ = self.eye_pos(side)
            cx, cy = u * S, v * S
            ew, eh = 0.050 * h * px_u, 0.064 * h * px_v
            cv.ellipse(cx, cy, ew, eh, np.array([0.98, 0.98, 0.98]))
            cv.ellipse(cx, cy + eh * 0.55, ew * 1.02, eh * 0.45, np.array([0.80, 0.80, 0.85]), alpha=0.35, soft=8)
            cv.ellipse(cx - sg * ew * 0.05, cy - eh * 0.06, ew * 0.72, eh * 0.82, None,
                       grad=(eyec * 0.45, np.minimum(eyec * 1.35, 1)))
            cv.ellipse(cx - sg * ew * 0.05, cy - eh * 0.04, ew * 0.34, eh * 0.42, np.array([0.06, 0.05, 0.06]))
            cv.ellipse(cx - sg * ew * 0.28, cy + eh * 0.30, ew * 0.20, eh * 0.18, np.array([1, 1, 1]))
            cv.ellipse(cx + sg * ew * 0.22, cy - eh * 0.35, ew * 0.09, eh * 0.08, np.array([1, 1, 1]), alpha=0.85)
            # Upper lash line with an outer flick, and a soft lower lid
            lash = []
            for t in np.linspace(0.12, 0.92, 14):
                a = math.pi * t
                lash.append((cx + sg * math.cos(a) * ew * 1.05 * -1, cy + math.sin(a) * eh * 1.02))
            lash.append((cx + sg * ew * 1.30, cy + eh * 0.55))
            cv.line(lash, 0.016 * h * px_v * (1.15 if self.f else 1.0), np.array([0.10, 0.07, 0.07]), taper=True)
            low = [(cx + math.cos(a) * ew * 0.9, cy - math.sin(a) * eh * 0.95) for a in np.linspace(0.25 * math.pi, 0.75 * math.pi, 8)]
            cv.line(low, 0.005 * h * px_v, skin * 0.70, alpha=0.6)
            # Brow
            bpts = []
            for t in np.linspace(-1, 1, 10):
                bx = cx + sg * t * ew * 1.15
                by = cy + eh * 1.55 + (1 - t * t) * eh * 0.22 - sg * t * eh * 0.10 * sg
                bpts.append((bx, by))
            cv.line(bpts, 0.022 * h * px_v * (0.8 if self.f else 1.0), browc, taper=True)
        cv.noise(0.012, seed=11)
        return cv

    def paste_face(self, cv, path, fi, U, V):
        """Maps a portrait onto the face so its eyes and mouth land where the head expects them."""
        img = bpy.data.images.load(path)
        w, hh = img.size
        px = np.empty(w * hh * 4, dtype=np.float32)
        img.pixels.foreach_get(px)
        src = px.reshape(hh, w, 4)[..., :3]
        bpy.data.images.remove(img)
        # Points in the portrait, given top-down in pixels -> bottom-up rows
        (lx, ly), (rx, ry) = fi["eyes"]  # viewer's left eye, viewer's right eye
        mx, my = fi["mouth"]
        ly, ry, my = hh - ly, hh - ry, hh - my
        S = cv.w
        (ul, ve), _ = self.eye_pos("Right")  # viewer's left = character's right
        (ur, _), _ = self.eye_pos("Left")
        vm = 0.205
        sx = (rx - lx) / ((ur - ul) * S)
        sy = (0.5 * (ly + ry) - my) / ((ve - vm) * S)
        cx_src = 0.5 * (lx + rx)
        cy_src = 0.5 * (ly + ry)
        yy, xx = np.mgrid[0:S, 0:S] + 0.5
        xs = cx_src + (xx - 0.5 * (ul + ur) * S) * sx
        ys = cy_src + (yy - ve * S) * sy
        x0 = np.clip(np.floor(xs).astype(int), 0, w - 2)
        y0 = np.clip(np.floor(ys).astype(int), 0, hh - 2)
        fx = np.clip(xs - x0, 0, 1)[..., None]
        fy = np.clip(ys - y0, 0, 1)[..., None]
        samp = (src[y0, x0] * (1 - fx) * (1 - fy) + src[y0, x0 + 1] * fx * (1 - fy) +
                src[y0 + 1, x0] * (1 - fx) * fy + src[y0 + 1, x0 + 1] * fx * fy)
        # Soft oval mask from the brows to the chin, cheek to cheek
        cxm, cym = 0.5 * S, (0.5 * (ve + vm) + 0.03) * S
        rxm, rym = (ur - ul) * S * 0.98, (ve - vm + 0.20) * S * 0.62
        d = np.sqrt(((xx - cxm) / rxm) ** 2 + ((yy - cym) / rym) ** 2)
        mask = np.clip((1.0 - d) / 0.18, 0, 1)
        inside = (xs >= 0) & (xs < w - 1) & (ys >= 0) & (ys < hh - 1)
        mask = np.where(inside, mask, 0)[..., None]
        # Match the skin around the face to the portrait's cheeks
        ch = src[int(cy_src - 0.6 * (cy_src - my)), int(lx - 0.15 * (rx - lx))]
        cv.a[:] = np.clip(ch, 0, 1)
        cv.a = cv.a * (1 - mask) + samp * mask
        self.look = dict(self.look)
        self.look["skin_sampled"] = "#%02x%02x%02x" % tuple(int(c * 255) for c in np.clip(ch, 0, 1))

    def cloth_textures(self):
        lk, Hm = self.look, self.H
        top = lk["top"]
        tcol = hexc(top["color"])
        tp = top["type"]
        S = 1024
        # Torso: u around (front at 0.75), v from crotch (0) to neck base (1)
        circ = 2 * math.pi * 0.10 * Hm
        height = self.neck_base - self.crotch
        cv = Canvas(S, S, tcol)
        sleeve = Canvas(256, 256, tcol)
        pat = top.get("pattern")
        if pat == "dots":
            pc = hexc(top.get("pattern_color", "#ffffff"))
            for c, rep_u, size in ((cv, circ / 0.028, S), (sleeve, (2 * math.pi * 0.03 * Hm) / 0.028, 256)):
                sx = size / rep_u
                sy = sx * 1.1
                yy, xx = np.mgrid[0:size, 0:size] + 0.5
                row = np.floor(yy / sy)
                xm = ((xx + (row % 2) * sx * 0.5) % sx) - sx / 2
                ym = (yy % sy) - sy / 2
                r = sx * 0.13
                d = np.hypot(xm, ym)
                cov = np.clip(r - d + 0.5, 0, 1)
                # tiny petals
                for ang in (0, math.pi / 2, math.pi, 3 * math.pi / 2):
                    d2 = np.hypot(xm - math.cos(ang) * r * 1.3, ym - math.sin(ang) * r * 1.3)
                    cov = np.maximum(cov, np.clip(r * 0.7 - d2 + 0.5, 0, 1))
                a = cov[..., None] * 0.9
                c.a = c.a * (1 - a) + pc * a
        if tp in ("sweater",):
            for c, size in ((cv, S), (sleeve, 256)):
                yy, xx = np.mgrid[0:size, 0:size] + 0.5
                sx = size / (40 if size == S else 14)
                k = (xx % sx) / sx
                val = 0.5 + 0.5 * np.cos(2 * math.pi * (yy / (sx * 0.8) + 2 * np.abs(k - 0.5)))
                c.a = c.a * (1 - 0.10 * val[..., None])
                rib = 0.5 + 0.5 * np.cos(2 * math.pi * xx / sx)
                c.a = c.a * (1 - 0.05 * rib[..., None])
        if tp == "buttonup":
            u0 = 0.75 * S
            cv.rect(u0 - 0.008 * S, 0.30 * S, u0 + 0.008 * S, S, tcol * 0.82)
            for v in np.linspace(0.42, 0.95, 6):
                cv.ellipse(u0, v * S, 4.5, 4.5, np.array([0.92, 0.92, 0.95]))
            # Pocket on the left chest
            pu, pv = 0.845 * S, 0.74 * S
            cv.line([(pu - 30, pv + 28), (pu - 30, pv - 26), (pu + 30, pv - 26), (pu + 30, pv + 28)], 3, tcol * 0.7)
            cv.line([(pu - 30, pv + 28), (pu + 30, pv + 28)], 3, tcol * 0.7)
        if tp == "jersey":
            t0, t1 = [hexc(c) for c in top.get("trim", ["#ff0000", "#00ff00"])]
            # Side panels and a crest
            for u in (0.0, 0.5):
                cv.rect(u * S - 0.015 * S, 0.30 * S, u * S + 0.015 * S, 0.95 * S, t0)
                cv.rect(u * S - 0.006 * S, 0.30 * S, u * S + 0.006 * S, 0.95 * S, t1)
            pu, pv = 0.86 * S, 0.78 * S
            cv.ellipse(pu, pv, 22, 26, t0)
            cv.rect(pu - 6, pv - 22, pu + 6, pv + 22, t1)
        num = top.get("number")
        if num:
            nc = hexc(top.get("number_color", "#ffffff"))
            draw_digits(cv, num, 0.75 * S, 0.70 * S, 0.12 * S, nc)
        if top.get("print") == "cyber":
            pc = hexc(top.get("print_color", "#ffff00"))
            cx, cy = 0.75 * S, 0.70 * S
            hexpts = [(cx + math.cos(a) * 80, cy + math.sin(a) * 80) for a in np.linspace(math.pi / 6, math.pi / 6 + 2 * math.pi, 7)]
            cv.line(hexpts, 9, pc)
            for i, (dx, wdt) in enumerate(((-60, 120), (-40, 80), (-20, 40))):
                cv.rect(cx - wdt / 2, cy - 18 - i * 22, cx + wdt / 2, cy - 8 - i * 22, pc)
            cv.rect(cx - 30, cy + 10, cx + 30, cy + 40, pc)
            cv.rect(cx - 18, cy + 18, cx + 18, cy + 32, tcol)
            for gx, gy in ((-100, 60), (95, -50), (110, 40), (-90, -70)):
                cv.rect(cx + gx, cy + gy, cx + gx + 14, cy + gy + 6, pc)
        cv.noise(0.015, seed=5)
        sleeve.noise(0.015, seed=6)
        self.mat("top", image=cv.image("%s_top" % self.id), rough=0.85)
        self.mat("sleeve", image=sleeve.image("%s_sleeve" % self.id), rough=0.85)
        rib = Canvas(128, 128, tcol * 0.92)
        yy, xx = np.mgrid[0:128, 0:128] + 0.5
        rib.a = rib.a * (1 - 0.12 * (0.5 + 0.5 * np.cos(2 * math.pi * xx / 6.0)))[..., None]
        self.mat("top_rib", image=rib.image("%s_rib" % self.id), rough=0.9)
        if tp == "jersey":
            t0, t1 = top.get("trim", ["#ff0000", "#00ff00"])
            self.mat("trim0", hexc(t0), rough=0.7)
            self.mat("trim1", hexc(t1), rough=0.7)
        else:
            self.mat("trim0", tcol * 0.85)
        bcol = hexc(lk["bottom"]["color"])
        bc = Canvas(256, 256, bcol)
        bc.noise(0.02, seed=9)
        self.mat("bottom", image=bc.image("%s_bottom" % self.id), rough=0.85)
        sh = lk["shoes"]
        self.mat("shoe", hexc(sh["color"]), rough=0.55 if sh["type"] == "leather" else 0.7)
        self.mat("sole", hexc(sh.get("sole", "#dddddd")), rough=0.8)

    def hair_texture(self):
        hc = hexc(self.look["hair"]["color"])
        S = 256
        cv = Canvas(S, S, hc)
        rng = np.random.default_rng(21)
        cols = np.zeros(S)
        for _ in range(6):
            f = rng.uniform(3, 40)
            cols += np.sin(np.linspace(0, 2 * math.pi * f, S) + rng.uniform(0, 6.28)) / f ** 0.4
        cols = cols / np.abs(cols).max()
        yy = np.linspace(0, 1, S)[:, None]
        shade = 1 + 0.16 * cols[None, :] - 0.12 * (1 - yy) + 0.10 * np.exp(-((yy - 0.75) / 0.08) ** 2)
        cv.a = np.clip(cv.a * shade[..., None], 0, 1)
        self.mat("hair", image=cv.image("%s_hair" % self.id), rough=0.55)

    # ------------------------------------------------------------------ assembly
    def build(self):
        self.torso()
        self.neck()
        for side in ("Left", "Right"):
            self.arm_part(side)
            self.leg_part(side)
        if self.look["bottom"]["type"] == "skirt":
            self.skirt()
        self.head()
        self.hair()
        self.collar()
        self.accessories()
        # Materials (the face first, so a pasted portrait can set the skin tone)
        face_cv = self.face_texture()
        skin = hexc(self.look.get("skin_sampled", self.look["skin"]))
        self.mat("face", image=face_cv.image("%s_face" % self.id), rough=0.6)
        self.mat("skin", skin, rough=0.6)
        self.cloth_textures()
        self.hair_texture()
        self.mat("lens", hexc("#121418"), rough=0.12)
        self.mat("frame", hexc("#b9a3d6") if "glasses" in self.look.get("acc", []) else hexc("#151515"), rough=0.4)
        self.mat("watch", hexc("#1c1c1e"), rough=0.4)
        self.mat("watch_face", hexc("#3a4a5a"), rough=0.2, metal=0.3)
        self.mat("cap", hexc("#16161a"), rough=0.8)
        self.mat("logo", hexc("#f2f2f2"), rough=0.6)
        return self.make_objects()

    def make_objects(self):
        md = self.md
        mesh = bpy.data.meshes.new(self.id + "_body")
        verts = [tuple(c) for c in md.co]
        faces = [f[0] for f in md.faces]
        mesh.from_pydata(verts, [], faces)
        keys = list(self.mats.keys())
        for k in keys:
            mesh.materials.append(self.mats[k])
        index = {k: i for i, k in enumerate(keys)}
        mesh.polygons.foreach_set("material_index", [index.get(f[1], 0) for f in md.faces])
        uvl = mesh.uv_layers.new(name="UVMap")
        uvs = []
        for f in md.faces:
            for uv in f[2]:
                uvs.extend(uv)
        uvl.data.foreach_set("uv", uvs)
        mesh.polygons.foreach_set("use_smooth", [True] * len(mesh.polygons))
        mesh.update()
        obj = bpy.data.objects.new(self.id + "_body", mesh)
        bpy.context.scene.collection.objects.link(obj)
        # Skeleton
        arm_data = bpy.data.armatures.new(self.id + "_rig")
        arm = bpy.data.objects.new(self.id + "_rig", arm_data)
        bpy.context.scene.collection.objects.link(arm)
        bpy.ops.object.select_all(action="DESELECT")
        bpy.context.view_layer.objects.active = arm
        bpy.ops.object.mode_set(mode="EDIT")
        parents = {"Hips": None, "Spine": "Hips", "Spine1": "Spine", "Spine2": "Spine1", "Neck": "Spine2",
                   "Head": "Neck"}
        for s in ("Left", "Right"):
            parents.update({s + "Shoulder": "Spine2", s + "Arm": s + "Shoulder", s + "ForeArm": s + "Arm",
                            s + "Hand": s + "ForeArm", s + "UpLeg": "Hips", s + "Leg": s + "UpLeg",
                            s + "Foot": s + "Leg", s + "ToeBase": s + "Foot"})
        for name, parent in parents.items():
            hd, tl = self.J[name]
            eb = arm_data.edit_bones.new(PFX + name)
            eb.head, eb.tail = hd, tl
            if parent:
                eb.parent = arm_data.edit_bones[PFX + parent]
        bpy.ops.object.mode_set(mode="OBJECT")
        # Weights
        groups = {}
        for vi, w in enumerate(md.w):
            for bone, val in w.items():
                groups.setdefault(bone, {}).setdefault(round(val, 3), []).append(vi)
        for bone, byval in groups.items():
            vg = obj.vertex_groups.new(name=bone)
            for val, ids in byval.items():
                vg.add(ids, val, "REPLACE")
        # Smooth it with one level of subdivision (weights interpolate), then skin it.
        bpy.ops.object.select_all(action="DESELECT")
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        sub = obj.modifiers.new("Subdivision", "SUBSURF")
        sub.levels = 1
        sub.render_levels = 1
        bpy.ops.object.modifier_apply(modifier=sub.name)
        obj.parent = arm
        mod = obj.modifiers.new("Armature", "ARMATURE")
        mod.object = arm
        return arm


def build(model_id):
    """Builds the hero and returns its armature (the body mesh is its child)."""
    return Hero(model_id).build()
