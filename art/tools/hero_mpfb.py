"""
Builds a hero as a realistic MakeHuman character with MPFB (MakeHuman Plugin For Blender):
body and face shaped from hero_mh.py, MakeHuman skin, eyes, brows, lashes and hair, and
MPFB's Mixamo rig with weights. Outfits come from garments.py (hero_looks.py), so skins are
just data. hero_assemble.py then retargets the Kimodo motions and exports the hero.

Needs MPFB and the MakeHuman system assets: run art/tools/makehuman_setup.py once.
"""

import importlib
import os
import tempfile

import bpy
import numpy as np

import hero_mh
import hero_specs as H

REPO = "vbd"  # see makehuman_setup.py: MPFB lives in a short-path extension repository
REPO_DIR = os.path.join(os.path.expanduser("~"), ".vbd", "blender_ext")
MODULE = "bl_ext.%s.mpfb" % REPO
EYES_UUID = "2c12f43b-1303-432c-b7ce-d78346baf2e6"  # MakeHuman's high-poly eyes
TEXDIR = tempfile.mkdtemp(prefix="vbd_mh_tex_")


def available():
    if not os.path.isdir(os.path.join(REPO_DIR, "mpfb")):
        return False
    try:
        repos = bpy.context.preferences.extensions.repos
        if not any(r.module == REPO for r in repos):
            bpy.ops.preferences.extension_repo_add(name=REPO, type="LOCAL", use_custom_directory=True,
                                                   custom_directory=REPO_DIR)
            for r in repos:
                if r.name == REPO:
                    r.module = REPO
        bpy.ops.preferences.addon_enable(module=MODULE)
        importlib.import_module(MODULE)
        return True
    except Exception:
        return False


def hexc(h):
    return np.array([int(h[i:i + 2], 16) / 255.0 for i in (1, 3, 5)])


# --------------------------------------------------------------------------- textures
def base_color_image(mat):
    """The image feeding a material's base color (MakeSkin materials use an image node)."""
    if not mat or not mat.node_tree:
        return None, None
    for node in mat.node_tree.nodes:
        if node.type == "TEX_IMAGE" and node.image and any(
                l.to_socket.name in ("Base Color", "Color", "Diffuse") or "diffuse" in node.name.lower()
                for l in node.outputs["Color"].links):
            return node, node.image
    for node in mat.node_tree.nodes:  # fall back to the first image
        if node.type == "TEX_IMAGE" and node.image:
            return node, node.image
    return None, None


def colorize(mat, color_hex, keep=0.0, name=None):
    """Recolors a material's base color texture to `color_hex`, keeping its shading detail
    (folds, strands) from the original's brightness. keep = how much original color stays."""
    node, img = base_color_image(mat)
    target = hexc(color_hex)
    if img is None:
        bsdf = next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None) if mat and mat.node_tree else None
        if bsdf:
            lin = np.where(target <= 0.04045, target / 12.92, ((target + 0.055) / 1.055) ** 2.4)
            bsdf.inputs["Base Color"].default_value = (*lin, 1.0)
        return
    w, h = img.size
    px = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(px)
    px = px.reshape(h, w, 4)
    rgb, alpha = px[..., :3], px[..., 3:4]
    lum = rgb @ np.array([0.299, 0.587, 0.114])
    valid = alpha[..., 0] > 0.5
    mean = float(lum[valid].mean()) if valid.any() else float(lum.mean())
    rel = np.clip(lum / max(mean, 1e-3), 0, 2.5)[..., None]
    out = np.clip(target * rel * (1 - keep) + rgb * keep, 0, 1)
    new = bpy.data.images.new(name or (img.name + "_recolor"), w, h, alpha=True)
    new.pixels.foreach_set(np.concatenate([out, alpha], axis=2).astype(np.float32).ravel())
    path = os.path.join(TEXDIR, new.name + ".png")
    new.filepath_raw = path
    new.file_format = "PNG"
    new.save()
    node.image = new


