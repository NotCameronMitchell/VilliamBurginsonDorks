"""
The game's cinematic trailer, built and rendered in Blender (see make_trailer.ps1).

    blender -b -P art/trailer/trailer.py -- --stage frames --out DIR [--res 1280x720]
    blender -b -P art/trailer/trailer.py -- --stage edit --out DIR --audio trailer_audio.wav

--stage frames  builds the scene and renders every frame to DIR/frames/ (resumable: frames
                that exist are skipped). --frames A-B renders just those frames.
--stage stills  renders one frame from the middle of each shot to DIR/stills/ (to check).
--stage edit    cuts DIR/frames/ together with the titles, subtitles, fades and the
                soundtrack into DIR/trailer.mp4.

A frozen office at night, the Ghost of James Civelli on a throne of office chairs, and the
heroes (the game's own models, assets/models/heroes/*.glb) clocking in to fight him.
The shot list, narration and text live in timeline.py.
"""

import math
import os
import random
import sys

import bpy
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import timeline as TL  # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "art", "tools"))
import hero_specs as HS  # noqa: E402  (the characters' real heights)
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def arg(name, default=None):
    if name in ARGS:
        i = ARGS.index(name)
        return ARGS[i + 1] if i + 1 < len(ARGS) and not ARGS[i + 1].startswith("--") else True
    return default


OUT = arg("--out", os.path.join(ROOT, "build", "trailer"))
LOG = arg("--log")
FPS = TL.FPS
FONT_TITLE = r"C:\Windows\Fonts\palab.ttf"
FONT_TEXT = r"C:\Windows\Fonts\segoeui.ttf"
FONT_LIGHT = r"C:\Windows\Fonts\segoeuil.ttf"
HERO_COLORS = {"mason": "#ff4f6d", "james": "#ffd23f", "cole": "#ff9a1f", "cam": "#4fc3ff",
               "sam": "#9b5cff", "sarah": "#ff5fa2"}
ANIMS = ["idle", "walk", "attack", "cast", "hit", "stunned", "faint", "victory", "ultimate", "run"]
# How fast the walk and run clips move at 1x, in meters per second, for a 1.75 m person
# (measured from the Kimodo motions). A character's clip is played faster or slower so its
# feet match how fast it actually travels, instead of sliding.
WALK_SPEED = 1.85
RUN_SPEED = 3.55
GHOST_SCALE = 1.15  # the ghost towers over the heroes
random.seed(3)


def log(msg):
    print(msg)
    if LOG:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(msg + "\n")


def F(t):
    """Seconds to a frame number (frame 1 = 0 s)."""
    return int(round(t * FPS)) + 1


