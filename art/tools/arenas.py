"""
Battle arenas for Blender: each arena is one low-poly diorama mesh, exported as
assets/models/arenas/<id>.glb. The battle screen (scenes/battle/arena.gd) adds the
lighting, the sky color and the two battle platforms on top.

Layouts are written in GAME coordinates (Godot: X right, Y up, Z toward the
camera) so they line up with the battle camera:
  - heroes' platform around (-2.6, 0, 2.4), enemies' around (2.3, 0, -0.3);
  - keep props out of x -6.5..6.5 for z > -3.5 (that's the fight);
  - the camera sees the floor from z ~4 (under the text box) back to z ~-12, and
    scenery 4-8 m behind the enemies up to about 1.2-2.2 m tall, so the backdrop
    goes there (x about -9..12), with smaller pieces at the sides.
"""

import math
import random

import bmesh
import bpy
from mathutils import Euler, Matrix, Vector

import chibi
import textures as T

ARENA_IDS = ["office", "parking_lot", "desk_pods", "meeting_room", "office_center", "james_desk", "villiam_burginson"]

_glass = {}

# Generated textures (textures.py), by key: make() -> image, tile = how many meters one
# copy covers (u, v), origin = where v starts on walls (meters up), plus roughness and glow.
TEX = {}
_tex_mats = {}


def tex(key, make, tile, rough=0.9, emit=0.0, origin=(0.0, 0.0)):
    """Registers a texture (once) and returns its key, for Scenery's tex= argument."""
    if key not in TEX:
        TEX[key] = dict(make=make, tile=tile, rough=rough, emit=emit, origin=origin)
    return key


def carpet(base, accent=None, seed=1):
    return tex("carpet_%s_%s" % (base.strip("#"), (accent or "").strip("#")), lambda: T.carpet(base, accent, seed=seed), (1.0, 1.0), rough=1.0)


def fabric(color):
    return tex("fabric_" + color.strip("#"), lambda: T.fabric(color), (0.6, 0.6), rough=1.0)


def view(mood):
    """The city through the windows (window_wall's glass), glowing a little."""
    make = T.facade if mood == "facade" else (lambda: T.skyline(mood))
    return tex("view_" + mood, make, (16.0, 1.9), rough=0.2, emit=0.9, origin=(0.0, 0.9))


def wood(kind="light"):
    if kind == "dark":
        return tex("wood_dark", lambda: T.wood("#7a5444", "#553a2e", seed=6), (1.6, 1.6), rough=0.5)
    if kind == "floor":
        return tex("wood_floor", lambda: T.wood("#b88f5f", "#8f6844", seed=7), (2.4, 2.4), rough=0.6)
    return tex("wood_light", lambda: T.wood("#dcc59f", "#c4a67c", seed=5), (1.6, 1.6), rough=0.55)


