"""
Textures for the arenas and the office, made in code with numpy (no image files to keep
around): carpet tiles, asphalt, glossy diner tiles, stone floor tiles, wood and fabric, plus
the city skyline seen through the windows. Each one tiles seamlessly.

Every generator returns an (h, w, 3) float array of sRGB colors in 0..1; image() turns it
into a Blender image (saved as a PNG in Blender's temp folder, so the glTF export can embed
it). arenas.py maps them onto surfaces with world-space UVs.
"""

import os

import numpy as np


def rgb(hex_color):
    h = hex_color.lstrip("#")
    return np.array([int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)])


def noise(h, w, cy, cx, rng, octaves=4, persistence=0.5):
    """Tileable value noise in 0..1: cy x cx cells at the first octave, each octave twice as
    fine. Unequal cy and cx give streaks."""
    out = np.zeros((h, w))
    amp = total = 1.0
    total = 0.0
    for o in range(octaves):
        ny, nx = max(1, cy * 2 ** o), max(1, cx * 2 ** o)
        g = rng.random((ny, nx))
        ys, xs = np.arange(h) * ny / h, np.arange(w) * nx / w
        y0, x0 = np.floor(ys).astype(int), np.floor(xs).astype(int)
        fy, fx = ys - y0, xs - x0
        fy, fx = fy * fy * (3 - 2 * fy), fx * fx * (3 - 2 * fx)
        y1, x1 = (y0 + 1) % ny, (x0 + 1) % nx
        y0, x0 = y0 % ny, x0 % nx
        top = g[np.ix_(y0, x0)] * (1 - fx) + g[np.ix_(y0, x1)] * fx
        bot = g[np.ix_(y1, x0)] * (1 - fx) + g[np.ix_(y1, x1)] * fx
        out += amp * (top * (1 - fy)[:, None] + bot * fy[:, None])
        total += amp
        amp *= persistence
    return out / total


def blur(a, r=1):
    """A cheap wrapping box blur (r pixels)."""
    out = a.copy()
    for ax in (0, 1):
        acc = np.zeros_like(out)
        for d in range(-r, r + 1):
            acc += np.roll(out, d, axis=ax)
        out = acc / (2 * r + 1)
    return out