def hexc(h, a=1.0):
    c = [int(h[i:i + 2], 16) / 255.0 for i in (1, 3, 5)]
    c = [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return (*c, a)


# =========================================================================== materials
def node_mat(name):
    m = bpy.data.materials.new(name)
    try:
        m.use_nodes = True
    except Exception:
        pass
    return m, m.node_tree, next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")


def set_in(node, names, value):
    for n in names if isinstance(names, (list, tuple)) else [names]:
        if n in node.inputs:
            node.inputs[n].default_value = value
            return True
    return False


def mat(name, color, rough=0.6, metal=0.0, emit=None, strength=0.0, alpha=1.0):
    m, nt, b = node_mat(name)
    b.inputs["Base Color"].default_value = color if len(color) == 4 else (*color, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if emit is not None:
        set_in(b, ["Emission Color", "Emission"], emit if len(emit) == 4 else (*emit, 1))
        set_in(b, "Emission Strength", strength)
    if alpha < 1:
        b.inputs["Alpha"].default_value = alpha
        for attr, val in (("surface_render_method", "BLENDED"), ("blend_method", "BLEND")):
            try:
                setattr(m, attr, val)
            except Exception:
                pass
    return m


def noise_mix_mat(name, c1, c2, scale=3.0, rough=(0.5, 0.8), bump=0.15):
    """Two colors mixed by noise (frost, icy floors)."""
    m, nt, b = node_mat(name)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    nz = nt.nodes.new("ShaderNodeTexNoise")
    set_in(nz, "Scale", scale)
    set_in(nz, "Detail", 8.0)
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.42
    ramp.color_ramp.elements[1].position = 0.62
    nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
    nt.links.new(nz.outputs["Fac"], ramp.inputs["Fac"])
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    nt.links.new(ramp.outputs["Color"], mix.inputs[0])
    mix.inputs[6].default_value = c1
    mix.inputs[7].default_value = c2
    nt.links.new(mix.outputs[2], b.inputs["Base Color"])
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["To Min"].default_value = rough[0]
    mr.inputs["To Max"].default_value = rough[1]
    nt.links.new(ramp.outputs["Color"], mr.inputs["Value"])
    nt.links.new(mr.outputs["Result"], b.inputs["Roughness"])
    if bump:
        bp = nt.nodes.new("ShaderNodeBump")
        set_in(bp, "Strength", bump)
        nt.links.new(nz.outputs["Fac"], bp.inputs["Height"])
        nt.links.new(bp.outputs["Normal"], b.inputs["Normal"])
    return m


_ghost_mats = {}


def ghost_mat(src=None):
    """A spectral version of one of James's materials: his own texture in cold blue (so
    the beard and face still read), lit softly, glowing at the edges, a little see-through.
    Hair, brows and lashes keep their texture's transparency."""
    img, alpha = None, False
    if src is not None and src.use_nodes:
        # The image behind the base color, even through a tint node (the detailed ghost's
        # materials multiply their texture by a pale blue).
        bsdf = next((n for n in src.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
        stack = [l.from_node for l in bsdf.inputs["Base Color"].links] if bsdf else []
        seen = set()
        while stack and img is None:
            n = stack.pop()
            if n.name in seen:
                continue
            seen.add(n.name)
            if n.type == "TEX_IMAGE" and n.image:
                img = n.image
                alpha = bool(bsdf.inputs["Alpha"].links)
            else:
                for inp in n.inputs:
                    stack += [l.from_node for l in inp.links]
    keyname = (img.name if img else "", alpha)
    if keyname in _ghost_mats:
        return _ghost_mats[keyname]
    m, nt, b = node_mat("ghost_" + (img.name if img else "plain"))
    out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
    tint = nt.nodes.new("ShaderNodeRGB")
    tint.outputs[0].default_value = (0.42, 0.78, 1.0, 1)
    if img is not None:
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.image = img
        bw = nt.nodes.new("ShaderNodeRGBToBW")
        nt.links.new(tex.outputs["Color"], bw.inputs[0])
        mr = nt.nodes.new("ShaderNodeMapRange")
        mr.inputs["To Min"].default_value = 0.18
        mr.inputs["To Max"].default_value = 1.15
        nt.links.new(bw.outputs[0], mr.inputs["Value"])
        mul = nt.nodes.new("ShaderNodeMix")
        mul.data_type = "RGBA"
        mul.blend_type = "MULTIPLY"
        mul.inputs[0].default_value = 1.0
        nt.links.new(tint.outputs[0], mul.inputs[6])
        cm = nt.nodes.new("ShaderNodeCombineColor")
        for k in range(3):
            nt.links.new(mr.outputs["Result"], cm.inputs[k])
        nt.links.new(cm.outputs[0], mul.inputs[7])
        col = mul.outputs[2]
    else:
        tex = None
        col = tint.outputs[0]
    nt.links.new(col, b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.45
    set_in(b, ["Emission Color", "Emission"], (0.42, 0.78, 1.0, 1))
    nt.links.new(col, b.inputs["Emission Color"] if "Emission Color" in b.inputs else b.inputs["Emission"])
    set_in(b, "Emission Strength", 0.55)
    rim = nt.nodes.new("ShaderNodeEmission")
    rim.inputs["Color"].default_value = (0.5, 0.88, 1.0, 1)
    rim.inputs["Strength"].default_value = 4.0
    lw = nt.nodes.new("ShaderNodeLayerWeight")
    lw.inputs["Blend"].default_value = 0.3
    rr = nt.nodes.new("ShaderNodeMapRange")
    rr.inputs["From Min"].default_value = 0.45
    rr.inputs["From Max"].default_value = 1.0
    nt.links.new(lw.outputs["Facing"], rr.inputs["Value"])
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(rr.outputs["Result"], mix.inputs["Fac"])
    nt.links.new(b.outputs[0], mix.inputs[1])
    nt.links.new(rim.outputs[0], mix.inputs[2])
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    see = nt.nodes.new("ShaderNodeMixShader")
    if alpha and tex is not None:  # hair cards: their own alpha, a bit more see-through
        mul_a = nt.nodes.new("ShaderNodeMath")
        mul_a.operation = "MULTIPLY"
        mul_a.inputs[1].default_value = 0.8
        nt.links.new(tex.outputs["Alpha"], mul_a.inputs[0])
        nt.links.new(mul_a.outputs[0], see.inputs["Fac"])
    else:
        see.inputs["Fac"].default_value = 0.82
    nt.links.new(tr.outputs[0], see.inputs[1])
    nt.links.new(mix.outputs[0], see.inputs[2])
    nt.links.new(see.outputs[0], out.inputs["Surface"])
    _ghost_mats[keyname] = m
    return m


def emissive(name, color, strength):
    m, nt, b = node_mat(name)
    for n in list(nt.nodes):
        if n.type == "BSDF_PRINCIPLED":
            nt.nodes.remove(n)
    out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = color
    em.inputs["Strength"].default_value = strength
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    return m, em


# =========================================================================== geometry
_meshes = {}


def unit_mesh(kind):
    if kind in _meshes:
        return _meshes[kind]
    if kind == "cube":
        bpy.ops.mesh.primitive_cube_add(size=2)
    elif kind == "cyl":
        bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=1, depth=2)
    elif kind == "cone":
        bpy.ops.mesh.primitive_cone_add(vertices=8, radius1=1, radius2=0, depth=2)
    elif kind == "ico":
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=1)
    elif kind == "sphere":
        bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12, radius=1)
    elif kind == "plane":
        bpy.ops.mesh.primitive_plane_add(size=2)
    elif kind == "torus":
        bpy.ops.mesh.primitive_torus_add(major_radius=1, minor_radius=0.04, major_segments=48, minor_segments=8)
    tmp = bpy.context.active_object
    me = tmp.data
    me.name = "unit_" + kind
    bpy.data.objects.remove(tmp, do_unlink=True)
    _meshes[kind] = me
    return me


def prim(kind, name, loc, size, material, rot=(0, 0, 0), smooth=False):
    """size = half-extents for cubes (like scale), radius/half-depth for others."""
    me = unit_mesh(kind).copy() if material is not None else unit_mesh(kind)
    if material is not None:
        me.materials.clear()
        me.materials.append(material)
    if smooth:
        me.polygons.foreach_set("use_smooth", [True] * len(me.polygons))
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    o.location = loc
    o.scale = size
    o.rotation_euler = rot
    return o


def fcurves(id_data):
    """The F-curves of a datablock's action (Blender 5 keeps them in layered channel bags)."""
    ad = getattr(id_data, "animation_data", None)
    if not ad or not ad.action:
        return []
    act = ad.action
    try:
        fcs = list(act.fcurves)
    except Exception:
        fcs = []
    if not fcs:
        for layer in getattr(act, "layers", []):
            for strip in layer.strips:
                for cb in getattr(strip, "channelbags", []):
                    fcs.extend(cb.fcurves)
    return fcs


def set_interp(id_data, frame, interp, path_part=""):
    for fc in fcurves(id_data):
        if path_part in fc.data_path:
            for kp in fc.keyframe_points:
                if abs(kp.co[0] - frame) < 0.5:
                    kp.interpolation = interp


def key(obj, path, frame, value=None, interp="BEZIER"):
    """Keyframes obj.path; `interp` is how it moves from this key to the next one."""
    if value is not None:
        setattr(obj, path, value)
    obj.keyframe_insert(path, frame=frame)
    set_interp(obj, frame, interp, path)


def key_value(owner, prop, frame, value, interp="BEZIER"):
    """Keyframes a property of a light, node socket, etc. (any struct)."""
    setattr(owner, prop, value)
    owner.keyframe_insert(prop, frame=frame)
    set_interp(owner.id_data, frame, interp, prop)


def key_socket(sock, frame, value, interp="BEZIER"):
    key_value(sock, "default_value", frame, value, interp)


# =========================================================================== the set
def build_world():
    sc = bpy.context.scene
    w = bpy.data.worlds.new("trailer_world")
    sc.world = w
    try:
        w.use_nodes = True
    except Exception:
        pass
    nt = w.node_tree
    bg = next(n for n in nt.nodes if n.type == "BACKGROUND")
    bg.inputs[0].default_value = (0.006, 0.009, 0.02, 1)
    bg.inputs[1].default_value = 1.0
    out = next(n for n in nt.nodes if n.type == "OUTPUT_WORLD")
    vol = nt.nodes.new("ShaderNodeVolumePrincipled")
    set_in(vol, "Color", (0.62, 0.76, 1.0, 1))
    set_in(vol, "Density", 0.010)
    set_in(vol, "Anisotropy", 0.4)
    nt.links.new(vol.outputs[0], out.inputs["Volume"])


def build_office():
    floor = noise_mix_mat("ice_floor", (0.035, 0.05, 0.08, 1), (0.30, 0.42, 0.55, 1), 1.6, (0.12, 0.45), 0.05)
    frost = noise_mix_mat("frost", (0.42, 0.52, 0.62, 1), (0.85, 0.92, 1.0, 1), 4.0, (0.45, 0.8), 0.25)
    desk_m = noise_mix_mat("desk", (0.25, 0.27, 0.3, 1), (0.7, 0.8, 0.9, 1), 6.0, (0.4, 0.7), 0.1)
    snow_m = mat("snow", (0.85, 0.9, 1.0), 0.75)
    dark = mat("dark", (0.02, 0.025, 0.035), 0.7)
    screen_m, _ = emissive("screen", (0.25, 0.55, 1.0, 1), 1.6)
    panel_m, panel_em = emissive("ceiling_panel", (0.75, 0.85, 1.0, 1), 1.2)
    window_m, _ = emissive("window", (0.4, 0.55, 0.9, 1), 2.5)
    icicle = mat("icicle", (0.75, 0.9, 1.0), 0.08, emit=(0.4, 0.7, 1.0), strength=0.25)
    prim("cube", "floor", (0, 0, -0.05), (14, 40, 0.05), floor)
    prim("cube", "ceiling", (0, 0, 4.35), (14, 40, 0.1), dark)
    prim("cube", "wall_right", (9.5, 0, 2.2), (0.2, 40, 2.3), frost)
    prim("cube", "wall_back", (0, 31, 2.2), (14, 0.2, 2.3), frost)
    # Windows on the left wall, moonlight pouring through.
    for i, y in enumerate(range(-26, 28, 6)):
        prim("cube", "wall_left_%d" % i, (-9.5, y + 3, 2.2), (0.2, 1.2, 2.3), frost)
        prim("cube", "window_%d" % i, (-9.6, y, 2.4), (0.05, 1.8, 1.6), window_m)
    # Cubicles down both sides of the aisle.
    for side in (-1, 1):
        for i in range(10):
            y = -24 + i * 4.2
            x0 = side * 3.2
            prim("cube", "part_f_%d_%d" % (side, i), (x0, y, 0.75), (0.04, 1.9, 0.75), frost)
            prim("cube", "part_s_%d_%d" % (side, i), (x0 + side * 1.3, y - 1.9, 0.75), (1.3, 0.04, 0.75), frost)
            prim("cube", "desk_%d_%d" % (side, i), (x0 + side * 1.6, y, 0.74), (0.7, 1.5, 0.03), desk_m)
            mon = prim("cube", "monitor_%d_%d" % (side, i), (x0 + side * 1.75, y - 0.3, 1.02), (0.03, 0.32, 0.2),
                       screen_m if (i + side) % 3 == 0 else dark)
            mon.rotation_euler = (0, 0, math.radians(8 * side))
            prim("ico", "drift_%d_%d" % (side, i), (x0 - side * 0.15, y + random.uniform(-1, 1), 0.0),
                 (0.5, random.uniform(0.6, 1.2), 0.16), snow_m, smooth=True)
            for k in range(5):
                h = random.uniform(0.08, 0.28)
                prim("cone", "icicle_%d_%d_%d" % (side, i, k), (x0, y + random.uniform(-1.8, 1.8), 1.5 - h),
                     (0.025, 0.025, h), icicle, rot=(math.pi, 0, 0))
    # Ceiling light panels; a few flicker.
    flick = []
    for i, y in enumerate(range(-26, 28, 5)):
        for x in (-2, 2):
            p = prim("plane", "panel_%d_%d" % (i, x), (x, y, 4.24), (0.35, 0.8, 1), panel_m, rot=(math.pi, 0, 0))
            if (i * 7 + x) % 5 == 0:
                flick.append(p)
    # One flickering light over the aisle.
    lt = bpy.data.lights.new("flicker", "POINT")
    lt.energy = 120
    lt.color = (0.7, 0.8, 1.0)
    lo = bpy.data.objects.new("flicker", lt)
    bpy.context.scene.collection.objects.link(lo)
    lo.location = (0, -6, 3.9)
    for f in range(1, F(TL.LENGTH), 9):
        key_value(lt, "energy", f, 120 if random.random() > 0.25 else random.uniform(0, 30), "CONSTANT")


def build_lights():
    sc = bpy.context.scene

    def light(name, kind, loc, rot, energy, color, size=None, spot=None):
        ld = bpy.data.lights.new(name, kind)
        ld.energy = energy
        ld.color = color
        if size is not None:
            ld.shadow_soft_size = size
        if spot is not None:
            ld.spot_size = math.radians(spot)
            ld.spot_blend = 0.4
        o = bpy.data.objects.new(name, ld)
        sc.collection.objects.link(o)
        o.location = loc
        o.rotation_euler = rot
        return o

    light("moon", "SUN", (0, 0, 10), (math.radians(55), math.radians(-18), math.radians(-65)), 0.9, (0.6, 0.72, 1.0))
    for i, y in enumerate(range(-24, 28, 8)):  # god rays through the windows
        light("shaft_%d" % i, "SPOT", (-12, y, 6.5), (math.radians(65), 0, math.radians(-90)), 7000,
              (0.55, 0.7, 1.0), 0.3, 22)
    light("throne_back", "POINT", (0, 29.5, 4.2), (0, 0, 0), 1600, (0.3, 0.75, 1.0), 1.0)
    light("throne_top", "SPOT", (0, 19, 7.5), (math.radians(30), 0, 0), 1800, (0.6, 0.85, 1.0), 0.5, 30)
    light("throne_key", "AREA", (-2.5, 19.5, 3.0), (math.radians(70), 0, math.radians(-30)), 220, (0.75, 0.88, 1.0), 2.0)


def office_chair(name, loc, rot, s, ice):
    parts = [
        prim("cube", name + "_seat", (0, 0, 0.48), (0.26, 0.26, 0.05), ice),
        prim("cube", name + "_back", (0, 0.24, 0.85), (0.24, 0.04, 0.3), ice),
        prim("cyl", name + "_pole", (0, 0, 0.25), (0.03, 0.03, 0.22), ice),
    ]
    for k in range(5):
        a = k * 2 * math.pi / 5
        parts.append(prim("cube", name + "_leg%d" % k, (math.cos(a) * 0.15, math.sin(a) * 0.15, 0.04),
                          (0.15, 0.025, 0.02), ice, rot=(0, 0, a)))
    root = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(root)
    for p in parts:
        p.parent = root
    root.location = loc
    root.rotation_euler = rot
    root.scale = (s, s, s)
    return root


def build_throne():
    ice = mat("ice", (0.55, 0.8, 1.0), 0.06, emit=(0.3, 0.65, 1.0), strength=0.35)
    frost = bpy.data.materials["frost"]
    spike_m = mat("spike", (0.7, 0.9, 1.0), 0.05, emit=(0.35, 0.8, 1.0), strength=0.7)
    for i, (w, h) in enumerate(((5.0, 0.2), (4.2, 0.2), (3.4, 0.2))):
        prim("cube", "dais_%d" % i, (0, 24.0 + i * 0.4, 0.1 + i * 0.2), (w, 3.2 - i * 0.4, h / 2 + i * 0.2), frost)
    # A pile of frozen office chairs, the big one on top.
    for i in range(16):
        layer = 0 if i < 8 else (1 if i < 13 else 2)
        r = (2.4, 1.6, 0.8)[layer]
        a = (i % 8) * 2 * math.pi / 8 + layer * 0.4
        office_chair("pile_%d" % i, (math.cos(a) * r * 0.9, 26.6 + math.sin(a) * r * 0.5, 0.6 + layer * 0.75),
                     (random.uniform(-0.6, 0.6), random.uniform(-0.6, 0.6), random.uniform(0, 6.28)), 1.3, ice)
    office_chair("throne_seat", (0, 26.4, 2.2), (0, 0, math.pi), 2.4, ice)
    for k in range(13):  # crown of ice spikes fanning out behind
        a = math.radians(-70 + k * (140 / 12))
        h = 1.4 + 1.6 * math.cos(a) ** 2
        prim("cone", "spike_%d" % k, (math.sin(a) * 1.6, 28.0, 2.8 + math.cos(a) * h * 0.6),
             (0.16, 0.16, h), spike_m, rot=(0, a, 0))


def build_elevator():
    metal = mat("elevator_metal", (0.5, 0.55, 0.6), 0.25, metal=0.9)
    inside_m, _ = emissive("elevator_light", (1.0, 0.92, 0.8, 1), 2.2)
    frost = bpy.data.materials["frost"]
    prim("cube", "elev_wall_l", (-4.3, -30.5, 2.2), (2.6, 0.25, 2.3), frost)
    prim("cube", "elev_wall_r", (4.3, -30.5, 2.2), (2.6, 0.25, 2.3), frost)
    prim("cube", "elev_lintel", (0, -30.5, 3.6), (1.8, 0.25, 0.9), frost)
    prim("cube", "elev_back", (0, -34.2, 1.6), (2.0, 0.1, 1.6), inside_m)
    prim("cube", "elev_floor", (0, -32.4, -0.02), (2.0, 1.9, 0.02), metal)
    prim("cube", "elev_side_l", (-1.95, -32.4, 1.4), (0.05, 1.9, 1.4), inside_m)
    prim("cube", "elev_side_r", (1.95, -32.4, 1.4), (0.05, 1.9, 1.4), inside_m)
    doors = []
    for side in (-1, 1):
        d = prim("cube", "elev_door_%d" % side, (side * 0.9, -30.35, 1.35), (0.9, 0.05, 1.35), metal)
        key(d, "location", F(21.7), (side * 0.9, -30.35, 1.35))
        key(d, "location", F(23.0), (side * 2.7, -30.35, 1.35))
        doors.append(d)
    ld = bpy.data.lights.new("elevator", "AREA")
    ld.size = 3.0
    ld.color = (1.0, 0.92, 0.82)
    o = bpy.data.objects.new("elevator", ld)
    bpy.context.scene.collection.objects.link(o)
    o.location = (0, -33.8, 2.2)
    o.rotation_euler = (math.radians(-90), 0, 0)
    key_value(ld, "energy", F(21.6), 0.0, "LINEAR")
    key_value(ld, "energy", F(22.6), 320.0, "LINEAR")


def build_snow():
    snow_m, _ = emissive("snowflake", (0.85, 0.92, 1.0, 1), 0.6)
    flake = prim("ico", "flake", (0, 0, -50), (0.012, 0.012, 0.012), snow_m)
    em = prim("plane", "snow_emitter", (0, -2, 4.2), (9, 34, 1), None)
    em.hide_render = True
    mod = em.modifiers.new("snow", "PARTICLE_SYSTEM")
    ps = mod.particle_system.settings
    ps.count = 14000
    ps.frame_start = -400
    ps.frame_end = F(TL.LENGTH)
    ps.lifetime = 420
    ps.emit_from = "FACE"
    ps.normal_factor = 0.0
    ps.render_type = "OBJECT"
    ps.instance_object = flake
    ps.particle_size = 1.0
    ps.size_random = 0.6
    ps.brownian_factor = 0.12
    ps.drag_factor = 0.6
    ps.effector_weights.gravity = 0.035
    em.show_instancer_for_render = False
    # The title card gets its own snow.
    em2 = prim("plane", "snow_emitter_title", (300, -4, 4), (8, 6, 1), None)
    em2.hide_render = True
    mod2 = em2.modifiers.new("snow", "PARTICLE_SYSTEM")
    ps2 = mod2.particle_system.settings
    for attr in ("frame_start", "lifetime", "emit_from", "normal_factor", "render_type", "instance_object",
                 "size_random", "brownian_factor", "drag_factor"):
        setattr(ps2, attr, getattr(ps, attr))
    ps2.count = 2500
    ps2.frame_end = F(TL.LENGTH)
    ps2.effector_weights.gravity = 0.035
    em2.show_instancer_for_render = False


# =========================================================================== actors
def attach(obj, arm, bone):
    """Parents obj to an armature bone, keeping where it is (at the rest pose)."""
    arm.data.pose_position = "REST"
    bpy.context.view_layer.update()
    pb = arm.pose.bones[bone]
    tail = arm.matrix_world @ pb.matrix @ Matrix.Translation((0, pb.bone.length, 0))
    mw = obj.matrix_world.copy()
    obj.parent = arm
    obj.parent_type = "BONE"
    obj.parent_bone = bone
    obj.matrix_parent_inverse = tail.inverted()
    obj.matrix_world = mw
    arm.data.pose_position = "POSE"
    bpy.context.view_layer.update()


class Actor:
    def __init__(self, name, glb, scale=1.0):
        before_o, before_a = set(bpy.data.objects), set(bpy.data.actions)
        bpy.ops.import_scene.gltf(filepath=glb)
        new = [o for o in bpy.data.objects if o not in before_o]
        self.name = name
        self.arm = next(o for o in new if o.type == "ARMATURE")
        self.root = self.arm
        while self.root.parent is not None and self.root.parent in new:
            self.root = self.root.parent
        self.meshes = [o for o in new if o.type == "MESH"]
        self.acts = {}
        for a in set(bpy.data.actions) - before_a:
            for anim in ANIMS:
                if a.name == anim or a.name.startswith(anim + "_") or a.name.startswith(anim + "."):
                    a.name = "%s_%s" % (name, anim)
                    a.use_fake_user = True
                    self.acts[anim] = a
        ad = self.arm.animation_data or self.arm.animation_data_create()
        ad.action = None
        for t in list(ad.nla_tracks):
            ad.nla_tracks.remove(t)
        if self.root.rotation_mode == "QUATERNION":  # glTF imports use quaternions
            q = self.root.rotation_quaternion.copy()
            self.root.rotation_mode = "XYZ"
            self.root.rotation_euler = q.to_euler()
        self.root.scale = self.root.scale * scale
        self.home = Vector((0, -200, 0))
        bpy.context.view_layer.update()
        # Standing height, for matching the walk and run to how fast they move and for framing:
        # the character's real height at game scale (measuring the imported meshes in Blender's
        # rest pose came out wrong for these rigs).
        self.height = HS.spec(name)["height"] * HS.GAME_SCALE * scale
        log("actor %s: %.2f m, %d meshes, anims %s" % (name, self.height, len(self.meshes), sorted(self.acts)))

    def gait(self, anim, mps):
        """The playback speed that makes the walk or run clip travel at mps (no sliding)."""
        ref = (RUN_SPEED if anim == "run" else WALK_SPEED) * self.height / 1.75
        return mps / max(ref, 0.1)

    def play(self, anim, t, repeat=1.0, speed=1.0, hold=False, blend=4):
        act = self.acts.get(anim)
        if act is None:
            return None
        ad = self.arm.animation_data
        tr = ad.nla_tracks.new()
        tr.name = "%s@%.2f" % (anim, t)
        st = tr.strips.new(act.name, F(t), act)
        try:
            if getattr(st, "action_slot", None) is None and len(act.slots):
                st.action_slot = act.slots[0]
        except Exception:
            pass
        st.scale = 1.0 / speed
        st.repeat = repeat
        st.extrapolation = "HOLD" if hold else "NOTHING"
        length = st.frame_end - st.frame_start
        st.blend_in = min(blend, length / 3)
        st.blend_out = 0 if hold else min(blend, length / 3)
        return st

    def borrow(self, other, anim, as_name):
        """Uses another hero's animation (same rig), minus its hip height."""
        src = other.acts.get(anim)
        if src is None:
            return
        act = src.copy()
        act.name = "%s_%s" % (self.name, as_name)
        holder = bpy.data.objects.new("tmp_holder", None)  # to reach the copy's F-curves
        holder.animation_data_create().action = act
        for fc in fcurves(holder):
            if fc.data_path.endswith('"mixamorig:Hips"].location'):
                try:
                    fc.id_data.fcurves.remove(fc)
                except Exception:
                    for layer in getattr(act, "layers", []):
                        for strip in layer.strips:
                            for cb in getattr(strip, "channelbags", []):
                                if fc in list(cb.fcurves):
                                    cb.fcurves.remove(fc)
        holder.animation_data.action = None
        bpy.data.objects.remove(holder)
        act.use_fake_user = True
        self.acts[as_name] = act

    def pose_action(self, name, keys):
        """An action from hand-set poses. keys: [(time, {bone: (axis, degrees)}), ...] where
        axis is "x" (nod forward), "y" (swing sideways) or "z" (turn), in world space."""
        arm = self.arm
        ad = arm.animation_data
        saved = ad.action
        arm.data.pose_position = "POSE"
        to_arm = arm.matrix_world.to_3x3().normalized().inverted()
        for t, bones in keys:
            for pb in arm.pose.bones:
                pb.rotation_mode = "QUATERNION"
            for bname, (axis, deg) in bones.items():
                pb = arm.pose.bones.get("mixamorig:" + bname)
                if pb is None:
                    continue
                w = {"x": Vector((1, 0, 0)), "y": Vector((0, 1, 0)), "z": Vector((0, 0, 1))}[axis]
                a_arm = (to_arm @ w).normalized()
                rest = pb.bone.matrix_local.to_3x3()
                local = rest.inverted() @ Matrix.Rotation(math.radians(deg), 3, a_arm) @ rest
                pb.rotation_quaternion = local.to_quaternion()
                pb.keyframe_insert("rotation_quaternion", frame=F(t))
        act = ad.action
        act.name = "%s_%s" % (self.name, name)
        act.use_fake_user = True
        ad.action = saved
        self.acts[name] = act
        for pb in arm.pose.bones:
            pb.rotation_quaternion = (1, 0, 0, 0)

    def at(self, t, loc, rot_z=0.0, interp="CONSTANT"):
        """Puts the actor at loc at time t. Characters face -Y; rot_z=pi faces +Y.
        `interp` is how they get from here to their next position (CONSTANT = jump)."""
        self.root.location = loc
        self.root.rotation_euler = (self.root.rotation_euler[0], self.root.rotation_euler[1], rot_z)
        key(self.root, "location", F(t), interp=interp)
        key(self.root, "rotation_euler", F(t), interp=interp)

    def hide(self, t):
        self.at(t, self.home)

    def bone_world(self, bone, t_end="head"):
        pb = self.arm.pose.bones[bone]
        return self.arm.matrix_world @ (pb.head if t_end == "head" else pb.tail)


def make_ghost(path):
    g = Actor("ghost", path, scale=GHOST_SCALE)
    for o in g.meshes:
        for i, slot in enumerate(o.material_slots):
            o.data.materials[i] = ghost_mat(slot.material)
        o.visible_shadow = False
    bpy.context.view_layer.update()
    # Glowing eyes where James's eyes are.
    eyes = next((o for o in g.meshes if "high-poly" in o.name.lower() or "eye" in o.name.lower()), None)
    eye_m, eye_em = emissive("ghost_eyes", (0.55, 0.9, 1.0, 1), 8.0)
    g.eye_em = eye_em
    g.arm.data.pose_position = "REST"
    bpy.context.view_layer.update()
    if eyes is not None:
        cs = [eyes.matrix_world @ Vector(c) for c in eyes.bound_box]
        mn = Vector((min(c.x for c in cs), min(c.y for c in cs), min(c.z for c in cs)))
        mx = Vector((max(c.x for c in cs), max(c.y for c in cs), max(c.z for c in cs)))
        ctr = (mn + mx) / 2
        half = (mx.x - mn.x) / 4
        for side in (-1, 1):
            s = prim("sphere", "ghost_eye_%d" % side, (ctr.x + side * half, mn.y - 0.004, ctr.z), (0.011, 0.006, 0.008),
                     eye_m, smooth=True)
            attach(s, g.arm, "mixamorig:Head")
    # Ice crown on top of the head (the Head bone ends near the eyes, so use the meshes' top),
    # ice sword in the right hand. Everything is measured in the rest pose, because attach()
    # parents against the rest pose: measuring the posed rig left them floating off his head
    # and hand once he moved.
    g.arm.data.pose_position = "REST"
    bpy.context.view_layer.update()
    sc = g.root.scale[0]
    head = g.arm.pose.bones["mixamorig:Head"]
    ht_head = g.arm.matrix_world @ head.tail
    top_z = max((o.matrix_world @ Vector(c)).z for o in g.meshes for c in o.bound_box)
    top = Vector((ht_head.x, ht_head.y + 0.01 * sc, top_z - 0.035 * sc))
    crown_m = mat("crown", (0.7, 0.92, 1.0), 0.05, emit=(0.4, 0.85, 1.0), strength=3.0)
    crown = []
    for k in range(9):
        a = k * 2 * math.pi / 9
        h = (0.07 if k % 2 else 0.12) * sc
        crown.append(prim("cone", "crown_%d" % k, (top.x + math.cos(a) * 0.085 * sc, top.y + math.sin(a) * 0.085 * sc,
                                                   top.z - 0.03 * sc + h), (0.016 * sc, 0.016 * sc, h), crown_m))
    hand = g.arm.pose.bones["mixamorig:RightHand"]
    hh, ht = g.arm.matrix_world @ hand.head, g.arm.matrix_world @ hand.tail
    d = (ht - hh).normalized()  # along the hand, toward the fingers
    # A fist holds a sword square to the hand, the blade coming out of the thumb side.
    thumb = g.arm.pose.bones.get("mixamorig:RightHandThumb1")
    blade = Vector((0.0, -1.0, 0.0))
    if thumb is not None:
        tv = (g.arm.matrix_world @ thumb.head) - hh
        tv = tv - d * tv.dot(d)
        if tv.length > 1e-4:
            blade = tv.normalized()
    grip = hh + (ht - hh) * 0.5
    blade_m = mat("blade", (0.75, 0.95, 1.0), 0.03, emit=(0.4, 0.85, 1.0), strength=2.5)
    rot = blade.to_track_quat("Z", "Y").to_euler()
    parts = [prim("cube", "sword_blade", grip + blade * 0.62 * sc, (0.022 * sc, 0.006 * sc, 0.55 * sc), blade_m, rot=rot),
             prim("cube", "sword_guard", grip + blade * 0.06 * sc, (0.11 * sc, 0.02 * sc, 0.018 * sc), crown_m, rot=rot),
             prim("cyl", "sword_grip", grip - blade * 0.03 * sc, (0.016 * sc, 0.016 * sc, 0.06 * sc), crown_m, rot=rot)]
    for c in crown:
        attach(c, g.arm, "mixamorig:Head")
    for p in parts:
        attach(p, g.arm, "mixamorig:RightHand")
    g.arm.data.pose_position = "POSE"
    # A cold glow around him.
    ld = bpy.data.lights.new("ghost_glow", "POINT")
    ld.energy = 250
    ld.color = (0.4, 0.8, 1.0)
    ld.shadow_soft_size = 0.6
    lo = bpy.data.objects.new("ghost_glow", ld)
    bpy.context.scene.collection.objects.link(lo)
    lo.location = (0, 0.4, 1.4 * sc)
    lo.parent = g.root
    return g


# =========================================================================== effects
def burst(name, loc, t, color, count=220, speed=7.0, size=0.03, life=36, shard=True):
    """Ice shards (or sparks) flying out from loc at time t."""
    m, _ = emissive(name + "_m", color, 4.0)
    piece = prim("ico" if shard else "sphere", name + "_piece", (0, 0, -60),
                 (size * 0.5, size * 0.5, size * 2.2) if shard else (size, size, size), m)
    em = prim("ico", name + "_emit", loc, (0.15, 0.15, 0.15), None)
    em.hide_render = True
    mod = em.modifiers.new(name, "PARTICLE_SYSTEM")
    ps = mod.particle_system.settings
    ps.count = count
    ps.frame_start = F(t)
    ps.frame_end = F(t) + 3
    ps.lifetime = life
    ps.lifetime_random = 0.5
    ps.emit_from = "FACE"
    ps.normal_factor = speed
    ps.factor_random = speed * 0.5
    ps.render_type = "OBJECT"
    ps.instance_object = piece
    ps.size_random = 0.7
    ps.use_rotations = True
    ps.rotation_mode = "VEL"
    ps.effector_weights.gravity = 0.25
    ps.drag_factor = 0.2
    em.show_instancer_for_render = False
    flash(name + "_light", loc, t, color[:3], 6000 if shard else 2500)
    return em


def flash(name, loc, t, color, energy, dur=0.5):
    ld = bpy.data.lights.new(name, "POINT")
    ld.color = color
    ld.shadow_soft_size = 0.5
    o = bpy.data.objects.new(name, ld)
    bpy.context.scene.collection.objects.link(o)
    o.location = loc
    energy *= FLASH_SCALE  # point lights light up the fog a lot
    for tt, e in ((t - 0.05, 0), (t, energy), (t + dur, 0)):
        key_value(ld, "energy", F(tt), e, "LINEAR")


FLASH_SCALE = 0.3


def ring(name, loc, t, color, r1=2.4, dur=0.55):
    m, em = emissive(name + "_m", color, 6.0)
    o = prim("torus", name, loc, (0.2, 0.2, 0.2), m)
    key(o, "scale", F(t) - 1, (0.001, 0.001, 0.001), "LINEAR")
    key(o, "scale", F(t), (0.2, 0.2, 0.2), "LINEAR")
    key(o, "scale", F(t + dur), (r1, r1, r1 * 0.3), "LINEAR")
    key(o, "scale", F(t + dur) + 1, (0.001, 0.001, 0.001), "LINEAR")
    key_socket(em.inputs["Strength"], F(t), 8.0, "LINEAR")
    key_socket(em.inputs["Strength"], F(t + dur), 0.0, "LINEAR")


# =========================================================================== cameras
def camera(name, t0, t1, p0, p1, a0, a1, lens=35, fstop=None, shake=0.0):
    """A camera for one shot: moves from p0 to p1 while looking from a0 to a1."""
    sc = bpy.context.scene
    cd = bpy.data.cameras.new(name)
    cd.lens = lens
    cd.clip_end = 400
    cam = bpy.data.objects.new(name, cd)
    sc.collection.objects.link(cam)
    tgt = bpy.data.objects.new(name + "_target", None)
    sc.collection.objects.link(tgt)
    con = cam.constraints.new("TRACK_TO")
    con.target = tgt
    con.track_axis = "TRACK_NEGATIVE_Z"
    con.up_axis = "UP_Y"
    key(cam, "location", F(t0), p0)
    key(cam, "location", F(t1), p1)
    key(tgt, "location", F(t0), a0)
    key(tgt, "location", F(t1), a1)
    if fstop:
        cd.dof.use_dof = True
        cd.dof.focus_object = tgt
        cd.dof.aperture_fstop = fstop
    if shake:
        ad = tgt.animation_data
        act = ad.action if ad else None
        fcs = []
        if act is not None:
            fcs = list(getattr(act, "fcurves", []) or [])
            if not fcs:
                for layer in getattr(act, "layers", []):
                    for strip in layer.strips:
                        for cb in getattr(strip, "channelbags", []):
                            fcs.extend(cb.fcurves)
        for fc in fcs:
            md = fc.modifiers.new("NOISE")
            md.scale = 3.0
            md.strength = shake
            md.phase = random.uniform(0, 100)
    m = sc.timeline_markers.new(name, frame=F(t0))
    m.camera = cam
    return cam


# =========================================================================== the trailer
def build():
    sc = bpy.context.scene
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    sc.render.fps = FPS
    sc.frame_start = 1
    sc.frame_end = F(TL.LENGTH) - 1
    build_world()
    build_office()
    build_lights()
    build_throne()
    build_elevator()
    build_snow()
    heroes_dir = os.path.join(ROOT, "assets", "models", "heroes")
    actors = {h: Actor(h, os.path.join(heroes_dir, h + ".glb")) for h in TL.HEROES}
    # The ghost is the game's detailed boss: James's old-job self, with his own motions.
    ghost = make_ghost(os.path.join(ROOT, "assets", "models", "bosses", "ghost.glb"))
    # The ghost broods: arms down at his sides, head bowed, then he looks up as his eyes flare.
    down = {"LeftArm": ("y", 34), "RightArm": ("y", -34), "LeftForeArm": ("y", 8), "RightForeArm": ("y", -8)}
    bowed = dict(down, Head=("x", 22), Neck=("x", 8), Spine2=("x", 4))
    up = dict(down, Head=("x", -6), Neck=("x", -2), Spine2=("x", -2))
    breathe = dict(bowed, Spine2=("x", 6))
    ghost.pose_action("brood", [(-2.0, bowed), (4.0, breathe), (9.0, bowed), (13.0, breathe), (14.8, bowed),
                                (15.7, up), (TL.LENGTH, up)])
    for a in actors.values():
        a.play("idle", -2.0, repeat=60, hold=True)
    ghost.play("brood", -2.0, hold=True)
    # ------------------------------------------------------------------ the ghost
    gpos = Vector((0, 23.0, 0.6))
    ghost.at(0, gpos)
    ghost.play("cast", 17.45)  # he rises and raises the sword (both arms up, slowly)
    burst("ghost_burst1", gpos + Vector((0, -0.4, 1.6)), 17.9, (0.45, 0.85, 1.0, 1), 260, 8.0)
    ring("ghost_ring1", gpos + Vector((0, 0, 0.05)), 17.9, (0.45, 0.85, 1.0, 1), 4.0, 0.8)
    for tt, s in ((14.6, 8.0), (15.5, 60.0), (17.3, 30.0), (21.0, 10.0)):
        key_socket(ghost.eye_em.inputs["Strength"], F(tt), s, "BEZIER")
    ghost.play("ultimate", 41.1)  # the ice blast: arms flung wide, head thrown back
    burst("ghost_burst2", gpos + Vector((0, -0.6, 1.6)), 42.3, (0.45, 0.85, 1.0, 1), 420, 13.0, 0.04, 30)
    ring("ghost_ring2", gpos + Vector((0, 0, 0.05)), 42.3, (0.45, 0.85, 1.0, 1), 6.0, 0.7)
    # ------------------------------------------------------------------ heroes
    for h, a in actors.items():
        a.hide(0)
    # The elevator: six silhouettes, then they step out.
    xs = [-1.5, -0.9, -0.3, 0.3, 0.9, 1.5]
    order = ["sarah", "cole", "mason", "james", "cam", "sam"]
    for i, h in enumerate(order):
        actors[h].at(TL.SHOTS[4][1], Vector((xs[i], -32.2 + 0.15 * abs(xs[i]), 0)), math.pi)
    # Solo shots on the aisle "stage".
    stage = Vector((0, -2.0, 0))
    for h in TL.HEROES:
        _, t0, t1 = next(s for s in TL.SHOTS if s[0] == h)
        a = actors[h]
        a.at(t0, stage, 0.0)  # facing the camera (-Y)
        a.play(TL.HERO_SHOT_ANIM[h], t0 + 0.1)
        col = hexc(HERO_COLORS[h])
        ring(h + "_ring", stage + Vector((0, 0, 0.04)), t0 + 0.55, col, 2.6, 0.6)
        flash(h + "_flash", stage + Vector((0, 0.8, 1.6)), t0 + 0.55, col[:3], 2500, 0.6)
        burst(h + "_sparks", stage + Vector((0, -0.3, 1.2)), t0 + 0.6, col, 120, 5.0, 0.02, 24, shard=False)
        rim = bpy.data.lights.new(h + "_rim", "SPOT")
        rim.color = col[:3]
        rim.spot_size = math.radians(40)
        rim.shadow_soft_size = 0.3
        ro = bpy.data.objects.new(h + "_rim", rim)
        sc.collection.objects.link(ro)
        ro.location = stage + Vector((0.8, 3.2, 3.0))
        ro.rotation_euler = (Vector((0, 0, 0)) - Vector((0.8, 3.2, 3.0))).to_track_quat("-Z", "Y").to_euler()
        rim.spot_size = math.radians(28)
        for tt, e in ((0, 0), (t0, 1300), (t1, 0)):
            key_value(rim, "energy", F(tt), e, "CONSTANT")
        a.hide(t1)
    # Key light for the stage.
    kd = bpy.data.lights.new("stage_key", "AREA")
    kd.energy = 260
    kd.size = 2.0
    kd.color = (0.85, 0.9, 1.0)
    ko = bpy.data.objects.new("stage_key", kd)
    sc.collection.objects.link(ko)
    ko.location = stage + Vector((-2.2, -3.0, 2.6))
    ko.rotation_euler = (stage + Vector((0, 0, 1.2)) - ko.location).to_track_quat("-Z", "Y").to_euler()
    # The march: out of the fog, toward the camera.
    m0, m1 = 36.4, 41.0
    form = {"mason": (0.0, 0.0), "james": (-1.3, 0.5), "cole": (1.3, 0.5), "cam": (-2.5, 1.1), "sarah": (2.5, 1.1),
            "sam": (0.0, 1.5)}
    march = 7.1  # meters walked; the walk plays at the speed that matches it, so feet don't slide
    for h, (fx, fy) in form.items():
        a = actors[h]
        a.at(m0, Vector((fx, -4.2 - march - fy, 0)), math.pi, interp="LINEAR")  # walking toward +Y
        a.at(m1, Vector((fx, -4.2 - fy, 0)), math.pi)
        a.play("walk", m0, repeat=10, speed=a.gait("walk", march / (m1 - m0)))
        a.hide(m1 + 0.05)
    # The montage.
    shots_m = []
    cut = (TL.SHOTS[13][2] - TL.SHOTS[13][1]) / len(TL.MONTAGE)
    for i, (who, anim, side, skip) in enumerate(TL.MONTAGE):
        t0 = TL.SHOTS[13][1] + i * cut
        if who == "ghost":
            ghost.play(anim, t0 - skip)
            if anim == "hit":
                burst("mont_hit_%d" % i, gpos + Vector((0, -0.3, 1.5)), t0 + 0.15, (1.0, 0.9, 0.6, 1), 140, 6.0, 0.02, 20,
                      shard=False)
            else:
                ring("mont_ring_%d" % i, gpos + Vector((0, 0, 0.05)), t0 + 0.2, (0.45, 0.85, 1.0, 1), 4.0, 0.5)
        else:
            a = actors[who]
            a.at(t0, stage, 0.0)
            a.play(anim, t0 - skip, speed=1.3)  # `skip` lands the move's big moment inside the cut
            col = hexc(HERO_COLORS[who])
            flash("mont_flash_%d" % i, stage + Vector((0, 0.6, 1.5)), t0 + 0.3, col[:3], 3000, 0.4)
            ring("mont_ring_%d" % i, stage + Vector((0, 0, 0.04)), t0 + 0.25, col, 2.4, 0.45)
            a.hide(t0 + cut)
        shots_m.append((who, side, t0, t0 + cut))
    # The clash: everyone charges the throne.
    c0, c1 = TL.SHOTS[14][1], TL.SHOTS[14][2]
    for h, (fx, fy) in form.items():
        a = actors[h]
        a.at(c0, Vector((fx * 0.8, 9.0 - fy, 0)), math.pi, interp="LINEAR")  # charging toward +Y
        a.at(c1, Vector((fx * 0.5, 17.5 - fy, 0)), math.pi)
        a.play("run", c0, repeat=12, speed=a.gait("run", 8.5 / (c1 - c0)))
        a.play("attack", c1 - 0.9, speed=1.4)
        a.hide(c1 + 0.05)
    ghost.play("attack", c1 - 1.1, speed=1.2)
    flash("clash_flash", Vector((0, 19.5, 1.6)), 52.35, (0.8, 0.9, 1.0), 40000, 0.5)
    # ------------------------------------------------------------------ title card
    build_title()
    # ------------------------------------------------------------------ cameras
    S = {name: (a, b) for name, a, b in TL.SHOTS}
    camera("cam_office", *S["office"], (0.4, -27, 1.7), (0.0, -12, 1.5), (0, -6, 1.6), (0, 10, 1.7), 24)
    camera("cam_throne", *S["throne"], (0.6, 6, 1.5), (0.2, 12.5, 1.7), (0, 23, 2.2), (0, 23, 2.4), 32)
    hz = gpos.z + ghost.height * 0.93  # eye height
    camera("cam_ghost_face", *S["ghost_face"], (0.3, gpos.y - 2.1, hz + 0.02), (0.12, gpos.y - 1.55, hz),
           (0, gpos.y, hz - 0.03), (0, gpos.y, hz - 0.01), 60, fstop=2.8)
    camera("cam_ghost_rise", *S["ghost_rise"], (2.2, gpos.y - 4.2, 0.5), (1.6, gpos.y - 4.6, 0.7),
           (0, gpos.y, 1.9), (0, gpos.y, 2.3), 24, shake=0.04)
    camera("cam_elevator", *S["elevator"], (0, -24.0, 1.45), (0, -25.6, 1.35), (0, -31, 1.4), (0, -31, 1.3), 30)
    for h in TL.HEROES:
        t0, t1 = S[h]
        sgn = 1 if TL.HEROES.index(h) % 2 == 0 else -1
        camera("cam_" + h, t0, t1, stage + Vector((1.5 * sgn, -3.4, 0.9)), stage + Vector((0.9 * sgn, -2.8, 1.1)),
               stage + Vector((0, 0, 1.15)), stage + Vector((0, 0, 1.25)), 40, fstop=2.8)
    camera("cam_march", *S["march"], (0.0, -1.8, 0.75), (0.0, -0.2, 0.9), (0, -8, 1.3), (0, -5, 1.4), 28)
    camera("cam_ghost_attack", *S["ghost_attack"], (-1.2, gpos.y - 5.5, 1.2), (-0.6, gpos.y - 4.4, 1.3),
           (0, gpos.y, 2.0), (0, gpos.y, 2.0), 26, shake=0.06)
    for i, (who, side, t0, t1) in enumerate(shots_m):
        if who == "ghost":
            camera("cam_m%d" % i, t0, t1, gpos + Vector((side * 1.6, -3.6, 1.0)), gpos + Vector((side * 1.2, -3.1, 1.2)),
                   gpos + Vector((0, 0, 1.8)), gpos + Vector((0, 0, 1.9)), 32, shake=0.05)
        else:
            camera("cam_m%d" % i, t0, t1, stage + Vector((side * 1.8, -2.6, 0.7)), stage + Vector((side * 1.4, -2.3, 0.9)),
                   stage + Vector((0, 0, 1.1)), stage + Vector((0, 0, 1.2)), 30, shake=0.04)
    camera("cam_clash", *S["clash"], (1.9, 5.5, 0.55), (1.4, 11.0, 0.7), (0, 18, 1.5), (0, 21, 1.8), 22, shake=0.05)
    camera("cam_title", *S["title"], (300, -9.5, 0.6), (300, -7.6, 0.45), (300, 0, 0.3), (300, 0, 0.3), 40)
    camera("cam_end", *S["end"], (300, -14, 0.5), (300, -14.5, 0.5), (300, 0, 0.4), (300, 0, 0.4), 40)
    log("built: %d objects, %d frames" % (len(bpy.data.objects), sc.frame_end))


def build_title():
    sc = bpy.context.scene
    font = bpy.data.fonts.load(FONT_TITLE) if os.path.exists(FONT_TITLE) else None
    title_m = mat("title", (0.75, 0.88, 1.0), 0.18, metal=0.85, emit=(0.35, 0.7, 1.0), strength=0.4)
    for text, size, z in (("VILLIAM BURGINSON", 0.62, 0.95), ("DORKS", 1.55, -0.45)):
        cu = bpy.data.curves.new("title_" + text, "FONT")
        cu.body = text
        if font:
            cu.font = font
        cu.size = size
        cu.extrude = 0.05
        cu.bevel_depth = 0.012
        cu.align_x = "CENTER"
        cu.align_y = "CENTER"
        cu.space_character = 1.08
        o = bpy.data.objects.new("title_" + text, cu)
        sc.collection.objects.link(o)
        o.data.materials.append(title_m)
        o.location = (300, 0, z)
        o.rotation_euler = (math.radians(90), 0, 0)
    # A cold glow behind the letters, in the fog (no hard-edged panel).
    gd = bpy.data.lights.new("title_glow", "POINT")
    gd.energy = 1400
    gd.color = (0.35, 0.65, 1.0)
    gd.shadow_soft_size = 2.0
    go = bpy.data.objects.new("title_glow", gd)
    sc.collection.objects.link(go)
    go.location = (300, 7.0, 1.4)
    prim("cube", "title_floor", (300, 0, -1.6), (12, 12, 0.05), mat("title_floor", (0.02, 0.03, 0.05), 0.95))
    # A light sweeping across the letters.
    sd = bpy.data.lights.new("title_sweep", "SPOT")
    sd.energy = 3500
    sd.spot_size = math.radians(18)
    sd.color = (0.8, 0.92, 1.0)
    so = bpy.data.objects.new("title_sweep", sd)
    sc.collection.objects.link(so)
    t0, t1 = 53.2, 58.5
    for t, x in ((t0, 292.0), (t1, 308.0)):
        so.location = (x, -6, 3)
        so.rotation_euler = (Vector((300 + (x - 300) * 0.3, 0, 0.3)) - Vector((x, -6, 3))).to_track_quat("-Z", "Y").to_euler()
        key(so, "location", F(t), interp="LINEAR")
        key(so, "rotation_euler", F(t), interp="LINEAR")
    fd = bpy.data.lights.new("title_fill", "AREA")
    fd.energy = 400
    fd.size = 6
    fd.color = (0.5, 0.7, 1.0)
    fo = bpy.data.objects.new("title_fill", fd)
    sc.collection.objects.link(fo)
    fo.location = (300, -6, -0.5)
    fo.rotation_euler = (math.radians(80), 0, 0)


# =========================================================================== render settings
def setup_render(res):
    sc = bpy.context.scene
    for eng in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
        try:
            sc.render.engine = eng
            break
        except TypeError:
            continue
    w, h = (int(v) for v in res.lower().split("x"))
    sc.render.resolution_x, sc.render.resolution_y = w, h
    sc.render.resolution_percentage = 100
    ee = sc.eevee
    for attr, val in (("taa_render_samples", int(arg("--samples", 48))), ("use_shadows", True),
                      ("volumetric_tile_size", "8"), ("volumetric_samples", 64), ("volumetric_start", 0.5),
                      ("volumetric_end", 70.0), ("use_volumetric_shadows", True), ("use_raytracing", True),
                      ("ray_tracing_method", "SCREEN"), ("use_gtao", True), ("motion_blur_steps", 1)):
        try:
            setattr(ee, attr, val)
        except Exception:
            pass
    try:
        ee.ray_tracing_options.resolution_scale = "2"
    except Exception:
        pass
    sc.render.use_motion_blur = True
    try:
        sc.render.motion_blur_shutter = 0.4
    except Exception:
        pass
    vs = sc.view_settings
    try:
        vs.view_transform = "AgX"
        for look in ("AgX - Punchy", "Punchy", "AgX - High Contrast", "High Contrast"):
            try:
                vs.look = look
                break
            except TypeError:
                continue
    except Exception:
        pass
    vs.exposure = 0.3
    setup_bloom()
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGB"
    sc.render.use_overwrite = False
    sc.render.use_placeholder = True


def setup_bloom():
    """A glow on bright things (EEVEE has no bloom of its own any more): a Glare node."""
    sc = bpy.context.scene
    try:
        if hasattr(sc, "compositing_node_group"):  # Blender 5
            tree = bpy.data.node_groups.new("trailer_comp", "CompositorNodeTree")
            rl = tree.nodes.new("CompositorNodeRLayers")
            gl = tree.nodes.new("CompositorNodeGlare")
            out = tree.nodes.new("NodeGroupOutput")
            tree.interface.new_socket(name="Image", in_out="OUTPUT", socket_type="NodeSocketColor")
            sc.compositing_node_group = tree
        else:
            sc.use_nodes = True
            tree = sc.node_tree
            rl = next(n for n in tree.nodes if n.type == "R_LAYERS")
            out = next(n for n in tree.nodes if n.type == "COMPOSITE")
            gl = tree.nodes.new("CompositorNodeGlare")
        for attr, val in (("glare_type", "BLOOM"), ("glare_type", "FOG_GLOW")):
            try:
                setattr(gl, attr, val)
                break
            except Exception:
                continue
        for names, val in ((("Type",), "Bloom"), (("Threshold",), 1.2), (("Strength",), 0.5), (("Size",), 0.6)):
            for n in names:
                if n in gl.inputs:
                    try:
                        gl.inputs[n].default_value = val
                    except Exception:
                        pass
        for attr, val in (("threshold", 1.2), ("mix", -0.55), ("size", 8), ("quality", "MEDIUM")):
            try:
                setattr(gl, attr, val)
            except Exception:
                pass
        tree.links.new(rl.outputs["Image"], gl.inputs["Image"])
        tree.links.new(gl.outputs["Image"], out.inputs[0])
        log("bloom: glare node set up")
    except Exception as e:
        log("bloom skipped: %s" % e)


# =========================================================================== stages
def stage_frames():
    build()
    setup_render(arg("--res", "1280x720"))
    sc = bpy.context.scene
    fr = arg("--frames")
    if fr:
        a, b = (int(v) for v in fr.split("-"))
        sc.frame_start, sc.frame_end = a, b
    os.makedirs(os.path.join(OUT, "frames"), exist_ok=True)
    sc.render.filepath = os.path.join(OUT, "frames", "")
    if arg("--save-blend"):
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "trailer.blend"))
    log("rendering frames %d-%d to %s" % (sc.frame_start, sc.frame_end, sc.render.filepath))
    bpy.ops.render.render(animation=True)
    log("frames done")


