"""
Builds the game's detailed heroes: each Meshy model plus its Kimodo motions.

    powershell -File art/tools/heroes.ps1 assemble [options]
    blender --factory-startup -b -P art/tools/hero_assemble.py -- [options]

Options (after --):
    --only a,b        just these heroes/forms
    --mannequin       put the motions on a plain jointed stand-in instead of the hero's
                      model, to check them before (or without) a model
    --test-body       auto-rig a smooth test figure instead of the hero's model
    --motions DIR     read motions from DIR (default art/heroes/motion)
    --out DIR         write .glb files here (default assets/models/heroes)
    --render DIR      render a contact sheet of every animation into DIR
    --no-export       don't write .glb files
    --log FILE        write progress here

For each hero this takes art/heroes/<id>/model.glb (from Hunyuan 3D) and auto-rigs it, or
uses art/heroes/<id>/rigged.glb|fbx if the model already has a rig (Meshy, Mixamo). Then it
retargets art/heroes/motion/<hero>/<anim>.npz onto it and exports
assets/models/heroes/<id>.glb with the animations the game plays (idle, walk, attack...).

How the retargeting works: Kimodo poses its SOMA skeleton with world rotations relative
to a T-pose. Each Meshy bone is first turned so it points the way the matching SOMA bone
points in that T-pose, then gets the same world rotation the SOMA bone has in each frame.
The hips also get the root motion, scaled by leg length.
"""

import math
import os
import sys
import tempfile
import traceback

import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hero_specs as H  # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def arg(name, default=None):
    if name in ARGS:
        i = ARGS.index(name)
        return ARGS[i + 1] if i + 1 < len(ARGS) and not ARGS[i + 1].startswith("--") else True
    return default


LOG = arg("--log")


def log(msg):
    print(msg)
    if LOG:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(msg + "\n")


# --------------------------------------------------------------------------- Kimodo's skeleton
# Joint order and parents of Kimodo's SOMA skeletons (kimodo/skeleton/definitions.py).
_FINGERS = ["Thumb1", "Thumb2", "Thumb3", "ThumbEnd"] + [
    f + s for f in ("Index", "Middle", "Ring", "Pinky") for s in ("1", "2", "3", "4", "End")]


def _soma77():
    out = [("Hips", None), ("Spine1", "Hips"), ("Spine2", "Spine1"), ("Chest", "Spine2"),
           ("Neck1", "Chest"), ("Neck2", "Neck1"), ("Head", "Neck2"), ("HeadEnd", "Head"),
           ("Jaw", "Head"), ("LeftEye", "Head"), ("RightEye", "Head")]
    for side in ("Left", "Right"):
        out += [(side + "Shoulder", "Chest"), (side + "Arm", side + "Shoulder"),
                (side + "ForeArm", side + "Arm"), (side + "Hand", side + "ForeArm")]
        for f in _FINGERS:
            parent = side + "Hand"
            if not f.endswith("1"):
                prev = _FINGERS[_FINGERS.index(f) - 1]
                parent = side + "Hand" + prev
            out.append((side + "Hand" + f, parent))
    for side in ("Left", "Right"):
        out += [(side + "Leg", "Hips"), (side + "Shin", side + "Leg"), (side + "Foot", side + "Shin"),
                (side + "ToeBase", side + "Foot"), (side + "ToeEnd", side + "ToeBase")]
    return out


SOMA77 = _soma77()
SOMA30 = [("Hips", None), ("Spine1", "Hips"), ("Spine2", "Spine1"), ("Chest", "Spine2"),
          ("Neck1", "Chest"), ("Neck2", "Neck1"), ("Head", "Neck2"), ("Jaw", "Head"),
          ("LeftEye", "Head"), ("RightEye", "Head")]
for _s in ("Left", "Right"):
    SOMA30 += [(_s + "Shoulder", "Chest"), (_s + "Arm", _s + "Shoulder"), (_s + "ForeArm", _s + "Arm"),
               (_s + "Hand", _s + "ForeArm"), (_s + "HandThumbEnd", _s + "Hand"),
               (_s + "HandMiddleEnd", _s + "Hand")]
for _s in ("Left", "Right"):
    SOMA30 += [(_s + "Leg", "Hips"), (_s + "Shin", _s + "Leg"), (_s + "Foot", _s + "Shin"),
               (_s + "ToeBase", _s + "Foot")]
assert len(SOMA77) == 77 and len(SOMA30) == 30

# Slots: the joints both skeletons share. slot -> SOMA joint.
SOMA_SLOTS = {"hips": "Hips", "spine": "Spine1", "spine1": "Spine2", "spine2": "Chest",
              "neck": "Neck1", "head": "Head"}
for _s, _p in (("Left", "l_"), ("Right", "r_")):
    SOMA_SLOTS.update({_p + "shoulder": _s + "Shoulder", _p + "arm": _s + "Arm",
                       _p + "forearm": _s + "ForeArm", _p + "hand": _s + "Hand",
                       _p + "upleg": _s + "Leg", _p + "leg": _s + "Shin", _p + "foot": _s + "Foot",
                       _p + "toe": _s + "ToeBase"})
    # SOMA fingers have a metacarpal joint first (Index1); Mixamo's start at the knuckle.
    SOMA_SLOTS.update({_p + "thumb1": _s + "HandThumb1", _p + "thumb2": _s + "HandThumb2",
                       _p + "thumb3": _s + "HandThumb3"})
    for _f in ("index", "middle", "ring", "pinky"):
        for _k in (1, 2, 3):
            SOMA_SLOTS[_p + _f + str(_k)] = _s + "Hand" + _f.capitalize() + str(_k + 1)

# Each slot points at this child slot (used to line the two rest poses up).
CHILD = {"spine": "spine1", "spine1": "spine2", "spine2": "neck", "neck": "head"}
for _p in ("l_", "r_"):
    CHILD.update({_p + "shoulder": _p + "arm", _p + "arm": _p + "forearm", _p + "forearm": _p + "hand",
                  _p + "hand": _p + "middle1", _p + "upleg": _p + "leg", _p + "leg": _p + "foot",
                  _p + "foot": _p + "toe"})
    for _f in ("thumb", "index", "middle", "ring", "pinky"):
        CHILD[_p + _f + "1"] = _p + _f + "2"
        CHILD[_p + _f + "2"] = _p + _f + "3"

# Where the SOMA child is when the slot map doesn't have one (finger tips, 30-joint hands).
SOMA_CHILD_FALLBACK = {}
for _s, _p in (("Left", "l_"), ("Right", "r_")):
    SOMA_CHILD_FALLBACK[_p + "hand"] = [_s + "HandMiddle2", _s + "HandMiddleEnd"]
    SOMA_CHILD_FALLBACK[_p + "thumb3"] = [_s + "HandThumbEnd"]
    for _f in ("Index", "Middle", "Ring", "Pinky"):
        SOMA_CHILD_FALLBACK[_p + _f.lower() + "3"] = [_s + "Hand" + _f + "End"]