def lines(size, n, width):
    """1 on grid lines (n per side, `width` pixels wide), 0 elsewhere."""
    i = np.arange(size)
    on = (i % (size // n)) < width
    return np.maximum(on[:, None], on[None, :]).astype(float)


# ------------------------------------------------------------------------- floors
def carpet(base, accent=None, seed=1, size=512, tiles=2, fleck=0.035, contrast=1.0):
    """Carpet tiles, laid quarter-turned like an office floor (2x2 tiles per texture, so
    one texture is about 1 m): a fine pile, streaks that turn from tile to tile, a few
    flecks of a second color and thin seams."""
    rng = np.random.default_rng(seed)
    base = rgb(base)
    grain = rng.random((size, size))
    along_x = noise(size, size, 64, 6, rng, octaves=2)
    along_y = noise(size, size, 6, 64, rng, octaves=2)
    t = size // tiles
    ty, tx = np.meshgrid(np.arange(size) // t, np.arange(size) // t, indexing="ij")
    streak = np.where((ty + tx) % 2 == 0, along_x, along_y)
    blotch = noise(size, size, 3, 3, rng, octaves=3)
    v = 0.84 + contrast * (0.16 * grain + 0.22 * (streak - 0.5) + 0.12 * (blotch - 0.5))
    per_tile = 1 + 0.035 * rng.standard_normal((tiles, tiles))
    v = v * per_tile[ty, tx]
    img = base[None, None, :] * v[..., None]
    if accent:
        dots = rng.random((size, size)) < fleck
        img[dots] = img[dots] * 0.4 + rgb(accent) * 0.6
    seam = lines(size, tiles, 2)
    img *= (1 - 0.18 * seam)[..., None]
    return np.clip(img, 0, 1)


def asphalt(base="#4a4d55", seed=2, size=512, cracks=5):
    """Asphalt (one texture is about 4 m): grit, aggregate, patches and a few cracks."""
    rng = np.random.default_rng(seed)
    base = rgb(base)
    grit = rng.random((size, size))
    patch = noise(size, size, 4, 4, rng, octaves=4)
    v = 0.86 + 0.2 * (grit - 0.5) + 0.22 * (patch - 0.5)
    stones = rng.random((size, size))
    v = np.where(stones > 0.985, v * 1.35, v)
    v = np.where(stones < 0.012, v * 0.6, v)
    crack = np.zeros((size, size))
    for _ in range(cracks):
        y, x = rng.integers(0, size, 2)
        a = rng.uniform(0, 2 * np.pi)
        for _ in range(int(rng.integers(40, 160))):
            a += rng.normal(0, 0.35)
            y, x = (y + np.sin(a) * 1.6) % size, (x + np.cos(a) * 1.6) % size
            crack[int(y), int(x)] = 1.0
    v *= 1 - 0.45 * np.clip(blur(crack, 1) * 3, 0, 1)
    return np.clip(base[None, None, :] * v[..., None], 0, 1)


def diner_tile(c1, c2, seed=3, size=512, grout="#d9d4c8"):
    """Glossy checkered tiles (2x2 per texture) with grout and a little grime."""
    rng = np.random.default_rng(seed)
    t = size // 2
    ty, tx = np.meshgrid(np.arange(size) // t, np.arange(size) // t, indexing="ij")
    col = np.where(((ty + tx) % 2 == 0)[..., None], rgb(c1), rgb(c2))
    grain = noise(size, size, 16, 16, rng, octaves=3)
    img = col * (0.93 + 0.1 * (grain - 0.5))[..., None]
    # Each tile's edge catches the light on one side and shades on the other.
    yy, xx = np.arange(size) % t, np.arange(size) % t
    edge = 10
    hi = (np.clip(1 - yy / edge, 0, 1)[:, None] + np.clip(1 - xx / edge, 0, 1)[None, :]) * 0.06
    lo = (np.clip(1 - (t - 1 - yy) / edge, 0, 1)[:, None] + np.clip(1 - (t - 1 - xx) / edge, 0, 1)[None, :]) * 0.08
    img = img * (1 + hi - lo)[..., None]
    g = lines(size, 2, 5)
    g = np.roll(np.roll(g, -2, 0), -2, 1)
    grime = blur(g, 6) * 0.25 * noise(size, size, 8, 8, rng, octaves=2)
    img *= (1 - grime)[..., None]
    img = img * (1 - g[..., None]) + rgb(grout) * (0.9 + 0.1 * grain[..., None]) * g[..., None]
    return np.clip(img, 0, 1)


def stone_tile(base, seed=4, size=512, n=2, grout="#8d8a84"):
    """Large speckled stone tiles (terrazzo), n x n per texture."""
    rng = np.random.default_rng(seed)
    base = rgb(base)
    t = size // n
    ty, tx = np.meshgrid(np.arange(size) // t, np.arange(size) // t, indexing="ij")
    cloud = noise(size, size, 4, 4, rng, octaves=4)
    v = 0.9 + 0.16 * (cloud - 0.5) + 0.05 * rng.standard_normal((n, n))[ty, tx]
    img = base[None, None, :] * v[..., None]
    chips = rng.random((size, size))
    for lo, hi, c in ((0.0, 0.02, "#f4f1ea"), (0.02, 0.032, "#5d5a55"), (0.032, 0.04, "#b9a58a")):
        m = blur(((chips >= lo) & (chips < hi)).astype(float), 1) > 0.3
        img[m] = img[m] * 0.3 + rgb(c) * 0.7
    g = np.roll(np.roll(lines(size, n, 3), -1, 0), -1, 1)
    img = img * (1 - g[..., None]) + rgb(grout) * g[..., None]
    return np.clip(img, 0, 1)


def wood(c1="#b38b5d", c2="#8a6440", seed=5, size=512, planks=4):
    """Wood planks running along x (planks per texture across y)."""
    rng = np.random.default_rng(seed)
    yy, xx = np.meshgrid(np.arange(size), np.arange(size), indexing="ij")
    p = yy // (size // planks)
    shift = rng.random(planks)[p] * size
    warp = noise(size, size, 2, 6, rng, octaves=3)
    rings = np.sin((yy / size * planks * 3 + warp * 2.5 + rng.random(planks)[p] * 6) * np.pi * 2) * 0.5 + 0.5
    fine = noise(size, size, 96, 2, rng, octaves=2)
    t = np.clip(0.3 * rings + 0.7 * fine, 0, 1)
    img = rgb(c1) * (1 - t[..., None]) + rgb(c2) * t[..., None]
    img *= (1 + 0.06 * rng.standard_normal(planks)[p])[..., None]
    seam = (yy % (size // planks)) < 2
    ends = ((xx + shift.astype(int)) % size) < 2
    img *= (1 - 0.35 * (seam | ends))[..., None]
    return np.clip(img, 0, 1)


def fabric(base, seed=6, size=256):
    """Woven cubicle-wall fabric."""
    rng = np.random.default_rng(seed)
    yy, xx = np.meshgrid(np.arange(size), np.arange(size), indexing="ij")
    weave = (np.sin(xx * np.pi / 2) * np.sin(yy * np.pi / 2)) * 0.5 + 0.5
    v = 0.9 + 0.08 * (weave - 0.5) + 0.08 * (noise(size, size, 8, 8, rng) - 0.5) + 0.05 * (rng.random((size, size)) - 0.5)
    return np.clip(rgb(base)[None, None, :] * v[..., None], 0, 1)


def grass(base="#86b86a", seed=7, size=512):
    rng = np.random.default_rng(seed)
    v = 0.85 + 0.25 * (noise(size, size, 6, 6, rng, octaves=5) - 0.5) + 0.12 * (rng.random((size, size)) - 0.5)
    img = rgb(base)[None, None, :] * v[..., None]
    dry = noise(size, size, 3, 3, rng, octaves=3) > 0.62
    img[dry] = img[dry] * 0.8 + rgb("#b5b46a") * 0.2
    return np.clip(img, 0, 1)


# ------------------------------------------------------------------------- the view
SKYLINES = {  # sky top, horizon, far buildings, near buildings, window colors, share of lit windows
    "day": ("#5f9be0", "#d6ecff", "#a9bfd9", "#7a8ca6", ("#d8e8f8", "#9fb6cf"), 0.0),
    "sunset": ("#6d83d0", "#ffc98f", "#c9a3a6", "#5e4b66", ("#ffd27a", "#3c3148"), 0.35),
    "night": ("#0b0e22", "#2c3666", "#202a4d", "#11152e", ("#ffd27a", "#1c2140"), 0.45),
    "pink": ("#a77fd6", "#ffd6ee", "#d9abd1", "#8b6ba9", ("#fff0b8", "#b591c9"), 0.15),
    "dusk": ("#27344f", "#8fa3c9", "#6a7ca3", "#3a4767", ("#ffd27a", "#2c3756"), 0.3),
    "warm": ("#ff9a4a", "#ffe39a", "#e3a77f", "#7a4b3a", ("#ffe08a", "#5a3a30"), 0.4),
}


def skyline(mood="day", seed=8, w=2048, h=256):
    """The city through a window: a sky gradient, hazy far towers and near towers with
    rows of windows (some lit). Tiles left to right."""
    top, horizon, far, near, (lit, dark), lit_share = SKYLINES[mood]
    rng = np.random.default_rng(seed)
    t = (np.arange(h) / (h - 1))[:, None, None]  # 0 at the top
    img = np.broadcast_to(rgb(top) * (1 - t ** 0.8) + rgb(horizon) * t ** 0.8, (h, w, 3)).copy()
    for layer, color, hmin, hmax, wmin, wmax in ((0, far, 0.25, 0.6, 50, 140), (1, near, 0.38, 0.92, 70, 190)):
        x = 0
        while x < w:
            bw = int(rng.integers(wmin, wmax))
            bh = int(h * rng.uniform(hmin, hmax))
            xs = (np.arange(x, x + bw)) % w
            shade = rgb(color) * rng.uniform(0.9, 1.1)
            img[h - bh:, xs] = shade
            if rng.random() < 0.3:  # a rooftop mast or a stepped top
                img[h - bh - int(h * 0.05):h - bh, xs[bw // 2 - 2:bw // 2 + 2]] = shade
            if layer == 1:
                cw, ch = int(rng.integers(6, 10)), int(rng.integers(7, 11))
                for wy in range(h - bh + 8, h - 4, ch + 5):
                    for wx in range(4, bw - cw - 2, cw + 5):
                        on = rng.random() < lit_share
                        c = rgb(lit) if on else rgb(dark) * rng.uniform(0.85, 1.15)
                        img[wy:wy + ch, (x + wx + np.arange(cw)) % w] = c
            else:
                img[h - bh:, xs] = img[h - bh:, xs] * 0.92 + rgb(horizon) * 0.08  # haze
            x += bw + int(rng.integers(0, 30))
    return np.clip(img, 0, 1)


def facade(seed=9, w=2048, h=256):
    """The office's own windows seen from the parking lot: the sunset city reflected in
    tinted glass, with a couple of diagonal glints."""
    rng = np.random.default_rng(seed)
    city = skyline("sunset", seed=seed, w=w, h=h)
    t = (np.arange(h) / (h - 1))[:, None, None]
    glass = rgb("#9fb0e0") * (1 - t) + rgb("#ffd2a8") * t
    img = city * 0.55 + glass * 0.45
    yy, xx = np.meshgrid(np.arange(h), np.arange(w), indexing="ij")
    for x0 in rng.integers(0, w, 3):
        band = np.abs(((xx - x0 - yy * 0.6) % w) - 40) < 14
        img[band] = img[band] * 0.75 + 0.25
    return np.clip(img, 0, 1)


# ------------------------------------------------------------------------- Blender
def image(name, arr):
    """A Blender image from an (h, w, 3) sRGB array, saved as a PNG so the glTF export can
    embed it."""
    import bpy
    h, w = arr.shape[:2]
    old = bpy.data.images.get(name)
    if old:
        bpy.data.images.remove(old)
    im = bpy.data.images.new(name, w, h, alpha=False)
    px = np.ones((h, w, 4), dtype=np.float32)
    px[..., :3] = arr[::-1]  # Blender's rows run bottom to top
    im.pixels.foreach_set(px.ravel())
    path = os.path.join(bpy.app.tempdir or os.environ.get("TEMP", "."), "vbd_tex_%s.png" % name)
    im.filepath_raw = path
    im.file_format = "PNG"
    im.save()
    return im
