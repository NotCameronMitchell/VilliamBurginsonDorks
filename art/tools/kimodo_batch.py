"""
Generates every hero's motions with NVIDIA Kimodo (text to motion), from the prompts in
hero_specs.py. Run it with Kimodo's own Python (art/tools/heroes.ps1 motions does this):

    python art/tools/kimodo_batch.py [--only cole,sam] [--anims idle,attack] [--force]
    python art/tools/kimodo_batch.py --fetch-encoder     (once: downloads the text encoder)

- **Output:** art/heroes/motion/<hero>/<anim>.npz (Kimodo's format: joint rotations and
  positions at 30 fps on its SOMA skeleton), plus a .json with the prompt and seed.
  hero_assemble.py turns these into the heroes' animations.
- **Skips** motions whose prompt, length and seed haven't changed. --force redoes them.
- **Text encoder:** Kimodo reads prompts with LLM2Vec on Meta's Llama 3 8B Instruct. It
  runs on the CPU, because an 8 GB GPU can't hold it next to the motion model. Either:
  - a local folder ($env:TEXT_ENCODERS_DIR, default ~/.vbd/text_encoders). --fetch-encoder
    fills it (about 16 GB): the Llama weights from the public copy
    NousResearch/Meta-Llama-3-8B-Instruct (Meta's Llama 3 license still applies), saved as
    meta-llama/Meta-Llama-3-8B-Instruct, plus McGill-NLP's two LLM2Vec adapters. The mntp
    adapter is pointed at the local weights automatically. Or:
  - a Hugging Face login with access to the gated meta-llama/Meta-Llama-3-8B-Instruct.
"""

import json as _json
import os

os.environ.setdefault("TEXT_ENCODER_MODE", "local")
os.environ.setdefault("TEXT_ENCODER_DEVICE", "cpu")
_TE = os.environ.get("TEXT_ENCODERS_DIR") or os.path.join(os.path.expanduser("~"), ".vbd", "text_encoders")
_BASE = os.path.join(_TE, "meta-llama", "Meta-Llama-3-8B-Instruct")
_MNTP = os.path.join(_TE, "McGill-NLP", "LLM2Vec-Meta-Llama-3-8B-Instruct-mntp")
ENCODER_REPOS = (  # (Hugging Face repo, folder under the text encoder folder)
    ("McGill-NLP/LLM2Vec-Meta-Llama-3-8B-Instruct-mntp", "McGill-NLP/LLM2Vec-Meta-Llama-3-8B-Instruct-mntp"),
    ("McGill-NLP/LLM2Vec-Meta-Llama-3-8B-Instruct-mntp-supervised",
     "McGill-NLP/LLM2Vec-Meta-Llama-3-8B-Instruct-mntp-supervised"),
    ("NousResearch/Meta-Llama-3-8B-Instruct", "meta-llama/Meta-Llama-3-8B-Instruct"),
)


def local_encoder():
    """Use the local text encoder folder if it's there. True when it is."""
    if not (os.path.isfile(os.path.join(_BASE, "config.json")) and os.path.isdir(_MNTP)):
        return False
    os.environ["TEXT_ENCODERS_DIR"] = _TE
    cfg_path = os.path.join(_MNTP, "adapter_config.json")
    with open(cfg_path, encoding="utf-8") as f:
        cfg = _json.load(f)
    if cfg.get("base_model_name_or_path") != _BASE:  # load the base weights from the local folder
        cfg["base_model_name_or_path"] = _BASE
        with open(cfg_path, "w", encoding="utf-8") as f:
            _json.dump(cfg, f, indent=2)
    return True


def fetch_encoder():
    """Download the text encoder into the local folder (about 16 GB)."""
    from huggingface_hub import snapshot_download
    for repo, dest in ENCODER_REPOS:
        print("Downloading %s ..." % repo, flush=True)
        snapshot_download(repo, local_dir=os.path.join(_TE, dest), max_workers=8)
    print("Text encoder ready in %s" % _TE if local_encoder() else "Download incomplete: run it again.")


local_encoder()

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
    p.add_argument("--fetch-encoder", action="store_true",
                   help="download the text encoder (about 16 GB) and stop")
    args = p.parse_args()
    if args.fetch_encoder:
        fetch_encoder()
        return

    heroes = args.only.split(",") if args.only else list(H.HEROES) + list(H.BOSSES) + list(H.MINIONS)
    heroes = list(dict.fromkeys(H.motion_owner(h) for h in heroes))
    anims = args.anims.split(",") if args.anims else H.ANIMS
    jobs = []
    for hero in heroes:
        if hero not in H.HEROES and hero not in H.BOSSES and hero not in H.MINIONS:
            sys.exit("Unknown hero, boss or minion '%s'" % hero)
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

    made = {}  # (prompt, seconds, seed) -> a file made this run: shared motions are made once
    for i, (hero, anim, m, path) in enumerate(jobs, 1):
        t1 = time.time()
        same = made.get((m["prompt"], m["seconds"], m["seed"]))
        if same:
            import shutil
            os.makedirs(os.path.dirname(path), exist_ok=True)
            shutil.copyfile(same, path)
            with open(same[:-4] + ".json", encoding="utf-8") as f:
                meta = json.load(f)
            meta.update({"hero": hero, "anim": anim})
            with open(path[:-4] + ".json", "w", encoding="utf-8") as f:
                json.dump(meta, f, indent=2)
            print("[%d/%d] %s/%s: same as %s" % (i, len(jobs), hero, anim, os.path.relpath(same, args.out)))
            continue
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
        made[(m["prompt"], m["seconds"], m["seed"])] = path
        print("[%d/%d] %s/%s: %d frames in %.1fs" % (i, len(jobs), hero, anim,
                                                      single["posed_joints"].shape[0], time.time() - t1),
              flush=True)
    print("Done.")


if __name__ == "__main__":
    main()
