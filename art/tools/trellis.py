"""
Builds a hero's 3D model from their front concept art with Microsoft's TRELLIS.2, using the
free demo on Hugging Face's ZeroGPU (about 3 models a day on a free account).

    python art/tools/trellis.py --only cole [--resolution 1024] [--faces 60000] [--texture 2048] [--seed 1]
    (or: powershell -File art/tools/heroes.ps1 trellis --only cole)

- **Input:** art/heroes/<id>/concept_front.png or .jpg (from Gemini; see hero_specs.py).
- **Output:** art/heroes/<id>/model.glb, plus trellis.json with the settings used.
  hero_assemble.py then auto-rigs and animates it.
- **Account:** uses your Hugging Face login if there is one (more free GPU time), otherwise
  the smaller anonymous allowance.
"""

import argparse
import json
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hero_specs as H  # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
SPACE = "microsoft/TRELLIS.2"


def concept_path(mid):
    for ext in ("png", "jpg", "jpeg", "webp"):
        p = os.path.join(ROOT, "art", "heroes", mid, "concept_front." + ext)
        if os.path.exists(p):
            return p
    return None


def as_path(result):
    """Gradio returns files as a path string or a {"path": ...} dict."""
    if isinstance(result, dict):
        return result.get("path") or result.get("value")
    return result


def build(mid, args):
    from gradio_client import Client, handle_file
    from huggingface_hub import get_token

    src = concept_path(mid)
    if not src:
        print("SKIP %s: no art/heroes/%s/concept_front.png|jpg yet" % (mid, mid))
        return False
    out = os.path.join(ROOT, "art", "heroes", mid, "model.glb")
    t0 = time.time()
    token = get_token()  # your Hugging Face login, for the account's free GPU time
    print("%s: sending %s to %s (%s)..." % (mid, os.path.basename(src), SPACE,
                                           "logged in" if token else "anonymous"))
    client = Client(SPACE, token=token, verbose=False, httpx_kwargs={"timeout": 600})
    client.predict(api_name="/start_session")
    pre = as_path(client.predict(handle_file(src), api_name="/preprocess_image"))
    client.predict(image=handle_file(pre), seed=args.seed, resolution=str(args.resolution),
                   api_name="/image_to_3d")
    print("  shape and texture done in %.0fs, exporting the GLB..." % (time.time() - t0))
    for attempt in range(3):  # the generated model stays on the server, so only retry the export
        try:
            glb, download = client.predict(decimation_target=args.faces, texture_size=args.texture,
                                           api_name="/extract_glb")
            break
        except Exception as e:
            if attempt == 2 or "minimum" in str(e) or "maximum" in str(e):
                raise
            print("  export failed (%s), retrying..." % e)
            time.sleep(10)
    path = as_path(download) or as_path(glb)
    shutil.copyfile(path, out)
    with open(os.path.join(ROOT, "art", "heroes", mid, "trellis.json"), "w", encoding="utf-8") as f:
        json.dump({"space": SPACE, "input": os.path.basename(src), "seed": args.seed,
                   "resolution": args.resolution, "faces": args.faces, "texture": args.texture,
                   "made": time.strftime("%Y-%m-%d %H:%M")}, f, indent=2)
    print("  saved %s (%.1f MB) in %.0fs" % (os.path.relpath(out, ROOT), os.path.getsize(out) / 1e6,
                                             time.time() - t0))
    return True


def main():
    p = argparse.ArgumentParser(description="Hero 3D models with TRELLIS.2 (Hugging Face)")
    p.add_argument("--only", required=True, help="comma-separated hero/form ids")
    p.add_argument("--resolution", type=int, default=1024, choices=[512, 1024, 1536])
    p.add_argument("--faces", type=int, default=100000,
                   help="triangles in the exported model (the Space's minimum is 100000; "
                        "hero_assemble.py slims it down for the game)")
    p.add_argument("--texture", type=int, default=2048, help="texture size in pixels")
    p.add_argument("--seed", type=int, default=1)
    args = p.parse_args()
    for mid in args.only.split(","):
        if mid not in H.HEROES and mid not in H.FORMS:
            sys.exit("Unknown hero '%s'" % mid)
        for attempt in range(2):
            try:
                build(mid, args)
                break
            except Exception as e:  # quota, queue and connection errors come back as exceptions
                msg = str(e)
                print("FAILED %s (try %d): %s" % (mid, attempt + 1, msg))
                # Only a dropped connection is worth another (GPU-costing) generation.
                if not any(w in msg for w in ("disconnected", "forcibly closed", "timed out", "Connection")):
                    break
                time.sleep(20)


if __name__ == "__main__":
    main()
