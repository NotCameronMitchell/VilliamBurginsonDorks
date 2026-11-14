"""
Keyframed stand-in motions, written in Kimodo's own format (SOMA skeleton, 30 fps), for
while Kimodo can't run (it needs Meta's Llama 3 access). hero_assemble.py retargets them
exactly like Kimodo's output, and `heroes.ps1 motions` replaces them with real Kimodo
motions automatically (kimodo_batch.py regenerates any clip not made by Kimodo).

    python art/tools/motion_keys.py [--only cole,sam] [--force]

Poses are local joint rotations on the SOMA T-pose, whose axes line up with the world:
X = the character's left, Y = up, Z = forward. So, for example:
- lower the left arm to the side: LeftArm z=-72 (the right arm: z=+72)
- arm forward: LeftArm y=-90, RightArm y=+90
- bend the spine forward: x=+; lift a leg forward: Leg x=-; bend a knee: Shin x=+
"""

import argparse
import json
import math
import os
import sys

import numpy as np
from scipy.spatial.transform import Rotation as Rot
from scipy.spatial.transform import Slerp

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hero_specs as H  # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
MOTION_DIR = os.path.join(ROOT, "art", "heroes", "motion")
FPS = 30

JOINTS = [("Hips", None), ("Spine1", "Hips"), ("Spine2", "Spine1"), ("Chest", "Spine2"), ("Neck1", "Chest"),
          ("Neck2", "Neck1"), ("Head", "Neck2"), ("Jaw", "Head"), ("LeftEye", "Head"), ("RightEye", "Head")]
for _s in ("Left", "Right"):
    JOINTS += [(_s + "Shoulder", "Chest"), (_s + "Arm", _s + "Shoulder"), (_s + "ForeArm", _s + "Arm"),
               (_s + "Hand", _s + "ForeArm"), (_s + "HandThumbEnd", _s + "Hand"), (_s + "HandMiddleEnd", _s + "Hand")]
for _s in ("Left", "Right"):
    JOINTS += [(_s + "Leg", "Hips"), (_s + "Shin", _s + "Leg"), (_s + "Foot", _s + "Shin"), (_s + "ToeBase", _s + "Foot")]
NAMES = [j for j, _ in JOINTS]
IDX = {n: i for i, n in enumerate(NAMES)}
PARENT = [IDX[p] if p else -1 for _, p in JOINTS]

# SOMA T-pose offsets from parent (meters, Kimodo axes), measured from Kimodo's own output.
OFFSETS = {
    "Hips": (0, 0, 0), "Spine1": (0, 0.050, -0.001), "Spine2": (0, 0.071, 0), "Chest": (0, 0.076, -0.008),
    "Neck1": (0, 0.263, -0.006), "Neck2": (0, 0.077, 0.023), "Head": (0, 0.06, 0.01), "Jaw": (0, -0.02, 0.06),
    "LeftEye": (0.03, 0.06, 0.08), "RightEye": (-0.03, 0.06, 0.08),
    "LeftShoulder": (0.016, 0.232, 0.051), "LeftArm": (0.149, 0, -0.055), "LeftForeArm": (0.287, 0, 0),
    "LeftHand": (0.271, 0, 0), "LeftHandThumbEnd": (0.05, -0.01, 0.05), "LeftHandMiddleEnd": (0.17, 0, 0),
    "LeftLeg": (0.10, -0.084, 0.026), "LeftShin": (0, -0.432, -0.008), "LeftFoot": (0, -0.422, -0.035),
    "LeftToeBase": (0, -0.051, 0.132),
}
for _k, _v in list(OFFSETS.items()):
    if _k.startswith("Left"):
        OFFSETS["Right" + _k[4:]] = (-_v[0], _v[1], _v[2])
OFF = np.array([OFFSETS[n] for n in NAMES], dtype=float)
HIPS_H = 0.432 + 0.422 + 0.084 + 0.051 + 0.03  # standing hip height above the floor