# --------------------------------------------------------------------------- build
def build_base(model_id, stock_clothes=None):
    """Creates the MakeHuman character; returns (rig, basemesh)."""
    if not available():
        raise RuntimeError("MPFB isn't installed in Blender; run art/tools/makehuman_setup.py")
    HumanService = importlib.import_module(MODULE + ".services").HumanService

    d = hero_mh.get(model_id)
    ph = dict(d["phenotype"])
    ph.setdefault("cupsize", 0.5)
    ph.setdefault("firmness", 0.5)
    ph.setdefault("race", {"asian": 0.0, "caucasian": 1.0, "african": 0.0})
    info = {
        "name": model_id,
        "phenotype": ph,
        "targets": [{"target": k, "value": v} for k, v in d.get("targets", {}).items()],
        "rig": "mixamo",
        "eyes": "high-poly.mhclo",
        "eyebrows": d["eyebrows"] + ".mhclo",
        "eyelashes": d["eyelashes"] + ".mhclo",
        "tongue": "", "teeth": "", "proxy": "",
        "hair": (d["hair"] + ".mhclo") if d.get("hair") else "",
        "clothes": [c if c.endswith(".mhclo") else c + ".mhclo" for c in (stock_clothes or [])],
        "skin_mhmat": d["skin"] + ".mhmat",
        "skin_material_type": "MAKESKIN",
        "eyes_material_type": "MAKESKIN",
        "skin_material_settings": {}, "eyes_material_settings": {}, "expressions": [],
        "alternative_materials": {EYES_UUID: d.get("eyes", "brown") + ".mhmat"},
    }
    settings = HumanService.get_default_deserialization_settings()
    settings["subdiv_levels"] = 0
    settings["material_instances"] = "NEVER"
    basemesh = HumanService.deserialize_from_dict(info, settings)
    rig = basemesh.parent if basemesh.parent and basemesh.parent.type == "ARMATURE" else \
        next(o for o in bpy.data.objects if o.type == "ARMATURE")
    for o in bpy.data.objects:  # everything under the rig, so it moves and scales together
        if o.type == "MESH" and o.parent is None and o is not basemesh:
            o.parent = rig
    if d.get("hair"):
        hair = next((o for o in rig.children_recursive if o.type == "MESH" and d["hair"] in o.name.lower()), None)
        if hair:
            for slot in hair.material_slots:
                colorize(slot.material, d["hair_color"], keep=0.15, name="%s_hair" % model_id)
    return rig, basemesh


def finalize(rig, basemesh, model_id):
    """Bakes shape keys and applies helper masks so the meshes export as they look, then
    scales the hero to their real height (hero_assemble applies GAME_SCALE on export)."""
    meshes = [o for o in rig.children_recursive if o.type == "MESH"]

    def select_only(o):
        bpy.ops.object.select_all(action="DESELECT")
        bpy.context.view_layer.objects.active = o
        o.select_set(True)

    for o in meshes:
        if o.data.shape_keys:
            select_only(o)
            bpy.ops.object.shape_key_remove(all=True, apply_mix=True)
    # Measure the whole body now: once the masks are applied, skin under the clothes is gone
    # (with leggings and shoes, nothing below the hands is left to measure).
    bpy.context.view_layer.update()
    vg = basemesh.vertex_groups.get("body")
    mw = basemesh.matrix_world
    zs = [(mw @ v.co).z for v in basemesh.data.vertices
          if vg is None or any(g.group == vg.index and g.weight > 0.5 for g in v.groups)]
    height = max(zs) - min(zs)
    for o in meshes:
        select_only(o)
        for m in list(o.modifiers):
            if m.type == "ARMATURE":
                continue
            try:
                bpy.ops.object.modifier_apply(modifier=m.name)
            except RuntimeError:
                o.modifiers.remove(m)
    target = H.spec(model_id)["height"]
    if height > 1e-3:
        rig.scale = rig.scale * (target / height)
    bpy.context.view_layer.update()
    return height


def build(model_id, stock_clothes=None, look=None, log=print):
    rig, basemesh = build_base(model_id, stock_clothes=stock_clothes)
    if stock_clothes is None:
        import garments
        garments.dress(rig, basemesh, model_id, look=look)
    measured = finalize(rig, basemesh, model_id)
    log("  body measured %.3f m, scaled to %.2f m" % (measured, H.spec(model_id)["height"]))
    return rig
