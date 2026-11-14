"""
Builds every character with chibi.py and exports them for the game.

    blender --factory-startup -b -P art/tools/make_models.py -- [options]

Options (after --):
    --only a,b,c        just these ids (characters or arenas, e.g. cole,parking_lot)
    --characters-only   skip the arenas
    --arenas-only       skip the characters
    --no-export         don't write .glb files
    --no-blend          don't save the .blend lineups
    --render DIR        render preview PNGs of each character's poses into DIR
    --chibi-heroes      also export the detailed characters as chibis: the 6 base heroes,
                        2 forms and the detailed bosses and remixes (normally skipped:
                        their game models come from hero_assemble.py now)
    --log FILE          write progress here (Blender's console isn't always visible)

Writes:
    assets/models/heroes|bosses|minions/<id>.glb   characters the game loads
    assets/models/arenas/<id>.glb                   battle arenas (art/tools/arenas.py)
    art/characters.blend                            the base heroes, bosses and
                                                    minions in a lineup, to edit by hand
    art/arenas.blend                                all seven arenas side by side
"""

import os
import sys
import traceback

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import characters  # noqa: E402
import chibi  # noqa: E402

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


def clear_scene():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for coll in (bpy.data.meshes, bpy.data.armatures, bpy.data.actions, bpy.data.cameras, bpy.data.lights):
        for d in list(coll):
            coll.remove(d)


def remove_character(arm):
    actions = {s.action for t in (arm.animation_data.nla_tracks if arm.animation_data else []) for s in t.strips if s.action}
    for child in list(arm.children):
        mesh = child.data
        bpy.data.objects.remove(child, do_unlink=True)
        if mesh and mesh.users == 0:
            bpy.data.meshes.remove(mesh)
    data = arm.data
    bpy.data.objects.remove(arm, do_unlink=True)
    if data.users == 0:
        bpy.data.armatures.remove(data)
    for a in actions:
        if a:
            a.use_fake_user = False
            if a.users == 0:
                bpy.data.actions.remove(a)