def euler(x=0.0, y=0.0, z=0.0):
    return Rot.from_euler("xyz", [x, y, z], degrees=True)


def mirror(pose):
    """Left <-> right with the pose mirrored across the body's center plane."""
    out = {}
    for k, v in pose.items():
        if k.startswith("_"):
            out[k] = v
            continue
        name = ("Right" + k[4:]) if k.startswith("Left") else (("Left" + k[5:]) if k.startswith("Right") else k)
        x, y, z = v
        out[name] = (x, -y, -z)
    return out


# A relaxed standing pose every clip starts from.
BASE = {"LeftArm": (0, -6, -80), "RightArm": (0, 6, 80), "LeftForeArm": (0, -14, 0), "RightForeArm": (0, 14, 0),
        "LeftHand": (0, 0, -6), "RightHand": (0, 0, 6)}


def P(**kw):
    """A pose: BASE plus overrides. Keys are joint names; '_root' = (dx, dy, dz) meters;
    '_turn' = (x, y, z) degrees for the whole body."""
    pose = dict(BASE)
    for k, v in kw.items():
        pose[k] = v
    return pose


def sample(keys, n):
    """Keys: [(time in seconds, pose)]. Returns per-frame local rotations, root offsets, body turn."""
    times = [t for t, _ in keys]
    t_frames = np.arange(n) / FPS
    rots = np.zeros((n, len(NAMES), 3, 3))
    for j, name in enumerate(NAMES):
        rr = Rot.from_euler("xyz", [p.get(name, (0, 0, 0)) for _, p in keys], degrees=True)
        if len(keys) == 1:
            rots[:, j] = rr[0].as_matrix()
            continue
        sl = Slerp(times, rr)
        tt = np.clip(eased(t_frames, times), times[0], times[-1])
        rots[:, j] = sl(tt).as_matrix()
    root = np.array([p.get("_root", (0, 0, 0)) for _, p in keys], dtype=float)
    turn = Rot.from_euler("xyz", [p.get("_turn", (0, 0, 0)) for _, p in keys], degrees=True)
    tt = np.clip(eased(t_frames, times), times[0], times[-1])
    root_f = np.stack([np.interp(tt, times, root[:, k]) for k in range(3)], 1)
    turn_f = Slerp(times, turn)(tt).as_matrix() if len(keys) > 1 else np.repeat(turn[0].as_matrix()[None], n, 0)
    return rots, root_f, turn_f


def eased(t, times):
    """Smooth in/out between keyframes (keeps key times, eases each segment)."""
    out = np.array(t, dtype=float)
    for a, b in zip(times, times[1:]):
        m = (t >= a) & (t <= b)
        u = (t[m] - a) / max(b - a, 1e-6)
        out[m] = a + (b - a) * (u * u * (3 - 2 * u))
    return out


def fk(rots, root, turn):
    n = len(rots)
    G = np.zeros_like(rots)
    Pp = np.zeros((n, len(NAMES), 3))
    for j in range(len(NAMES)):
        p = PARENT[j]
        if p < 0:
            G[:, j] = turn @ rots[:, j]
            Pp[:, j] = np.array([0, HIPS_H, 0]) + root
        else:
            G[:, j] = G[:, p] @ rots[:, j]
            Pp[:, j] = Pp[:, p] + np.einsum("fij,j->fi", G[:, p], OFF[j])
    return Pp, G


def wobble(n, amp, freq, phase=0.0):
    t = np.arange(n) / FPS
    return amp * np.sin(2 * math.pi * freq * t + phase)


def clip(keys, seconds, extra=None):
    n = int(round(seconds * FPS))
    rots, root, turn = sample(keys, n)
    if extra:
        extra(rots, root, turn, n)
    return fk(rots, root, turn)


def add_rot(rots, name, x=None, y=None, z=None):
    """Adds per-frame rotations (arrays in degrees) on top of a joint's keyframed rotation."""
    n = len(rots)
    e = np.zeros((n, 3))
    for k, arr in enumerate((x, y, z)):
        if arr is not None:
            e[:, k] = arr
    rots[:, IDX[name]] = rots[:, IDX[name]] @ Rot.from_euler("xyz", e, degrees=True).as_matrix()


