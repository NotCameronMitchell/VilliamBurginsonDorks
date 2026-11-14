"""
Low-poly chibi character builder for Blender (run inside Blender's Python).

Every character is one mesh built from simple parts (spheres, cylinders, boxes),
each part rigidly weighted to one bone of a shared 8-bone skeleton:

    root -> hips -> torso -> head
                   torso -> arm.L, arm.R
            hips -> leg.L, leg.R

so every character shares the same animations (see ANIMATIONS). Coordinates are
Blender's: Z up, the character faces -Y, its left side is +X.

build(name, spec) returns the armature object (the mesh is its child).
The spec format is documented in characters.py.
"""

import math

import bmesh
import bpy
from mathutils import Euler, Matrix, Vector

BONES = ["root", "hips", "torso", "head", "arm.L", "arm.R", "leg.L", "leg.R"]
FPS = 30


# --------------------------------------------------------------------- materials
_materials = {}


def material(color, ghost=False, emit=0.0, metal=0.0):
    """A flat-colored material, cached by its look."""
    key = (color, ghost, emit, metal)
    if key in _materials:
        return _materials[key]
    m = bpy.data.materials.new("mat_%s%s%s" % (color.strip("#"), "_ghost" if ghost else "", "_emit" if emit else ""))
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    rgb = hex_rgb(color)
    bsdf.inputs["Base Color"].default_value = (*rgb, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.75
    bsdf.inputs["Metallic"].default_value = metal
    if emit or ghost:
        name = "Emission Color" if "Emission Color" in bsdf.inputs else "Emission"
        bsdf.inputs[name].default_value = (*rgb, 1.0)
        bsdf.inputs["Emission Strength"].default_value = emit if emit else 0.35
    if ghost:
        bsdf.inputs["Alpha"].default_value = 0.55
        if hasattr(m, "surface_render_method"):
            m.surface_render_method = "BLENDED"
        if hasattr(m, "blend_method"):
            m.blend_method = "BLEND"
    m.diffuse_color = (*rgb, 0.55 if ghost else 1.0)
    _materials[key] = m
    return m


def hex_rgb(h):
    """sRGB hex -> linear RGB (what Blender's color inputs expect)."""
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c)