def export(arm, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    bpy.ops.object.select_all(action="DESELECT")
    arm.select_set(True)
    for c in arm.children:
        c.select_set(True)
    bpy.context.view_layer.objects.active = arm
    opts = dict(
        filepath=path, export_format="GLB", use_selection=True, export_apply=False,
        export_animations=True, export_animation_mode="NLA_TRACKS", export_skins=True,
        export_yup=True, export_force_sampling=True, export_def_bones=False,
    )
    try:
        bpy.ops.export_scene.gltf(**opts)
    except TypeError:
        opts.pop("export_def_bones", None)
        bpy.ops.export_scene.gltf(**opts)


# --------------------------------------------------------------------- preview renders
POSES = [("idle", 0), ("walk", 6), ("attack", 11), ("cast", 12), ("hit", 3), ("faint", 30), ("victory", 8)]


def render_previews(arm, name, out_dir):
    """Renders the model in a few poses side by side (one PNG per pose)."""
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "MATERIAL"
    scene.render.resolution_x = 360
    scene.render.resolution_y = 420
    scene.render.film_transparent = False
    if not scene.camera:
        cam_data = bpy.data.cameras.new("preview_cam")
        cam = bpy.data.objects.new("preview_cam", cam_data)
        scene.collection.objects.link(cam)
        scene.camera = cam
    cam = scene.camera
    h = 1.4 * arm.scale[0]
    # Front three-quarter view (the character faces -Y).
    cam.location = (arm.location.x + 1.1 * h, arm.location.y - 1.6 * h, h * 0.85)
    direction = (arm.location.x - cam.location[0], arm.location.y - cam.location[1], h * 0.5 - cam.location[2])
    import mathutils
    cam.rotation_euler = mathutils.Vector(direction).to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = 50
    ad = arm.animation_data
    for anim, frame in POSES:
        for t in ad.nla_tracks:
            t.mute = t.name != anim
        scene.frame_set(frame)
        scene.render.filepath = os.path.join(out_dir, "%s_%s.png" % (name, anim))
        bpy.ops.render.render(write_still=True)
    for t in ad.nla_tracks:
        t.mute = False


# --------------------------------------------------------------------- main
def main():
    if LOG and os.path.exists(LOG):
        os.remove(LOG)
    only = set(arg("--only").split(",")) if arg("--only") else None
    do_export = not arg("--no-export")
    count = 0
    if not arg("--arenas-only"):
        count += build_characters(only, arg("--render"), do_export)
    if not arg("--characters-only"):
        count += build_arenas(only, do_export)
    log("DONE %d models" % count)


def export_static(obj, path):
    """A static model (arenas, the office, props). Its generated textures go in as WebP:
    Godot 4.7's glTF importer fails on JPEG, and WebP is far smaller than PNG."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    opts = dict(filepath=path, export_format="GLB", use_selection=True, export_apply=True,
                export_animations=False, export_yup=True, export_image_format="WEBP", export_image_quality=85)
    try:
        bpy.ops.export_scene.gltf(**opts)
    except TypeError:
        for k in ("export_image_format", "export_image_quality"):
            opts.pop(k, None)
        bpy.ops.export_scene.gltf(**opts)


def build_arenas(only, do_export):
    """Battle arenas (art/tools/arenas.py) -> assets/models/arenas/<id>.glb, plus
    art/arenas.blend with all of them side by side."""
    import arenas
    clear_scene()
    count = 0
    for i, aid in enumerate(list(arenas.ARENA_IDS) + list(arenas.EXTRA_IDS)):  # + the overworld and props
        if only and aid not in only:
            continue
        try:
            obj = arenas.build(aid)
            if do_export:
                folder = arenas.EXTRA_IDS.get(aid, "arenas")
                export_static(obj, os.path.join(ROOT, "assets", "models", folder, aid + ".glb"))
            count += 1
            log("built arenas/%s" % aid)
            if only:
                bpy.data.objects.remove(obj, do_unlink=True)
            else:
                obj.location.x = i * 45.0
        except Exception:
            log("FAILED arena %s:\n%s" % (aid, traceback.format_exc()))
    if not only and not arg("--no-blend"):
        path = os.path.join(ROOT, "art", "arenas.blend")
        bpy.ops.wm.save_as_mainfile(filepath=path, compress=True)
        log("saved %s" % path)
    return count


def detailed_ids():
    """Heroes, forms and bosses that now come from the detailed pipeline (hero_assemble.py)."""
    try:
        import hero_specs
        return set(hero_specs.all_ids()) | set(hero_specs.boss_ids()) | set(hero_specs.minion_ids())
    except Exception:
        bosses = ["trucker", "sales_guy", "guardian", "ghost", "copilot", "cashier", "grill_master", "sauce_keeper"]
        return {"mason", "james", "cole", "cam", "sam", "sarah", "cole_uw", "james_buff",
                "reply_all", "fish_guy", "loud_typer", "close_talker"} | set(bosses) | {b + "_remix" for b in bosses}


def build_characters(only, render_dir, do_export):
    clear_scene()
    lineup_x = {"heroes": 0.0, "bosses": 0.0, "minions": 0.0}
    lineup_y = {"heroes": 0.0, "bosses": 3.0, "minions": 6.0}
    count = 0
    detailed = detailed_ids()
    for folder, mid, spec, in_lineup in characters.all_models():
        if only and mid not in only:
            continue
        # Don't overwrite a detailed hero or boss with its chibi stand-in (unless asked with
        # --chibi-heroes); the chibi still goes in the lineup .blend.
        overwrite = mid not in detailed or bool(arg("--chibi-heroes"))
        try:
            arm = chibi.build(mid, spec)
            if do_export and overwrite:
                export(arm, os.path.join(ROOT, "assets", "models", folder, mid + ".glb"))
            if render_dir:
                render_previews(arm, mid, render_dir)
            count += 1
            log("built %s/%s" % (folder, mid))
            if in_lineup and not only:
                arm.location = (lineup_x[folder], lineup_y[folder], 0)
                lineup_x[folder] += 1.6 * arm.scale[0]
            else:
                remove_character(arm)
        except Exception:
            log("FAILED %s:\n%s" % (mid, traceback.format_exc()))
    if not only and not arg("--no-blend"):
        path = os.path.join(ROOT, "art", "characters.blend")
        bpy.ops.wm.save_as_mainfile(filepath=path, compress=True)
        log("saved %s" % path)
    return count


main()