# =========================================================================== clips
def idle(style):
    if style == "boxer":  # a loose guard: fists at chest height, not up by the face
        pose = P(LeftArm=(0, -32, -72), RightArm=(0, 32, 72), LeftForeArm=(0, -88, 0), RightForeArm=(0, 88, 0),
                 Spine2=(6, 0, 0), LeftShin=(10, 0, 0), RightShin=(10, 0, 0), LeftLeg=(-8, 0, 0), RightLeg=(-6, 0, 0),
                 _root=(0, -0.03, 0))
    elif style == "crossed":
        pose = P(LeftArm=(0, -55, -70), RightArm=(0, 55, 70), LeftForeArm=(0, -115, 10), RightForeArm=(0, 112, -10),
                 Head=(-4, 0, 3))
    elif style == "pockets":
        pose = P(LeftArm=(0, 12, -80), RightArm=(0, -12, 80), LeftForeArm=(0, -25, 0), RightForeArm=(0, 25, 0))
    else:
        pose = P()
    bounce = {"boxer": 0.018, "bounce": 0.02, "dance": 0.03}.get(style, 0.006)
    freq = {"boxer": 1.6, "bounce": 1.5, "dance": 2.0}.get(style, 0.5)

    def extra(rots, root, turn, n):
        root[:, 1] += -np.abs(wobble(n, bounce, freq / 2)) if bounce > 0.01 else wobble(n, bounce, freq)
        root[:, 0] += wobble(n, 0.012, 0.25)
        add_rot(rots, "Chest", x=wobble(n, 1.5, 0.5))
        add_rot(rots, "Hips", z=wobble(n, 1.5, 0.25))
        add_rot(rots, "Head", y=wobble(n, 6 if style == "look" else 3, 0.125), x=wobble(n, 3 if style == "pockets" else 1, 1.0 if style == "pockets" else 0.4))
        add_rot(rots, "LeftArm", z=wobble(n, 2, 0.5, 1.0))
        add_rot(rots, "RightArm", z=wobble(n, 2, 0.5, 2.0))
        if style in ("bounce", "dance"):
            add_rot(rots, "LeftShin", x=np.abs(wobble(n, 10, freq / 2)))
            add_rot(rots, "RightShin", x=np.abs(wobble(n, 10, freq / 2)))
            add_rot(rots, "LeftLeg", x=-np.abs(wobble(n, 5, freq / 2)))
            add_rot(rots, "RightLeg", x=-np.abs(wobble(n, 5, freq / 2)))
        if style == "dance":
            add_rot(rots, "Hips", y=wobble(n, 8, 1.0))
            add_rot(rots, "LeftArm", z=wobble(n, 10, 1.0))
            add_rot(rots, "RightArm", z=wobble(n, 10, 1.0, math.pi))
        if style == "lean":
            add_rot(rots, "Hips", z=np.full(n, 4.0))
            add_rot(rots, "LeftLeg", z=np.full(n, -3.0))

    return clip([(0, pose), (4.0, pose)], 4.0, extra)


