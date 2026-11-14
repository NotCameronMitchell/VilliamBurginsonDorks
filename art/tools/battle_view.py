"""
Where a spot in an arena lands on the battle screen (1280x720), and whether the HUD covers
it. Use it to place signs and props where the player will see them.

    python art/tools/battle_view.py X Y Z                  a point (game coordinates)
    python art/tools/battle_view.py X Y Z W H [ENEMIES]    a sign: bottom-center X Y Z,
                                                           W wide and H tall, in a fight
                                                           with ENEMIES enemies (default 1)

The camera is read from scenes/battle/battle_scene.gd (CAM_POS, CAM_LOOK, CAM_FOV). The HUD
rectangles were measured on screenshots: the enemies' health list (about 55 px per enemy),
the party list on the right, the top bar and the text box at the bottom.
"""

import math
import os
import re
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SCENE = os.path.join(HERE, "..", "..", "scenes", "battle", "battle_scene.gd")
W, H = 1280, 720


def camera():
    pos, look, fov = (-1.3, 5.0, 11.0), (0.2, -0.2, -0.6), 38.0
    try:
        src = open(SCENE, encoding="utf-8").read()
        vec = lambda name: tuple(float(v) for v in re.search(r"const %s := Vector3\(([^)]*)\)" % name, src).group(1).split(","))
        pos, look = vec("CAM_POS"), vec("CAM_LOOK")
        fov = float(re.search(r"const CAM_FOV := ([\d.]+)", src).group(1))
    except (OSError, AttributeError, ValueError):
        pass
    return np.array(pos), np.array(look), fov


POS, LOOK, FOV = camera()
_f = (LOOK - POS) / np.linalg.norm(LOOK - POS)
_r = np.cross(_f, [0.0, 1.0, 0.0])
_r /= np.linalg.norm(_r)
_u = np.cross(_r, _f)
_t = math.tan(math.radians(FOV / 2))


def screen(p):
    """Pixel position (x, y) of a game-space point on a 1280x720 battle screen."""
    d = np.array(p, float) - POS
    depth = d @ _f
    return ((d @ _r) / (depth * _t * W / H) + 1) / 2 * W, (1 - (d @ _u) / (depth * _t)) / 2 * H


def covered_by(sx, sy, enemies=1):
    if sy < 40:
        return "top bar"
    if sx < 325 and sy < 30 + 55 * enemies:
        return "enemy health"
    if sx > 955 and 150 < sy < 390:
        return "party health"
    if sy > 515:
        return "text box"
    if not (0 <= sx <= W and 0 <= sy <= H):
        return "off screen"
    return ""


def main(argv):
    if len(argv) not in (3, 5, 6):
        print(__doc__)
        return 1
    x, y, z = (float(a) for a in argv[:3])
    if len(argv) == 3:
        sx, sy = screen((x, y, z))
        print("(%.0f, %.0f) %s" % (sx, sy, covered_by(sx, sy) or "visible"))
        return 0
    w, h = float(argv[3]), float(argv[4])
    enemies = int(argv[5]) if len(argv) == 6 else 1
    corners = [screen(p) for p in ((x - w / 2, y + h, z), (x + w / 2, y + h, z), (x - w / 2, y, z), (x + w / 2, y, z))]
    hidden = sorted({covered_by(sx, sy, enemies) for sx, sy in corners} - {""})
    print("top-left (%.0f, %.0f), bottom-right (%.0f, %.0f): %s" % (
        corners[0][0], corners[0][1], corners[3][0], corners[3][1], ", ".join(hidden) if hidden else "all visible"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