# Target bone names per slot, normalized (lowercase, letters and digits, no "mixamorig").
TARGET_NAMES = {
    "hips": ["hips", "pelvis", "hip"],
    "spine": ["spine", "spine01", "spine0"],
    "spine1": ["spine1", "spine02", "chest"],
    "spine2": ["spine2", "spine03", "upperchest"],
    "neck": ["neck", "neck1", "neck01"],
    "head": ["head"],
}
for _s, _p, _l in (("left", "l_", "l"), ("right", "r_", "r")):
    TARGET_NAMES.update({
        _p + "shoulder": [_s + "shoulder", "shoulder" + _l, "clavicle" + _l, _l + "shoulder"],
        _p + "arm": [_s + "arm", "upperarm" + _l, _s + "upperarm", _l + "upperarm"],
        _p + "forearm": [_s + "forearm", "lowerarm" + _l, "forearm" + _l, _s + "lowerarm"],
        _p + "hand": [_s + "hand", "hand" + _l, _l + "hand"],
        _p + "upleg": [_s + "upleg", "thigh" + _l, _s + "thigh", "upperleg" + _l, _s + "upperleg"],
        _p + "leg": [_s + "leg", "calf" + _l, _s + "shin", "lowerleg" + _l, _s + "lowerleg", _s + "knee"],
        _p + "foot": [_s + "foot", "foot" + _l, _l + "foot"],
        _p + "toe": [_s + "toebase", "toebase" + _l, "ball" + _l, _s + "toe", "toe" + _l],
    })
    for _f in ("thumb", "index", "middle", "ring", "pinky"):
        for _k in (1, 2, 3):
            TARGET_NAMES[_p + _f + str(_k)] = [_s + "hand" + _f + str(_k), _f + "0" + str(_k) + _l]

REQUIRED = ["hips", "spine", "head", "l_arm", "r_arm", "l_forearm", "r_forearm",
            "l_upleg", "r_upleg", "l_leg", "r_leg", "l_foot", "r_foot"]

# Kimodo is Y-up and faces +Z; Blender is Z-up and models face -Y.
C = np.array([[1.0, 0.0, 0.0], [0.0, 0.0, -1.0], [0.0, 1.0, 0.0]])
MAX_STEP = 0.6    # "free" motions: furthest the hips may wander (Kimodo meters)
LOOP_BLEND = 12   # frames blended to close a loop


def norm_name(name):
    n = name.split(":")[-1].lower().replace("mixamorig", "")
    return "".join(ch for ch in n if ch.isalnum())


# --------------------------------------------------------------------------- motion data
class Motion:
    """A Kimodo .npz in Blender's axes, with the T-pose rest positions it implies."""

    def __init__(self, path):
        d = np.load(path)
        P = np.asarray(d["posed_joints"], dtype=np.float64)
        R = np.asarray(d["global_rot_mats"], dtype=np.float64)
        if P.ndim == 4:
            P, R = P[0], R[0]
        joints = SOMA30 if P.shape[1] == 30 else SOMA77
        if len(joints) != P.shape[1]:
            raise ValueError("%s: unexpected joint count %d" % (path, P.shape[1]))
        self.names = [j for j, _ in joints]
        self.parent = dict(joints)
        self.idx = {n: i for i, n in enumerate(self.names)}
        self.P = P @ C.T
        self.R = np.einsum("ij,tkjl,ml->tkim", C, R, C)
        self.frames = P.shape[0]
        # Rest offsets: in the T-pose rest every global rotation is identity, so a
        # child's offset is its parent-local offset in any frame.
        self.rest = {}
        for n in self.names:
            p = self.parent[n]
            if p is None:
                self.rest[n] = np.zeros(3)
            else:
                pi, ci = self.idx[p], self.idx[n]
                self.rest[n] = self.rest[p] + self.R[0, pi].T @ (self.P[0, ci] - self.P[0, pi])

    def has(self, n):
        return n in self.idx

    def rest_v(self, n):
        return Vector(self.rest[n].tolist())


# --------------------------------------------------------------------------- retargeting
def find_target_bones(arm):
    by_norm = {}
    for b in arm.data.bones:
        by_norm.setdefault(norm_name(b.name), b.name)
    tmap = {}
    for slot, cands in TARGET_NAMES.items():
        for c in cands:
            if c in by_norm:
                tmap[slot] = by_norm[c]
                break
    missing = [s for s in REQUIRED if s not in tmap]
    if missing:
        raise ValueError("Couldn't find these bones on the rig: %s (bones: %s)" % (
            missing, ", ".join(b.name for b in arm.data.bones)))
    return tmap


def yaw_between(a, b):
    a = Vector((a.x, a.y, 0)).normalized()
    b = Vector((b.x, b.y, 0)).normalized()
    return Matrix.Rotation(math.atan2(a.cross(b).z, a.dot(b)), 3, "Z")


def forward_of(right):
    f = Vector((0, 0, 1)).cross(right)
    f.z = 0
    return f.normalized()


def bone_order(arm):
    order = []
    todo = [b for b in arm.data.bones if b.parent is None]
    while todo:
        b = todo.pop(0)
        order.append(b)
        todo.extend(b.children)
    return order


def ground_z(arm):
    zs = []
    for o in arm.children_recursive:
        if o.type == "MESH":
            zs += [(o.matrix_world @ Vector(c)).z for c in o.bound_box]
    return min(zs) if zs else 0.0