def walk():
    """A natural walk cycle (two steps per second), keyed over several full cycles so the
    loop cutter in hero_assemble.py always finds a real cycle (a clip that holds still at
    the end loops "perfectly" and got picked before, giving a walk that barely moved)."""
    T = 1.0
    # Contact: left heel strikes in front, right foot pushes off behind; opposite arm forward.
    contact = P(LeftLeg=(-28, 0, 0), LeftShin=(4, 0, 0), LeftFoot=(-14, 0, 0),
                RightLeg=(20, 0, 0), RightShin=(18, 0, 0), RightFoot=(22, 0, 0),
                LeftArm=(0, 18, -76), RightArm=(0, 26, 76), LeftForeArm=(0, -12, 0), RightForeArm=(0, 30, 0),
                Hips=(0, 6, 0), Spine2=(0, -4, 0), Chest=(0, -4, 0), Head=(0, 2, 0), _root=(0.0, -0.022, 0))
    # Down: weight onto the front leg, knee soaks it up.
    down = P(LeftLeg=(-18, 0, 0), LeftShin=(16, 0, 0), LeftFoot=(0, 0, 0),
             RightLeg=(12, 0, 0), RightShin=(42, 0, 0), RightFoot=(30, 0, 0),
             LeftArm=(0, 10, -78), RightArm=(0, 16, 78), LeftForeArm=(0, -14, 0), RightForeArm=(0, 26, 0),
             Hips=(0, 4, 3), Spine2=(0, -2, 0), Chest=(0, -2, 0), _root=(0.012, -0.03, 0))
    # Passing: standing on the left leg, the right swings through with the knee lifted.
    passing = P(LeftLeg=(-2, 0, 0), LeftShin=(6, 0, 0), LeftFoot=(2, 0, 0),
                RightLeg=(-14, 0, 0), RightShin=(62, 0, 0), RightFoot=(8, 0, 0),
                LeftArm=(0, -2, -80), RightArm=(0, 4, 80), LeftForeArm=(0, -16, 0), RightForeArm=(0, 18, 0),
                Hips=(0, 0, 4), _root=(0.016, 0.006, 0))
    # Up: the right leg reaches forward, the left starts to push.
    up = P(LeftLeg=(10, 0, 0), LeftShin=(8, 0, 0), LeftFoot=(10, 0, 0),
           RightLeg=(-26, 0, 0), RightShin=(22, 0, 0), RightFoot=(-6, 0, 0),
           LeftArm=(0, -10, -78), RightArm=(0, -8, 78), LeftForeArm=(0, -22, 0), RightForeArm=(0, 12, 0),
           Hips=(0, -3, 2), Spine2=(0, 2, 0), Chest=(0, 2, 0), _root=(0.008, 0.002, 0))
    half = [contact, down, passing, up]
    other = [mirror(p) for p in half]
    for p in other:  # mirror() keeps root offsets; the sway goes the other way
        if "_root" in p:
            x, y, z = p["_root"]
            p["_root"] = (-x, y, z)
    cycle = half + other
    keys = []
    cycles = 3
    for c in range(cycles):
        for i, p in enumerate(cycle):
            keys.append((c * T + i * T / len(cycle), p))
    keys.append((cycles * T, cycle[0]))
    return clip(keys, cycles * T + 1.0 / FPS)