# --------------------------------------------------------------------- mesh building
class Builder:
    """Accumulates parts into one bmesh with material slots and bone weights."""

    def __init__(self, ghost=False):
        self.bm = bmesh.new()
        self.deform = self.bm.verts.layers.deform.verify()
        self.mats = []
        self.ghost = ghost

    def _mat_index(self, color, emit=0.0, metal=0.0, ghost=None):
        m = material(color, self.ghost if ghost is None else ghost, emit, metal)
        if m not in self.mats:
            self.mats.append(m)
        return self.mats.index(m)

    def _finish(self, verts, color, bone, smooth, emit=0.0, metal=0.0, ghost=None):
        idx = self._mat_index(color, emit, metal, ghost)
        g = BONES.index(bone)
        faces = set()
        for v in verts:
            v[self.deform][g] = 1.0
            faces.update(v.link_faces)
        for f in faces:
            f.material_index = idx
            f.smooth = smooth
        return verts

    @staticmethod
    def _matrix(loc, size, rot):
        return Matrix.Translation(Vector(loc)) @ Euler([math.radians(a) for a in rot]).to_matrix().to_4x4() @ Matrix.Diagonal((*size, 1.0))

    def sphere(self, loc, size, color, bone, rot=(0, 0, 0), segs=12, smooth=True, cut_below=None, keep=None, **kw):
        """An ellipsoid. cut_below / keep: drop vertices by their local (unit-sphere) position."""
        r = bmesh.ops.create_uvsphere(self.bm, u_segments=segs, v_segments=max(6, segs // 2 + 1), radius=1.0)
        verts = r["verts"]
        drop = []
        for v in verts:
            if (cut_below is not None and v.co.z < cut_below) or (keep is not None and not keep(v.co)):
                drop.append(v)
        if drop:
            bmesh.ops.delete(self.bm, geom=drop, context="VERTS")
            verts = [v for v in verts if v.is_valid]
        bmesh.ops.transform(self.bm, matrix=self._matrix(loc, size, rot), verts=verts)
        return self._finish(verts, color, bone, smooth, **kw)

    def cylinder(self, loc, radius, depth, color, bone, rot=(0, 0, 0), segs=10, radius2=None, smooth=False, sx=1.0, sy=1.0, **kw):
        """A cylinder (or cone with radius2) along local Z, centered at loc."""
        r = bmesh.ops.create_cone(self.bm, cap_ends=True, cap_tris=False, segments=segs,
                                  radius1=1.0, radius2=(radius2 / radius) if radius2 is not None else 1.0, depth=1.0)
        verts = r["verts"]
        bmesh.ops.transform(self.bm, matrix=self._matrix(loc, (radius * sx, radius * sy, depth), rot), verts=verts)
        return self._finish(verts, color, bone, smooth, **kw)

    def box(self, loc, size, color, bone, rot=(0, 0, 0), bevel=0.0, **kw):
        r = bmesh.ops.create_cube(self.bm, size=1.0)
        verts = r["verts"]
        bmesh.ops.transform(self.bm, matrix=self._matrix(loc, size, rot), verts=verts)
        if bevel > 0:
            edges = list({e for v in verts for e in v.link_edges})
            res = bmesh.ops.bevel(self.bm, geom=verts + edges, offset=bevel, segments=1, affect="EDGES")
            verts = [v for v in res.get("verts", []) if v.is_valid] + [v for v in verts if v.is_valid]
            verts = list({v for v in verts})
        return self._finish(verts, color, bone, False, **kw)

    def to_object(self, name):
        bmesh.ops.recalc_face_normals(self.bm, faces=self.bm.faces)
        mesh = bpy.data.meshes.new(name)
        self.bm.to_mesh(mesh)
        self.bm.free()
        for m in self.mats:
            mesh.materials.append(m)
        obj = bpy.data.objects.new(name, mesh)
        bpy.context.scene.collection.objects.link(obj)
        for b in BONES:
            obj.vertex_groups.new(name=b)
        return obj


# --------------------------------------------------------------------- skeleton
def make_armature(name, P):
    """P: proportions dict from build(). Bones are laid out so local X rotation
    swings limbs forward/back and leans the torso and head."""
    arm_data = bpy.data.armatures.new(name + "_rig")
    arm = bpy.data.objects.new(name, arm_data)
    bpy.context.scene.collection.objects.link(arm)
    bpy.context.view_layer.objects.active = arm
    arm.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    eb = arm_data.edit_bones

    def bone(n, head, tail, parent=None):
        b = eb.new(n)
        b.head = Vector(head)
        b.tail = Vector(tail)
        b.roll = 0.0
        if parent:
            b.parent = eb[parent]
        return b

    hip_z, top_z, sh_z = P["hip_z"], P["torso_top"], P["shoulder_z"]
    bone("root", (0, 0, 0), (0, 0, 0.12))
    bone("hips", (0, 0, hip_z), (0, 0, hip_z + 0.1), "root")
    bone("torso", (0, 0, hip_z + 0.02), (0, 0, top_z), "hips")
    bone("head", (0, 0, top_z), (0, 0, top_z + P["head_r"] * 2), "torso")
    for side, sx in (("L", 1), ("R", -1)):
        bone("arm." + side, (sx * P["shoulder_x"], 0, sh_z), (sx * P["shoulder_x"], 0, sh_z - P["arm_len"]), "torso")
        bone("leg." + side, (sx * P["leg_x"], 0, hip_z), (sx * P["leg_x"], 0, 0.02), "hips")
    bpy.ops.object.mode_set(mode="POSE")
    for pb in arm.pose.bones:
        pb.rotation_mode = "XYZ"
    bpy.ops.object.mode_set(mode="OBJECT")
    return arm


# --------------------------------------------------------------------- animations
# Each: (length in frames, loop?, {frame: {bone: {"rot": (x, y, z) degrees, "loc": (x, y, z)}}}).
# Local axes: arms and legs point down, so +X swings them backward and -X forward;
# torso, head and root point up, so +X leans forward, -X leans back, Y twists.
ANIMATIONS = {
    "idle": (60, True, {
        0: {"torso": {"rot": (0, 0, 0)}, "head": {"rot": (0, 0, 0)}, "arm.L": {"rot": (0, 0, 6)}, "arm.R": {"rot": (0, 0, -6)}, "hips": {"loc": (0, 0, 0)}},
        30: {"torso": {"rot": (3, 0, 0)}, "head": {"rot": (-4, 0, 2)}, "arm.L": {"rot": (4, 0, 9)}, "arm.R": {"rot": (4, 0, -9)}, "hips": {"loc": (0, 0, -0.012)}},
        60: {"torso": {"rot": (0, 0, 0)}, "head": {"rot": (0, 0, 0)}, "arm.L": {"rot": (0, 0, 6)}, "arm.R": {"rot": (0, 0, -6)}, "hips": {"loc": (0, 0, 0)}},
    }),
    "walk": (24, True, {
        0: {"leg.L": {"rot": (-30, 0, 0)}, "leg.R": {"rot": (30, 0, 0)}, "arm.L": {"rot": (25, 0, 5)}, "arm.R": {"rot": (-25, 0, -5)}, "hips": {"loc": (0, 0, 0)}},
        6: {"hips": {"loc": (0, 0, 0.025)}},
        12: {"leg.L": {"rot": (30, 0, 0)}, "leg.R": {"rot": (-30, 0, 0)}, "arm.L": {"rot": (-25, 0, 5)}, "arm.R": {"rot": (25, 0, -5)}, "hips": {"loc": (0, 0, 0)}},
        18: {"hips": {"loc": (0, 0, 0.025)}},
        24: {"leg.L": {"rot": (-30, 0, 0)}, "leg.R": {"rot": (30, 0, 0)}, "arm.L": {"rot": (25, 0, 5)}, "arm.R": {"rot": (-25, 0, -5)}, "hips": {"loc": (0, 0, 0)}},
    }),
    "attack": (22, False, {
        0: {"torso": {"rot": (0, 0, 0)}, "arm.R": {"rot": (0, 0, 0)}, "root": {"loc": (0, 0, 0)}},
        6: {"torso": {"rot": (-6, 28, 0)}, "arm.R": {"rot": (70, 0, -10)}},
        11: {"torso": {"rot": (16, -22, 0)}, "arm.R": {"rot": (-105, 0, -10)}, "root": {"loc": (0, -0.18, 0)}},
        22: {"torso": {"rot": (0, 0, 0)}, "arm.R": {"rot": (0, 0, 0)}, "root": {"loc": (0, 0, 0)}},
    }),
    "cast": (26, False, {
        0: {"arm.L": {"rot": (0, 0, 0)}, "arm.R": {"rot": (0, 0, 0)}, "head": {"rot": (0, 0, 0)}, "root": {"loc": (0, 0, 0)}},
        10: {"arm.L": {"rot": (-150, 0, 15)}, "arm.R": {"rot": (-150, 0, -15)}, "head": {"rot": (-15, 0, 0)}, "root": {"loc": (0, 0, 0.07)}},
        16: {"arm.L": {"rot": (-155, 0, 20)}, "arm.R": {"rot": (-155, 0, -20)}, "head": {"rot": (-15, 0, 0)}, "root": {"loc": (0, 0, 0.05)}},
        26: {"arm.L": {"rot": (0, 0, 0)}, "arm.R": {"rot": (0, 0, 0)}, "head": {"rot": (0, 0, 0)}, "root": {"loc": (0, 0, 0)}},
    }),
    "hit": (14, False, {
        0: {"torso": {"rot": (0, 0, 0)}, "head": {"rot": (0, 0, 0)}, "arm.L": {"rot": (0, 0, 0)}, "arm.R": {"rot": (0, 0, 0)}, "root": {"loc": (0, 0, 0)}},
        3: {"torso": {"rot": (-20, 0, 4)}, "head": {"rot": (-16, 0, 0)}, "arm.L": {"rot": (28, 0, 15)}, "arm.R": {"rot": (28, 0, -15)}, "root": {"loc": (0, 0.09, 0)}},
        14: {"torso": {"rot": (0, 0, 0)}, "head": {"rot": (0, 0, 0)}, "arm.L": {"rot": (0, 0, 0)}, "arm.R": {"rot": (0, 0, 0)}, "root": {"loc": (0, 0, 0)}},
    }),
    "stunned": (40, True, {
        0: {"head": {"rot": (8, 0, -14)}, "torso": {"rot": (0, 0, 5)}, "arm.L": {"rot": (0, 0, 14)}, "arm.R": {"rot": (0, 0, -14)}},
        20: {"head": {"rot": (8, 0, 14)}, "torso": {"rot": (0, 0, -5)}, "arm.L": {"rot": (0, 0, 10)}, "arm.R": {"rot": (0, 0, -10)}},
        40: {"head": {"rot": (8, 0, -14)}, "torso": {"rot": (0, 0, 5)}, "arm.L": {"rot": (0, 0, 14)}, "arm.R": {"rot": (0, 0, -14)}},
    }),
    "faint": (30, False, {
        0: {"root": {"rot": (0, 0, 0)}, "arm.L": {"rot": (0, 0, 0)}, "arm.R": {"rot": (0, 0, 0)}, "head": {"rot": (0, 0, 0)}},
        8: {"root": {"rot": (-10, 0, 0)}, "arm.L": {"rot": (-60, 0, 30)}, "arm.R": {"rot": (-60, 0, -30)}, "head": {"rot": (-20, 0, 0)}},
        20: {"root": {"rot": (-88, 0, 0)}, "arm.L": {"rot": (-40, 0, 40)}, "arm.R": {"rot": (-40, 0, -40)}, "head": {"rot": (0, 0, 20)}},
        30: {"root": {"rot": (-86, 0, 0)}, "arm.L": {"rot": (-40, 0, 40)}, "arm.R": {"rot": (-40, 0, -40)}, "head": {"rot": (0, 0, 20)}},
    }),
    "victory": (30, True, {
        0: {"root": {"loc": (0, 0, 0)}, "arm.L": {"rot": (-160, 0, 20)}, "arm.R": {"rot": (-160, 0, -20)}},
        8: {"root": {"loc": (0, 0, 0.16)}, "arm.L": {"rot": (-170, 0, 30)}, "arm.R": {"rot": (-170, 0, -30)}},
        15: {"root": {"loc": (0, 0, 0)}, "arm.L": {"rot": (-160, 0, 20)}, "arm.R": {"rot": (-160, 0, -20)}},
        23: {"root": {"loc": (0, 0, 0.16)}, "arm.L": {"rot": (-170, 0, 30)}, "arm.R": {"rot": (-170, 0, -30)}},
        30: {"root": {"loc": (0, 0, 0)}, "arm.L": {"rot": (-160, 0, 20)}, "arm.R": {"rot": (-160, 0, -20)}},
    }),
    "ultimate": (34, False, {
        0: {"root": {"rot": (0, 0, 0), "loc": (0, 0, 0)}, "arm.L": {"rot": (0, 0, 0)}, "arm.R": {"rot": (0, 0, 0)}},
        10: {"root": {"rot": (0, 180, 0), "loc": (0, 0, 0.25)}, "arm.L": {"rot": (-150, 0, 40)}, "arm.R": {"rot": (-150, 0, -40)}},
        20: {"root": {"rot": (0, 360, 0), "loc": (0, 0, 0)}, "arm.L": {"rot": (-170, 0, 30)}, "arm.R": {"rot": (-170, 0, -30)}},
        34: {"root": {"rot": (0, 360, 0), "loc": (0, 0, 0)}, "arm.L": {"rot": (0, 0, 0)}, "arm.R": {"rot": (0, 0, 0)}},
    }),
}


def add_animations(arm):
    """Keys every animation as its own action, each pushed to an NLA track named
    after it (the glTF exporter writes one animation per track)."""
    ad = arm.animation_data_create()
    for name, (length, loop, frames) in ANIMATIONS.items():
        action = bpy.data.actions.new("%s|%s" % (arm.name, name))
        action.use_fake_user = True
        ad.action = action
        for frame in sorted(frames):
            for b, v in frames[frame].items():
                pb = arm.pose.bones[b]
                if "rot" in v:
                    pb.rotation_euler = Euler([math.radians(a) for a in v["rot"]])
                    pb.keyframe_insert("rotation_euler", frame=frame)
                if "loc" in v:
                    pb.location = Vector(v["loc"])
                    pb.keyframe_insert("location", frame=frame)
        # Every animation sets every bone, so nothing is left over from the last one
        # played (e.g. a revived hero still lying down from "faint").
        for b in BONES:
            pb = arm.pose.bones[b]
            for channel, key in (("rotation_euler", "rot"), ("location", "loc")):
                if any(key in f.get(b, {}) for f in frames.values()):
                    continue
                pb.rotation_euler = Euler((0, 0, 0))
                pb.location = Vector((0, 0, 0))
                for frame in (0, length):
                    pb.keyframe_insert(channel, frame=frame)
        track = ad.nla_tracks.new()
        track.name = name
        strip = track.strips.new(name, 0, action)
        strip.action_frame_end = length
        ad.action = None
        for pb in arm.pose.bones:
            pb.rotation_euler = Euler((0, 0, 0))
            pb.location = Vector((0, 0, 0))
    return ad


# --------------------------------------------------------------------- characters
def proportions(spec):
    s = spec.get("scale", 1.0)
    leg = 0.32 * spec.get("leg", 1.0)
    torso = 0.36 * spec.get("torso_h", 1.0)
    head_r = 0.27 * spec.get("head", 1.0)
    width = spec.get("width", 1.0)
    return {
        "s": s, "hip_z": leg + 0.02, "torso_top": leg + 0.02 + torso, "torso_h": torso,
        "shoulder_z": leg + 0.02 + torso - 0.05, "shoulder_x": 0.2 * width + 0.03,
        "arm_len": 0.3 * spec.get("arm", 1.0), "leg_x": 0.085 * width, "head_r": head_r,
        "width": width, "depth": spec.get("depth", 1.0),
    }


def build(name, spec):
    """Builds one character: returns its armature (with the skinned mesh as a child)."""
    P = proportions(spec)
    B = Builder(ghost=spec.get("ghost", False))
    body = spec.get("body", "person")
    {"person": _person, "can": _can, "disc": _disc, "tin": _tin, "boombox": _boombox}[body](B, spec, P)
    for acc in spec.get("acc", []):
        ACCESSORIES[acc if isinstance(acc, str) else acc[0]](B, spec, P, *([] if isinstance(acc, str) else acc[1:]))
    mesh = B.to_object(name + "_mesh")
    arm = make_armature(name, P)
    mesh.parent = arm
    mod = mesh.modifiers.new("Armature", "ARMATURE")
    mod.object = arm
    add_animations(arm)
    arm.scale = (P["s"],) * 3
    return arm


def _face(B, spec, P, cx=0.0, cz=None, eye_gap=0.085, eye_size=0.04, front=None, bone="head"):
    """Eyes (with a highlight) and a little mouth on the front of the head."""
    hz = cz if cz is not None else P["torso_top"] + P["head_r"]
    fy = front if front is not None else -P["head_r"] * 0.93
    eye = spec.get("eyes", "#1a1020")
    for sx in (-1, 1):
        B.sphere((cx + sx * eye_gap, fy, hz + 0.01), (eye_size * 0.8, eye_size * 0.5, eye_size * 1.15), eye, bone, segs=8,
                 emit=spec.get("eye_glow", 0.0), ghost=False if not spec.get("ghost") else None)
        if not spec.get("eye_glow"):
            B.sphere((cx + sx * eye_gap + 0.012, fy - 0.022, hz + 0.03), (0.011, 0.008, 0.011), "#ffffff", bone, segs=6)
    if spec.get("mouth", True):
        B.box((cx, fy + 0.005, hz - 0.085), (0.06, 0.02, 0.016), spec.get("mouth_color", "#a83a44"), bone)
    if spec.get("blush"):
        for sx in (-1, 1):
            B.sphere((cx + sx * 0.15, fy + 0.03, hz - 0.04), (0.035, 0.01, 0.02), "#ff9aa8", bone, segs=6)


def _person(B, spec, P):
    w, d = P["width"], P["depth"]
    skin = spec.get("skin", "#f2c09a")
    top = spec.get("top", "#888888")
    bottom = spec.get("bottom", "#555555")
    shoes = spec.get("shoes", "#333333")
    hip, tt, th = P["hip_z"], P["torso_top"], P["torso_h"]
    # Legs and feet
    for sx in (-1, 1):
        lx = sx * P["leg_x"]
        leg_color = spec.get("legs", bottom)
        if spec.get("shorts"):
            B.cylinder((lx, 0, hip - 0.07), 0.075 * w, 0.16, bottom, "leg.L" if sx > 0 else "leg.R", segs=8)
            B.cylinder((lx, 0, (hip - 0.15) / 2 + 0.04), 0.055, hip - 0.17, skin, "leg.L" if sx > 0 else "leg.R", segs=8)
        else:
            B.cylinder((lx, 0, hip / 2 + 0.02), 0.068 * w, hip - 0.02, leg_color, "leg.L" if sx > 0 else "leg.R", segs=8)
        B.box((lx, -0.03, 0.035), (0.11 * w, 0.17, 0.07), shoes, "leg.L" if sx > 0 else "leg.R", bevel=0.015)
    # Hips / skirt
    if spec.get("dress"):
        B.cylinder((0, 0, hip - 0.06), 0.2 * w, 0.32, spec["dress"], "hips", radius2=0.13 * w, segs=12, smooth=True)
    else:
        B.box((0, 0, hip), (0.3 * w, 0.2 * d, 0.1), bottom, "hips", bevel=0.02)
    # Torso
    belly = spec.get("belly", 0.0)
    B.sphere((0, 0, hip + th * 0.5), (0.2 * w, 0.14 * d + belly * 0.08, th * 0.62), top, "torso", segs=12)
    if belly:
        B.sphere((0, -0.06 * d - belly * 0.05, hip + th * 0.38), (0.17 * w, 0.12 + belly * 0.06, th * 0.4), top, "torso", segs=10)
    # Neck and head
    B.cylinder((0, 0, tt - 0.01), 0.06, 0.06, skin, "torso", segs=8)
    hz = tt + P["head_r"]
    B.sphere((0, 0, hz), (P["head_r"], P["head_r"] * 0.95, P["head_r"] * 0.98), skin, "head", segs=14)
    for sx in (-1, 1):
        B.sphere((sx * P["head_r"] * 0.98, 0, hz - 0.02), (0.035, 0.03, 0.05), skin, "head", segs=6)
    if spec.get("face", True):
        _face(B, spec, P)
    # Arms
    sleeve = spec.get("sleeves", top)
    for sx in (-1, 1):
        bone = "arm.L" if sx > 0 else "arm.R"
        ax = sx * P["shoulder_x"]
        sz = P["shoulder_z"]
        al = P["arm_len"]
        thick = spec.get("arm_thick", 1.0)
        B.sphere((ax, 0, sz), (0.07 * thick, 0.07 * thick, 0.07 * thick), sleeve, bone, segs=8)
        B.cylinder((ax, 0, sz - al * 0.45), 0.055 * thick, al * 0.85, sleeve if spec.get("long_sleeves", True) else skin, bone, segs=8)
        B.sphere((ax, 0, sz - al), (0.06 * thick, 0.06 * thick, 0.065 * thick), spec.get("hands", skin), bone, segs=8)
    _hair(B, spec, P)


def _hair(B, spec, P):
    style = spec.get("hair", "short")
    c = spec.get("hair_color", "#3c2418")
    r = P["head_r"]
    hz = P["torso_top"] + r
    if style == "none":
        return
    if style in ("short", "long", "bob", "buzz", "slick", "ponytail"):
        grow = 1.06 if style != "buzz" else 1.02
        # Cap of hair over the top and back, leaving the face clear.
        B.sphere((0, 0.015, hz + 0.01), (r * grow, r * grow, r * grow), c, "head", segs=14,
                 keep=lambda v: v.z > -0.05 and not (v.y < -0.55 and v.z < 0.55))
    if style == "slick":
        B.sphere((0, -0.05, hz + r * 0.75), (r * 0.7, r * 0.5, r * 0.3), c, "head", segs=10)
    if style in ("long", "bob", "ponytail"):
        length = {"long": 0.46, "bob": 0.2, "ponytail": 0.0}[style]
        if length:
            # A soft curtain of hair down the back, and locks framing the face.
            B.sphere((0, r * 0.38, hz - length * 0.42), (r * 1.0, r * 0.62, length * 0.6 + r * 0.45), c, "head", segs=12)
            for sx in (-1, 1):
                B.sphere((sx * r * 0.82, -r * 0.05, hz - length * 0.3), (r * 0.17, r * 0.32, length * 0.42 + r * 0.22), c, "head", segs=8)
        else:
            B.sphere((0, r * 1.05, hz - 0.02), (0.09, 0.09, 0.16), c, "head", segs=8)
    if style == "receding":
        # Cole: sides and back only.
        B.sphere((0, 0.02, hz - 0.01), (r * 1.04, r * 1.04, r * 1.04), c, "head", segs=14,
                 keep=lambda v: -0.25 < v.z < 0.45 and v.y > -0.2)
    if spec.get("mustache"):
        B.box((0, -r * 0.97, hz - 0.055), (0.13, 0.03, 0.035), spec.get("mustache_color", c), "head", bevel=0.01)
    if spec.get("beard"):
        B.sphere((0, -r * 0.55, hz - r * 0.62), (r * 0.75, r * 0.45, r * 0.35), spec["beard"], "head", segs=10)


def _can(B, spec, P):
    """Energy drink can: a body that is also the head. Tiny arms and legs."""
    tall = spec.get("tall", 1.0)
    c = spec.get("top", "#3ad1ff")
    h = 0.62 * tall
    for sx in (-1, 1):
        B.cylinder((sx * 0.08, 0, 0.1), 0.035, 0.18, "#2a2a2a", "leg.L" if sx > 0 else "leg.R", segs=6)
        B.box((sx * 0.08, -0.03, 0.03), (0.08, 0.12, 0.05), "#2a2a2a", "leg.L" if sx > 0 else "leg.R", bevel=0.01)
    B.cylinder((0, 0, 0.2 + h / 2), 0.2, h, c, "torso", segs=14, smooth=True)
    B.cylinder((0, 0, 0.2 + h + 0.02), 0.17, 0.04, "#cfd3dc", "torso", segs=14, radius2=0.15, metal=0.8)
    B.box((0, -0.2, 0.2 + h * 0.4), (0.22, 0.02, h * 0.35), spec.get("label", "#ffffff"), "torso")
    for sx in (-1, 1):
        bone = "torso"  # tiny arms stay on the body (the arm bones are person-sized)
        B.cylinder((sx * 0.22, 0, 0.2 + h * 0.55 - 0.08), 0.03, 0.16, "#2a2a2a", bone, segs=6)
        B.sphere((sx * 0.22, 0, 0.2 + h * 0.55 - 0.17), (0.04, 0.04, 0.04), "#2a2a2a", bone, segs=6)
    _face(B, spec, P, cz=0.2 + h * 0.72, front=-0.2, bone="torso", eye_gap=0.07)


def _disc(B, spec, P):
    """Nicotine pouch: a soft rounded pillow standing on its edge."""
    c = spec.get("top", "#e8e8f0")
    for sx in (-1, 1):
        B.cylinder((sx * 0.07, 0, 0.08), 0.03, 0.14, "#555566", "leg.L" if sx > 0 else "leg.R", segs=6)
    B.sphere((0, 0, 0.36), (0.26, 0.11, 0.22), c, "torso", segs=12)
    for sx in (-1, 1):
        bone = "torso"
        B.sphere((sx * 0.27, 0, 0.3), (0.035, 0.035, 0.035), "#555566", bone, segs=6)
    _face(B, spec, P, cz=0.4, front=-0.1, bone="torso", eye_gap=0.07, eye_size=0.035)


def _tin(B, spec, P):
    """Pouch tin: a flat round tin standing on its edge, lid on the front."""
    c = spec.get("top", "#6fb3e0")
    for sx in (-1, 1):
        B.cylinder((sx * 0.1, 0, 0.08), 0.035, 0.16, "#2a2a3a", "leg.L" if sx > 0 else "leg.R", segs=6)
    B.cylinder((0, 0, 0.42), 0.3, 0.18, c, "torso", rot=(90, 0, 0), segs=16, smooth=True)
    B.cylinder((0, -0.1, 0.42), 0.31, 0.04, spec.get("lid", "#d0e6f5"), "torso", rot=(90, 0, 0), segs=16, smooth=True)
    for sx in (-1, 1):
        bone = "torso"
        B.sphere((sx * 0.32, 0, 0.36), (0.04, 0.04, 0.04), "#2a2a3a", bone, segs=6)
    _face(B, spec, P, cz=0.45, front=-0.125, bone="torso", eye_gap=0.09)


def _boombox(B, spec, P):
    c = spec.get("top", "#2d2d2d")
    for sx in (-1, 1):
        B.cylinder((sx * 0.15, 0, 0.07), 0.03, 0.12, "#111111", "leg.L" if sx > 0 else "leg.R", segs=6)
    B.box((0, 0, 0.36), (0.8, 0.28, 0.44), c, "torso", bevel=0.03)
    for sx in (-1, 1):
        B.cylinder((sx * 0.22, -0.15, 0.36), 0.14, 0.03, "#888888", "torso", rot=(90, 0, 0), segs=14, metal=0.6)
        B.cylinder((sx * 0.22, -0.165, 0.36), 0.07, 0.02, "#111111", "torso", rot=(90, 0, 0), segs=12)
    B.box((0, -0.15, 0.47), (0.18, 0.02, 0.07), "#7cff4f", "torso", emit=2.0)
    B.box((0, 0, 0.62), (0.5, 0.05, 0.05), "#555555", "torso")
    for sx in (-1, 1):
        B.box((sx * 0.25, 0, 0.6), (0.04, 0.05, 0.08), "#555555", "torso")


# --------------------------------------------------------------------- accessories
def _head_z(P):
    return P["torso_top"] + P["head_r"]


def acc_cap(B, s, P, color="#1c1c26", brim=None, logo=None):
    r, hz = P["head_r"], _head_z(P)
    B.sphere((0, 0.01, hz + r * 0.35), (r * 1.08, r * 1.08, r * 0.75), color, "head", segs=14, cut_below=0.0)
    B.box((0, -r * 1.05, hz + r * 0.38), (r * 1.3, r * 0.75, 0.025), brim or color, "head", rot=(-8, 0, 0), bevel=0.01)
    if logo:
        B.box((0, -r * 1.0, hz + r * 0.62), (0.07, 0.02, 0.05), logo, "head")


def acc_trucker_hat(B, s, P, color="#2c3e50", front="#ecf0f1"):
    acc_cap(B, s, P, color, color, None)
    r, hz = P["head_r"], _head_z(P)
    B.box((0, -r * 0.9, hz + r * 0.62), (r * 1.2, 0.04, r * 0.5), front, "head", rot=(-20, 0, 0))


def acc_visor(B, s, P, color="#ffcc33"):
    r, hz = P["head_r"], _head_z(P)
    B.cylinder((0, 0, hz + r * 0.45), r * 1.07, 0.06, color, "head", segs=14)
    B.box((0, -r * 1.05, hz + r * 0.42), (r * 1.2, r * 0.7, 0.02), color, "head", rot=(-10, 0, 0))


def acc_shades(B, s, P, color="#0a0a12"):
    r, hz = P["head_r"], _head_z(P)
    for sx in (-1, 1):
        B.box((sx * 0.085, -r * 0.98, hz + 0.015), (0.11, 0.025, 0.065), color, "head", bevel=0.01)
    B.box((0, -r * 0.99, hz + 0.03), (0.06, 0.02, 0.015), color, "head")


def acc_glasses(B, s, P, color="#2b2b33"):
    r, hz = P["head_r"], _head_z(P)
    for sx in (-1, 1):
        x = sx * 0.085
        for dz, w, h in ((0.045, 0.1, 0.012), (-0.03, 0.1, 0.012)):
            B.box((x, -r * 1.0, hz + 0.01 + dz), (w, 0.015, h), color, "head")
        for dx in (-0.05, 0.05):
            B.box((x + dx, -r * 1.0, hz + 0.017), (0.012, 0.015, 0.08), color, "head")
    B.box((0, -r * 1.0, hz + 0.03), (0.05, 0.015, 0.012), color, "head")


def acc_headphones(B, s, P, color="#222222", cushion="#e84393"):
    r, hz = P["head_r"], _head_z(P)
    B.sphere((0, 0, hz), (r * 1.13, r * 0.22, r * 1.13), color, "head", segs=14, cut_below=0.25)
    for sx in (-1, 1):
        B.cylinder((sx * r * 1.05, 0, hz - 0.01), 0.075, 0.07, cushion, "head", rot=(0, 90, 0), segs=12)


def acc_stirrer(B, s, P, side=1):
    r, hz = P["head_r"], _head_z(P)
    B.box((side * r * 1.02, -0.02, hz + 0.05), (0.018, 0.22, 0.018), "#d35400", "head", rot=(20, 0, 0))


def acc_tie(B, s, P, color="#ff3b4a", collar="#f4f4f0"):
    hip, th, tt = P["hip_z"], P["torso_h"], P["torso_top"]
    front = -0.14 * P["depth"] - 0.01
    B.box((0, front + 0.005, tt - 0.05), (0.14, 0.04, 0.06), collar, "torso")
    B.box((0, front - 0.005, hip + th * 0.55), (0.05, 0.02, th * 0.55), color, "torso", rot=(0, 0, 0))


def acc_watch(B, s, P, color="#1a1a22"):
    ax, sz, al = P["shoulder_x"], P["shoulder_z"], P["arm_len"]
    B.cylinder((ax, 0, sz - al * 0.8), 0.062, 0.035, color, "arm.L", segs=8)


def acc_hood(B, s, P, color="#1b1b2f"):
    r, hz = P["head_r"], _head_z(P)
    B.sphere((0, 0.04, hz + 0.02), (r * 1.2, r * 1.15, r * 1.18), color, "head", segs=14,
             keep=lambda v: not (v.y < -0.35 and abs(v.x) < 0.75 and -0.75 < v.z < 0.65))


def acc_chef_hat(B, s, P, color="#ffffff"):
    r, hz = P["head_r"], _head_z(P)
    B.cylinder((0, 0, hz + r * 0.85), r * 0.85, r * 0.4, color, "head", segs=12)
    B.sphere((0, 0, hz + r * 1.25), (r * 0.95, r * 0.95, r * 0.45), color, "head", segs=12)


def acc_paper_hat(B, s, P, color="#ffffff", stripe="#e74c3c"):
    r, hz = P["head_r"], _head_z(P)
    B.box((0, 0, hz + r * 0.95), (r * 1.6, r * 0.9, r * 0.35), color, "head")
    B.box((0, -r * 0.46, hz + r * 0.95), (r * 1.62, 0.01, r * 0.1), stripe, "head")


def acc_santa_hat(B, s, P):
    r, hz = P["head_r"], _head_z(P)
    B.cylinder((0, 0, hz + r * 0.7), r * 1.07, 0.08, "#ffffff", "head", segs=14)
    B.cylinder((0.05, 0.03, hz + r * 1.2), r * 0.95, r * 0.9, "#d63031", "head", radius2=0.02, rot=(10, -15, 0), segs=12)
    B.sphere((0.17, 0.12, hz + r * 1.6), (0.05, 0.05, 0.05), "#ffffff", "head", segs=8)


def acc_witch_hat(B, s, P, color="#1b1b2f"):
    r, hz = P["head_r"], _head_z(P)
    B.cylinder((0, 0, hz + r * 0.62), r * 1.6, 0.03, color, "head", segs=16)
    B.cylinder((0, 0.03, hz + r * 1.3), r * 0.9, r * 1.4, color, "head", radius2=0.02, rot=(8, 0, 0), segs=12)
    B.cylinder((0, 0, hz + r * 0.7), r * 0.92, 0.06, "#9b5cff", "head", segs=12)


def acc_hivis(B, s, P):
    hip, th, w, d = P["hip_z"], P["torso_h"], P["width"], P["depth"]
    B.sphere((0, 0, hip + th * 0.5), (0.215 * w, 0.155 * d + s.get("belly", 0) * 0.08, th * 0.6), "#d7ff3a", "torso", segs=12,
             keep=lambda v: -0.8 < v.z < 0.8)
    for z in (0.35, 0.6):
        B.box((0, -0.16 * d - s.get("belly", 0) * 0.08, hip + th * z), (0.36 * w, 0.02, 0.025), "#dfe6e9", "torso", metal=0.5)


def acc_apron(B, s, P, color="#ffffff"):
    hip, th, d = P["hip_z"], P["torso_h"], P["depth"]
    B.box((0, -0.15 * d - s.get("belly", 0) * 0.1, hip + th * 0.25), (0.3 * P["width"], 0.02, th * 0.9), color, "torso")


def acc_lanyard(B, s, P, color="#ff3b4a"):
    hip, th, tt, d = P["hip_z"], P["torso_h"], P["torso_top"], P["depth"]
    for sx in (-1, 1):
        B.box((sx * 0.05, -0.145 * d, tt - th * 0.25), (0.015, 0.01, th * 0.45), color, "torso", rot=(0, sx * 12, 0))
    B.box((0, -0.15 * d, hip + th * 0.45), (0.08, 0.01, 0.1), "#ffffff", "torso")


def acc_belt(B, s, P, color="#1a1a1a"):
    B.cylinder((0, 0, P["hip_z"] + 0.05), 0.2 * P["width"], 0.06, color, "hips", segs=12, sy=0.75)


def acc_pattern(B, s, P, color="#f0f4ff"):
    """Cole's patterned button-up: a few light squares on the shirt front."""
    hip, th, d = P["hip_z"], P["torso_h"], P["depth"]
    for i, (x, z) in enumerate([(-0.09, 0.3), (0.06, 0.25), (-0.03, 0.55), (0.1, 0.6), (-0.11, 0.75), (0.04, 0.8)]):
        B.box((x, -0.135 * d - 0.012, hip + th * z), (0.035, 0.01, 0.035), color, "torso", rot=(0, 45, 0))
    B.box((0, -0.14 * d - 0.012, hip + th * 0.5), (0.012, 0.01, th * 0.8), color, "torso")


def acc_stripes(B, s, P, c1="#ff3b4a", c2="#14b05a"):
    """Mason's kit trim: colored bands on the sleeves and collar."""
    ax, sz = P["shoulder_x"], P["shoulder_z"]
    for sx, c in ((-1, c1), (1, c2)):
        B.cylinder((sx * ax, 0, sz - 0.08), 0.06, 0.03, c, "arm.L" if sx > 0 else "arm.R", segs=8)
    B.box((0, -0.14 * P["depth"], P["torso_top"] - 0.04), (0.14, 0.02, 0.03), c1, "torso")


def acc_number(B, s, P, color="#ffd23f"):
    hip, th, d = P["hip_z"], P["torso_h"], P["depth"]
    B.box((0, -0.14 * d - 0.012, hip + th * 0.5), (0.1, 0.01, 0.14), color, "torso")


def acc_lights(B, s, P):
    """Holiday sweater: little glowing bulbs."""
    hip, th, d = P["hip_z"], P["torso_h"], P["depth"]
    for i, (x, z, c) in enumerate([(-0.12, 0.35, "#ff3b3b"), (-0.04, 0.45, "#ffd23f"), (0.05, 0.38, "#3bff6a"),
                                   (0.13, 0.5, "#3bb2ff"), (-0.1, 0.7, "#ffd23f"), (0.08, 0.72, "#ff3b3b")]):
        B.sphere((x, -0.14 * d - 0.015, hip + th * z), (0.022, 0.022, 0.022), c, "torso", segs=6, emit=2.5)


def acc_scythe(B, s, P):
    ax, sz, al = P["shoulder_x"], P["shoulder_z"], P["arm_len"]
    hx, hz = -ax, sz - al
    B.cylinder((hx, -0.02, hz + 0.25), 0.025, 1.6, "#6d4c41", "arm.R", segs=6)
    B.box((hx - 0.22, -0.02, hz + 1.02), (0.5, 0.025, 0.1), "#bdc3c7", "arm.R", rot=(0, -20, 0), metal=0.8)
    B.box((hx - 0.46, -0.02, hz + 0.92), (0.12, 0.025, 0.12), "#bdc3c7", "arm.R", rot=(0, 30, 0), metal=0.8)


def acc_laptop(B, s, P, side=1, color="#2d3436", screen="#7fd4ff"):
    ax, sz, al = P["shoulder_x"], P["shoulder_z"], P["arm_len"]
    bone = "arm.L" if side > 0 else "arm.R"
    x, z = side * ax, sz - al - 0.02
    B.box((x, -0.12, z), (0.26, 0.2, 0.02), color, bone)
    B.box((x, -0.02, z + 0.1), (0.26, 0.02, 0.18), color, bone, rot=(-15, 0, 0))
    B.box((x, -0.035, z + 0.1), (0.22, 0.01, 0.14), screen, bone, rot=(-15, 0, 0), emit=3.0)


def acc_bottle(B, s, P, color="#e67e22"):
    ax, sz, al = P["shoulder_x"], P["shoulder_z"], P["arm_len"]
    x, z = ax, sz - al - 0.02
    B.cylinder((x, -0.06, z + 0.06), 0.055, 0.18, color, "arm.L", segs=10, smooth=True)
    B.cylinder((x, -0.06, z + 0.19), 0.04, 0.08, color, "arm.L", radius2=0.012, segs=10)
    B.box((x, -0.115, z + 0.06), (0.07, 0.01, 0.07), "#ffffff", "arm.L")


def acc_spatula(B, s, P):
    ax, sz, al = P["shoulder_x"], P["shoulder_z"], P["arm_len"]
    x, z = -ax, sz - al
    B.cylinder((x, -0.05, z + 0.12), 0.015, 0.3, "#5d4037", "arm.R", segs=6)
    B.box((x, -0.05, z + 0.33), (0.12, 0.015, 0.14), "#b2bec3", "arm.R", metal=0.8)


def acc_keyboard(B, s, P):
    sz, al = P["shoulder_z"], P["arm_len"]
    B.box((0, -0.18, sz - al + 0.02), (0.5, 0.14, 0.03), "#2d3436", "torso")
    for i in range(5):
        B.box((-0.18 + i * 0.09, -0.2, sz - al + 0.04), (0.06, 0.08, 0.015), "#dfe6e9", "torso")


def acc_mug(B, s, P, color="#ffffff"):
    ax, sz, al = P["shoulder_x"], P["shoulder_z"], P["arm_len"]
    B.cylinder((ax, -0.06, sz - al + 0.03), 0.045, 0.09, color, "arm.L", segs=10)


def acc_fish(B, s, P):
    ax, sz, al = P["shoulder_x"], P["shoulder_z"], P["arm_len"]
    B.cylinder((ax, -0.1, sz - al), 0.12, 0.02, "#ecf0f1", "arm.L", segs=12)
    B.sphere((ax, -0.1, sz - al + 0.03), (0.09, 0.04, 0.03), "#fa8072", "arm.L", segs=8)


def acc_golf_bag(B, s, P):
    hip, th = P["hip_z"], P["torso_h"]
    B.cylinder((0.12, 0.2, hip + th * 0.4), 0.09, 0.55, s.get("bag", "#1e3799"), "torso", rot=(-15, 20, 0), segs=10, ghost=s.get("ghost"))
    for dx in (-0.03, 0.0, 0.03):
        B.cylinder((0.18 + dx, 0.28, hip + th * 0.4 + 0.33), 0.012, 0.18, "#bdc3c7", "torso", rot=(-15, 20, 0), segs=5, metal=0.8)


def acc_badge(B, s, P, color="#f1c40f"):
    hip, th, d = P["hip_z"], P["torso_h"], P["depth"]
    B.box((0.08, -0.15 * d, hip + th * 0.7), (0.06, 0.01, 0.07), color, "torso", rot=(0, 25, 0))


def acc_throne(B, s, P):
    """Sam's Booster Seat Throne: a gold seat behind her."""
    B.box((0, 0.28, 0.25), (0.62, 0.3, 0.5), "#d4af37", "root", metal=0.7, bevel=0.03)
    B.box((0, 0.42, 0.75), (0.62, 0.1, 0.6), "#d4af37", "root", metal=0.7, bevel=0.03)
    B.box((0, 0.36, 0.52), (0.5, 0.05, 0.5), "#8e44ad", "root")


def acc_shako(B, s, P, color="#8e44ad", plume="#f1c40f"):
    r, hz = P["head_r"], _head_z(P)
    B.cylinder((0, 0, hz + r * 0.85), r * 0.9, r * 0.7, color, "head", segs=12)
    B.box((0, -r * 0.95, hz + r * 0.5), (r * 1.1, r * 0.4, 0.02), "#111111", "head")
    B.cylinder((0, 0, hz + r * 1.35), 0.03, 0.2, plume, "head", segs=6, radius2=0.06)


def acc_jacket_stripes(B, s, P, color="#ffd23f"):
    for sx in (-1, 1):
        B.box((sx * 0.06, -0.14 * P["depth"] - 0.01, P["hip_z"] + P["torso_h"] * 0.5), (0.025, 0.01, P["torso_h"] * 0.9), color, "torso")


ACCESSORIES = {
    "cap": acc_cap, "trucker_hat": acc_trucker_hat, "visor": acc_visor, "shades": acc_shades,
    "glasses": acc_glasses, "headphones": acc_headphones, "stirrer": acc_stirrer, "tie": acc_tie,
    "watch": acc_watch, "hood": acc_hood, "chef_hat": acc_chef_hat, "paper_hat": acc_paper_hat,
    "santa_hat": acc_santa_hat, "witch_hat": acc_witch_hat, "hivis": acc_hivis, "apron": acc_apron,
    "lanyard": acc_lanyard, "belt": acc_belt, "pattern": acc_pattern, "stripes": acc_stripes,
    "number": acc_number, "lights": acc_lights, "scythe": acc_scythe, "laptop": acc_laptop,
    "bottle": acc_bottle, "spatula": acc_spatula, "keyboard": acc_keyboard, "mug": acc_mug,
    "fish": acc_fish, "golf_bag": acc_golf_bag, "badge": acc_badge, "throne": acc_throne,
    "shako": acc_shako, "jacket_stripes": acc_jacket_stripes,
}