def tex_material(key):
    if key in _tex_mats:
        return _tex_mats[key]
    t = TEX[key]
    im = T.image(key, t["make"]())
    m = bpy.data.materials.new("tex_" + key)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    node = nt.nodes.new("ShaderNodeTexImage")
    node.image = im
    nt.links.new(node.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = t["rough"]
    if t["emit"] > 0:
        for nm in ("Emission Color", "Emission"):
            if nm in bsdf.inputs:
                nt.links.new(node.outputs["Color"], bsdf.inputs[nm])
                break
        if "Emission Strength" in bsdf.inputs:
            bsdf.inputs["Emission Strength"].default_value = t["emit"]
    m["vbd_tex"] = key
    _tex_mats[key] = m
    return m


def glass_material(color, alpha=0.35):
    key = (color, alpha)
    if key in _glass:
        return _glass[key]
    m = bpy.data.materials.new("glass_%s" % color.strip("#"))
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    rgb = chibi.hex_rgb(color)
    bsdf.inputs["Base Color"].default_value = (*rgb, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.1
    bsdf.inputs["Alpha"].default_value = alpha
    if hasattr(m, "surface_render_method"):
        m.surface_render_method = "BLENDED"
    if hasattr(m, "blend_method"):
        m.blend_method = "BLEND"
    m.diffuse_color = (*rgb, alpha)
    _glass[key] = m
    return m


class Scenery:
    """Collects boxes, cylinders and spheres into one mesh. Positions are game
    coordinates; box/cyl positions are the bottom center unless noted."""

    def __init__(self):
        self.bm = bmesh.new()
        self.mats = []

    def mat(self, color, emit=0.0, metal=0.0, glass=False, tex=None):
        """A material index: a flat color, glass, or (tex=key) a generated texture."""
        if tex:
            m = tex_material(tex)
        else:
            m = glass_material(color) if glass else chibi.material(color, False, emit, metal)
        if m not in self.mats:
            self.mats.append(m)
        return self.mats.index(m)

    def _paint(self, verts, color, smooth=False, **kw):
        idx = self.mat(color, **kw)
        for f in {f for v in verts for f in v.link_faces}:
            f.material_index = idx
            f.smooth = smooth
        return verts

    @staticmethod
    def _xf(center, size, rot):
        return (Matrix.Translation(Vector(center)) @ Euler([math.radians(a) for a in rot]).to_matrix().to_4x4()
                @ Matrix.Diagonal((*size, 1.0)))

    def box(self, pos, size, color, yaw=0.0, pitch=0.0, roll=0.0, bevel=0.0, **kw):
        """pos: bottom center (x, y, z); size: (width x, height y, depth z)."""
        x, y, z = pos
        w, h, d = size
        verts = bmesh.ops.create_cube(self.bm, size=1.0)["verts"]
        bmesh.ops.transform(self.bm, matrix=self._xf((x, -z, y + h / 2), (w, d, h), (pitch, roll, yaw)), verts=verts)
        if bevel > 0:
            edges = list({e for v in verts for e in v.link_edges})
            res = bmesh.ops.bevel(self.bm, geom=verts + edges, offset=bevel, segments=1, affect="EDGES")
            verts = list({v for v in res.get("verts", []) + verts if v.is_valid})
        return self._paint(verts, color, **kw)

    def cyl(self, pos, r, h, color, segs=12, r2=None, axis="y", yaw=0.0, smooth=False, **kw):
        """Upright (axis y): pos is the bottom center. Lying along x or z: pos is the center."""
        x, y, z = pos
        verts = bmesh.ops.create_cone(self.bm, cap_ends=True, cap_tris=False, segments=segs, radius1=1.0,
                                      radius2=(r2 / r) if r2 is not None else 1.0, depth=1.0)["verts"]
        if axis == "y":
            m = self._xf((x, -z, y + h / 2), (r, r, h), (0, 0, yaw))
        elif axis == "x":
            m = self._xf((x, -z, y), (r, r, h), (0, 90, yaw))
        else:
            m = self._xf((x, -z, y), (r, r, h), (90, 0, yaw))
        bmesh.ops.transform(self.bm, matrix=m, verts=verts)
        return self._paint(verts, color, smooth=smooth, **kw)

    def sph(self, center, radii, color, segs=10, smooth=True, **kw):
        x, y, z = center
        rx, ry, rz = radii
        verts = bmesh.ops.create_uvsphere(self.bm, u_segments=segs, v_segments=max(5, segs // 2 + 1), radius=1.0)["verts"]
        bmesh.ops.transform(self.bm, matrix=self._xf((x, -z, y), (rx, rz, ry), (0, 0, 0)), verts=verts)
        return self._paint(verts, color, smooth=smooth, **kw)

    def floor(self, x0, z0, x1, z1, tile, c1, c2, y=0.0):
        """A checker floor of square-ish tiles."""
        i1, i2 = self.mat(c1), self.mat(c2)
        nx = max(1, round((x1 - x0) / tile))
        nz = max(1, round((z1 - z0) / tile))
        grid = {}
        for i in range(nx + 1):
            for j in range(nz + 1):
                gx = x0 + (x1 - x0) * i / nx
                gz = z0 + (z1 - z0) * j / nz
                grid[i, j] = self.bm.verts.new((gx, -gz, y))
        for i in range(nx):
            for j in range(nz):
                f = self.bm.faces.new((grid[i, j], grid[i, j + 1], grid[i + 1, j + 1], grid[i + 1, j]))
                f.material_index = i1 if (i + j) % 2 == 0 else i2

    def decal(self, x, z, w, d, color, yaw=0.0, y=0.0, **kw):
        """A flat marking on the floor (lines, rugs, stains)."""
        return self.box((x, y, z), (w, 0.012, d), color, yaw=yaw, **kw)

    def tex_floor(self, x0, z0, x1, z1, key, step=2.0, y=0.0):
        """A floor of one generated texture (its UVs come from world position)."""
        idx = self.mat(None, tex=key)
        nx, nz = max(1, round((x1 - x0) / step)), max(1, round((z1 - z0) / step))
        grid = {}
        for i in range(nx + 1):
            for j in range(nz + 1):
                grid[i, j] = self.bm.verts.new((x0 + (x1 - x0) * i / nx, -(z0 + (z1 - z0) * j / nz), y))
        for i in range(nx):
            for j in range(nz):
                f = self.bm.faces.new((grid[i, j], grid[i, j + 1], grid[i + 1, j + 1], grid[i + 1, j]))
                f.material_index = idx

    def text(self, body, pos, size, color, yaw=0.0, pitch=0.0, emit=0.0, depth=0.0, flat=False, align="CENTER"):
        """Text as geometry. Standing (the default) it faces +z at yaw 0 and pos is the middle
        of its baseline; flat, it lies on the floor reading toward the camera."""
        cu = bpy.data.curves.new("vbd_text", type="FONT")
        cu.body = body
        cu.size = size
        cu.align_x = align
        cu.extrude = depth
        ob = bpy.data.objects.new("vbd_text", cu)
        bpy.context.scene.collection.objects.link(ob)
        me = bpy.data.meshes.new_from_object(ob.evaluated_get(bpy.context.evaluated_depsgraph_get()))
        bpy.data.objects.remove(ob, do_unlink=True)
        bpy.data.curves.remove(cu)
        x, y, z = pos
        rot = Matrix.Rotation(math.radians(yaw), 4, "Z")
        if not flat:
            rot = rot @ Matrix.Rotation(math.radians(90 + pitch), 4, "X")
        me.transform(Matrix.Translation((x, -z, y)) @ rot)
        n = len(self.bm.faces)
        self.bm.from_mesh(me)
        bpy.data.meshes.remove(me)
        idx = self.mat(color, emit=emit)
        self.bm.faces.ensure_lookup_table()
        for f in self.bm.faces[n:]:
            f.material_index = idx

    def to_object(self, name):
        # Textured faces get UVs from their world position: floors by x and depth, walls
        # by their run and height (the texture's tile size says how many meters one copy
        # covers).
        self.bm.normal_update()
        uv = self.bm.loops.layers.uv.verify()
        info = {}
        for i, m in enumerate(self.mats):
            key = m.get("vbd_tex") if hasattr(m, "get") else None
            if key:
                info[i] = (TEX[key]["tile"], TEX[key]["origin"])
        for f in self.bm.faces:
            t = info.get(f.material_index)
            if not t:
                continue
            (tu, tv), (u0, v0) = t
            n = f.normal
            ax, ay, az = abs(n.x), abs(n.y), abs(n.z)
            for lp in f.loops:
                co = lp.vert.co
                if az >= ax and az >= ay:
                    lp[uv].uv = (co.x / tu, co.y / tv)
                elif ay >= ax:
                    lp[uv].uv = ((co.x - u0) / tu, (co.z - v0) / tv)
                else:
                    lp[uv].uv = ((co.y - u0) / tu, (co.z - v0) / tv)
        mesh = bpy.data.meshes.new(name)
        self.bm.to_mesh(mesh)
        self.bm.free()
        for m in self.mats:
            mesh.materials.append(m)
        obj = bpy.data.objects.new(name, mesh)
        bpy.context.scene.collection.objects.link(obj)
        return obj


# ===================================================================== props
# Each prop takes the Scenery, a floor position (x, z) and a yaw in degrees. With
# yaw 0 a prop's "front" faces the camera (+z).

def _rot(x, z, dx, dz, yaw):
    """Offset (dx, dz) from (x, z), turned by yaw degrees."""
    a = math.radians(yaw)
    return x + dx * math.cos(a) + dz * math.sin(a), z - dx * math.sin(a) + dz * math.cos(a)


def desk(S, x, z, yaw=0.0, top="#d7c4a3", body="#8d8a84", screen="#7fd4ff", monitor=True, clutter=True, screen_on=True):
    """An office desk; the monitor sits at the back facing the front. The default top is
    light wood laminate."""
    S.box((x, 0.72, z), (1.6, 0.05, 0.8), top, yaw=yaw, bevel=0.01, tex=wood("light") if top == "#d7c4a3" else None)
    for dx in (-0.74, 0.74):
        px, pz = _rot(x, z, dx, 0, yaw)
        S.box((px, 0, pz), (0.06, 0.72, 0.74), body, yaw=yaw)
    mx, mz = _rot(x, z, 0, -0.35, yaw)
    S.box((mx, 0.18, mz), (1.5, 0.5, 0.03), body, yaw=yaw)  # modesty panel
    if monitor:
        sx, sz = _rot(x, z, 0, -0.22, yaw)
        S.box((sx, 0.77, sz), (0.2, 0.02, 0.16), "#2d3436", yaw=yaw)
        S.box((sx, 0.77, sz), (0.05, 0.2, 0.05), "#2d3436", yaw=yaw)
        S.box((sx, 0.92, sz), (0.68, 0.42, 0.04), "#1e272e", yaw=yaw, bevel=0.005)
        fx, fz = _rot(x, z, 0, -0.195, yaw)
        S.box((fx, 0.95, fz), (0.6, 0.35, 0.01), screen if screen_on else "#2c3e50", yaw=yaw, emit=1.6 if screen_on else 0.0)
        kx, kz = _rot(x, z, 0, 0.12, yaw)
        S.box((kx, 0.75, kz), (0.48, 0.02, 0.16), "#dfe6e9", yaw=yaw)
    if clutter:
        cx, cz = _rot(x, z, 0.55, 0.12, yaw)
        S.cyl((cx, 0.745, cz), 0.04, 0.1, "#ffffff", segs=8)
        px, pz = _rot(x, z, -0.55, 0.05, yaw)
        S.box((px, 0.745, pz), (0.22, 0.03, 0.3), "#fdfdfd", yaw=yaw + 8)


def office_chair(S, x, z, yaw=0.0, color="#2d3436"):
    for i in range(5):
        a = yaw + i * 72
        lx, lz = _rot(x, z, 0, 0.18, a)
        S.box((lx, 0.04, lz), (0.06, 0.04, 0.36), "#555555", yaw=a)
    S.cyl((x, 0.05, z), 0.03, 0.38, "#777777", segs=6)
    S.box((x, 0.43, z), (0.48, 0.08, 0.46), color, yaw=yaw, bevel=0.02)
    bx, bz = _rot(x, z, 0, -0.22, yaw)  # the backrest is behind the seat
    S.box((bx, 0.5, bz), (0.44, 0.52, 0.07), color, yaw=yaw, bevel=0.02)


def partition(S, x, z, length, yaw=0.0, h=1.3, color="#95a5a6", trim="#7f8c8d"):
    """A cubicle wall: woven fabric with a metal trim on top."""
    S.box((x, 0, z), (length, h, 0.07), color, yaw=yaw, tex=fabric(color))
    S.box((x, h, z), (length + 0.04, 0.04, 0.09), trim, yaw=yaw)


def hanging_sign(S, x, y, z, text, w=1.8, h=0.5, bg="#2d3436", fg="#ffffff", emit=0.0, yaw=0.0, frame=None):
    """A sign hung from the ceiling on two wires (its bottom edge at y)."""
    for dx in (-w / 2 + 0.12, w / 2 - 0.12):
        px, pz = _rot(x, z, dx, 0, yaw)
        S.box((px, y + h, pz), (0.012, 2.5, 0.012), "#3d3d3d", yaw=yaw)
    sign(S, x, y, z, text, w=w, h=h, bg=bg, fg=fg, yaw=yaw, emit=emit, frame=frame)


def column(S, x, z, h=3.4, w=0.5, color="#d9d4ca", clock=False, hour=10, minute=10, clock_y=2.0):
    """A square structural column (with a wall clock on its front, if asked)."""
    S.box((x, 0, z), (w, h, w), color)
    S.box((x, 0, z), (w + 0.04, 0.12, w + 0.04), "#8d8a84")
    if clock:
        wall_clock(S, x, clock_y, z + w / 2, r=0.22, hour=hour, minute=minute)


def poster(S, x, y, z, yaw=0.0, w=0.6, h=0.8, colors=("#ff7675", "#ffeaa7", "#74b9ff")):
    """A framed picture/poster facing +z (on a partition or wall)."""
    S.box((x, y, z), (w, h, 0.02), "#2d3436", yaw=yaw)
    fx, fz = _rot(x, z, 0, 0.012, yaw)
    S.box((fx, y + 0.04, fz), (w - 0.08, h - 0.08, 0.01), colors[0], yaw=yaw)
    for i, c in enumerate(colors[1:]):
        ox, oz = _rot(x, z, (i - 0.5) * (w * 0.35), 0.02, yaw)
        S.box((ox, y + h * 0.25, oz), (w * 0.28, h * 0.35, 0.01), c, yaw=yaw)


def plant(S, x, z, size=1.0, pot="#c0703a", leaves="#2e8b57", dead=False):
    S.cyl((x, 0, z), 0.22 * size, 0.42 * size, pot, segs=10, r2=0.28 * size)
    S.cyl((x, 0.42 * size, z), 0.25 * size, 0.04, "#5d4037", segs=10)
    c = "#8d6e3f" if dead else leaves
    if dead:
        for i in range(4):
            a = math.radians(i * 90 + 20)
            S.box((x + math.cos(a) * 0.12, 0.45 * size, z + math.sin(a) * 0.12), (0.04, 0.45 * size, 0.04), c,
                  pitch=math.degrees(math.sin(a)) * 0.6, roll=math.degrees(math.cos(a)) * 0.6)
        return
    S.sph((x, 0.85 * size, z), (0.38 * size, 0.42 * size, 0.38 * size), c)
    S.sph((x + 0.18 * size, 1.1 * size, z - 0.05), (0.26 * size, 0.3 * size, 0.26 * size), c)
    S.sph((x - 0.16 * size, 1.15 * size, z + 0.08), (0.24 * size, 0.28 * size, 0.24 * size), "#27ae60" if not dead else c)


def tall_plant(S, x, z):
    S.cyl((x, 0, z), 0.26, 0.5, "#ecf0f1", segs=10, r2=0.3)
    S.cyl((x, 0.5, z), 0.04, 0.9, "#6d4c41", segs=6)
    for i, (dx, dy, dz) in enumerate([(0.15, 1.3, 0), (-0.2, 1.5, 0.05), (0.05, 1.75, -0.1), (-0.1, 1.15, -0.12), (0.2, 1.6, 0.1)]):
        S.sph((x + dx, dy, z + dz), (0.2, 0.12, 0.14), "#2e8b57" if i % 2 else "#27ae60")


def water_cooler(S, x, z, yaw=0.0):
    S.box((x, 0, z), (0.36, 1.0, 0.36), "#ecf0f1", yaw=yaw, bevel=0.02)
    fx, fz = _rot(x, z, 0, 0.19, yaw)
    S.box((fx, 0.72, fz), (0.08, 0.06, 0.04), "#3498db", yaw=yaw)
    S.cyl((x, 1.0, z), 0.15, 0.42, "#74b9ff", segs=12, glass=True)
    S.cyl((x, 1.42, z), 0.06, 0.06, "#74b9ff", segs=8)


def filing_cabinet(S, x, z, yaw=0.0, drawers=3, color="#7f8c8d"):
    h = drawers * 0.42
    S.box((x, 0, z), (0.5, h, 0.62), color, yaw=yaw, bevel=0.01)
    for i in range(drawers):
        fx, fz = _rot(x, z, 0, 0.315, yaw)
        S.box((fx, i * 0.42 + 0.06, fz), (0.44, 0.34, 0.01), "#95a5a6", yaw=yaw)
        S.box((fx, i * 0.42 + 0.27, fz), (0.16, 0.03, 0.03), "#bdc3c7", yaw=yaw)


def vending_machine(S, x, z, yaw=0.0, body="#c0392b"):
    S.box((x, 0, z), (1.0, 1.95, 0.8), body, yaw=yaw, bevel=0.03)
    fx, fz = _rot(x, z, -0.12, 0.405, yaw)
    S.box((fx, 0.6, fz), (0.62, 1.2, 0.02), "#dff9fb", yaw=yaw, emit=0.8)
    for r in range(4):
        for c in range(4):
            px, pz = _rot(x, z, -0.36 + c * 0.16, 0.42, yaw)
            S.box((px, 0.7 + r * 0.28, pz), (0.1, 0.16, 0.02), ["#e17055", "#00b894", "#fdcb6e", "#0984e3"][(r + c) % 4], yaw=yaw)
    kx, kz = _rot(x, z, 0.33, 0.405, yaw)
    S.box((kx, 1.0, kz), (0.18, 0.4, 0.02), "#2d3436", yaw=yaw)
    sx, sz = _rot(x, z, 0, 0.405, yaw)
    S.box((sx, 0.18, sz), (0.7, 0.22, 0.02), "#2d3436", yaw=yaw)


def whiteboard(S, x, z, yaw=0.0, w=2.0, scribbles="chart"):
    for dx in (-w / 2 + 0.1, w / 2 - 0.1):
        lx, lz = _rot(x, z, dx, 0, yaw)
        S.box((lx, 0, lz), (0.05, 1.9, 0.05), "#95a5a6", yaw=yaw)
        S.box((lx, 0, lz), (0.06, 0.04, 0.6), "#7f8c8d", yaw=yaw)
    S.box((x, 0.75, z), (w, 1.05, 0.04), "#bdc3c7", yaw=yaw)
    fx, fz = _rot(x, z, 0, 0.025, yaw)
    S.box((fx, 0.78, fz), (w - 0.08, 0.99, 0.01), "#fbfbfb", yaw=yaw)
    tx, tz = _rot(x, z, 0, 0.06, yaw)
    S.box((tx, 0.72, tz), (w * 0.6, 0.03, 0.08), "#95a5a6", yaw=yaw)
    if scribbles == "chart":
        # A rising sales chart, with one bar that fell off a cliff.
        heights = [0.25, 0.4, 0.55, 0.7, 0.12]
        for i, hh in enumerate(heights):
            bx, bz = _rot(x, z, -w * 0.35 + i * (w * 0.16), 0.032, yaw)
            S.box((bx, 0.88, bz), (w * 0.1, hh, 0.01), "#e74c3c" if i == 4 else "#0984e3", yaw=yaw)
    elif isinstance(scribbles, (list, tuple)):  # lines of marker writing
        for i, (line, c) in enumerate(scribbles):
            lx, lz = _rot(x, z, -w / 2 + 0.12, 0.034, yaw)
            S.text(line, (lx, 1.58 - i * 0.2, lz), 0.15 if i == 0 else 0.12, c, yaw=yaw, align="LEFT")
    else:
        for i in range(5):
            lx, lz = _rot(x, z, -w * 0.3 + (i % 2) * 0.1, 0.032, yaw)
            S.box((lx, 1.55 - i * 0.14, lz), (w * (0.55 - i * 0.06), 0.03, 0.01), ["#2d3436", "#c0392b", "#2980b9"][i % 3], yaw=yaw)


def couch(S, x, z, yaw=0.0, color="#16a085", length=2.2):
    S.box((x, 0.08, z), (length, 0.36, 0.9), color, yaw=yaw, bevel=0.04)
    bx, bz = _rot(x, z, 0, -0.36, yaw)
    S.box((bx, 0.3, bz), (length, 0.55, 0.22), color, yaw=yaw, bevel=0.05)
    for dx in (-length / 2, length / 2):
        ax, az = _rot(x, z, dx, 0, yaw)
        S.box((ax, 0.08, az), (0.22, 0.5, 0.9), color, yaw=yaw, bevel=0.05)
    dark = "#0e6655"
    for dx in (-length / 4, length / 4):
        cx, cz = _rot(x, z, dx, 0.05, yaw)
        S.box((cx, 0.44, cz), (length / 2 - 0.2, 0.1, 0.62), dark if color == "#16a085" else color, yaw=yaw, bevel=0.03)
    for dx in (-length / 2 + 0.1, length / 2 - 0.1):
        for dz in (-0.35, 0.35):
            fx, fz = _rot(x, z, dx, dz, yaw)
            S.cyl((fx, 0, fz), 0.03, 0.08, "#2d3436", segs=6)


def coffee_table(S, x, z, yaw=0.0, w=1.1, d=0.6, color="#a1785c"):
    S.box((x, 0.36, z), (w, 0.05, d), color, yaw=yaw, bevel=0.01)
    for dx in (-w / 2 + 0.06, w / 2 - 0.06):
        for dz in (-d / 2 + 0.06, d / 2 - 0.06):
            lx, lz = _rot(x, z, dx, dz, yaw)
            S.box((lx, 0, lz), (0.05, 0.36, 0.05), "#5d4037", yaw=yaw)


def bookshelf(S, x, z, yaw=0.0, w=1.2, h=1.8, seed=1):
    rnd = random.Random(seed)
    S.box((x, 0, z), (w, h, 0.36), "#8d6e63", yaw=yaw, tex=wood("dark"))
    for i in range(4):
        y = 0.08 + i * (h - 0.1) / 4
        fx, fz = _rot(x, z, 0, 0.02, yaw)
        S.box((fx, y, fz), (w - 0.08, 0.03, 0.32), "#6d4c41", yaw=yaw)
        bx = -w / 2 + 0.08
        while bx < w / 2 - 0.12:
            bw = rnd.uniform(0.05, 0.11)
            bh = rnd.uniform(0.22, 0.34)
            px, pz = _rot(x, z, bx + bw / 2, 0.04, yaw)
            S.box((px, y + 0.03, pz), (bw, bh, 0.24), rnd.choice(["#c0392b", "#2980b9", "#27ae60", "#f39c12", "#8e44ad", "#ecf0f1"]), yaw=yaw)
            bx += bw + 0.01


def speaker_tower(S, x, z, yaw=0.0, h=2.3, glow="#ff5fa2"):
    S.box((x, 0, z), (1.0, h, 0.85), "#1e1e24", yaw=yaw, bevel=0.03)
    for i, (y, r) in enumerate([(h * 0.25, 0.36), (h * 0.55, 0.36), (h * 0.82, 0.18)]):
        fx, fz = _rot(x, z, 0, 0.43, yaw)
        S.cyl((fx, y, fz), r, 0.04, "#333340", segs=18, axis="z")
        fx2, fz2 = _rot(x, z, 0, 0.455, yaw)
        S.cyl((fx2, y, fz2), r * 0.82, 0.02, glow, segs=18, axis="z", emit=2.2)
        fx3, fz3 = _rot(x, z, 0, 0.47, yaw)
        S.cyl((fx3, y, fz3), r * 0.55, 0.02, "#111116", segs=16, axis="z")


def dj_table(S, x, z, yaw=0.0):
    S.box((x, 0, z), (2.0, 0.92, 0.8), "#2d2d35", yaw=yaw, bevel=0.02)
    fx, fz = _rot(x, z, 0, 0.405, yaw)
    S.box((fx, 0.25, fz), (1.8, 0.45, 0.01), "#ff5fa2", yaw=yaw, emit=1.8)
    for dx in (-0.55, 0.55):
        tx, tz = _rot(x, z, dx, 0, yaw)
        S.cyl((tx, 0.92, tz), 0.26, 0.03, "#111111", segs=20)
        S.cyl((tx, 0.95, tz), 0.08, 0.01, "#ff5fa2", segs=12, emit=2.0)
    lx, lz = _rot(x, z, 0, -0.1, yaw)
    S.box((lx, 0.92, lz), (0.36, 0.02, 0.26), "#b2bec3", yaw=yaw)
    S.box((lx, 0.94, lz - 0.1), (0.34, 0.22, 0.02), "#b2bec3", yaw=yaw, pitch=-15)


def string_lights(S, x0, x1, z, y, n=14, sag=0.25):
    for i in range(n):
        t = i / (n - 1)
        x = x0 + (x1 - x0) * t
        yy = y - sag * 4 * t * (1 - t)
        S.sph((x, yy, z), (0.06, 0.08, 0.06), ["#ffd23f", "#ff5fa2", "#4fc3ff", "#7cff4f"][i % 4], segs=6, emit=3.0)
        if i < n - 1:
            nx = x0 + (x1 - x0) * (i + 1) / (n - 1)
            S.box(((x + nx) / 2, yy + 0.06, z), (abs(nx - x), 0.012, 0.012), "#2d3436")


def ping_pong_table(S, x, z, yaw=0.0):
    S.box((x, 0.72, z), (2.74, 0.04, 1.52), "#1e6b3a", yaw=yaw)
    for dx in (-1.1, 1.1):
        for dz in (-0.6, 0.6):
            lx, lz = _rot(x, z, dx, dz, yaw)
            S.box((lx, 0, lz), (0.05, 0.72, 0.05), "#2d3436", yaw=yaw)
    S.box((x, 0.76, z), (0.02, 0.15, 1.6), "#ecf0f1", yaw=yaw)
    S.decal(x, z, 2.7, 0.02, "#ffffff", yaw=yaw, y=0.742)
    S.sph((x + 0.5, 0.9, z + 0.2), (0.025, 0.025, 0.025), "#ff9a1f", segs=6)


def bean_bag(S, x, z, color="#e84393"):
    S.sph((x, 0.25, z), (0.45, 0.3, 0.42), color, segs=12)
    S.sph((x, 0.42, z + 0.12), (0.32, 0.18, 0.28), color, segs=10)


def meeting_table(S, x, z, length=5.0, width=1.6, yaw=0.0, color="#5d4037"):
    S.box((x, 0.72, z), (length, 0.06, width), color, yaw=yaw, bevel=0.02, tex=wood("dark"))
    for dx in (-length / 3, length / 3):
        px, pz = _rot(x, z, dx, 0, yaw)
        S.box((px, 0, pz), (0.5, 0.72, 0.5), "#3e2723", yaw=yaw)


def laptop(S, x, y, z, yaw=0.0, screen="#7fd4ff"):
    S.box((x, y, z), (0.34, 0.02, 0.24), "#b2bec3", yaw=yaw)
    bx, bz = _rot(x, z, 0, -0.12, yaw)
    S.box((bx, y + 0.01, bz), (0.34, 0.22, 0.015), "#b2bec3", yaw=yaw, pitch=-12)
    sx, sz = _rot(x, z, 0, -0.105, yaw)
    S.box((sx, y + 0.03, sz), (0.3, 0.17, 0.006), screen, yaw=yaw, pitch=-12, emit=1.8)


def tv_stand(S, x, z, yaw=0.0, w=3.2, h=1.8, screen="#2e86de", caption=None):
    for dx in (-0.5, 0.5):
        px, pz = _rot(x, z, dx, 0, yaw)
        S.box((px, 0, pz), (0.08, 1.2, 0.08), "#2d3436", yaw=yaw)
        S.box((px, 0, pz), (0.12, 0.05, 0.8), "#2d3436", yaw=yaw)
    S.box((x, 0.9, z), (w, h, 0.08), "#111111", yaw=yaw, bevel=0.01)
    fx, fz = _rot(x, z, 0, 0.045, yaw)
    S.box((fx, 0.96, fz), (w - 0.14, h - 0.12, 0.01), screen, yaw=yaw, emit=1.4)
    # A chart on the screen (above the caption, if there is one: the bottom of the screen
    # is what the battle camera sees best)
    y0, k = (1.42, 0.62) if caption else (1.1, 1.0)
    for i, hh in enumerate([0.3, 0.5, 0.42, 0.75, 0.95]):
        bx, bz = _rot(x, z, -w * 0.32 + i * w * 0.15, 0.052, yaw)
        S.box((bx, y0, bz), (w * 0.08, hh * k, 0.006), "#ffffff", yaw=yaw, emit=1.5)
    if caption:
        tx, tz = _rot(x, z, 0, 0.055, yaw)
        S.text(caption, (tx, 1.1, tz), 0.28, "#ffffff", yaw=yaw, emit=2.5)


def credenza(S, x, z, yaw=0.0, w=2.0):
    S.box((x, 0, z), (w, 0.8, 0.5), "#6d4c41", yaw=yaw, bevel=0.02, tex=wood("dark"))
    for dx in (-w / 4, w / 4):
        fx, fz = _rot(x, z, dx, 0.255, yaw)
        S.box((fx, 0.1, fz), (w / 2 - 0.1, 0.6, 0.01), "#795548", yaw=yaw)


def printer(S, x, z, yaw=0.0):
    S.box((x, 0, z), (0.9, 0.75, 0.7), "#dfe6e9", yaw=yaw, bevel=0.02)
    S.box((x, 0.75, z), (0.8, 0.28, 0.6), "#b2bec3", yaw=yaw, bevel=0.02)
    fx, fz = _rot(x, z, 0.25, 0.31, yaw)
    S.box((fx, 1.03, fz), (0.18, 0.02, 0.12), "#2ecc71", yaw=yaw, emit=1.5)
    px, pz = _rot(x, z, 0, 0.2, yaw)
    S.box((px, 0.85, pz), (0.45, 0.02, 0.3), "#ffffff", yaw=yaw)


def cardboard_box(S, x, z, yaw=0.0, size=0.5, y=0.0):
    S.box((x, y, z), (size, size * 0.7, size * 0.8), "#c8a165", yaw=yaw)
    S.box((x, y + size * 0.7, z), (size + 0.01, 0.012, 0.06), "#b38b4f", yaw=yaw)


def desk_lamp(S, x, y, z, yaw=0.0):
    S.cyl((x, y, z), 0.09, 0.03, "#2d3436", segs=10)
    S.box((x, y + 0.03, z), (0.03, 0.35, 0.03), "#2d3436", yaw=yaw, roll=15)
    hx, hz = _rot(x, z, 0.08, 0.05, yaw)
    S.cyl((hx, y + 0.34, hz), 0.08, 0.12, "#2d3436", segs=10, r2=0.04)
    S.sph((hx, y + 0.34, hz), (0.05, 0.03, 0.05), "#fff3b0", segs=8, emit=4.0)


def golf_bag(S, x, z, yaw=0.0, color="#1e3799"):
    S.cyl((x, 0, z), 0.17, 0.95, color, segs=10, yaw=yaw)
    S.cyl((x, 0.1, z), 0.175, 0.05, "#ecf0f1", segs=10)
    S.cyl((x, 0.88, z), 0.175, 0.06, "#ecf0f1", segs=10)
    for i, (dx, dz) in enumerate([(-0.06, 0.03), (0.05, 0.05), (0.0, -0.06), (0.07, -0.02)]):
        S.cyl((x + dx, 0.9, z + dz), 0.012, 0.45, "#bdc3c7", segs=5, metal=0.8)
        S.box((x + dx, 1.34, z + dz), (0.09, 0.05, 0.05), "#2d3436" if i % 2 else "#dfe6e9", yaw=yaw + i * 40, metal=0.6)


def putting_green(S, x, z, w=3.2, d=1.1, yaw=0.0):
    S.box((x, 0, z), (w, 0.03, d), "#3fa34d", yaw=yaw, bevel=0.01)
    hx, hz = _rot(x, z, w * 0.35, 0, yaw)
    S.cyl((hx, 0.025, hz), 0.07, 0.01, "#111111", segs=12)
    S.cyl((hx, 0.03, hz), 0.012, 0.7, "#ecf0f1", segs=6)
    S.box((hx + 0.13, 0.6, hz), (0.24, 0.14, 0.01), "#e74c3c", yaw=yaw)
    for (dx, dz) in [(-w * 0.3, 0.2), (0.1, -0.25), (w * 0.1, 0.3)]:
        bx, bz = _rot(x, z, dx, dz, yaw)
        S.sph((bx, 0.055, bz), (0.022, 0.022, 0.022), "#ffffff", segs=6)


def car(S, x, z, yaw=0.0, color="#2e86c1"):
    """A little sedan pointing along +x (yaw 0)."""
    S.box((x, 0.25, z), (3.8, 0.6, 1.7), color, yaw=yaw, bevel=0.12)
    cx, cz = _rot(x, z, -0.2, 0, yaw)
    S.box((cx, 0.82, cz), (2.0, 0.55, 1.5), color, yaw=yaw, bevel=0.12)
    for dz in (-0.76, 0.76):
        wx, wz = _rot(x, z, -0.2, dz, yaw)
        S.box((wx, 0.88, wz), (1.7, 0.38, 0.02), "#2c3e50", yaw=yaw, glass=True)
    for dx in (-0.85, 0.85):
        fx, fz = _rot(x, z, -0.2 + dx * 1.18, 0, yaw)
        S.box((fx, 0.88, fz), (0.02, 0.38, 1.3), "#2c3e50", yaw=yaw, glass=True)
    for dx in (-1.2, 1.2):
        for dz in (-0.8, 0.8):
            wx, wz = _rot(x, z, dx, dz, yaw)
            S.cyl((wx, 0.32, wz), 0.32, 0.22, "#1a1a1a", segs=12, axis="z", yaw=yaw)
            S.cyl((wx, 0.32, wz + (0.12 if dz > 0 else -0.12)), 0.16, 0.02, "#bdc3c7", segs=10, axis="z", yaw=yaw)
    for dz in (-0.55, 0.55):
        hx, hz = _rot(x, z, 1.9, dz, yaw)
        S.box((hx, 0.5, hz), (0.03, 0.14, 0.3), "#fff7c2", yaw=yaw, emit=2.0)
        tx, tz = _rot(x, z, -1.9, dz, yaw)
        S.box((tx, 0.5, tz), (0.03, 0.14, 0.3), "#e74c3c", yaw=yaw, emit=1.5)


def semi_truck(S, x, z, yaw=0.0, cab="#c0392b", trailer="#ecf0f1"):
    """A semi with its cab at +x (yaw 0)."""
    # Trailer
    tx, tz = _rot(x, z, -3.0, 0, yaw)
    S.box((tx, 1.0, tz), (8.0, 2.7, 2.5), trailer, yaw=yaw, bevel=0.04)
    sx, sz = _rot(x, z, -3.0, 1.26, yaw)
    S.box((sx, 2.1, sz), (7.4, 0.35, 0.02), "#e74c3c", yaw=yaw)
    S.box((sx, 1.6, sz), (7.4, 0.12, 0.02), "#2c3e50", yaw=yaw)
    for dx in (-6.2, -5.1):
        for dz in (-1.0, 1.0):
            wx, wz = _rot(x, z, dx, dz, yaw)
            S.cyl((wx, 0.5, wz), 0.5, 0.35, "#1a1a1a", segs=14, axis="z", yaw=yaw)
    lx, lz = _rot(x, z, 0.2, 0, yaw)
    S.box((lx, 0.55, lz), (1.2, 0.3, 2.3), "#555555", yaw=yaw)
    # Cab
    cx, cz = _rot(x, z, 2.4, 0, yaw)
    S.box((cx, 0.55, cz), (2.2, 2.3, 2.5), cab, yaw=yaw, bevel=0.1)
    hx, hz = _rot(x, z, 4.1, 0, yaw)
    S.box((hx, 0.55, hz), (1.4, 1.35, 2.2), cab, yaw=yaw, bevel=0.12)
    gx, gz = _rot(x, z, 4.81, 0, yaw)
    S.box((gx, 0.7, gz), (0.04, 0.95, 1.5), "#bdc3c7", yaw=yaw, metal=0.9)
    for dz in (-0.85, 0.85):
        lx2, lz2 = _rot(x, z, 4.82, dz, yaw)
        S.box((lx2, 1.2, lz2), (0.04, 0.2, 0.3), "#fff7c2", yaw=yaw, emit=2.0)
    wx, wz = _rot(x, z, 3.51, 0, yaw)
    S.box((wx, 1.75, wz), (0.03, 0.75, 2.2), "#34495e", yaw=yaw, glass=True)
    for dz in (-1.15, 1.15):
        px, pz = _rot(x, z, 1.4, dz, yaw)
        S.cyl((px, 1.0, pz), 0.11, 2.6, "#bdc3c7", segs=8, metal=0.9)
        fx, fz = _rot(x, z, 2.2, dz * 1.04, yaw)
        S.cyl((fx, 0.75, fz), 0.32, 1.2, "#bdc3c7", segs=12, axis="x", yaw=yaw, metal=0.8)
    for dx in (2.0, 4.0):
        for dz in (-1.1, 1.1):
            wx2, wz2 = _rot(x, z, dx, dz, yaw)
            S.cyl((wx2, 0.55, wz2), 0.55, 0.38, "#1a1a1a", segs=14, axis="z", yaw=yaw)
            S.cyl((wx2, 0.55, wz2 + (0.2 if dz > 0 else -0.2)), 0.26, 0.02, "#bdc3c7", segs=10, axis="z", yaw=yaw, metal=0.8)


def lamp_post(S, x, z, yaw=0.0, h=4.2):
    S.cyl((x, 0, z), 0.16, 0.4, "#7f8c8d", segs=8)
    S.cyl((x, 0, z), 0.07, h, "#95a5a6", segs=8)
    ax, az = _rot(x, z, 0.5, 0, yaw)
    S.box((ax, h - 0.05, az), (1.0, 0.06, 0.06), "#95a5a6", yaw=yaw)
    hx, hz = _rot(x, z, 1.0, 0, yaw)
    S.box((hx, h - 0.2, hz), (0.5, 0.15, 0.25), "#7f8c8d", yaw=yaw)
    S.box((hx, h - 0.22, hz), (0.42, 0.03, 0.2), "#fff3b0", yaw=yaw, emit=4.0)


def cone(S, x, z):
    S.box((x, 0, z), (0.38, 0.04, 0.38), "#e67e22")
    S.cyl((x, 0.04, z), 0.15, 0.55, "#e67e22", segs=10, r2=0.03)
    S.cyl((x, 0.28, z), 0.105, 0.08, "#ffffff", segs=10, r2=0.09)


def dumpster(S, x, z, yaw=0.0):
    S.box((x, 0.12, z), (1.9, 1.15, 1.1), "#1e8449", yaw=yaw, bevel=0.03)
    S.box((x, 1.27, z), (1.95, 0.06, 1.15), "#145a32", yaw=yaw, pitch=4)
    for dx in (-0.8, 0.8):
        for dz in (-0.45, 0.45):
            wx, wz = _rot(x, z, dx, dz, yaw)
            S.cyl((wx, 0.07, wz), 0.07, 0.05, "#1a1a1a", segs=8, axis="z")


def counter(S, x, z, length, yaw=0.0, front="#c0392b", stripe="#ffd23f", top="#ecf0f1"):
    S.box((x, 0, z), (length, 1.0, 0.9), front, yaw=yaw, bevel=0.02)
    fx, fz = _rot(x, z, 0, 0.455, yaw)
    S.box((fx, 0.62, fz), (length, 0.12, 0.01), stripe, yaw=yaw)
    S.box((fx, 0.02, fz), (length, 0.1, 0.01), "#7b241c", yaw=yaw)
    S.box((x, 1.0, z), (length + 0.1, 0.05, 1.0), top, yaw=yaw, bevel=0.01)


def register(S, x, y, z, yaw=0.0):
    S.box((x, y, z), (0.42, 0.14, 0.38), "#2d3436", yaw=yaw, bevel=0.01)
    sx, sz = _rot(x, z, 0, -0.08, yaw)
    S.box((sx, y + 0.14, sz), (0.36, 0.24, 0.03), "#2d3436", yaw=yaw, pitch=-15)
    fx, fz = _rot(x, z, 0, -0.06, yaw)
    S.box((fx, y + 0.17, fz), (0.3, 0.18, 0.01), "#55efc4", yaw=yaw, pitch=-15, emit=1.8)


def sauce_display(S, x, y, z, size=1.0):
    """The Village Sauce, on a little pedestal. The whole point of the game."""
    k = size
    S.cyl((x, y, z), 0.22 * k, 0.1 * k, "#d4af37", segs=14, metal=0.8)
    S.cyl((x, y + 0.1 * k, z), 0.12 * k, 0.36 * k, "#ff7a1a", segs=14, smooth=True, emit=2.2)
    S.cyl((x, y + 0.46 * k, z), 0.09 * k, 0.08 * k, "#ff7a1a", segs=12, r2=0.04 * k, emit=2.2)
    S.cyl((x, y + 0.54 * k, z), 0.04 * k, 0.06 * k, "#ffffff", segs=8)
    S.box((x, y + 0.2 * k, z + 0.12 * k), (0.16 * k, 0.12 * k, 0.01), "#fff3d6")


def fryer(S, x, z, yaw=0.0):
    S.box((x, 0, z), (0.8, 0.95, 0.7), "#b2bec3", yaw=yaw, metal=0.7)
    for dx in (-0.18, 0.18):
        px, pz = _rot(x, z, dx, 0, yaw)
        S.box((px, 0.9, pz), (0.3, 0.06, 0.5), "#f1c40f", yaw=yaw, emit=0.4)
        bx, bz = _rot(x, z, dx, 0.15, yaw)
        S.box((bx, 0.98, bz), (0.26, 0.16, 0.32), "#7f8c8d", yaw=yaw, metal=0.6)


def grill(S, x, z, yaw=0.0, w=1.4):
    S.box((x, 0, z), (w, 0.88, 0.75), "#b2bec3", yaw=yaw, metal=0.7)
    S.box((x, 0.88, z), (w, 0.05, 0.7), "#2d3436", yaw=yaw)
    for i in range(3):
        px, pz = _rot(x, z, -w * 0.3 + i * w * 0.3, 0, yaw)
        S.cyl((px, 0.93, pz), 0.11, 0.04, "#5d4037", segs=10)
        S.cyl((px, 0.97, pz), 0.12, 0.05, "#f0b35b", segs=10, r2=0.11)
    hx, hz = _rot(x, z, 0, -0.25, yaw)
    S.box((hx, 1.7, hz), (w + 0.2, 0.35, 0.6), "#95a5a6", yaw=yaw, metal=0.6)


def soda_fountain(S, x, z, yaw=0.0):
    S.box((x, 0, z), (1.1, 0.9, 0.6), "#7f8c8d", yaw=yaw)
    S.box((x, 0.9, z), (1.0, 0.75, 0.5), "#2c3e50", yaw=yaw, bevel=0.02)
    for i, c in enumerate(["#e74c3c", "#f39c12", "#27ae60", "#2980b9"]):
        px, pz = _rot(x, z, -0.36 + i * 0.24, 0.26, yaw)
        S.box((px, 1.3, pz), (0.18, 0.28, 0.01), c, yaw=yaw, emit=1.2)
        nx, nz = _rot(x, z, -0.36 + i * 0.24, 0.2, yaw)
        S.box((nx, 1.08, nz), (0.04, 0.1, 0.06), "#bdc3c7", yaw=yaw)
    for i in range(4):
        cx, cz = _rot(x, z, 0.62, 0.0, yaw)
        S.cyl((cx, 0.9 + i * 0.09, cz), 0.06, 0.1, "#ffffff", segs=8, r2=0.05)


def heat_lamp_shelf(S, x, z, w=2.4, yaw=0.0):
    S.box((x, 1.2, z), (w, 0.04, 0.45), "#bdc3c7", yaw=yaw, metal=0.7)
    for dx in (-w / 2 + 0.05, w / 2 - 0.05):
        px, pz = _rot(x, z, dx, 0, yaw)
        S.box((px, 1.0, pz), (0.04, 0.9, 0.04), "#95a5a6", yaw=yaw)
    S.box((x, 1.75, z), (w, 0.06, 0.4), "#ff8c42", yaw=yaw, emit=3.0)
    for i in range(4):
        bx, bz = _rot(x, z, -w * 0.35 + i * w * 0.23, 0.05, yaw)
        S.sph((bx, 1.29, bz), (0.12, 0.05, 0.12), "#f0b35b", segs=10)
        S.cyl((bx, 1.24, bz), 0.12, 0.03, "#5d4037", segs=10)
        S.sph((bx, 1.22, bz), (0.12, 0.04, 0.12), "#e8a74c", segs=10)


def booth(S, x, z, yaw=0.0, seat="#c0392b", table="#ecf0f1"):
    """Two high-backed benches facing each other with a table between (along z)."""
    for dz in (-0.85, 0.85):
        bx, bz = _rot(x, z, 0, dz, yaw)
        S.box((bx, 0, bz), (1.5, 0.45, 0.55), seat, yaw=yaw, bevel=0.04)
        ox, oz = _rot(x, z, 0, dz * 1.32, yaw)
        S.box((ox, 0.3, oz), (1.5, 0.95, 0.18), seat, yaw=yaw, bevel=0.05)
        S.box((ox, 1.25, oz), (1.52, 0.05, 0.2), "#7b241c", yaw=yaw)
    S.box((x, 0.72, z), (1.3, 0.05, 0.8), table, yaw=yaw, bevel=0.01)
    S.cyl((x, 0, z), 0.08, 0.72, "#95a5a6", segs=8)
    condiments(S, x + 0.2, 0.745, z)


def condiments(S, x, y, z):
    S.cyl((x, y, z), 0.035, 0.18, "#e74c3c", segs=8, r2=0.025)
    S.cyl((x + 0.09, y, z), 0.035, 0.18, "#f1c40f", segs=8, r2=0.025)
    S.cyl((x - 0.09, y, z), 0.035, 0.16, "#ff7a1a", segs=8, r2=0.025)


def diner_table(S, x, z, color="#ecf0f1"):
    S.cyl((x, 0, z), 0.3, 0.05, "#95a5a6", segs=12)
    S.cyl((x, 0.05, z), 0.05, 0.68, "#95a5a6", segs=8)
    S.cyl((x, 0.72, z), 0.48, 0.04, color, segs=16)
    condiments(S, x, 0.76, z)
    for i in range(3):
        a = math.radians(i * 120 + 30)
        sx, sz = x + math.cos(a) * 0.8, z + math.sin(a) * 0.8
        S.cyl((sx, 0, sz), 0.04, 0.6, "#95a5a6", segs=6)
        S.cyl((sx, 0.6, sz), 0.2, 0.08, "#c0392b", segs=12)


def neon_sign(S, x, y, z, yaw=0.0, w=1.4, h=0.8, frame="#ff5fa2", fill="#ffd23f"):
    """A glowing burger sign: a neon frame with a bun-patty-bun inside."""
    S.box((x, y, z), (w, h, 0.05), "#1a1a22", yaw=yaw)
    for (dx, dy, ww, hh) in [(0, 0.04, w - 0.1, 0.04), (0, h - 0.08, w - 0.1, 0.04),
                             (-w / 2 + 0.07, 0.04, 0.04, h - 0.08), (w / 2 - 0.07, 0.04, 0.04, h - 0.08)]:
        px, pz = _rot(x, z, dx, 0.035, yaw)
        S.box((px, y + dy, pz), (ww, hh, 0.02), frame, yaw=yaw, emit=4.0)
    for i, (dy, c, ww) in enumerate([(0.42, fill, 0.6), (0.33, "#ff7a1a", 0.64), (0.24, fill, 0.6)]):
        px, pz = _rot(x, z, 0, 0.04, yaw)
        S.box((px, y + h * dy / 0.8 - 0.06, pz), (ww * w / 1.4, 0.07, 0.02), c, yaw=yaw, emit=4.0)


def trash_can(S, x, z, color="#2c3e50"):
    S.cyl((x, 0, z), 0.26, 0.85, color, segs=12, r2=0.3)
    S.cyl((x, 0.85, z), 0.31, 0.12, color, segs=12, r2=0.2)
    S.box((x, 0.9, z + 0.2), (0.3, 0.04, 0.02), "#ffd23f")


def a_frame_sign(S, x, z, yaw=0.0, text=None):
    """A chalkboard sign on the floor (with chalk lines, or lines of text)."""
    S.box((x, 0, z), (0.7, 1.05, 0.04), "#8d6e63", yaw=yaw, pitch=-12)
    fx, fz = _rot(x, z, 0, 0.03, yaw)
    S.box((fx, 0.08, fz), (0.6, 0.85, 0.01), "#2d3436", yaw=yaw, pitch=-12)
    if text:
        rows = text.split("\n")
        for i, row in enumerate(rows):
            lx, lz = _rot(x, z, 0, 0.038 - (0.66 - i * 0.17 - 0.505) * math.tan(math.radians(12)), yaw)
            S.text(row, (lx, 0.66 - i * 0.17, lz), min(0.11, 0.5 / (0.62 * max(len(r) for r in rows))),
                   ["#ffd23f", "#ffffff", "#ff7a1a", "#ffffff"][i % 4], yaw=yaw, pitch=-12)
        return
    for i, c in enumerate(["#ffd23f", "#ffffff", "#ffffff", "#ff7a1a"]):
        lx, lz = _rot(x, z, 0, 0.04 - i * 0.022, yaw)
        S.box((lx, 0.75 - i * 0.16, lz), (0.42 - (i % 2) * 0.1, 0.035, 0.01), c, yaw=yaw, pitch=-12)


def window_wall(S, z, x0, x1, h=3.2, sill=0.9, win_h=1.9, color="#d9d4ca", sky="#bfe6ff", every=2.2, mood=None):
    """A back wall with a row of windows: the city outside (mood: textures.SKYLINES, or
    "facade" for the office's own windows from outside), or just a glowing sky color."""
    S.box(((x0 + x1) / 2, 0, z), (x1 - x0, sill, 0.25), color)
    S.box(((x0 + x1) / 2, sill + win_h, z), (x1 - x0, h - sill - win_h, 0.25), color)
    S.box(((x0 + x1) / 2, 0, z + 0.13), (x1 - x0, 0.12, 0.02), "#6f6a62")
    n = int((x1 - x0) / every)
    for i in range(n + 1):
        x = x0 + i * (x1 - x0) / n
        S.box((x, sill, z), (0.14, win_h, 0.27), color)
    if mood:
        S.box(((x0 + x1) / 2, sill, z - 0.02), (x1 - x0, win_h, 0.04), sky, tex=view(mood))
    else:
        S.box(((x0 + x1) / 2, sill, z - 0.02), (x1 - x0, win_h, 0.04), sky, emit=0.8)
    S.box(((x0 + x1) / 2, sill - 0.02, z + 0.14), (x1 - x0, 0.04, 0.12), "#ecf0f1")


# --------------------------------------------------------------------- signs and set dressing
def sign(S, x, y, z, text, w=1.2, h=0.4, bg="#2d3436", fg="#ffffff", yaw=0.0, emit=0.0, frame=None, size=None):
    """A flat sign facing +z, its bottom edge at y: a panel with centered lines of text."""
    S.box((x, y, z), (w, h, 0.03), frame or bg, yaw=yaw)
    if frame:
        fx, fz = _rot(x, z, 0, 0.016, yaw)
        S.box((fx, y + 0.03, fz), (w - 0.06, h - 0.06, 0.005), bg, yaw=yaw)
    rows = text.split("\n")
    s = size or min(h * 0.7 / (len(rows) * 1.05), (w - 0.08) / (0.62 * max(len(r) for r in rows)))
    cap = 0.72 * s
    first = y + h / 2 + (cap + (len(rows) - 1) * 1.2 * s) / 2 - cap
    tx, tz = _rot(x, z, 0, 0.024, yaw)
    for i, row in enumerate(rows):
        S.text(row, (tx, first - i * 1.2 * s, tz), s, fg, yaw=yaw, emit=emit)


def motivational_poster(S, x, y, z, word, sub="", yaw=0.0, sky="#2e86de", sun="#f6e58d", ground="#1e3799"):
    """The classic office poster: a black border, a picture, and one big word."""
    w, h = 0.78, 1.04
    S.box((x, y, z), (w, h, 0.025), "#111111", yaw=yaw)
    fx, fz = _rot(x, z, 0, 0.014, yaw)
    S.box((fx, y + 0.3, fz), (w - 0.12, h - 0.4, 0.004), sky, yaw=yaw)
    gx, gz = _rot(x, z, 0, 0.018, yaw)
    S.box((gx, y + 0.3, gz), (w - 0.12, 0.13, 0.004), ground, yaw=yaw)
    sx, sz = _rot(x, z, 0.12, 0.02, yaw)
    S.cyl((sx, y + 0.66, sz), 0.07, 0.004, sun, segs=16, axis="z", yaw=yaw)
    tx, tz = _rot(x, z, 0, 0.02, yaw)
    S.text(word, (tx, y + 0.14, tz), min(0.1, 0.6 / max(1, len(word)) * 1.4), "#ffffff", yaw=yaw)
    if sub:
        S.text(sub, (tx, y + 0.06, tz), min(0.032, 0.62 / max(1, len(sub)) * 1.5), "#b2bec3", yaw=yaw)


def incident_board(S, x, y, z, days="0", what="A REPLY-ALL", yaw=0.0):
    """DAYS WITHOUT <what>: <days>."""
    S.box((x, y, z), (1.15, 0.78, 0.03), "#ecf0f1", yaw=yaw)
    fx, fz = _rot(x, z, 0, 0.016, yaw)
    S.box((fx, y + 0.6, fz), (1.15, 0.18, 0.005), "#27ae60", yaw=yaw)
    tx, tz = _rot(x, z, 0, 0.022, yaw)
    S.text("DAYS WITHOUT", (tx, y + 0.645, tz), 0.09, "#ffffff", yaw=yaw)
    S.text(days, (tx, y + 0.2, tz), 0.42, "#c0392b", yaw=yaw)
    S.text(what, (tx, y + 0.07, tz), min(0.075, 1.0 / max(1, len(what)) * 1.5), "#2d3436", yaw=yaw)


def wall_clock(S, x, y, z, r=0.24, hour=10, minute=10):
    """A round wall clock facing +z, centered at height y."""
    S.cyl((x, y, z), r, 0.05, "#2d3436", segs=24, axis="z")
    S.cyl((x, y, z + 0.026), r * 0.88, 0.01, "#fdfdfd", segs=24, axis="z")
    for a, length, wd in ((hour * 30 + minute * 0.5, r * 0.5, 0.024), (minute * 6, r * 0.75, 0.016)):
        c = (x + math.sin(math.radians(a)) * length / 2, y + math.cos(math.radians(a)) * length / 2)
        S.box((c[0], c[1] - length / 2, z + 0.035), (wd, length, 0.006), "#2d3436", roll=a)
    for i in range(12):
        a = math.radians(i * 30)
        S.box((x + math.sin(a) * r * 0.76, y + math.cos(a) * r * 0.76 - 0.015, z + 0.033), (0.012, 0.03, 0.004), "#2d3436", roll=i * 30)


def exit_sign(S, x, y, z, yaw=0.0):
    S.box((x, y, z), (0.56, 0.22, 0.07), "#ecf0f1", yaw=yaw)
    fx, fz = _rot(x, z, 0, 0.036, yaw)
    S.box((fx, y + 0.02, fz), (0.5, 0.18, 0.005), "#1e8449", yaw=yaw, emit=1.2)
    tx, tz = _rot(x, z, 0, 0.042, yaw)
    S.text("EXIT", (tx, y + 0.055, tz), 0.15, "#ffffff", yaw=yaw, emit=2.5)


def fire_extinguisher(S, x, z, yaw=0.0):
    S.cyl((x, 0, z), 0.085, 0.48, "#c0392b", segs=12)
    S.cyl((x, 0.48, z), 0.03, 0.07, "#2d3436", segs=8)
    hx, hz = _rot(x, z, 0.05, 0, yaw)
    S.box((hx, 0.53, hz), (0.13, 0.02, 0.03), "#2d3436", yaw=yaw)
    nx, nz = _rot(x, z, -0.07, 0.02, yaw)
    S.box((nx, 0.18, nz), (0.025, 0.32, 0.025), "#2d3436", yaw=yaw)


def wet_floor_sign(S, x, z, yaw=0.0):
    """A yellow CAUTION A-frame."""
    for s in (-1, 1):
        fx, fz = _rot(x, z, 0, s * 0.09, yaw)
        S.box((fx, 0, fz), (0.34, 0.66, 0.02), "#f1c40f", yaw=yaw, pitch=-s * 12)
    for word, y, s in (("CAUTION", 0.46, 0.065), ("WET FLOOR", 0.36, 0.05)):
        tx, tz = _rot(x, z, 0, 0.104 - (y - 0.33) * math.tan(math.radians(12)), yaw)
        S.text(word, (tx, y, tz), s, "#2d3436", yaw=yaw, pitch=-12)


def recycle_bin(S, x, z, color="#2e86de"):
    S.box((x, 0, z), (0.42, 0.7, 0.42), color, bevel=0.02)
    S.box((x, 0.7, z), (0.45, 0.04, 0.45), "#1b4f72")
    S.box((x, 0.72, z), (0.24, 0.012, 0.06), "#0b0b0b")


def bulletin_board(S, x, y, z, yaw=0.0, w=1.3, h=0.85, seed=1):
    """A cork board with pinned notes."""
    rnd = random.Random(seed)
    S.box((x, y, z), (w, h, 0.03), "#8d6e63", yaw=yaw)
    fx, fz = _rot(x, z, 0, 0.016, yaw)
    S.box((fx, y + 0.04, fz), (w - 0.08, h - 0.08, 0.005), "#c8a165", yaw=yaw)
    for i in range(7):
        dx, dy = rnd.uniform(-w / 2 + 0.15, w / 2 - 0.15), rnd.uniform(0.12, h - 0.25)
        px, pz = _rot(x, z, dx, 0.022, yaw)
        S.box((px, y + dy, pz), (rnd.uniform(0.13, 0.22), rnd.uniform(0.12, 0.2), 0.003),
              rnd.choice(["#ffeaa7", "#fdfdfd", "#a3f7bf", "#fab1a0", "#74b9ff"]), yaw=yaw, roll=rnd.uniform(-8, 8))


def gong(S, x, z, yaw=0.0):
    """The sales floor's gong (ring it when you close a deal)."""
    for dx in (-0.55, 0.55):
        px, pz = _rot(x, z, dx, 0, yaw)
        S.box((px, 0, pz), (0.08, 1.7, 0.08), "#5d4037", yaw=yaw, tex=wood("dark"))
        S.box((px, 0, pz), (0.12, 0.05, 0.5), "#3e2723", yaw=yaw)
    S.box((x, 1.7, z), (1.3, 0.1, 0.1), "#5d4037", yaw=yaw, tex=wood("dark"))
    S.cyl((x, 1.0, z), 0.42, 0.035, "#d4a937", segs=24, axis="z", yaw=yaw, metal=0.8)
    S.cyl((x, 1.0, z + 0.02), 0.14, 0.02, "#b8860b", segs=16, axis="z", yaw=yaw, metal=0.8)
    S.box((x - 0.2, 1.42, z), (0.01, 0.28, 0.01), "#2d3436")
    S.box((x + 0.2, 1.42, z), (0.01, 0.28, 0.01), "#2d3436")


def disco_ball(S, x, y, z, r=0.32):
    S.box((x, y + r, z), (0.012, 1.4, 0.012), "#2d3436")
    S.sph((x, y, z), (r, r, r), "#dfe6e9", segs=14, smooth=False, metal=0.9, emit=0.6)


def hydrant(S, x, z):
    S.cyl((x, 0, z), 0.13, 0.08, "#a93226", segs=12)
    S.cyl((x, 0.08, z), 0.1, 0.5, "#e74c3c", segs=12)
    S.sph((x, 0.6, z), (0.11, 0.1, 0.11), "#e74c3c", segs=10)
    S.cyl((x, 0.4, z), 0.045, 0.32, "#c0392b", segs=8, axis="x")
    S.cyl((x, 0.4, z), 0.05, 0.14, "#c0392b", segs=8, axis="z")


def bike_rack(S, x, z, n=4, yaw=0.0):
    for i in range(n):
        px, pz = _rot(x, z, (i - (n - 1) / 2) * 0.5, 0, yaw)
        for dx in (-0.16, 0.16):
            lx, lz = _rot(px, pz, dx, 0, yaw)
            S.cyl((lx, 0, lz), 0.025, 0.7, "#95a5a6", segs=6, metal=0.7)
        S.box((px, 0.7, pz), (0.36, 0.05, 0.05), "#95a5a6", yaw=yaw, metal=0.7)


def parking_sign(S, x, z, text, yaw=0.0):
    """A small sign on a post: RESERVED and friends."""
    S.cyl((x, 0, z), 0.035, 1.75, "#7f8c8d", segs=6)
    sign(S, x, 1.05, z + 0.04, text, w=0.9, h=0.7, bg="#ffffff", fg="#1e3799", yaw=yaw, frame="#1e3799")


def speed_bump(S, x, z, length=4.0, yaw=0.0):
    S.box((x, 0, z), (length, 0.08, 0.4), "#f1c40f", yaw=yaw, bevel=0.03)
    for i in range(int(length / 0.5)):
        px, pz = _rot(x, z, -length / 2 + 0.25 + i * 0.5, 0, yaw)
        if i % 2:
            S.box((px, 0.081, pz), (0.5, 0.004, 0.38), "#2d3436", yaw=yaw)


def floor_text(S, text, x, z, size, color="#f5f5f0", yaw=0.0):
    """Painted on the floor (STOP, SLOW...), reading toward the camera."""
    S.text(text, (x, 0.008, z), size, color, yaw=yaw, flat=True)


def kitchenette(S, x, z, length=2.4, yaw=0.0):
    """Base cabinets, a counter, a microwave (and the sign about fish), a coffee maker."""
    S.box((x, 0, z), (length, 0.86, 0.6), "#ecf0f1", yaw=yaw)
    S.box((x, 0.86, z), (length + 0.04, 0.04, 0.64), "#7f8c8d", yaw=yaw)
    for i in range(int(length / 0.6)):
        dx = -length / 2 + 0.3 + i * 0.6
        fx, fz = _rot(x, z, dx, 0.305, yaw)
        S.box((fx, 0.08, fz), (0.54, 0.7, 0.01), "#dfe6e9", yaw=yaw)
        hx, hz = _rot(x, z, dx + 0.18, 0.315, yaw)
        S.box((hx, 0.66, hz), (0.1, 0.02, 0.02), "#95a5a6", yaw=yaw)
    mx, mz = _rot(x, z, -length / 4, 0, yaw)
    S.box((mx, 0.9, mz), (0.52, 0.3, 0.38), "#2d3436", yaw=yaw, bevel=0.01)
    wx, wz = _rot(x, z, -length / 4 - 0.06, 0.195, yaw)
    S.box((wx, 0.95, wz), (0.32, 0.2, 0.005), "#111111", yaw=yaw)
    cx, cz = _rot(x, z, -length / 4 + 0.19, 0.195, yaw)
    S.box((cx, 1.1, cz), (0.08, 0.03, 0.005), "#2ecc71", yaw=yaw, emit=2.0)
    kx, kz = _rot(x, z, length / 4, 0, yaw)
    S.box((kx, 0.9, kz), (0.26, 0.36, 0.28), "#1e1e24", yaw=yaw)
    S.cyl((kx, 0.92, kz + 0.04), 0.07, 0.14, "#5d4037", segs=10, glass=True)
    bx, bz = _rot(x, z, 0, -0.32, yaw)
    S.box((bx, 0.9, bz), (length + 0.04, 1.0, 0.04), "#dfe6e9", yaw=yaw)  # the backsplash
    sx, sz = _rot(x, z, 0, -0.29, yaw)
    sign(S, sx, 1.24, sz, "NO FISH IN\nTHE MICROWAVE", w=1.5, h=0.6, bg="#fdfdfd", fg="#c0392b", yaw=yaw, frame="#c0392b")


def menu_board(S, x, y, z, yaw=0.0, w=3.0, h=1.0, items=()):
    """A glowing menu board: dark panel, the items in two columns."""
    S.box((x, y, z), (w, h, 0.06), "#1a1a22", yaw=yaw)
    tx, tz = _rot(x, z, 0, 0.035, yaw)
    S.text("MENU", (tx, y + h - 0.2, tz), 0.15, "#ffd23f", yaw=yaw, emit=3.0)
    for i, (name, price) in enumerate(items):
        col, row = i % 2, i // 2
        nx, nz = _rot(x, z, -w / 2 + 0.15 + col * w / 2, 0.035, yaw)
        S.text(name, (nx, y + h - 0.38 - row * 0.17, nz), 0.085, "#ffffff", yaw=yaw, emit=2.0, align="LEFT")
        px, pz = _rot(x, z, -0.12 + col * w / 2, 0.035, yaw)
        S.text(price, (px, y + h - 0.38 - row * 0.17, pz), 0.085, "#ff7a1a", yaw=yaw, emit=2.5, align="RIGHT")


def low_wall(S, z, x0, x1, h=1.1, color="#d9d4ca", trim="#6f6a62"):
    S.box(((x0 + x1) / 2, 0, z), (x1 - x0, h, 0.2), color)
    S.box(((x0 + x1) / 2, h, z), (x1 - x0 + 0.02, 0.05, 0.24), trim)


def glass_wall(S, x, z0, z1, h=2.6):
    """A glass wall along z (the meeting room's side), with a frosted band."""
    S.box((x, 0, (z0 + z1) / 2), (0.12, 0.08, z1 - z0), "#95a5a6")
    S.box((x, h, (z0 + z1) / 2), (0.12, 0.08, z1 - z0), "#95a5a6")
    n = int((z1 - z0) / 1.5)
    for i in range(n + 1):
        zz = z0 + i * (z1 - z0) / n
        S.box((x, 0, zz), (0.08, h, 0.08), "#95a5a6", metal=0.6)
    S.box((x, 0.08, (z0 + z1) / 2), (0.03, h - 0.1, z1 - z0), "#cfe8ff", glass=True)
    S.box((x + 0.02, 1.1, (z0 + z1) / 2), (0.01, 0.35, z1 - z0), "#ffffff", glass=True)


def rug(S, x, z, w, d, color, border, yaw=0.0):
    S.decal(x, z, w, d, border, yaw=yaw, y=0.0)
    S.decal(x, z, w - 0.3, d - 0.3, color, yaw=yaw, y=0.004)


def papers(S, x, z, n=5, seed=3):
    rnd = random.Random(seed)
    for i in range(n):
        S.decal(x + rnd.uniform(-1.2, 1.2), z + rnd.uniform(-0.8, 0.8), 0.22, 0.3, "#fdfdfd", yaw=rnd.uniform(0, 180), y=0.006)


# ===================================================================== arenas
def build_office(S):
    """Generic office floor (the minion fights)."""
    S.tex_floor(-18, -16, 18, 12, carpet("#56667f", "#9fb0cc", 1))
    window_wall(S, -10.5, -16, 16, mood="day")
    # Back row of desks with people's chairs, the kitchenette (and its sign about fish)
    # among them, cubicle walls behind. Signs stay where the HUD doesn't cover them.
    for x in (-7.2, -4.8, 0.0, 2.4, 4.8, 7.2, 9.6):
        desk(S, x, -6.6, screen=["#7fd4ff", "#a3f7bf", "#ffeaa7"][int(x) % 3])
        office_chair(S, x + 0.1, -5.7, yaw=180 + (x * 7) % 25)
    kitchenette(S, -2.4, -6.75)
    partition(S, 1.2, -7.25, 19.6)
    for x, word, sub, sky in ((-6.0, "SYNERGY", "WE'RE ALL IN THIS MEETING", "#2e86de"),
                              (1.2, "CIRCLE BACK", "UNTIL WE'RE DIZZY", "#e17055"),
                              (3.6, "BANDWIDTH", "WE HAVE NONE", "#00b894"),
                              (6.0, "OWNERSHIP", "OF OTHER PEOPLE'S TASKS", "#6c5ce7")):
        motivational_poster(S, x, 0.24, -7.2, word, sub, sky=sky)
    # A second row further back (just their monitors peeking over), under the team signs.
    for x in (-6.0, -3.0, 0.0, 3.0, 6.0, 9.0):
        desk(S, x, -8.9, clutter=False)
    hanging_sign(S, -1.9, 1.62, -8.3, "CUSTOMER SUCCESS", w=2.6, h=0.42, bg="#1e3799")
    hanging_sign(S, 3.4, 1.62, -8.3, "REPLY-ALL DEPT.", w=2.4, h=0.42, bg="#c0392b")
    column(S, 5.6, -9.6, clock=True, hour=4, minute=55)
    # Left side: the whiteboard, a recycling bin
    whiteboard(S, -7.4, -4.4, yaw=30, scribbles="notes")
    recycle_bin(S, -6.3, -5.2)
    tall_plant(S, -10.6, -3.0)
    # Right side
    water_cooler(S, 8.6, -4.6, yaw=-30)
    vending_machine(S, 10.4, -4.3, yaw=-60)
    wet_floor_sign(S, 6.9, -4.2, yaw=-15)
    fire_extinguisher(S, 9.6, -5.6)
    plant(S, 9.0, 1.6, 1.1)
    papers(S, -4.4, -4.6, 4)


def build_parking_lot(S):
    """Behind the office: asphalt, parking stalls, cars, and the Trucker's semi."""
    S.tex_floor(-18, -9.5, 18, 12, tex("asphalt", T.asphalt, (4.0, 4.0), rough=0.95))
    # Sidewalk, curb and a hedge along the back
    S.box((0, 0, -10.5), (36, 0.15, 2.0), "#b8b4aa", tex=tex("sidewalk", lambda: T.stone_tile("#c2bdb2", seed=12, n=2, grout="#9a958c"), (2.0, 2.0)))
    S.box((0, 0, -9.45), (36, 0.18, 0.15), "#f1c40f")
    for i in range(18):
        S.sph((-17 + i * 2.0, 0.55, -11.3), (1.1, 0.6, 0.6), "#2e7d4f", segs=10)
    window_wall(S, -12.6, -18, 18, h=3.5, color="#b9b2a5", sky="#ffd7a8", mood="facade")
    # The signs: reserved spots, and a NO TRUCKS sign right next to the semi
    parking_sign(S, -4.0, -9.2, "RESERVED\nCEO")
    parking_sign(S, -9.0, -9.2, "COMPACT\nONLY")
    parking_sign(S, -1.7, -9.2, "NO\nTRUCKS")
    floor_text(S, "CEO", -3.9, -6.6, 0.9, "#f5f5f0")
    floor_text(S, "SLOW", -6.4, -3.6, 0.8, "#f1c40f")
    speed_bump(S, -6.6, -4.9, length=3.2)
    hydrant(S, -6.2, -9.9)
    bike_rack(S, -11.6, -10.3, n=4)
    trash_can(S, 0.8, -10.1)
    # Stall lines: a row along the back and a row on the left
    for i in range(-6, 8):
        S.decal(i * 2.6, -7.0, 0.12, 4.0, "#f5f5f0")
    S.decal(1.3, -9.0, 36.0, 0.12, "#f5f5f0")
    for i in range(4):
        S.decal(-9.2, -3.0 + i * 2.6, 3.4, 0.12, "#f5f5f0")
    # Oil stains and a painted arrow
    for (x, z, r) in [(-5.2, -6.2, 0.6), (3.9, -6.5, 0.5), (-8.3, 1.1, 0.45), (7.8, 2.6, 0.55)]:
        S.cyl((x, 0.004, z), r, 0.01, "#34363c", segs=14)
    S.decal(-1.0, 4.2, 0.35, 1.6, "#f5f5f0", yaw=0)
    # The semi, parked behind the boss's spot
    semi_truck(S, 3.4, -6.0, yaw=180)  # cab on the left, in view
    # Cars on the left, a lamp post, cones, the dumpster
    car(S, -7.6, -6.9, yaw=90, color="#2e86c1")
    car(S, -10.6, -6.9, yaw=90, color="#bdc3c7")
    car(S, -10.3, -1.6, yaw=0, color="#f39c12")
    lamp_post(S, -5.4, -4.6, yaw=0)
    lamp_post(S, 11.5, -3.0, yaw=180)
    cone(S, -6.9, -3.4)
    cone(S, -7.5, -2.6)
    cone(S, 8.3, -2.2)
    dumpster(S, 13.5, -7.2, yaw=-20)


def build_desk_pods(S):
    """Sales floor: pods of four desks with partitions, the leaderboard, the printer."""
    S.tex_floor(-18, -16, 18, 12, carpet("#4a6189", "#ffd23f", 2))
    window_wall(S, -11.0, -16, 16, sky="#d9ecff", mood="day")
    hanging_sign(S, -2.8, 1.7, -8.6, "Q4 OR BUST", w=2.8, h=0.5, bg="#c0392b")
    hanging_sign(S, 2.4, 1.7, -8.6, "ALWAYS BE FOLLOWING UP", w=3.6, h=0.42, bg="#1e272e", fg="#ffd23f")
    gong(S, 4.6, -7.2, yaw=-10)
    sign(S, -6.6, 1.92, -5.62, "LEADERBOARD", w=2.0, h=0.32, bg="#0984e3")

    def pod(cx, cz, seed):
        for dx in (-0.8, 0.8):
            desk(S, cx + dx, cz + 0.55, screen=["#7fd4ff", "#a3f7bf"][seed % 2])
            office_chair(S, cx + dx + 0.05, cz + 1.4, yaw=180 + seed * 9)
            desk(S, cx + dx, cz - 0.55, yaw=180, screen="#ffeaa7")
        partition(S, cx, cz, 3.4, h=1.25, color="#a4b0be")
        partition(S, cx, cz, 2.3, yaw=90, h=1.25, color="#a4b0be")
        # Sticky notes on the monitors, a ringing phone
        S.box((cx - 1.1, 1.1, cz + 0.36), (0.07, 0.07, 0.005), "#ffeaa7", emit=0.5)
        S.box((cx + 0.55, 0.75, cz + 0.75), (0.16, 0.06, 0.2), "#e74c3c")
    pod(1.6, -6.8, 1)
    pod(-4.6, -6.8, 2)
    pod(7.8, -6.8, 3)
    # Sales leaderboard (one bar is dropping hard) and the printer station
    whiteboard(S, -6.6, -5.6, yaw=0, w=2.2, scribbles="chart")
    printer(S, -9.6, -6.4, yaw=60)
    cardboard_box(S, -10.3, -5.2, yaw=15, size=0.6)
    cardboard_box(S, -10.2, -5.18, yaw=-10, size=0.45, y=0.42)
    recycle_bin(S, -8.9, -3.6, color="#27ae60")
    filing_cabinet(S, 9.4, -3.3, yaw=-50, drawers=4)
    plant(S, 10.2, 0.4, 1.2)
    tall_plant(S, -10.8, -7.6)
    papers(S, -4.6, -4.4, 4, seed=7)


def build_meeting_room(S):
    """The Copilot's meeting room: long table, the big screen, glass wall."""
    S.tex_floor(-18, -16, 18, 12, carpet("#454c72", "#8f9be0", 3))
    window_wall(S, -11.2, -16, 16, color="#2f3450", sky="#7f8fd6", mood="night")
    meeting_table(S, 2.4, -6.9, length=7.6, width=1.7)
    for i in range(6):
        x = -0.9 + i * 1.32
        office_chair(S, x, -8.05, yaw=0, color="#1b2745")
        laptop(S, x, 0.75, -7.45, yaw=0, screen=["#7fd4ff", "#a3f7bf"][i % 2])
    for x in (-1.9, 6.7):
        office_chair(S, x, -6.9, yaw=90 if x < 0 else -90, color="#1b2745")
    S.cyl((2.4, 0.75, -6.9), 0.16, 0.04, "#2d3436", segs=12)
    S.cyl((2.4, 0.79, -6.9), 0.06, 0.01, "#7fd4ff", segs=10, emit=2.0)
    tv_stand(S, 2.4, -9.3, w=4.2, h=2.2, screen="#2e86de", caption="NOW WITH AI")
    glass_wall(S, -8.6, -10.5, 3.5)
    whiteboard(S, -6.6, -8.4, yaw=12, w=2.2, scribbles=[("AGENDA", "#2d3436"), ("1. AI", "#c0392b"),
                                                       ("2. MORE AI", "#2980b9"), ("3. ???", "#27ae60")])
    credenza(S, 9.6, -5.6, yaw=-60)
    S.cyl((9.4, 0.8, -5.3), 0.1, 0.28, "#2d3436", segs=10)
    column(S, 7.8, -9.8, color="#2f3450", clock=True, hour=11, minute=58)
    plant(S, -7.6, -5.4, 1.2)
    tall_plant(S, 11.0, -8.0)


def build_office_center(S):
    """Middle of the office: the Guardian's speakers and DJ table, a lounge, ping pong."""
    S.tex_floor(-18, -16, 18, 12, carpet("#6e5394", "#ff5fa2", 4))
    window_wall(S, -11.0, -16, 16, sky="#ffd1ec", mood="pink")
    speaker_tower(S, -1.4, -5.4, glow="#ff5fa2")
    speaker_tower(S, 6.4, -5.4, glow="#4fc3ff")
    dj_table(S, 2.5, -6.2)
    string_lights(S, -1.4, 6.4, -5.9, 2.3, n=16, sag=0.4)
    disco_ball(S, 4.8, 2.27, -7.2)
    # A light-up dance floor behind the DJ, and a neon sign over it
    for i in range(8):
        for j in range(4):
            S.box((0.4 + i * 0.6, 0, -9.6 + j * 0.6), (0.56, 0.02, 0.56),
                  ["#ff5fa2", "#4fc3ff", "#ffd23f", "#9b59b6"][(i + j * 3) % 4], emit=1.4)
    S.box((2.5, 1.2, -10.4), (4.6, 0.7, 0.06), "#1a1a22")
    S.text("NOW PLAYING", (2.5, 1.33, -10.35), 0.42, "#ff5fa2", emit=4.0)
    # Lounge on the left
    couch(S, -8.4, -6.6, yaw=30, color="#16a085", length=2.4)
    bean_bag(S, -6.4, -5.0, "#e84393")
    bean_bag(S, -9.4, -4.4, "#fdcb6e")
    coffee_table(S, -7.4, -5.6, yaw=30)
    S.cyl((-7.4, 0.41, -5.6), 0.06, 0.12, "#ffffff", segs=8)
    hanging_sign(S, 7.6, 1.75, -9.4, "VIBE CHECK", w=2.4, h=0.46, bg="#6c3483", fg="#ffd23f", emit=1.2)
    # Ping pong in the back left, snacks
    ping_pong_table(S, -4.4, -9.2, yaw=8)
    vending_machine(S, -10.6, -8.4, yaw=40, body="#2980b9")
    bookshelf(S, 9.6, -7.2, yaw=-40, seed=4)
    plant(S, 9.8, -1.0, 1.2)
    tall_plant(S, -10.8, -2.8)


def build_james_desk(S):
    """James's old desk: never cleaned out. Golf stuff, a dead plant, dim screens."""
    S.tex_floor(-18, -16, 18, 12, carpet("#55688a", "#a9b8d6", 5))
    window_wall(S, -11.0, -16, 16, sky="#8fa3c9", mood="dusk")
    # His name on the cubicle wall, a note, and the clock that stopped at quitting time
    sign(S, 2.6, 1.34, -7.96, "JAMES", w=1.1, h=0.34, bg="#ecf0f1", fg="#2d3436", frame="#7f8c8d")
    sign(S, -1.2, 0.7, -7.94, "OUT OF\nOFFICE", w=0.62, h=0.42, bg="#fdfdfd", fg="#c0392b")
    sign(S, 5.2, 0.62, -7.94, "GONE\nGOLFING", w=0.62, h=0.42, bg="#ffeaa7", fg="#2d3436")
    column(S, -7.4, -6.2, clock=True, hour=5, minute=0, clock_y=1.7)
    hanging_sign(S, -3.2, 1.75, -9.4, "LOST & FOUND", w=2.2, h=0.4, bg="#34495e")
    for (x, z, r) in [(1.2, -5.0, 0.7), (4.4, -4.6, 0.5), (-3.2, -6.4, 0.8)]:  # dust
        S.cyl((x, 0.003, z), r, 0.006, "#6c7a94", segs=14)
    # His desk, still logged in
    desk(S, 2.6, -6.2, screen="#9fd3ff")
    desk_lamp(S, 3.2, 0.745, -6.45)
    S.box((2.0, 0.745, -6.5), (0.2, 0.25, 0.03), "#d4af37", pitch=-10)  # framed photo
    S.box((2.01, 0.77, -6.48), (0.15, 0.18, 0.01), "#74b9ff", pitch=-10)
    office_chair(S, 3.3, -5.1, yaw=150)
    golf_bag(S, 0.6, -5.9)
    cardboard_box(S, 4.6, -5.4, yaw=20, size=0.55)
    S.cyl((4.5, 0.39, -5.4), 0.04, 0.12, "#ffffff", segs=8)
    papers(S, 2.4, -4.6, 6, seed=11)
    # Putting green on the left, balls everywhere
    putting_green(S, -8.6, -2.8, yaw=25)
    for (x, z) in [(-6.9, -1.2), (-7.4, 0.8), (6.8, -3.4)]:
        S.sph((x, 0.03, z), (0.025, 0.025, 0.025), "#ffffff", segs=6)
    # Empty desks around, screens off
    for x in (-5.0, -2.4, 8.0, 10.6):
        desk(S, x, -7.4, screen_on=False, clutter=False)
    partition(S, 2.8, -8.0, 17.0, color="#7f8c8d")
    plant(S, -10.4, -5.0, 1.1, dead=True)
    filing_cabinet(S, 10.2, -3.6, yaw=-50)
    bookshelf(S, -10.6, -7.8, yaw=35, seed=9)


def build_villiam_burginson(S):
    """The burger joint: the counter, the kitchen, booths, and the Village Sauce."""
    S.tex_floor(-18, -16, 18, 12, tex("diner_tile", lambda: T.diner_tile("#c0392b", "#f4f1e8"), (1.6, 1.6), rough=0.35))
    window_wall(S, -11.6, -16, 16, color="#8e2b20", sky="#ffe08a", mood="warm")
    # The name in neon across the windows, the menu over the kitchen
    S.box((2.0, 1.02, -11.3), (6.4, 0.74, 0.06), "#1a1a22")
    S.text("VILLIAM BURGINSON'S", (2.0, 1.2, -11.25), 0.4, "#ff5fa2", emit=4.0)
    menu_board(S, 7.2, 1.45, -8.9, w=3.0, h=0.95, items=(("DORK BURGER", "6.99"), ("FRIES", "2.99"),
                                                       ("VILLAGE SAUCE", "FREE*"), ("SHAKE", "3.49")))
    # Kitchen behind the counter (the grill and its tall hood off to the side, so they don't
    # hide the neon sign)
    fryer(S, -0.6, -8.2)
    fryer(S, 0.4, -8.2)
    grill(S, -3.6, -8.2, w=1.8)
    heat_lamp_shelf(S, 3.6, -7.6, w=2.6)
    soda_fountain(S, 7.0, -8.2)
    # The counter
    counter(S, 2.0, -6.3, 13.0)
    register(S, -0.6, 1.05, -6.3)
    register(S, 3.0, 1.05, -6.3)
    sauce_display(S, -1.9, 1.05, -6.35, size=1.8)
    S.box((-2.6, 1.05, -6.3), (0.5, 0.06, 0.35), "#c0392b")  # a tray
    S.cyl((-2.5, 1.11, -6.3), 0.1, 0.07, "#f0b35b", segs=10)
    neon_sign(S, 7.2, 1.2, -11.35, w=1.6, h=0.9)
    # Booths on the left, tables on the right
    booth(S, -4.3, -4.5, yaw=0)
    booth(S, -7.7, -1.4, yaw=90)
    diner_table(S, 9.2, -3.2)
    diner_table(S, 9.8, 0.6)
    a_frame_sign(S, -6.6, -6.6, yaw=30, text="TRY THE\nVILLAGE\nSAUCE")
    trash_can(S, -7.0, -7.0)
    trash_can(S, 11.0, -6.0, color="#c0392b")
    plant(S, 11.4, -1.6, 1.0)


def pickup(S, x, z, yaw=0.0, color="#4fc3ff"):
    """A pickup truck pointing along +x (yaw 0): a cab up front, an open bed behind."""
    S.box((x, 0.25, z), (4.2, 0.62, 1.8), color, yaw=yaw, bevel=0.1)
    cx, cz = _rot(x, z, 0.55, 0, yaw)
    S.box((cx, 0.86, cz), (1.6, 0.62, 1.62), color, yaw=yaw, bevel=0.1)
    for dz in (-0.82, 0.82):
        wx, wz = _rot(x, z, 0.55, dz, yaw)
        S.box((wx, 0.94, wz), (1.3, 0.4, 0.02), "#2c3e50", yaw=yaw, glass=True)
    fx, fz = _rot(x, z, 1.36, 0, yaw)
    S.box((fx, 0.94, fz), (0.02, 0.4, 1.4), "#2c3e50", yaw=yaw, glass=True)
    for dz in (-0.86, 0.86):  # the bed's walls and tailgate
        bx, bz = _rot(x, z, -1.15, dz, yaw)
        S.box((bx, 0.87, bz), (1.9, 0.3, 0.08), color, yaw=yaw)
    tx, tz = _rot(x, z, -2.08, 0, yaw)
    S.box((tx, 0.87, tz), (0.08, 0.3, 1.8), color, yaw=yaw)
    for dx in (-1.35, 1.35):
        for dz in (-0.85, 0.85):
            wx, wz = _rot(x, z, dx, dz, yaw)
            S.cyl((wx, 0.36, wz), 0.36, 0.24, "#1a1a1a", segs=12, axis="z", yaw=yaw)
            S.cyl((wx, 0.36, wz + (0.13 if dz > 0 else -0.13)), 0.18, 0.02, "#bdc3c7", segs=10, axis="z", yaw=yaw)
    for dz in (-0.6, 0.6):
        hx, hz = _rot(x, z, 2.1, dz, yaw)
        S.box((hx, 0.55, hz), (0.03, 0.15, 0.3), "#fff7c2", yaw=yaw, emit=2.0)
        rx, rz = _rot(x, z, -2.1, dz, yaw)
        S.box((rx, 0.55, rz), (0.03, 0.15, 0.25), "#e74c3c", yaw=yaw, emit=1.5)
    gx, gz = _rot(x, z, 2.11, 0, yaw)
    S.box((gx, 0.42, gz), (0.02, 0.3, 0.9), "#2d3436", yaw=yaw)


# ===================================================================== the overworld office
# The office floor the party walks around (scenes/overworld/office_map.gd loads it and keeps
# the walls' and furniture's collision from its own copy of this layout). Rooms mirror
# office_map.gd ROOMS: (x, z, width, depth, floor color, tile size).
OVERWORLD_ROOMS = {
    "hallway": (-27, -8, 54, 8, "#a99d86", 2.0),
    "lobby": (-9, 0, 18, 16, "#b48a63", 2.0),
    "parking_lot": (-27, 0, 18, 16, "#4a4d55", 6.0),
    "james_desk": (9, 0, 18, 16, "#5f7396", 1.5),
    "desk_pods": (-27, -26, 18, 18, "#4f6a94", 1.5),
    "office_center": (-9, -26, 18, 18, "#7a5f9e", 1.5),
    "meeting_room": (9, -26, 18, 18, "#3f4566", 1.5),
}
SCREENS = ["#7fd4ff", "#a3f7bf", "#ffeaa7"]


def overworld_floor(room):
    """Each room's floor texture: stone in the hallway, wood in the lobby, asphalt out back,
    and each department's own carpet (the same colors as its battle arena)."""
    return {
        "hallway": lambda: tex("hall_tile", lambda: T.stone_tile("#bcb19b", seed=21, n=2, grout="#91887a"), (2.4, 2.4)),
        "lobby": lambda: wood("floor"),
        "parking_lot": lambda: tex("asphalt", T.asphalt, (4.0, 4.0), rough=0.95),
        "james_desk": lambda: carpet("#55688a", "#a9b8d6", 5),
        "desk_pods": lambda: carpet("#4a6189", "#ffd23f", 2),
        "office_center": lambda: carpet("#6e5394", "#ff5fa2", 4),
        "meeting_room": lambda: carpet("#454c72", "#8f9be0", 3),
    }[room]()


def _shade(color, k):
    """A hex color darkened by k (0 to 1)."""
    c = color.lstrip("#")
    return "#" + "".join("%02x" % int(int(c[i:i + 2], 16) * (1 - k)) for i in (0, 2, 4))


def _wall(S, a, b, fixed, along_x, h, color, t=0.25):
    """One stretch of wall from a to b, at x or z = fixed, with a trim on top and a baseboard."""
    mid, length = (a + b) / 2, b - a
    for y, hh, tt, c in ((0, h, t, color), (h, 0.06, t + 0.04, "#6f6a62"), (0, 0.1, t + 0.03, "#8d8a84")):
        if along_x:
            S.box((mid, y, fixed), (length, hh, tt), c)
        else:
            S.box((fixed, y, mid), (tt, hh, length), c)


def _walls(S, fixed, a0, a1, gaps, h, color, along_x):
    """A wall with doorways: gaps = [(center, half width), ...]."""
    cuts = [a0]
    for c, half in gaps:
        cuts += [c - half, c + half]
    cuts.append(a1)
    for i in range(0, len(cuts), 2):
        if cuts[i + 1] - cuts[i] > 0.05:
            _wall(S, cuts[i], cuts[i + 1], fixed, along_x, h, color)


def build_overworld(S):
    """The whole office floor: the code-built layout with real furniture, and the empty
    corners filled. Extra pieces sit along walls and in corners, off the walking paths."""
    for room, (x, z, w, d, col, tile) in OVERWORLD_ROOMS.items():
        S.tex_floor(x, z, x + w, z + d, overworld_floor(room), step=2.0)
    # Grass all around the building (the game's own green plane sits just under it).
    S.tex_floor(-70, -70, 70, 70, tex("grass", T.grass, (6.0, 6.0), rough=1.0), step=10.0, y=-0.05)
    outer, inner = "#c9c4ba", "#ebe7df"
    _walls(S, -26.0, -27.0, 27.0, [], 1.4, outer, True)
    _walls(S, 16.0, -27.0, 27.0, [], 1.4, outer, True)
    _walls(S, -27.0, -26.0, 16.0, [], 1.4, outer, False)
    _walls(S, 27.0, -26.0, 16.0, [], 1.4, outer, False)
    _walls(S, -8.0, -27.0, 27.0, [(-18.0, 2.0), (0.0, 2.0), (18.0, 2.0)], 1.1, inner, True)
    _walls(S, 0.0, -27.0, 27.0, [(-18.0, 2.0), (0.0, 3.0), (18.0, 2.0)], 1.1, inner, True)
    for x in (-9.0, 9.0):
        _walls(S, x, -26.0, -8.0, [], 1.1, inner, False)
        _walls(S, x, 0.0, 16.0, [], 1.1, inner, False)
    for dx, dz in ((-18, -8), (0, -8), (18, -8), (-18, 0), (18, 0)):
        for s in (-1, 1):
            S.box((dx + s * 2.15, 0, dz), (0.3, 1.6, 0.4), "#8d8a84", bevel=0.02)
    for s in (-1, 1):
        S.box((s * 3.15, 0, 0), (0.3, 1.6, 0.4), "#8d8a84", bevel=0.02)

    # Lobby: rug, reception desk, couch and coffee table, plants, a bookshelf, water.
    rug(S, 0.0, 9.0, 7.0, 7.0, "#8e3b46", "#6d2c35")
    S.box((4.0, 0, 5.4), (4.6, 1.02, 1.2), "#a1785c", bevel=0.03)
    S.box((4.0, 1.02, 5.4), (4.8, 0.05, 1.32), "#ecf0f1", bevel=0.01)
    S.box((4.0, 0.35, 4.79), (4.4, 0.12, 0.02), "#ffd23f")
    laptop(S, 4.6, 1.07, 5.7, yaw=180)
    couch(S, -3.0, 14.4, yaw=180, color="#2e86c1", length=3.0)
    coffee_table(S, -3.0, 12.9)
    plant(S, -8.0, 15.0, 1.1)
    plant(S, 8.0, 15.0, 1.1)
    tall_plant(S, 8.0, 1.0)
    bookshelf(S, 8.4, 8.6, yaw=-90)
    water_cooler(S, 8.3, 11.6, yaw=-90)
    # The company's name behind reception, and a welcome mat by the elevator
    S.box((4.0, 0, 8.3), (4.2, 1.35, 0.12), "#2d3436")
    sign(S, 4.0, 0.62, 8.22, "VILLIAM BURGINSON INC.", w=3.9, h=0.5, bg="#2d3436", fg="#ffd23f", yaw=180)
    S.decal(-6.2, 10.0, 1.6, 1.1, "#5d4037", y=0.002)
    floor_text(S, "WELCOME", -6.2, 10.1, 0.28, "#ffd23f")
    # Hallway: water cooler, plants, vending machines at the far ends, a runner rug and
    # posters on the walls.
    water_cooler(S, -11.0, -7.3)
    plant(S, 11.0, -0.7)
    plant(S, -26.0, -0.8)
    plant(S, 26.0, -7.2)
    vending_machine(S, -26.3, -4.4, yaw=90)
    vending_machine(S, 26.3, -3.4, yaw=-90, body="#2e86c1")
    rug(S, 0.0, -4.0, 40.0, 2.2, "#7b3b46", "#5a2a33")
    for x, word, sky in ((-9.0, "SYNERGY", "#2e86de"), (9.0, "HUSTLE", "#e17055"), (-24.0, "FOCUS", "#00b894"), (24.0, "TEAMWORK", "#6c5ce7")):
        motivational_poster(S, x, 0.04, -7.84, word, sky=sky)
    # Parking lot: stall lines, the semi, two cars, a lamp post, cones, a dumpster.
    for x in (-25.6, -22.4, -13.6, -10.4):
        S.decal(x, 8.5, 0.12, 3.4, "#f1c40f")
    floor_text(S, "CEO", -18.0, 13.0, 1.0, "#f5f5f0")
    speed_bump(S, -18.0, 4.6, length=3.6)
    semi_truck(S, -24.0, 6.8, yaw=90)
    car(S, -12.0, 4.2, yaw=90, color="#2e86c1")
    car(S, -12.0, 11.6, yaw=90, color="#f39c12")
    lamp_post(S, -14.4, 8.0)
    for x, z in ((-20.6, 2.6), (-21.3, 3.3), (-20.4, 3.9)):
        cone(S, x, z)
    dumpster(S, -25.6, 15.0)
    # James's old desk: four desks with chairs, his old desk at the back, his golf bag.
    for i, (x, z) in enumerate(((12.5, 5.0), (12.5, 10.0), (23.5, 5.0), (23.5, 10.0))):
        desk(S, x, z, screen=SCREENS[i % 3])
        office_chair(S, x + 0.1, z + 0.85, yaw=180 + i * 9)
    desk(S, 18.0, 15.0, yaw=180, top="#8d6e63", screen="#2c3e50", screen_on=False)
    golf_bag(S, 20.2, 15.0)
    plant(S, 26.0, 1.0)
    filing_cabinet(S, 26.3, 7.4, yaw=-90)
    filing_cabinet(S, 26.3, 8.1, yaw=-90, drawers=4)
    printer(S, 9.9, 13.6, yaw=90)
    papers(S, 21.0, 12.4, 4, seed=5)
    # Desk pods: cubicles with partitions, chairs and posters; a printer and cabinets.
    for x in (-24.0, -12.0):
        for j, z in enumerate((-12.0, -17.0, -22.0)):
            partition(S, x, z - 0.85, 2.8)
            partition(S, x + (1.45 if x < -18 else -1.45), z - 0.1, 1.8, yaw=90)
            desk(S, x, z, screen=SCREENS[(j + int(x)) % 3])
            office_chair(S, x - 0.1, z + 0.85, yaw=180 - j * 8)
            poster(S, x - 0.75, 0.7, z - 0.8, w=0.42, h=0.5, colors=["#74b9ff", "#ffffff", "#ff7675"][j:] + ["#ffeaa7"] * j)
    printer(S, -26.2, -9.4, yaw=90)
    filing_cabinet(S, -26.3, -24.6, yaw=90, drawers=4)
    plant(S, -26.0, -25.2)
    plant(S, -10.0, -25.2)
    water_cooler(S, -10.2, -14.5, yaw=-90)
    # Middle of the office: the rug, the speakers and DJ table, couches, bean bags.
    rug(S, 0.0, -21.0, 6.0, 6.0, "#e056a0", "#a8327a")
    for x in (-4.2, 4.2):
        speaker_tower(S, x, -23.6)
    dj_table(S, 0.0, -24.6)
    couch(S, -6.0, -14.0, yaw=180, length=3.0)
    couch(S, 6.0, -14.0, yaw=180, length=3.0)
    bean_bag(S, -3.4, -11.6)
    bean_bag(S, 3.4, -11.6, color="#00cec9")
    plant(S, -8.0, -25.0)
    plant(S, 8.0, -25.0)
    # Meeting room: the long table and chairs, laptops, the big screen, a whiteboard.
    meeting_table(S, 12.6, -17.0, length=7.0, width=2.2, yaw=90)
    for z in (-19.5, -17.0, -14.5):
        office_chair(S, 10.9, z, yaw=90)
        office_chair(S, 14.3, z, yaw=-90)
    laptop(S, 12.1, 0.78, -18.4, yaw=90)
    laptop(S, 13.1, 0.78, -15.6, yaw=-90)
    tv_stand(S, 18.0, -25.4, w=6.0, h=2.4, screen="#7fd4ff")
    credenza(S, 23.6, -25.4)
    whiteboard(S, 26.3, -16.0, yaw=-90)
    plant(S, 26.0, -9.2)


BUILDERS = {
    "office": build_office, "parking_lot": build_parking_lot, "desk_pods": build_desk_pods,
    "meeting_room": build_meeting_room, "office_center": build_office_center,
    "james_desk": build_james_desk, "villiam_burginson": build_villiam_burginson,
    "overworld": build_overworld,
    "titan": lambda S: pickup(S, 0.0, 0.0, 0.0, "#4fc3ff"),  # Cam's Nissan Titan drive-by
    "subaru": lambda S: car(S, 0.0, 0.0, 0.0, "#2e5cb8"),  # Sarah's Subaru drive-by
}
# Built and exported with the arenas, but not battle arenas: id -> assets/models/<folder>.
EXTRA_IDS = {"overworld": "arenas", "titan": "props", "subaru": "props"}


def build(arena_id):
    S = Scenery()
    BUILDERS[arena_id](S)
    return S.to_object("arena_" + arena_id)