def attack(kind):
    if kind == "kick":
        keys = [(0, P()), (0.35, P(RightLeg=(25, 0, 0), RightShin=(70, 0, 0), LeftShin=(15, 0, 0), Spine2=(-8, 0, 0),
                                    LeftArm=(0, 30, -40), RightArm=(0, -30, 40), _root=(0, -0.03, -0.05))),
                (0.55, P(RightLeg=(-85, 0, 0), RightShin=(5, 0, 0), Spine2=(-15, 0, 0), LeftArm=(0, -20, -30),
                         RightArm=(0, 40, 50), _root=(0, 0, 0.08))),
                (0.8, P(RightLeg=(-40, 0, 0), RightShin=(40, 0, 0), _root=(0, 0, 0.12))), (1.4, P(_root=(0, 0, 0.05)))]
    elif kind == "golf":
        up = P(Spine2=(15, 55, 0), Chest=(0, 20, 0), LeftArm=(0, -60, -30), RightArm=(0, 100, 10),
               LeftForeArm=(0, -10, 0), RightForeArm=(0, 60, 0), Head=(0, -40, 0), LeftShin=(12, 0, 0), RightShin=(12, 0, 0))
        hit = P(Spine2=(18, -10, 0), LeftArm=(0, 50, -45), RightArm=(0, 40, 45), LeftForeArm=(0, 0, 0),
                RightForeArm=(0, 0, 0), Head=(10, 10, 0), LeftShin=(10, 0, 0), RightShin=(10, 0, 0))
        follow = P(Spine2=(0, -65, 0), Chest=(0, -20, 0), LeftArm=(0, 80, -10), RightArm=(0, -50, 30),
                   LeftForeArm=(0, 60, 0), RightForeArm=(0, -10, 0), Head=(-5, 20, 0))
        keys = [(0, P(Spine2=(18, 0, 0), LeftArm=(0, 40, -50), RightArm=(0, -40, 50))), (0.5, up), (0.72, hit),
                (0.95, follow), (1.5, P())]
    elif kind == "putt":
        address = P(Spine2=(30, 0, 0), Head=(15, 0, 0), LeftArm=(0, 35, -70), RightArm=(0, -35, 70),
                    LeftForeArm=(0, -10, 0), RightForeArm=(0, 10, 0), LeftShin=(10, 0, 0), RightShin=(10, 0, 0))
        back = dict(address, Spine2=(30, 10, 0), LeftArm=(0, 25, -66), RightArm=(0, -45, 74))
        thru = dict(address, Spine2=(30, -12, 0), LeftArm=(0, 45, -74), RightArm=(0, -25, 66))
        keys = [(0, P()), (0.25, address), (0.45, back), (0.65, thru), (0.85, back), (1.05, thru), (1.6, P())]
    elif kind == "blast":
        keys = [(0, P()), (0.4, P(LeftArm=(0, 60, -10), RightArm=(0, -60, 10), LeftForeArm=(0, -110, 0),
                                  RightForeArm=(0, 110, 0), Spine2=(-10, 0, 0), _root=(0, -0.02, -0.04))),
                (0.6, P(LeftArm=(0, -85, -5), RightArm=(0, 85, 5), LeftForeArm=(0, 0, 0), RightForeArm=(0, 0, 0),
                        Spine2=(10, 0, 0), _root=(0, 0, 0.08))), (1.0, P(LeftArm=(0, -80, -10), RightArm=(0, 80, 10))),
                (1.5, P())]
    elif kind == "slam":
        keys = [(0, P()), (0.45, P(LeftArm=(0, -40, 150), RightArm=(0, 40, -150), LeftForeArm=(0, -20, 0),
                                   RightForeArm=(0, 20, 0), Spine2=(-12, 0, 0), _root=(0, 0.03, 0))),
                (0.7, P(LeftArm=(0, -90, -10), RightArm=(0, 90, 10), Spine2=(35, 0, 0), LeftShin=(30, 0, 0),
                        RightShin=(30, 0, 0), LeftLeg=(-20, 0, 0), RightLeg=(-20, 0, 0), _root=(0, -0.09, 0.05))),
                (1.0, P(Spine2=(25, 0, 0), _root=(0, -0.05, 0.03))), (1.6, P())]
    else:  # spin strike
        keys = [(0, P()), (0.3, P(Spine2=(0, 40, 0), RightArm=(0, -40, 40), LeftArm=(0, 20, -60))),
                (0.55, P(_turn=(0, -180, 0), Spine2=(0, -20, 0), RightArm=(0, 80, 20))),
                (0.75, P(_turn=(0, -360, 0), RightArm=(0, 95, 0), RightForeArm=(0, 0, 0), _root=(0, 0, 0.1))),
                (1.4, P(_turn=(0, -360, 0)))]
    return clip(keys, keys[-1][0] + 0.1)