def smooth(xy, window):
    """Moving average along time (edge-padded), for removing drift."""
    if len(xy) < 3:
        return xy.copy()
    w = max(3, min(window, len(xy) // 2 * 2 - 1))
    pad = w // 2
    padded = np.concatenate([np.repeat(xy[:1], pad, 0), xy, np.repeat(xy[-1:], pad, 0)])
    kernel = np.ones(w) / w
    return np.stack([np.convolve(padded[:, k], kernel, mode="valid") for k in range(xy.shape[1])], 1)


class Retargeter:
    """Retargets Kimodo motions onto one armature (Meshy's rig or the mannequin)."""

    def __init__(self, arm):
        self.arm = arm
        self.tmap = find_target_bones(arm)
        self.slot_of = {v: k for k, v in self.tmap.items()}
        mw = arm.matrix_world.copy()
        self.mw_inv = mw.inverted()
        self.mw_rot = mw.to_3x3().normalized()
        self.mw_rot_inv = self.mw_rot.transposed()
        self.order = bone_order(arm)
        self.rest_rot = {b.name: (self.mw_rot @ b.matrix_local.to_3x3()).normalized() for b in arm.data.bones}
        self.rest_head = {b.name: mw @ b.head_local for b in arm.data.bones}
        self.rest_rel = {}
        for b in self.order:
            self.rest_rel[b.name] = (b.parent.matrix_local.inverted() @ b.matrix_local) if b.parent else b.matrix_local.copy()
        t = self.tmap
        h = self.rest_head
        self.forward = forward_of(h[t["r_arm"]] - h[t["l_arm"]])
        self.leg = (h[t["l_leg"]] - h[t["l_upleg"]]).length + (h[t["l_foot"]] - h[t["l_leg"]]).length
        self.hips_rest = h[t["hips"]].copy()
        self.ground = ground_z(arm)

    def solve(self, mo, spec):
        """Per-frame pose-bone values: ({bone: [Quaternion]}, [hips location])."""
        t = self.tmap
        h = self.rest_head
        # Face the same way: the source's rest pose turns to the target's, and the motion
        # is turned so it starts facing straight ahead.
        f_src = forward_of(mo.rest_v("RightArm") - mo.rest_v("LeftArm"))
        Y = yaw_between(f_src, self.forward)
        hips_f0 = Vector((mo.R[0, mo.idx["Hips"]] @ np.array(f_src)).tolist())
        W = yaw_between(hips_f0, f_src)
        YW = np.array(Y @ W)
        Yn = np.array(Y)
        P = mo.P @ YW.T
        R = np.einsum("ij,tkjl,ml->tkim", YW, mo.R, Yn)

        # Line each target bone up with its source bone in the rest pose.
        slots = {s: j for s, j in SOMA_SLOTS.items() if s in t and mo.has(j)}
        align = {}
        for s, j in slots.items():
            child = CHILD.get(s)
            src_child = SOMA_SLOTS.get(child) if child else None
            if not (src_child and mo.has(src_child)):
                src_child = next((c for c in SOMA_CHILD_FALLBACK.get(s, []) if mo.has(c)), None)
            tgt_child = t.get(child) if child else None
            if src_child and tgt_child:
                d_t = (h[tgt_child] - h[t[s]]).normalized()
                d_s = (Y @ (mo.rest_v(src_child) - mo.rest_v(j))).normalized()
                align[s] = d_t.rotation_difference(d_s).to_matrix()
            else:
                align[s] = Matrix.Identity(3)

        # Root motion, scaled by leg length.
        hi = mo.idx["Hips"]
        src_leg = (mo.rest_v("LeftShin") - mo.rest_v("LeftLeg")).length + \
            (mo.rest_v("LeftFoot") - mo.rest_v("LeftShin")).length
        src_hips_h = -min(mo.rest["LeftToeBase"][2], mo.rest["RightToeBase"][2]) + 0.02
        k = self.leg / src_leg
        hp = P[:, hi, :].copy()
        rel = hp - np.array([hp[0, 0], hp[0, 1], src_hips_h])
        if spec.get("root") == "inplace":
            rel[:, :2] -= smooth(rel[:, :2], 31)
        else:
            dist = np.linalg.norm(rel[:, :2], axis=1, keepdims=True)
            rel[:, :2] *= np.minimum(1.0, MAX_STEP / np.maximum(dist, 1e-6))
        hips_world = [self.hips_rest + Vector((k * rel[f]).tolist()) for f in range(mo.frames)]

        rot = {b.name: [] for b in self.order}
        hips_loc = []
        rest_rot = self.rest_rot
        for f in range(mo.frames):
            M = {}
            for b in self.order:
                base = (M[b.parent.name] @ self.rest_rel[b.name]) if b.parent else self.rest_rel[b.name]
                s = self.slot_of.get(b.name)
                if s in slots:
                    Rw = Matrix(R[f, mo.idx[slots[s]]].tolist()) @ align[s] @ rest_rot[b.name]
                    Ra = self.mw_rot_inv @ Rw
                    loc = (self.mw_inv @ hips_world[f]) if s == "hips" else base.translation
                    Mb = Matrix.Translation(loc) @ Ra.to_4x4()
                    basis = base.inverted() @ Mb
                    if s == "hips":
                        hips_loc.append(basis.translation.copy())
                else:
                    basis = Matrix.Identity(4)
                    Mb = base
                M[b.name] = Mb
                q = basis.to_quaternion().normalized()
                prev = rot[b.name][-1] if rot[b.name] else None
                if prev is not None and prev.dot(q) < 0:
                    q.negate()
                rot[b.name].append(q)
        return rot, hips_loc

    def driven_bones(self):
        return [b.name for b in self.order]


# --------------------------------------------------------------------------- loops
def blend_loop(seq, start, end, k, mix):
    """seq[start:end], with its last k frames blended toward seq[start-k:start], so the
    clip flows from its last frame straight back into its first."""
    out = list(seq[start:end])
    n = len(out)
    k = min(k, start, n // 3)
    for i in range(k):
        w = (i + 1) / (k + 1)
        out[n - k + i] = mix(out[n - k + i], seq[start - k + i], w)
    return out


def find_cycle(rot, bones, lo, min_len, max_len):
    """The most seamless start/end pair for a walk cycle."""
    n = len(rot[bones[0]])
    best = None
    for s in range(lo, n - min_len):
        for e in range(s + min_len, min(n - 1, s + max_len) + 1):
            d = sum(1.0 - abs(rot[b][s].dot(rot[b][e])) for b in bones)
            if best is None or d < best[0]:
                best = (d, s, e)
    return best


def finish_clip(rt, rot, hips_loc, spec):
    """Turns the solved frames into the final clip (loops closed, walk cycle cut out)."""
    n = len(hips_loc)
    if spec.get("cycle"):
        limbs = [rt.tmap[s] for s in ("l_upleg", "r_upleg", "l_leg", "r_leg", "l_arm", "r_arm") if s in rt.tmap]
        _, start, end = find_cycle(rot, limbs, max(LOOP_BLEND, min(30, n // 4)), 24, 48)
    elif spec.get("loop"):
        start, end = LOOP_BLEND, n
    else:
        return rot, hips_loc
    rot = {b: blend_loop(qs, start, end, LOOP_BLEND, lambda a, c, w: a.slerp(c, w)) for b, qs in rot.items()}
    hips_loc = blend_loop(hips_loc, start, end, LOOP_BLEND, lambda a, c, w: a.lerp(c, w))
    return rot, hips_loc


# --------------------------------------------------------------------------- keys
def write_action(arm, name, rot, hips_bone, hips_loc):
    """One action for one animation, pushed to an NLA track of the same name (the glTF
    exporter writes one animation per track)."""
    ad = arm.animation_data_create()
    action = bpy.data.actions.new("%s|%s" % (arm.name, name))
    action.use_fake_user = True
    ad.action = action
    n = len(hips_loc)
    channels = []
    for bname, qs in rot.items():
        pb = arm.pose.bones[bname]
        pb.rotation_mode = "QUATERNION"
        path = pb.path_from_id("rotation_quaternion")
        for i in range(4):
            channels.append((bname, path, i, [q[i] for q in qs]))
    lpath = arm.pose.bones[hips_bone].path_from_id("location")
    for i in range(3):
        channels.append((hips_bone, lpath, i, [v[i] for v in hips_loc]))
    try:
        for group, path, index, values in channels:
            fc = action.fcurve_ensure_for_datablock(arm, path, index=index, group_name=group)
            fc.keyframe_points.add(n)
            fc.keyframe_points.foreach_set("co", [c for f in range(n) for c in (float(f), float(values[f]))])
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"
            fc.update()
    except AttributeError:  # older Blender: key frame by frame
        for f in range(n):
            for bname, qs in rot.items():
                pb = arm.pose.bones[bname]
                pb.rotation_quaternion = qs[f]
                pb.keyframe_insert("rotation_quaternion", frame=f, group=bname)
            arm.pose.bones[hips_bone].location = hips_loc[f]
            arm.pose.bones[hips_bone].keyframe_insert("location", frame=f, group=hips_bone)
    track = ad.nla_tracks.new()
    track.name = name
    strip = track.strips.new(name, 0, action)
    strip.action_frame_end = max(1, n - 1)
    ad.action = None
    for pb in arm.pose.bones:
        pb.rotation_quaternion = Quaternion()
        pb.location = Vector()
    return n


# --------------------------------------------------------------------------- models
def clear_scene():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for coll in (bpy.data.meshes, bpy.data.armatures, bpy.data.actions, bpy.data.materials,
                 bpy.data.images, bpy.data.cameras, bpy.data.lights, bpy.data.curves):
        for d in list(coll):
            coll.remove(d)


def import_rigged(path, height):
    """A model that already has a skeleton (Meshy, Mixamo...), sized to the hero's height."""
    if path.lower().endswith(".fbx"):
        bpy.ops.import_scene.fbx(filepath=path)
    else:
        bpy.ops.import_scene.gltf(filepath=path)
    arms = [o for o in bpy.data.objects if o.type == "ARMATURE"]
    if not arms:
        raise ValueError("%s has no armature (is it the rigged model?)" % path)
    arm = arms[0]
    bpy.context.view_layer.update()
    zs = [(o.matrix_world @ Vector(c)).z for o in arm.children_recursive if o.type == "MESH" for c in o.bound_box]
    if zs and max(zs) - min(zs) > 1e-4:
        arm.scale = arm.scale * (height / (max(zs) - min(zs)))
    for o in bpy.data.objects:  # drop anything Meshy animated, we bring our own
        if o.animation_data:
            o.animation_data.action = None
            for t in list(o.animation_data.nla_tracks):
                o.animation_data.nla_tracks.remove(t)
    for a in list(bpy.data.actions):
        bpy.data.actions.remove(a)
    for pb in arm.pose.bones:
        pb.rotation_mode = "QUATERNION"
        pb.rotation_quaternion = Quaternion()
        pb.location = Vector()
        pb.scale = Vector((1, 1, 1))
    return arm


# --------------------------------------------------------------------------- auto-rig
# Rigs an unrigged A-pose character (a Hunyuan 3D model): finds the joints by slicing
# the mesh, builds a Mixamo-named skeleton, and skins it with Blender's automatic weights.

def import_model(path):
    """Imports a model file and joins every mesh in it into one object."""
    ext = os.path.splitext(path)[1].lower()
    if ext in (".glb", ".gltf"):
        bpy.ops.import_scene.gltf(filepath=path)
    elif ext == ".fbx":
        bpy.ops.import_scene.fbx(filepath=path)
    elif ext == ".obj":
        bpy.ops.wm.obj_import(filepath=path)
    else:
        raise ValueError("Don't know how to import %s" % path)
    for o in list(bpy.data.objects):
        if o.type == "ARMATURE":
            bpy.data.objects.remove(o, do_unlink=True)
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    if not meshes:
        raise ValueError("%s has no mesh" % path)
    bpy.ops.object.select_all(action="DESELECT")
    for o in meshes:
        o.select_set(True)
        for m in list(o.modifiers):
            o.modifiers.remove(m)
    bpy.context.view_layer.objects.active = meshes[0]
    if len(meshes) > 1:
        bpy.ops.object.join()
    obj = bpy.context.view_layer.objects.active
    obj.parent = None
    for o in list(bpy.data.objects):  # leftover empties from the file's node tree
        if o.type == "EMPTY":
            bpy.data.objects.remove(o, do_unlink=True)
    obj.vertex_groups.clear()
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    obj.name = "body"
    return obj


def mesh_points(obj):
    n = len(obj.data.vertices)
    co = np.empty(n * 3, dtype=np.float64)
    obj.data.vertices.foreach_get("co", co)
    return co.reshape(n, 3)


def normalize_model(obj, height):
    """Stands the model up straight: arms along X, facing -Y, feet on the floor at the
    origin, scaled to the hero's real height."""
    pts = mesh_points(obj)
    lo, hi = pts.min(0), pts.max(0)
    ext = hi - lo
    up = int(np.argmax(ext)) if ext[2] < 0.8 * ext.max() else 2
    if up != 2:  # lying down: stand it up (rare; generators usually export upright)
        obj.rotation_euler = (math.radians(90), 0, 0) if up == 1 else (0, math.radians(-90), 0)
        bpy.ops.object.transform_apply(rotation=True)
        pts = mesh_points(obj)
        lo, hi = pts.min(0), pts.max(0)
        ext = hi - lo
    if ext[1] > ext[0] * 1.05:  # the arm span should run along X
        obj.rotation_euler = (0, 0, math.radians(90))
        bpy.ops.object.transform_apply(rotation=True)
        pts = mesh_points(obj)
        lo, hi = pts.min(0), pts.max(0)
    hgt = hi[2] - lo[2]
    # Feet point forward: the toes stick out further in front of the shins than the heels do behind.
    feet = pts[pts[:, 2] < lo[2] + 0.04 * hgt]
    shins = pts[(pts[:, 2] > lo[2] + 0.15 * hgt) & (pts[:, 2] < lo[2] + 0.25 * hgt)]
    if len(feet) and len(shins):
        shin_y = np.median(shins[:, 1])
        if (feet[:, 1].max() - shin_y) > (shin_y - feet[:, 1].min()):
            obj.rotation_euler = (0, 0, math.radians(180))  # it faced +Y
            bpy.ops.object.transform_apply(rotation=True)
            pts = mesh_points(obj)
            lo, hi = pts.min(0), pts.max(0)
            hgt = hi[2] - lo[2]
    s = height / hgt
    center = pts[pts[:, 2] < lo[2] + 0.6 * hgt].mean(0)
    obj.location = (-center[0] * s, -center[1] * s, -lo[2] * s)
    obj.scale = (s, s, s)
    bpy.ops.object.transform_apply(location=True, scale=True)
    return mesh_points(obj)


def slice_clusters(pts, z, band, gap):
    """Groups the vertices near height z into separate pieces along X (legs, arms, torso)."""
    sel = pts[np.abs(pts[:, 2] - z) < band]
    if len(sel) < 3:
        return []
    order = np.argsort(sel[:, 0])
    xs = sel[order, 0]
    splits = np.where(np.diff(xs) > gap)[0]
    out = []
    start = 0
    for end in list(splits + 1) + [len(xs)]:
        part = sel[order[start:end]]
        if len(part) >= 3:
            out.append({"x0": part[:, 0].min(), "x1": part[:, 0].max(), "c": part.mean(0), "n": len(part)})
        start = end
    return out


def find_joints(pts, log_fn=log):
    """Joint positions (Mixamo names) for an A-pose character facing -Y, feet at z=0."""
    H = pts[:, 2].max()
    band, gap = 0.012 * H, 0.025 * H
    notes = []

    def frac(z):
        return z * H

    # Chest: the widest single central piece around 70% height tells us the torso width.
    chest = [c for c in slice_clusters(pts, frac(0.68), band, gap) if c["x0"] < 0 < c["x1"]]
    torso_half = (chest[0]["x1"] - chest[0]["x0"]) / 2 if chest else 0.13 * H
    # Armpits: going down from the shoulders, the first height where both arms have split off.
    armpit = None
    for f in np.arange(0.80, 0.50, -0.005):
        cl = slice_clusters(pts, frac(f), band, gap)
        if len(cl) >= 3 and any(c["c"][0] < -0.5 * torso_half for c in cl) and any(c["c"][0] > 0.5 * torso_half for c in cl):
            if any(c["x0"] < 0 < c["x1"] for c in cl):
                armpit = frac(f)
                break
    if armpit is None:
        armpit = frac(0.72)
        notes.append("armpits guessed")
    # Torso half-width just above the armpits.
    upper = [c for c in slice_clusters(pts, armpit + 0.03 * H, band, gap) if c["x0"] < 0 < c["x1"]]
    if upper:
        torso_half = min(torso_half, (upper[0]["x1"] - upper[0]["x0"]) / 2) if chest else (upper[0]["x1"] - upper[0]["x0"]) / 2

    # Arms: centerline through the outer pieces below the armpits, down to the hand tip.
    def arm(sign):
        cents = []
        tip = None
        for f in np.arange(armpit / H - 0.01, 0.2, -0.01):
            cl = [c for c in slice_clusters(pts, frac(f), band, gap) if sign * c["c"][0] > torso_half * 0.9]
            if not cl:
                if cents:
                    break
                continue
            c = max(cl, key=lambda c: sign * c["c"][0])
            cents.append(c["c"])
            tip = np.array([c["x1"] if sign > 0 else c["x0"], c["c"][1], frac(f) - band])
        if len(cents) < 3:
            return None
        cents = np.array(cents)
        mean = cents.mean(0)
        _, _, vt = np.linalg.svd(cents - mean)
        d = vt[0] if vt[0][2] < 0 else -vt[0]  # pointing down the arm
        # Shoulder: back up the line to where it meets the torso side.
        t_sh = (sign * 0.75 * torso_half - mean[0]) / d[0] if abs(d[0]) > 1e-6 else -0.2 * H
        shoulder = mean + d * t_sh
        t_tip = np.dot(tip - mean, d)
        hand_tip = mean + d * t_tip
        return shoulder, hand_tip

    arms = {}
    for side, sign in (("Left", 1), ("Right", -1)):
        a = arm(sign)
        if a is None:
            notes.append("%s arm guessed" % side.lower())
            sh = np.array([sign * 0.75 * torso_half, 0, armpit + 0.04 * H])
            tip = sh + np.array([sign * 0.29 * H, 0, -0.29 * H])
            a = (sh, tip)
        arms[side] = a

    # Feet and legs.
    feet = {}
    for side, sign in (("Left", 1), ("Right", -1)):
        foot = pts[(pts[:, 2] < 0.05 * H) & (sign * pts[:, 0] > 0)]
        if len(foot) < 3:
            foot = pts[pts[:, 2] < 0.05 * H]
            notes.append("feet guessed")
        toe_y, heel_y = foot[:, 1].min(), foot[:, 1].max()
        fx = np.median(foot[:, 0])
        feet[side] = {"x": fx, "toe": toe_y, "heel": heel_y}
    crotch = None
    for f in np.arange(0.12, 0.62, 0.005):
        cl = [c for c in slice_clusters(pts, frac(f), band, gap) if abs(c["c"][0]) < torso_half * 1.4]
        if len(cl) == 1 and cl[0]["x0"] < 0 < cl[0]["x1"]:
            crotch = frac(f)
            break
    if crotch is None or not (0.36 * H < crotch < 0.56 * H):  # dresses and skirts hide the crotch
        notes.append("hips guessed (%s)" % ("none found" if crotch is None else "%.2f" % (crotch / H)))
        crotch = 0.46 * H

    def torso_y(z):
        cl = [c for c in slice_clusters(pts, z, band, gap) if c["x0"] < 0 < c["x1"]]
        return cl[0]["c"][1] if cl else 0.0

    # Neck: the narrowest central slice between the shoulders and the widest part of the
    # head (long hair can make the crown the narrowest slice, so stop below the head).
    widths = []
    for f in np.arange(armpit / H + 0.05, 0.97, 0.005):
        cl = [c for c in slice_clusters(pts, frac(f), band, gap) if c["x0"] < 0 < c["x1"]]
        if cl:
            widths.append((cl[0]["x1"] - cl[0]["x0"], frac(f)))
    head_top = [w for w in widths if w[1] > 0.78 * H]
    head_z = max(head_top)[1] if head_top else 0.9 * H
    below = [w for w in widths if w[1] < head_z]
    neck = min(below)[1] if below else H - H / 5.5
    if not (armpit + 0.03 * H < neck < 0.93 * H):
        neck = H - H / 5.5
        notes.append("neck guessed")

    hips_z = crotch + 0.05 * H
    sh_z = (arms["Left"][0][2] + arms["Right"][0][2]) / 2
    neck_base = max(sh_z + 0.02 * H, neck - 0.06 * H)
    J = {}
    J["Hips"] = (np.array([0, torso_y(hips_z), hips_z]), np.array([0, torso_y(hips_z), hips_z + 0.06 * H]))
    spine_pts = [hips_z + (neck_base - hips_z) * t for t in (0.12, 0.40, 0.70, 1.0)]
    for name, (z0, z1) in zip(["Spine", "Spine1", "Spine2"], zip(spine_pts, spine_pts[1:])):
        J[name] = (np.array([0, torso_y(z0), z0]), np.array([0, torso_y(z1), z1]))
    J["Neck"] = (np.array([0, torso_y(neck_base), neck_base]), np.array([0, torso_y(neck), neck + 0.02 * H]))
    J["Head"] = (J["Neck"][1], np.array([0, torso_y(neck + 0.02 * H), H]))
    for side, sign in (("Left", 1), ("Right", -1)):
        sh, tip = arms[side]
        clav = np.array([sign * 0.15 * torso_half, sh[1], sh[2]])
        elbow = sh + (tip - sh) * 0.45
        wrist = sh + (tip - sh) * 0.82
        elbow[1] += 0.01 * H  # a slight bend back, so the elbow bends the right way
        J[side + "Shoulder"] = (clav, sh)
        J[side + "Arm"] = (sh, elbow)
        J[side + "ForeArm"] = (elbow, wrist)
        J[side + "Hand"] = (wrist, tip)
        ft = feet[side]
        leg_x = ft["x"] * 0.85 + sign * 0.15 * torso_half * 0.5
        hip = np.array([leg_x, torso_y(crotch), crotch + 0.02 * H])
        ankle = np.array([ft["x"], ft["heel"] - 0.25 * (ft["heel"] - ft["toe"]), 0.065 * H])
        knee = (hip + ankle) / 2
        knee[1] -= 0.012 * H  # knees bend forward
        ball = np.array([ft["x"], ft["toe"] + 0.3 * (ft["heel"] - ft["toe"]), 0.02 * H])
        J[side + "UpLeg"] = (hip, knee)
        J[side + "Leg"] = (knee, ankle)
        J[side + "Foot"] = (ankle, ball)
        J[side + "ToeBase"] = (ball, np.array([ft["x"], ft["toe"], 0.02 * H]))
    log_fn("  auto-rig: hips %.2f, armpits %.2f, neck %.2f of height%s" % (
        crotch / H, armpit / H, neck / H, (" (" + ", ".join(notes) + ")") if notes else ""))
    return J


AUTO_PARENTS = {"Hips": None, "Spine": "Hips", "Spine1": "Spine", "Spine2": "Spine1", "Neck": "Spine2",
                "Head": "Neck"}
for _s in ("Left", "Right"):
    AUTO_PARENTS.update({_s + "Shoulder": "Spine2", _s + "Arm": _s + "Shoulder", _s + "ForeArm": _s + "Arm",
                         _s + "Hand": _s + "ForeArm", _s + "UpLeg": "Hips", _s + "Leg": _s + "UpLeg",
                         _s + "Foot": _s + "Leg", _s + "ToeBase": _s + "Foot"})


def auto_rig(body, height):
    """Rigs `body` (an unrigged A-pose character) and returns the armature."""
    pts = normalize_model(body, height)
    joints = find_joints(pts)
    arm_data = bpy.data.armatures.new("rig")
    arm = bpy.data.objects.new("rig", arm_data)
    bpy.context.scene.collection.objects.link(arm)
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")
    for name in AUTO_PARENTS:  # parents come first in this order
        head, tail = joints[name]
        eb = arm_data.edit_bones.new("mixamorig:" + name)
        eb.head = Vector(head.tolist())
        eb.tail = Vector(tail.tolist())
        if (eb.tail - eb.head).length < 1e-3:
            eb.tail = eb.head + Vector((0, 0, 0.02))
        if AUTO_PARENTS[name]:
            eb.parent = arm_data.edit_bones["mixamorig:" + AUTO_PARENTS[name]]
    bpy.ops.object.mode_set(mode="OBJECT")
    skin(body, arm, height)
    return arm


def skin(body, arm, height):
    """Automatic weights, computed on a solid voxel copy of the body (AI meshes have holes
    and loose parts that make Blender's bone-heat weighting fail), then copied over."""
    proxy = body.copy()
    proxy.data = body.data.copy()
    proxy.name = "skin_proxy"
    bpy.context.scene.collection.objects.link(proxy)
    rm = proxy.modifiers.new("remesh", "REMESH")
    rm.mode = "VOXEL"
    rm.voxel_size = height / 140.0
    dec = proxy.modifiers.new("decimate", "DECIMATE")
    dec.ratio = 0.5
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active = proxy
    proxy.select_set(True)
    bpy.ops.object.modifier_apply(modifier="remesh")
    if len(proxy.data.polygons) > 60000:
        bpy.ops.object.modifier_apply(modifier="decimate")
    else:
        proxy.modifiers.remove(dec)
    bpy.ops.object.select_all(action="DESELECT")
    proxy.select_set(True)
    arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.parent_set(type="ARMATURE_AUTO")
    # Copy the weights onto the real mesh.
    for b in arm.data.bones:
        body.vertex_groups.new(name=b.name)
    dt = body.modifiers.new("weights", "DATA_TRANSFER")
    dt.object = proxy
    dt.use_vert_data = True
    dt.data_types_verts = {"VGROUP_WEIGHTS"}
    dt.vert_mapping = "POLYINTERP_NEAREST"
    dt.layers_vgroup_select_src = "ALL"
    dt.layers_vgroup_select_dst = "NAME"
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active = body
    body.select_set(True)
    bpy.ops.object.modifier_apply(modifier="weights")
    bpy.data.objects.remove(proxy, do_unlink=True)
    body.parent = arm
    mod = body.modifiers.new("Armature", "ARMATURE")
    mod.object = arm
    unweighted = sum(1 for v in body.data.vertices if not v.groups or sum(g.weight for g in v.groups) < 1e-4)
    log("  auto-rig: %d bones, %d of %d vertices unweighted" % (len(arm.data.bones), unweighted, len(body.data.vertices)))


MANNEQUIN_BONES = [  # name, parent, head, tail, half-width
    ("Hips", None, (0, 0, 0.95), (0, 0, 1.05), 0.13),
    ("Spine", "Hips", (0, 0, 1.05), (0, 0, 1.17), 0.12),
    ("Spine1", "Spine", (0, 0, 1.17), (0, 0, 1.29), 0.13),
    ("Spine2", "Spine1", (0, 0, 1.29), (0, 0, 1.42), 0.15),
    ("Neck", "Spine2", (0, 0, 1.42), (0, 0, 1.52), 0.045),
    ("Head", "Neck", (0, 0, 1.52), (0, 0, 1.76), 0.1),
]
for _s, _x in (("Left", 1), ("Right", -1)):
    _d = Vector((_x * math.cos(math.radians(45)), 0, -math.sin(math.radians(45))))
    _a = Vector((_x * 0.17, 0, 1.40))
    _e = _a + _d * 0.28
    _w = _e + _d * 0.26
    MANNEQUIN_BONES += [
        (_s + "Shoulder", "Spine2", (_x * 0.03, 0, 1.40), tuple(_a), 0.05),
        (_s + "Arm", _s + "Shoulder", tuple(_a), tuple(_e), 0.045),
        (_s + "ForeArm", _s + "Arm", tuple(_e), tuple(_w), 0.04),
        (_s + "Hand", _s + "ForeArm", tuple(_w), tuple(_w + _d * 0.09), 0.035),
        (_s + "UpLeg", "Hips", (_x * 0.09, 0, 0.93), (_x * 0.09, 0, 0.51), 0.07),
        (_s + "Leg", _s + "UpLeg", (_x * 0.09, 0, 0.51), (_x * 0.09, 0.01, 0.09), 0.055),
        (_s + "Foot", _s + "Leg", (_x * 0.09, 0.01, 0.09), (_x * 0.09, -0.12, 0.03), 0.045),
        (_s + "ToeBase", _s + "Foot", (_x * 0.09, -0.12, 0.03), (_x * 0.09, -0.19, 0.03), 0.04),
    ]


def build_mannequin(height):
    """A plain jointed mannequin with Mixamo bone names, in an A-pose like Meshy's rigs.
    Left limbs are blue and right limbs red, so mirrored motion is easy to spot."""
    import bmesh
    s = height / 1.76
    arm_data = bpy.data.armatures.new("mannequin")
    arm = bpy.data.objects.new("mannequin", arm_data)
    bpy.context.scene.collection.objects.link(arm)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")
    for name, parent, head, tail, _w in MANNEQUIN_BONES:
        eb = arm_data.edit_bones.new("mixamorig:" + name)
        eb.head = Vector(head) * s
        eb.tail = Vector(tail) * s
        if parent:
            eb.parent = arm_data.edit_bones["mixamorig:" + parent]
    bpy.ops.object.mode_set(mode="OBJECT")

    mesh = bpy.data.meshes.new("mannequin_body")
    body = bpy.data.objects.new("mannequin_body", mesh)
    bpy.context.scene.collection.objects.link(body)
    colors = {"Left": (0.2, 0.45, 1.0, 1), "Right": (1.0, 0.25, 0.25, 1), "": (0.75, 0.75, 0.72, 1),
              "Head": (0.95, 0.78, 0.62, 1), "Nose": (0.2, 0.2, 0.2, 1)}
    mats = {}
    for key, col in colors.items():
        m = bpy.data.materials.new("mannequin_" + (key or "body"))
        m.diffuse_color = col
        mesh.materials.append(m)
        mats[key] = len(mesh.materials) - 1
    bm = bmesh.new()
    groups = []
    for name, _parent, head, tail, w in MANNEQUIN_BONES + [("Nose", "Head", (0, -0.08, 1.63), (0, -0.14, 1.63), 0.025)]:
        a, b = Vector(head) * s, Vector(tail) * s
        axis = (b - a).normalized()
        u = axis.orthogonal().normalized() * w * s
        v = axis.cross(u).normalized() * w * s
        verts = [bm.verts.new(p + du + dv) for p in (a, b) for du in (u, -u) for dv in (v, -v)]
        faces = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
        key = "Nose" if name == "Nose" else ("Head" if name == "Head" else
                                              ("Left" if name.startswith("Left") else ("Right" if name.startswith("Right") else "")))
        for fi in faces:
            face = bm.faces.new([verts[i] for i in fi])
            face.material_index = mats[key]
        groups.append(("mixamorig:" + ("Head" if name == "Nose" else name), verts))
    bm.to_mesh(mesh)
    for gname, verts in groups:
        vg = body.vertex_groups.get(gname) or body.vertex_groups.new(name=gname)
        vg.add([vt.index for vt in verts], 1.0, "REPLACE")
    bm.free()
    body.parent = arm
    mod = body.modifiers.new("Armature", "ARMATURE")
    mod.object = arm
    return arm


def build_test_body(height):
    """A smooth one-piece figure in the mannequin's A-pose (no skeleton), for testing the
    auto-rig without a Hunyuan model."""
    s = height / 1.76
    verts, edges, radii, index = [], [], [], {}

    def vid(p, r):
        key = tuple(round(c, 4) for c in p)
        if key not in index:
            index[key] = len(verts)
            verts.append(Vector(p) * s)
            radii.append(r * s)
        return index[key]

    ends = {}
    for name, parent, head, tail, w in MANNEQUIN_BONES:
        r = 0.11 if name == "Head" else w
        a, b = vid(head, r), vid(tail, r)
        edges.append((a, b))
        ends[name] = (a, b)
        if parent:  # join limbs to the body (shoulders and hips start beside their parent)
            near = min(ends[parent], key=lambda i: (verts[i] - verts[a]).length)
            if near != a:
                edges.append((near, a))
    mesh = bpy.data.meshes.new("test_body")
    mesh.from_pydata(verts, edges, [])
    body = bpy.data.objects.new("test_body", mesh)
    bpy.context.scene.collection.objects.link(body)
    sk = body.modifiers.new("skin", "SKIN")
    for i, r in enumerate(radii):
        mesh.skin_vertices[0].data[i].radius = (r, r)
        mesh.skin_vertices[0].data[i].use_root = i == ends["Hips"][0]
    body.modifiers.new("subsurf", "SUBSURF").levels = 2
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active = body
    body.select_set(True)
    bpy.ops.object.modifier_apply(modifier=sk.name)
    bpy.ops.object.modifier_apply(modifier="subsurf")
    return body


# --------------------------------------------------------------------------- previews
def render_sheet(arm, clips, out_path, cols=6):
    """One PNG: a row per animation, `cols` frames across."""
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    textured = any(n.type == "TEX_IMAGE" for m in bpy.data.materials if m.use_nodes for n in m.node_tree.nodes)
    scene.display.shading.color_type = "TEXTURE" if textured else "MATERIAL"
    w, hgt = 220, 280
    scene.render.resolution_x, scene.render.resolution_y = w, hgt
    scene.render.resolution_percentage = 100
    cam = bpy.data.objects.new("sheet_cam", bpy.data.cameras.new("sheet_cam"))
    scene.collection.objects.link(cam)
    scene.camera = cam
    top = max((arm.matrix_world @ b.head_local).z for b in arm.data.bones) + 0.15
    cam.location = (1.3 * top, -2.2 * top, 0.75 * top)
    look = Vector((0, 0, 0.48 * top)) - cam.location
    cam.rotation_euler = look.to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = 50
    label = bpy.data.objects.new("sheet_label", bpy.data.curves.new("sheet_label", "FONT"))
    scene.collection.objects.link(label)
    label.parent = cam
    label.location = (-0.33, -0.36, -1.5)
    label.scale = (0.07, 0.07, 0.07)
    tmp = tempfile.mkdtemp(prefix="vbd_sheet_")
    ad = arm.animation_data
    tiles = []
    for name, n in clips:
        for t in ad.nla_tracks:
            t.mute = t.name != name
        label.data.body = name
        row = []
        for c in range(cols):
            frame = int(round(c * (n - 1) / max(1, cols - 1)))
            scene.frame_set(frame)
            p = os.path.join(tmp, "%s_%d.png" % (name, c))
            scene.render.filepath = p
            bpy.ops.render.render(write_still=True)
            img = bpy.data.images.load(p)
            px = np.empty(w * hgt * 4, dtype=np.float32)
            img.pixels.foreach_get(px)
            row.append(px.reshape(hgt, w, 4))
            bpy.data.images.remove(img)
        tiles.append(np.concatenate(row, axis=1))
    for t in ad.nla_tracks:
        t.mute = False
    sheet = np.concatenate(tiles[::-1], axis=0)  # images are stored bottom row first
    out = bpy.data.images.new("sheet", sheet.shape[1], sheet.shape[0], alpha=False)
    out.pixels.foreach_set(sheet.ravel())
    out.filepath_raw = out_path
    out.file_format = "PNG"
    out.save()
    bpy.data.images.remove(out)
    bpy.data.objects.remove(label, do_unlink=True)
    bpy.data.objects.remove(cam, do_unlink=True)
    log("  preview: %s" % out_path)


def render_portrait(arm, out_path):
    """A rest-pose check image: full body from the front, plus a close-up of the face."""
    scene = bpy.context.scene
    ad = arm.animation_data
    muted = []
    if ad:
        for t in ad.nla_tracks:
            muted.append((t, t.mute))
            t.mute = True
    scene.frame_set(0)
    for engine in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT", "BLENDER_WORKBENCH"):
        try:
            scene.render.engine = engine
            break
        except TypeError:
            continue
    if scene.render.engine == "BLENDER_WORKBENCH":
        scene.display.shading.light = "STUDIO"
        scene.display.shading.color_type = "TEXTURE"
    else:
        world = scene.world or bpy.data.worlds.new("preview_world")
        scene.world = world
        try:
            world.use_nodes = True
        except Exception:
            pass
        bg = next((n for n in world.node_tree.nodes if n.type == "BACKGROUND"), None)
        if bg:
            bg.inputs[0].default_value = (0.55, 0.57, 0.62, 1)
            bg.inputs[1].default_value = 1.0
        sun = bpy.data.objects.new("preview_sun", bpy.data.lights.new("preview_sun", "SUN"))
        sun.data.energy = 3.0
        sun.rotation_euler = (math.radians(50), 0, math.radians(-30))
        scene.collection.objects.link(sun)
    scene.render.resolution_x, scene.render.resolution_y = 1000, 900
    scene.render.resolution_percentage = 100
    cam = bpy.data.objects.new("portrait_cam", bpy.data.cameras.new("portrait_cam"))
    scene.collection.objects.link(cam)
    scene.camera = cam
    top = max((arm.matrix_world @ b.tail_local).z for b in arm.data.bones)
    tmp = tempfile.mkdtemp(prefix="vbd_portrait_")
    shots = []
    for name, loc, look, lens in (("body", (0.9 * top, -2.6 * top, 0.6 * top), (0, 0, 0.5 * top), 50),
                                  ("face", (0.12 * top, -0.75 * top, 0.93 * top), (0, 0, 0.9 * top), 85)):
        cam.location = loc
        cam.rotation_euler = (Vector(look) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
        cam.data.lens = lens
        p = os.path.join(tmp, name + ".png")
        scene.render.filepath = p
        bpy.ops.render.render(write_still=True)
        img = bpy.data.images.load(p)
        px = np.empty(1000 * 900 * 4, dtype=np.float32)
        img.pixels.foreach_get(px)
        shots.append(px.reshape(900, 1000, 4))
        bpy.data.images.remove(img)
    sheet = np.concatenate(shots, axis=1)
    out = bpy.data.images.new("portrait", sheet.shape[1], sheet.shape[0], alpha=False)
    out.pixels.foreach_set(sheet.ravel())
    out.filepath_raw = out_path
    out.file_format = "PNG"
    out.save()
    bpy.data.images.remove(out)
    bpy.data.objects.remove(cam, do_unlink=True)
    for o in [o for o in bpy.data.objects if o.name.startswith("preview_sun")]:
        bpy.data.objects.remove(o, do_unlink=True)
    for t, m in muted:
        t.mute = m
    scene.render.engine = "BLENDER_WORKBENCH"
    log("  portrait: %s" % out_path)


# --------------------------------------------------------------------------- export
def texture_budget(name):
    """Largest side for each kind of texture in the game files."""
    n = name.lower()
    if "eye" in n and "brow" not in n and "lash" not in n:
        return 256
    if "brow" in n or "lash" in n:
        return 256
    if "hair" in n or "shoe" in n:
        return 512
    return 1024  # skin, tops (prints and numbers), everything else


SEE_THROUGH = ("hair", "brow", "lash", "eye")  # the only textures that need transparency


def slim_materials():
    """Game-sized textures: no normal/bump maps (the toon-ish look doesn't need them),
    images scaled to texture_budget() and saved as JPEG; only hair, brows, lashes and eyes
    keep transparency (everything else is made opaque, which also sorts correctly)."""
    tmp = tempfile.mkdtemp(prefix="vbd_slim_")

    def see_through(m):
        names = [m.name.lower()] + [n.image.name.lower() for n in m.node_tree.nodes
                                    if n.type == "TEX_IMAGE" and n.image]
        return any(s in nm for nm in names for s in SEE_THROUGH)

    for m in bpy.data.materials:
        if not m.use_nodes or not m.node_tree:
            continue
        nt = m.node_tree
        for node in list(nt.nodes):
            if node.type in ("NORMAL_MAP", "BUMP"):
                nt.nodes.remove(node)
        if not see_through(m):
            for link in list(nt.links):
                if link.to_socket.name == "Alpha":
                    nt.links.remove(link)
            for attr, val in (("blend_method", "OPAQUE"), ("surface_render_method", "DITHERED")):
                try:
                    setattr(m, attr, val)
                except Exception:
                    pass
        for node in list(nt.nodes):
            if node.type == "TEX_IMAGE" and node.image and not node.outputs["Color"].links and \
                    not node.outputs["Alpha"].links:
                nt.nodes.remove(node)  # e.g. a normal map texture left without its node
    done = set()
    for m in bpy.data.materials:
        if not m.use_nodes or not m.node_tree:
            continue
        for node in m.node_tree.nodes:
            img = node.image if node.type == "TEX_IMAGE" else None
            if img is None or img.name in done or img.size[0] == 0:
                continue
            done.add(img.name)
            w, h = img.size
            cap = texture_budget(img.name)
            if max(w, h) > cap:
                img.scale(max(1, w * cap // max(w, h)), max(1, h * cap // max(w, h)))
            uses_alpha = bool(node.outputs["Alpha"].links) and see_through(m)
            ext = "png" if uses_alpha else "jpg"
            path = os.path.join(tmp, "%s.%s" % ("".join(c if c.isalnum() else "_" for c in img.name), ext))
            img.filepath_raw = path
            img.file_format = "PNG" if uses_alpha else "JPEG"
            img.save()
            try:
                img.source = "FILE"
                img.filepath = path
                img.reload()
            except Exception:
                pass


def export(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    for o in list(bpy.data.objects):
        if o.type not in ("ARMATURE", "MESH", "EMPTY"):
            bpy.data.objects.remove(o, do_unlink=True)
    slim_materials()
    # WebP: small, keeps transparency, and Godot reads it (its glTF JPEG decoding failed on these).
    opts = dict(filepath=path, export_format="GLB", use_selection=False, export_apply=False,
                export_animations=True, export_animation_mode="NLA_TRACKS", export_skins=True,
                export_yup=True, export_force_sampling=True, export_def_bones=False,
                export_image_format="WEBP", export_image_quality=88)
    for drop in (None, "export_image_quality", "export_def_bones"):
        if drop:
            opts.pop(drop, None)
        try:
            bpy.ops.export_scene.gltf(**opts)
            return
        except TypeError:
            continue
    raise RuntimeError("glTF export failed")


# --------------------------------------------------------------------------- main
def first_file(folder, names):
    for n in names:
        p = os.path.join(folder, n)
        if os.path.exists(p):
            return p
    return None


def build(mid, motions_dir, mode):
    """mode: "auto" (art/heroes/<id>/rigged.* or model.*), "mannequin" or "test-body"."""
    clear_scene()
    spec = H.spec(mid)
    owner = H.motion_owner(mid)
    if mode == "mannequin":
        arm = build_mannequin(spec["height"])
    elif mode == "makehuman":
        import hero_mpfb
        stock = arg("--stock")
        log("%s: building with MakeHuman%s" % (mid, " (stock clothes: %s)" % stock if stock else ""))
        arm = hero_mpfb.build(mid, stock_clothes=stock.split(",") if stock else None, log=log)
    elif mode == "test-body":
        arm = auto_rig(build_test_body(spec["height"]), spec["height"])
    else:
        folder = os.path.join(ROOT, "art", "heroes", mid)
        rigged = first_file(folder, ["rigged.glb", "rigged.fbx"])
        model = first_file(folder, ["model.glb", "model.obj", "model.fbx"])
        if rigged and mode != "procedural":
            log("%s: using the rigged model %s" % (mid, os.path.basename(rigged)))
            arm = import_rigged(rigged, spec["height"])
        elif model and mode != "procedural":
            log("%s: auto-rigging %s" % (mid, os.path.basename(model)))
            arm = auto_rig(import_model(model), spec["height"])
        else:
            import hero_builder
            log("%s: building in Blender (hero_looks.py)" % mid)
            arm = hero_builder.build(mid)
    bpy.context.view_layer.update()
    if arg("--looks-only"):
        return arm, []
    rt = Retargeter(arm)
    log("%s: rig has %d bones; matched %d slots" % (mid, len(arm.data.bones), len(rt.tmap)))
    clips = []
    for anim, mspec in H.motions(owner).items():
        mpath = os.path.join(motions_dir, owner, anim + ".npz")
        if not os.path.exists(mpath):
            log("  %s: no motion yet (%s)" % (anim, os.path.relpath(mpath, ROOT)))
            continue
        mo = Motion(mpath)
        rot, hips_loc = rt.solve(mo, mspec)
        rot, hips_loc = finish_clip(rt, rot, hips_loc, mspec)
        n = write_action(arm, anim, rot, rt.tmap["hips"], hips_loc)
        clips.append((anim, n))
        log("  %s: %d frames (%.1fs)%s" % (anim, n, n / 30.0, " loop" if mspec.get("loop") else ""))
    return arm, clips


def main():
    if LOG and os.path.exists(LOG):
        os.remove(LOG)
    only = arg("--only")
    ids = only.split(",") if only else H.all_ids()
    motions_dir = arg("--motions") or os.path.join(ROOT, "art", "heroes", "motion")
    out_dir = arg("--out") or os.path.join(ROOT, "assets", "models", "heroes")
    render_dir = arg("--render")
    mode = "mannequin" if arg("--mannequin") else ("test-body" if arg("--test-body") else
                                                   ("procedural" if arg("--procedural") else
                                                    ("makehuman" if arg("--makehuman") else "auto")))
    scene = bpy.context.scene
    scene.render.fps = 30
    built = 0
    for mid in ids:
        try:
            res = build(mid, motions_dir, mode)
            if not res:
                continue
            arm, clips = res
            if arg("--looks-only"):  # quick check of the model: a portrait, no motions or export
                if render_dir:
                    os.makedirs(render_dir, exist_ok=True)
                    render_portrait(arm, os.path.join(render_dir, mid + "_portrait.png"))
                built += 1
                continue
            if not clips:
                log("SKIP %s: no motions" % mid)
                continue
            if render_dir:
                os.makedirs(render_dir, exist_ok=True)
                render_portrait(arm, os.path.join(render_dir, mid + "_portrait.png"))
                render_sheet(arm, clips, os.path.join(render_dir, mid + ("" if mode == "auto" else "_" + mode) + ".png"))
            if not arg("--no-export"):
                arm.scale = arm.scale * H.GAME_SCALE
                path = os.path.join(out_dir, mid + ".glb")
                export(path)
                log("  wrote %s" % path)
            built += 1
        except Exception:
            log("FAILED %s:\n%s" % (mid, traceback.format_exc()))
    log("DONE %d heroes" % built)


main()
