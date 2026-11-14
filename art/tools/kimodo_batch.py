"""
Generates every hero's motions with NVIDIA Kimodo (text to motion), from the prompts in
hero_specs.py. Run it with Kimodo's own Python (art/tools/heroes.ps1 motions does this):

    python art/tools/kimodo_batch.py [--only cole,sam] [--anims idle,attack] [--force]

- **Output:** art/heroes/motion/<hero>/<anim>.npz (Kimodo's format: joint rotations and
  positions at 30 fps on its SOMA skeleton), plus a .json with the prompt and seed.
  hero_assemble.py turns these into the heroes' animations.
- **Skips** motions whose prompt, length and seed haven't changed. --force redoes them.
- **Needs** a Hugging Face login with access to meta-llama/Meta-Llama-3-8B-Instruct
  (Kimodo's text encoder). The encoder runs on the CPU, because an 8 GB GPU can't hold
  it next to the motion model.
"""

import os

os.environ.setdefault("TEXT_ENCODER_MODE", "local")
os.environ.setdefault("TEXT_ENCODER_DEVICE", "cpu")

import argparse  # noqa: E402
import json  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402

import numpy as np  # noqa: E402
import torch  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hero_specs as H  # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
MOTION_DIR = os.path.join(ROOT, "art", "heroes", "motion")
MODEL = "Kimodo-SOMA-RP-v1.2"
STEPS = 100


def wanted(path, m):
    """True when the motion needs (re)generating."""
    meta_path = path[:-4] + ".json"
    if not (os.path.exists(path) and os.path.exists(meta_path)):
        return True
    with open(meta_path, encoding="utf-8") as f:
        meta = json.load(f)
    return any(meta.get(k) != m[k] for k in ("prompt", "seconds", "seed")) or meta.get("model") != MODEL


def main():
    p = argparse.ArgumentParser(description="Kimodo motions for the detailed heroes")
    p.add_argument("--only", help="comma-separated hero ids (forms use their hero's motions)")
    p.add_argument("--anims", help="comma-separated animation names (default: all)")
    p.add_argument("--force", action="store_true", help="regenerate even if unchanged")
    p.add_argument("--out", default=MOTION_DIR, help="output folder (default art/heroes/motion)")
    args = p.parse_args()

    heroes = args.only.split(",") if args.only else list(H.HEROES)
    heroes = list(dict.fromkeys(H.motion_owner(h) for h in heroes))
    anims = args.anims.split(",") if args.anims else H.ANIMS
    jobs = []
    for hero in heroes:
        if hero not in H.HEROES:
            sys.exit("Unknown hero '%s'" % hero)
        for anim, m in H.motions(hero).items():
            if anim not in anims:
                continue
            path = os.path.join(args.out, hero, anim + ".npz")
            if args.force or wanted(path, m):
                jobs.append((hero, anim, m, path))
    if not jobs:
        print("Every motion is up to date.")
        return

    from kimodo import load_model
    from kimodo.exports.motion_io import save_kimodo_npz
    from kimodo.tools import seed_everything

    device = "cuda:0" if torch.cuda.is_available() else "cpu"
    print("Loading %s on %s (text encoder on %s)..." % (MODEL, device, os.environ["TEXT_ENCODER_DEVICE"]))
    t0 = time.time()
    model = load_model(MODEL, device=device, default_family="Kimodo")
    print("Loaded in %.0fs. Generating %d motions." % (time.time() - t0, len(jobs)))

    for i, (hero, anim, m, path) in enumerate(jobs, 1):
        t1 = time.time()
        seed_everything(m["seed"])
        frames = int(round(m["seconds"] * model.fps))
        out = model(m["prompt"], frames, num_denoising_steps=STEPS, num_samples=1,
                    return_numpy=True, post_processing=False, progress_bar=lambda x: x)
        single = {}
        for k, v in out.items():
            v = np.asarray(v)
            single[k] = v[0] if v.ndim > 1 and v.shape[0] == 1 else v
        os.makedirs(os.path.dirname(path), exist_ok=True)
        save_kimodo_npz(path, single)
        with open(path[:-4] + ".json", "w", encoding="utf-8") as f:
            json.dump({"hero": hero, "anim": anim, "prompt": m["prompt"], "seconds": m["seconds"],
                       "seed": m["seed"], "model": MODEL, "frames": int(single["posed_joints"].shape[0]),
                       "joints": int(single["posed_joints"].shape[1]), "fps": model.fps}, f, indent=2)
        print("[%d/%d] %s/%s: %d frames in %.1fs" % (i, len(jobs), hero, anim,
                                                      single["posed_joints"].shape[0], time.time() - t1))
    print("Done.")


if __name__ == "__main__":
    main()