def cast(kind):
    if kind == "command":
        keys = [(0, P()), (0.5, P(Spine2=(15, 0, 0), RightArm=(0, 85, 10), RightForeArm=(0, 0, 0), LeftShin=(20, 0, 0),
                                  RightShin=(20, 0, 0), _root=(0, -0.05, 0))), (1.4, P(Spine2=(15, 0, 0), RightArm=(0, 88, 5))),
                (2.0, P())]
    elif kind == "flex":
        flex = P(LeftArm=(0, 0, 5), RightArm=(0, 0, -5), LeftForeArm=(0, -120, 0), RightForeArm=(0, 120, 0),
                 Spine2=(-12, 0, 0), Head=(-20, 0, 0), _root=(0, -0.02, 0))
        keys = [(0, P()), (0.5, flex), (1.4, dict(flex, Spine2=(-18, 0, 0))), (2.0, P())]
    elif kind == "argue":
        g1 = P(LeftArm=(0, -60, -40), RightArm=(0, 60, 40), LeftForeArm=(0, -60, 0), RightForeArm=(0, 60, 0), Spine2=(5, 15, 0))
        g2 = P(RightArm=(0, 85, 10), RightForeArm=(0, 10, 0), LeftArm=(0, -30, -60), Spine2=(10, -10, 0), Head=(5, 0, 0))
        keys = [(0, P()), (0.4, g1), (0.8, g2), (1.2, g1), (1.6, g2), (2.2, P())]
    elif kind == "story":
        g1 = P(LeftArm=(0, -50, -30), RightArm=(0, 50, 30), LeftForeArm=(0, -70, 20), RightForeArm=(0, 70, -20))
        g2 = P(LeftArm=(0, -70, 10), RightArm=(0, 70, -10), LeftForeArm=(0, -30, 0), RightForeArm=(0, 30, 0), Head=(-8, 0, 0))
        keys = [(0, P()), (0.45, g1), (0.9, g2), (1.35, g1), (1.8, g2), (2.2, P())]
    elif kind == "spell":
        up = P(LeftArm=(0, -30, 100), RightArm=(0, 30, -100), LeftForeArm=(0, -30, 0), RightForeArm=(0, 30, 0),
               Spine2=(-12, 0, 0), Head=(-15, 0, 0))
        push = P(LeftArm=(0, -85, -5), RightArm=(0, 85, 5), LeftForeArm=(0, 0, 0), RightForeArm=(0, 0, 0),
                 LeftHand=(0, 0, 80), RightHand=(0, 0, -80), Spine2=(12, 0, 0), _root=(0, 0, 0.06))
        keys = [(0, P()), (0.6, up), (1.0, push), (1.5, push), (2.0, P())]
    else:  # dab
        dab = P(RightArm=(0, -20, -40), RightForeArm=(0, 10, 0), LeftArm=(0, -70, -60), LeftForeArm=(0, -140, 0),
                Head=(35, 25, 20), Spine2=(10, 15, 10))
        keys = [(0, P()), (0.35, dab), (1.3, dab), (1.8, P())]
    return clip(keys, keys[-1][0] + 0.1)


def hit():
    keys = [(0, P()), (0.12, P(Spine2=(-18, 0, 0), Head=(-20, 0, 0), LeftArm=(0, -30, -55), RightArm=(0, 30, 55),
                               LeftForeArm=(0, -60, 0), RightForeArm=(0, 60, 0), _root=(0, -0.02, -0.06))),
            (0.4, P(Spine2=(-10, 0, 0), LeftShin=(15, 0, 0), RightLeg=(10, 0, 0), _root=(0, -0.03, -0.12))),
            (1.2, P(_root=(0, 0, -0.08)))]
    return clip(keys, 1.3)


def stunned():
    pose = P(Spine2=(12, 0, 0), Head=(25, 0, 0), LeftArm=(0, 0, -80), RightArm=(0, 0, 80), LeftShin=(12, 0, 0),
             RightShin=(12, 0, 0))

    def extra(rots, root, turn, n):
        add_rot(rots, "Hips", z=wobble(n, 7, 0.5), x=wobble(n, 4, 0.5, math.pi / 2))
        add_rot(rots, "Spine2", z=wobble(n, -8, 0.5))
        add_rot(rots, "Head", z=wobble(n, 18, 0.5, 1.0), y=wobble(n, 12, 0.25))
        add_rot(rots, "LeftArm", z=wobble(n, 8, 0.5, 0.5))
        add_rot(rots, "RightArm", z=wobble(n, 8, 0.5, 2.0))
        root[:, 0] += wobble(n, 0.04, 0.5)
        root[:, 2] += wobble(n, 0.03, 0.5, math.pi / 2)

    return clip([(0, pose), (4.0, pose)], 4.0, extra)