def stage_stills():
    build()
    setup_render(arg("--res", "640x360"))
    sc = bpy.context.scene
    os.makedirs(os.path.join(OUT, "stills"), exist_ok=True)
    sc.render.use_overwrite = True
    sc.render.use_placeholder = False
    only = arg("--shots")
    for name, a, b in TL.SHOTS:
        if only and name not in only.split(","):
            continue
        times = [a + (b - a) * 0.5] if name != "montage" else [a + 0.4 + i * 0.75 for i in range(8)]
        for k, t in enumerate(times):
            sc.frame_set(F(t))
            sc.render.filepath = os.path.join(OUT, "stills", "%s_%d.png" % (name, k))
            bpy.ops.render.render(write_still=True)
            log("still %s at %.1fs" % (name, t))


def stage_edit():
    """Puts frames, titles, subtitles, fades and sound together into trailer.mp4."""
    sc = bpy.context.scene
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    sc.render.fps = FPS
    sc.frame_start, sc.frame_end = 1, F(TL.LENGTH) - 1
    w, h = (int(v) for v in arg("--res", "1280x720").lower().split("x"))
    sc.render.resolution_x, sc.render.resolution_y = w, h
    sc.render.resolution_percentage = 100
    se = sc.sequence_editor_create()
    strips = se.strips if hasattr(se, "strips") else se.sequences  # renamed in Blender 4.4+
    fdir = os.path.join(OUT, "frames")
    files = sorted(f for f in os.listdir(fdir) if f.endswith(".png"))
    img = strips.new_image("frames", os.path.join(fdir, files[0]), 1, 1)
    for f in files[1:]:
        img.elements.append(f)
    audio = arg("--audio")
    if audio and os.path.exists(audio):
        strips.new_sound("audio", audio, 9, 1)
    # Real gameplay over every other montage cut (recorded by the game; see TL.GAMEPLAY_CUTS).
    gdir = os.path.join(OUT, "gameplay")
    gfiles = sorted(f for f in os.listdir(gdir) if f.endswith(".png")) if os.path.isdir(gdir) else []
    if gfiles:
        m0, m1 = next((a, b) for name, a, b in TL.SHOTS if name == "montage")
        cut = (m1 - m0) / len(TL.MONTAGE)
        for i, start in TL.GAMEPLAY_CUTS:
            n = F(m0 + (i + 1) * cut) - F(m0 + i * cut)
            sel = gfiles[start:start + n]
            if len(sel) < n:
                continue
            g = strips.new_image("gameplay_%d" % i, os.path.join(gdir, sel[0]), 2, F(m0 + i * cut))
            for f in sel[1:]:
                g.elements.append(f)
        log("gameplay cuts: %d (from %d recorded frames)" % (len(TL.GAMEPLAY_CUTS), len(gfiles)))
    fonts = {k: bpy.data.fonts.load(p) for k, p in (("title", FONT_TITLE), ("text", FONT_TEXT), ("light", FONT_LIGHT))
             if os.path.exists(p)}
    scale = h / 720.0
    ch = [2]

    def effect(name, kind, t0, t1, channel):
        try:
            return strips.new_effect(name, type=kind, channel=channel, frame_start=F(t0), length=F(t1) - F(t0))
        except TypeError:
            return strips.new_effect(name, type=kind, channel=channel, frame_start=F(t0), frame_end=F(t1))

    def fade(st, t0, t1, fin=0.35, fout=0.35, top=1.0):
        bpy.context.preferences.edit.keyframe_new_interpolation_type = "LINEAR"
        for t, v in ((t0, 0.0), (t0 + fin, top), (t1 - fout, top), (t1, 0.0)):
            st.blend_alpha = v
            st.keyframe_insert("blend_alpha", frame=F(t))

    def text(content, t0, t1, size, loc, color=(1, 1, 1, 1), font="text", outline=True, channel=None, fin=0.35, fout=0.35,
             box=False):
        c = channel or (ch[0] + 1)
        ch[0] = max(ch[0], c) if channel is None else ch[0]
        st = effect("txt_%d_%s" % (F(t0), content[:10]), "TEXT", t0, t1, c)
        st.text = content
        st.font_size = size * scale
        st.color = color
        st.location = loc
        for attr, val in (("anchor_x", "CENTER"), ("anchor_y", "CENTER"), ("align_x", "CENTER"), ("align_y", "CENTER")):
            try:
                setattr(st, attr, val)
            except Exception:
                pass
        if font in fonts:
            st.font = fonts[font]
        for attr, val in (("use_shadow", True), ("shadow_color", (0, 0, 0, 0.8))):
            try:
                setattr(st, attr, val)
            except Exception:
                pass
        if outline:
            for attr, val in (("use_outline", True), ("outline_color", (0.02, 0.05, 0.12, 1)), ("outline_width", 0.08)):
                try:
                    setattr(st, attr, val)
                except Exception:
                    pass
        if box:  # a soft dark box, so subtitles read on bright shots
            for attr, val in (("use_box", True), ("box_color", (0.0, 0.0, 0.0, 0.42)), ("box_margin", 0.012),
                              ("box_roundness", 0.4)):
                try:
                    setattr(st, attr, val)
                except Exception:
                    pass
        try:
            st.blend_type = "ALPHA_OVER"
        except Exception:
            pass
        fade(st, t0, t1, fin, fout)
        return st

    # Narration subtitles.
    for vid, t, line in TL.NARRATION:
        dur = 2.6 if len(line) < 32 else 4.6
        text(line, t, t + dur, 26, (0.5, 0.08), (0.92, 0.95, 1.0, 1), "text", channel=3, fin=0.2, fout=0.3, box=True)
    # Hero name cards.
    S = {name: (a, b) for name, a, b in TL.SHOTS}
    for hname in TL.HEROES:
        t0, t1 = S[hname]
        col = hexc(HERO_COLORS[hname])
        lift = tuple(min(1.0, c * 0.6 + 0.4) for c in col[:3]) + (1.0,)
        text(hname.upper(), t0 + 0.25, t1 - 0.05, 78, (0.24, 0.24), lift, "title", channel=4, fin=0.25, fout=0.2)
        text(TL.HERO_TAGLINE[hname], t0 + 0.45, t1 - 0.05, 28, (0.24, 0.155), (0.9, 0.93, 1.0, 1), "text", channel=5,
             fin=0.25, fout=0.2)
    # Titles.
    for t0, t1, content, style in TL.TEXT:
        if style == "title":
            continue  # the 3D title is in the shot
        size = {"title2": 46, "tag": 34, "small": 30}.get(style, 30)
        loc = {"title2": (0.5, 0.22), "tag": (0.5, 0.16), "small": (0.5, 0.5)}.get(style, (0.5, 0.5))
        font = {"title2": "title", "tag": "title", "small": "light"}.get(style, "text")
        text(content, t0, t1, size, loc, (0.85, 0.93, 1.0, 1), font, channel=6, fin=0.6, fout=0.6)
    # Fades and the flash.
    def color(name, t0, t1, rgb, channel, fin, fout, top=1.0):
        st = effect(name, "COLOR", t0, t1, channel)
        st.color = rgb
        try:
            st.blend_type = "ALPHA_OVER"
        except Exception:
            pass
        fade(st, t0, t1, fin, fout, top)
        return st

    color("fade_in", 0.0, 1.6, (0, 0, 0), 7, 0.01, 1.5)
    color("dip", 20.85, 21.7, (0, 0, 0), 7, 0.15, 0.5)
    color("flash", 52.3, 53.1, (1, 1, 1), 7, 0.06, 0.7)
    color("to_black", 59.4, TL.LENGTH + 1.0, (0, 0, 0), 7, 0.8, 0.1)  # (keys on distinct frames)
    color("hit_flash_1", 17.85, 18.25, (0.7, 0.9, 1.0), 8, 0.03, 0.35, 0.6)
    color("hit_flash_2", 42.25, 42.65, (0.7, 0.9, 1.0), 8, 0.03, 0.35, 0.6)
    # The "coming to" text sits above the final black.
    for st in list(strips):
        if st.type == "TEXT" and "Coming" in getattr(st, "text", ""):
            st.channel = 10
    # Encode.
    r = sc.render
    try:
        r.image_settings.media_type = "VIDEO"
    except Exception:
        pass
    r.image_settings.file_format = "FFMPEG"
    ff = r.ffmpeg
    ff.format = "MPEG4"
    ff.codec = "H264"
    for attr, val in (("constant_rate_factor", "HIGH"), ("ffmpeg_preset", "GOOD"), ("audio_codec", "AAC"),
                      ("audio_bitrate", 192), ("audio_channels", "STEREO"), ("audio_mixrate", 48000),
                      ("gopsize", 12)):
        try:
            setattr(ff, attr, val)
        except Exception:
            pass
    r.filepath = os.path.join(OUT, "trailer.mp4")
    fr = arg("--frames")  # a quick test of part of it
    if fr:
        a, b = (int(v) for v in fr.split("-"))
        sc.frame_start, sc.frame_end = a, b
        r.filepath = os.path.join(OUT, "trailer_test.mp4")
    r.use_sequencer = True
    log("encoding %s" % r.filepath)
    bpy.ops.render.render(animation=True)
    log("video done: %s" % r.filepath)


def main():
    if LOG and os.path.exists(LOG):
        os.remove(LOG)
    st = arg("--stage", "frames")
    try:
        {"frames": stage_frames, "stills": stage_stills, "edit": stage_edit}[st]()
    except Exception:
        import traceback
        log("FAILED:\n" + traceback.format_exc())


main()
