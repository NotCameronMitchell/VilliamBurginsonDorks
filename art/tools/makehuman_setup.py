"""
One-time setup for MakeHuman in Blender (MPFB, the MakeHuman Plugin For Blender):

    blender -b -P art/tools/makehuman_setup.py -- --addon <add-on-mpfb-*.zip> [--assets <makehuman_system_assets_cc0.zip>] [--log FILE]

- **--addon:** installs the MPFB extension from its zip (extensions.blender.org/add-ons/mpfb).
- **--assets:** unpacks a MakeHuman asset pack (skins, eyes, hair, clothes; CC0) into MPFB's
  data folder. The system assets pack is at static.makehumancommunity.org (asset packs).

MPFB goes into its own extension repository in a short folder (~/.vbd/blender_ext):
some of its files have long names, and Blender's default extensions folder (inside the
Microsoft Store app's AppData) pushes them past Windows' 260-character path limit.

Safe to run again: it skips what's already done.
"""

import importlib
import os
import sys
import zipfile

import bpy

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
REPO = "vbd"
REPO_DIR = os.path.join(os.path.expanduser("~"), ".vbd", "blender_ext")
MODULE = "bl_ext.%s.mpfb" % REPO


def arg(name):
    return ARGS[ARGS.index(name) + 1] if name in ARGS else None


_print = print


def print(*a):  # noqa: A001 - also write to --log (the Store build's console isn't capturable)
    _print(*a)
    if arg("--log"):
        with open(arg("--log"), "a", encoding="utf-8") as f:
            f.write(" ".join(str(x) for x in a) + "\n")


def ensure_repo():
    """Registers the short-path extension repository (factory startup forgets it)."""
    os.makedirs(REPO_DIR, exist_ok=True)
    repos = bpy.context.preferences.extensions.repos
    if not any(r.module == REPO for r in repos):
        bpy.ops.preferences.extension_repo_add(name=REPO, type="LOCAL", use_custom_directory=True,
                                               custom_directory=REPO_DIR)
        for r in repos:  # the add operator names the module after the repo name
            if r.name == REPO:
                r.module = REPO


def enable_mpfb():
    ensure_repo()
    if not os.path.isdir(os.path.join(REPO_DIR, "mpfb")):
        return None
    try:
        bpy.ops.preferences.addon_enable(module=MODULE)
        return importlib.import_module(MODULE)
    except Exception as e:
        print("MPFB not enabled:", e)
        return None


def main():
    addon = arg("--addon")
    mpfb = enable_mpfb()
    if mpfb is None and addon:
        print("Installing MPFB from", addon, "into", REPO_DIR)
        bpy.ops.extensions.package_install_files(filepath=addon, repo=REPO, enable_on_install=True)
        mpfb = enable_mpfb()
    if mpfb is None:
        print("SETUP FAILED: MPFB isn't installed")
        return
    services = importlib.import_module(MODULE + ".services")
    data_dir = services.LocationService.get_user_data()
    print("MPFB module:", MODULE)
    print("MPFB user data:", data_dir)
    probe = os.path.join(REPO_DIR, "mpfb", "data", "targets", "macrodetails", "proportions",
                         "male-young-averagemuscle-averageweight-idealproportions.target.gz")
    print("long-name target present:", os.path.exists(probe))
    assets = arg("--assets")
    if assets:
        print("Unpacking", os.path.basename(assets), "into", data_dir)
        os.makedirs(data_dir, exist_ok=True)
        with zipfile.ZipFile(assets) as zf:
            zf.extractall(data_dir)
        services.AssetService.update_all_asset_lists()
    for sub in ("skins", "eyes", "eyebrows", "eyelashes", "hair", "clothes", "proxymeshes"):
        p = os.path.join(data_dir, sub)
        print("  %-12s %s" % (sub, len(os.listdir(p)) if os.path.isdir(p) else "-"))
    bpy.ops.wm.save_userpref()
    print("SETUP DONE")


main()