def faint():
    buckle = P(Spine2=(20, 0, 0), Head=(30, 0, 0), LeftShin=(70, 0, 0), RightShin=(70, 0, 0), LeftLeg=(-50, 0, 0),
               RightLeg=(-45, 0, 0), _root=(0, -0.35, -0.05))
    lie = P(_turn=(-88, 0, 0), _root=(0, -0.85, -0.55), LeftArm=(0, 0, -50), RightArm=(0, 0, 50), Head=(-10, 20, 0),
            LeftShin=(10, 0, 0), RightShin=(25, 0, 0), RightLeg=(-15, 0, 0))
    keys = [(0, P()), (0.45, buckle), (1.1, lie), (2.6, lie)]
    return clip(keys, 2.7)


def victory(kind):
    if kind == "flex":
        a = P(LeftArm=(0, 0, 5), RightArm=(0, 0, -5), LeftForeArm=(0, -120, 0), RightForeArm=(0, 120, 0), Spine2=(-8, 0, 0))
        b = P(LeftArm=(0, -40, -20), RightArm=(0, 40, 20), LeftForeArm=(0, -100, 30), RightForeArm=(0, 100, -30), Spine2=(10, 0, 0))
        keys = [(0, a), (1.0, a), (2.0, b), (3.0, b), (4.0, a)]
    elif kind == "hips":
        hips = P(LeftArm=(0, 30, -75), RightArm=(0, -30, 75), LeftForeArm=(0, -100, 0), RightForeArm=(0, 100, 0), Head=(-8, 10, 5))
        keys = [(0, P()), (0.6, P(Head=(-15, -30, 0), RightArm=(0, 60, -60), RightForeArm=(0, 120, 0))), (1.3, hips), (4.0, hips)]
    elif kind == "dance":
        a = P(LeftArm=(0, -20, -40), RightArm=(0, 20, 40), LeftForeArm=(0, -80, 0), RightForeArm=(0, 80, 0))
        keys = [(0, a), (4.0, a)]

        def extra(rots, root, turn, n):
            add_rot(rots, "Hips", z=wobble(n, 10, 1.0), y=wobble(n, 12, 0.5))
            add_rot(rots, "Chest", z=wobble(n, -10, 1.0), y=wobble(n, -8, 2.0))
            add_rot(rots, "LeftArm", z=wobble(n, 15, 1.0))
            add_rot(rots, "RightArm", z=wobble(n, 15, 1.0, math.pi))
            root[:, 1] += -np.abs(wobble(n, 0.03, 1.0))
        return clip(keys, 4.0, extra)
    else:  # cheer: fist pumps, arms up
        up = P(LeftArm=(0, -10, 150), RightArm=(0, 10, -150), LeftForeArm=(0, -20, 0), RightForeArm=(0, 20, 0), Head=(-12, 0, 0),
               _root=(0, 0.02, 0))
        pump = P(RightArm=(0, 40, -120), RightForeArm=(0, 90, 0), LeftArm=(0, -10, -60), _root=(0, -0.02, 0))
        keys = [(0, pump), (0.5, up), (1.0, pump), (1.5, up), (2.5, up), (3.2, pump), (4.0, pump)]
    return clip(keys, keys[-1][0])


def ultimate(kind):
    crouch = P(Spine2=(25, 0, 0), LeftShin=(60, 0, 0), RightShin=(60, 0, 0), LeftLeg=(-45, 0, 0), RightLeg=(-45, 0, 0),
               LeftArm=(0, 40, -40), RightArm=(0, -40, 40), _root=(0, -0.25, 0))
    leap = P(Spine2=(-15, 0, 0), LeftArm=(0, -20, 140), RightArm=(0, 20, -140), LeftLeg=(-30, 0, 0), RightLeg=(10, 0, 0),
             LeftShin=(40, 0, 0), RightShin=(20, 0, 0), Head=(-20, 0, 0), _root=(0, 0.35, 0.15))
    land = P(Spine2=(20, 0, 0), LeftShin=(50, 0, 0), RightShin=(50, 0, 0), LeftLeg=(-40, 0, 0), RightLeg=(-40, 0, 0),
             LeftArm=(0, -40, -10), RightArm=(0, 40, 10), _root=(0, -0.2, 0.3))
    if kind == "drive":
        wheel = P(LeftArm=(0, -60, -30), RightArm=(0, 60, 30), LeftForeArm=(0, -60, 20), RightForeArm=(0, 60, -20),
                  Spine2=(5, 0, 0), LeftShin=(40, 0, 0), RightShin=(40, 0, 0), LeftLeg=(-50, 0, 0), RightLeg=(-50, 0, 0),
                  _root=(0, -0.25, 0))
        turn_l = dict(wheel, Spine2=(5, 25, 15), LeftArm=(0, -40, -50), RightArm=(0, 75, 10))
        turn_r = dict(wheel, Spine2=(5, -25, -15), LeftArm=(0, -75, -10), RightArm=(0, 40, 50))
        keys = [(0, P()), (0.4, wheel), (0.9, turn_l), (1.5, turn_r), (2.1, turn_l), (2.6, leap), (3.2, land), (3.5, P())]
    elif kind == "ring":
        show = P(LeftArm=(0, -70, 30), LeftForeArm=(0, -90, 0), LeftHand=(0, 0, 0), RightArm=(0, 60, 40), RightForeArm=(0, 100, 0),
                 Head=(5, 15, 0))
        keys = [(0, P()), (0.6, show), (2.0, show), (2.6, leap), (3.2, land), (3.5, P())]
    else:
        keys = [(0, P()), (0.5, crouch), (0.9, crouch), (1.4, leap), (2.0, land), (2.6, land), (3.2, P())]
    return clip(keys, keys[-1][0] + 0.1)


STYLE = {  # idle, attack, cast, victory, ultimate per hero
    "mason": ("bounce", "kick", "command", "cheer", "ring"),
    "james": ("boxer", "golf", "flex", "flex", "jump"),
    "cole": ("lean", "putt", "argue", "cheer", "jump"),
    "cam": ("pockets", "blast", "story", "cheer", "drive"),
    "sam": ("crossed", "slam", "spell", "hips", "jump"),
    "sarah": ("dance", "spin", "dab", "dance", "drive"),
}


def make(hero):
    s = STYLE[hero]
    return {"idle": idle(s[0]), "walk": walk(), "attack": attack(s[1]), "cast": cast(s[2]), "hit": hit(),
            "stunned": stunned(), "faint": faint(), "victory": victory(s[3]), "ultimate": ultimate(s[4])}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--only")
    p.add_argument("--force", action="store_true", help="also overwrite real Kimodo motions")
    p.add_argument("--out", default=MOTION_DIR)
    args = p.parse_args()
    heroes = args.only.split(",") if args.only else list(H.HEROES)
    for hero in heroes:
        for anim, (pos, rot) in make(hero).items():
            path = os.path.join(args.out, hero, anim + ".npz")
            meta_path = path[:-4] + ".json"
            if os.path.exists(meta_path) and not args.force:
                with open(meta_path, encoding="utf-8") as f:
                    if json.load(f).get("model", "").startswith("Kimodo"):
                        continue  # never replace a real Kimodo motion
            os.makedirs(os.path.dirname(path), exist_ok=True)
            np.savez(path, posed_joints=pos.astype(np.float32), global_rot_mats=rot.astype(np.float32))
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump({"hero": hero, "anim": anim, "model": "keyframed", "frames": int(len(pos)), "fps": FPS,
                           "note": "stand-in until Kimodo runs (heroes.ps1 motions replaces it)"}, f, indent=2)
        print("%s: wrote %d stand-in motions" % (hero, 9))


if __name__ == "__main__":
    main()
