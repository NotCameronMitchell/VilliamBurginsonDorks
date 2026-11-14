"""
Makes the detailed heroes with the Meshy API: concept art, then a 3D model, then a rig.

    python art/tools/meshy.py balance
    python art/tools/meshy.py plan     [--only cole,sam]
    python art/tools/meshy.py concept  --only cole [--count 2] [--image-model nano-banana-pro] --yes
    python art/tools/meshy.py model    --only cole [--pick 2] --yes
    python art/tools/meshy.py rig      --only cole --yes
    python art/tools/meshy.py fetch    [--only cole]    finish and download anything still running

(art/tools/heroes.ps1 runs these with the right Python.)

- **Credits:** steps that spend credits print the cost and only run with --yes.
- **API key:** read from the MESHY_API_KEY environment variable (a Windows user variable
  works too). It's never printed or saved.
- **Reference photos** (optional, never committed): <photos>/<id>.jpg|jpeg|png|webp, where
  <photos> is $VBD_PHOTOS or "Pictures/Villiam Burginson Dorks" in your user folder. A hero
  with a photo gets concept art that looks like them.
- **Output:** everything Meshy returns is saved under art/heroes/<id>/, because Meshy deletes
  results after 3 days. Task ids go in art/heroes/<id>/meshy.json, so a rerun picks up where
  it left off.
"""

import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hero_specs as H  # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT = os.path.join(ROOT, "art", "heroes")
API = "https://api.meshy.ai/openapi"

# Credits per task (docs.meshy.ai/en/api/pricing). Tasks report what they really cost.
IMAGE_COST = {"nano-banana": 9, "nano-banana-pro": 9, "nano-banana-2": 6, "nano-banana-2-lite": 3,
              "nano-banana-2-1": 4}
MODEL_COST = 30   # Meshy 7.1, textured, 2K PBR
RIG_COST = 5

# The 3D model: game-ready size (heroes share the screen with up to 5 enemies on phones).
MODEL_SETTINGS = {
    "ai_model": "latest",
    "should_texture": True,
    "enable_pbr": True,
    "texture_resolution": "2k",
    "pose_mode": "a-pose",
    "should_remesh": True,
    "topology": "triangle",
    "target_polycount": 30000,
    "target_formats": ["glb"],
    "multi_view_thumbnails": True,
}
RIG_SETTINGS = {"skeleton_template": "mixamo", "include_fingers": True}


# --------------------------------------------------------------------------- basics
def die(msg):
    print("ERROR: " + msg)
    sys.exit(1)


def api_key():
    key = os.environ.get("MESHY_API_KEY", "")
    if not key and sys.platform == "win32":
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as reg:
                key = winreg.QueryValueEx(reg, "MESHY_API_KEY")[0]
        except OSError:
            pass
    key = key.strip()
    if not key:
        die("MESHY_API_KEY isn't set. Make a key at https://www.meshy.ai/developers/keys and save it "
            "as a user environment variable named MESHY_API_KEY.")
    return key


def call(method, path, body=None):
    """One Meshy API request. POSTs are only retried when Meshy says to slow down, so a
    flaky connection never creates (and charges for) a task twice."""
    data = json.dumps(body).encode("utf-8") if body is not None else None
    for attempt in range(6):
        req = urllib.request.Request(API + path, data=data, method=method, headers={
            "Authorization": "Bearer " + api_key(),
            "Content-Type": "application/json",
            "User-Agent": "vbd-hero-pipeline",
        })
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                raw = r.read()
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            text = e.read().decode("utf-8", "replace")[:600]
            if e.code == 429 or (method == "GET" and e.code >= 500):
                wait = int(e.headers.get("Retry-After") or 5 * (attempt + 1))
                print("  (Meshy is busy, retrying in %ds)" % wait)
                time.sleep(wait)
                continue
            if e.code == 402:
                die("Meshy says 402: not enough credits, or the plan doesn't include the API. " + text)
            die("Meshy said %d for %s %s: %s" % (e.code, method, path, text))
        except urllib.error.URLError as e:
            if method != "GET":
                die("Couldn't reach Meshy (%s). Nothing was created; try again." % e.reason)
            time.sleep(5 * (attempt + 1))
    die("Gave up on %s %s after several tries." % (method, path))


def download(url, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "vbd-hero-pipeline"})
    with urllib.request.urlopen(req, timeout=600) as r, open(path, "wb") as f:
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
    print("  saved %s (%.1f MB)" % (os.path.relpath(path, ROOT), os.path.getsize(path) / 1e6))


def data_uri(path):
    ext = os.path.splitext(path)[1].lower().lstrip(".")
    mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp",
            "glb": "model/gltf-binary"}[ext]
    with open(path, "rb") as f:
        return "data:%s;base64,%s" % (mime, base64.b64encode(f.read()).decode("ascii"))


def wait_task(kind, task_id, label, timeout=2400):
    t0 = time.time()
    last = None
    while True:
        t = call("GET", "/v1/%s/%s" % (kind, task_id))
        status, progress = t.get("status"), t.get("progress")
        if (status, progress) != last:
            print("  %s: %s %s%%" % (label, status, progress))
            last = (status, progress)
        if status == "SUCCEEDED":
            return t
        if status in ("FAILED", "CANCELED"):
            err = (t.get("task_error") or {}).get("message", "") if isinstance(t.get("task_error"), dict) else t.get("task_error")
            print("  %s %s: %s (failed tasks are refunded)" % (label, status.lower(), err))
            return t
        if time.time() - t0 > timeout:
            print("  %s is still running; run 'fetch' later to collect it." % label)
            return t
        time.sleep(6)


# --------------------------------------------------------------------------- state
def hero_dir(mid):
    return os.path.join(OUT, mid)


def load_state(mid):
    p = os.path.join(hero_dir(mid), "meshy.json")
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return {"concepts": [], "model": None, "rig": None}


def save_state(mid, state):
    os.makedirs(hero_dir(mid), exist_ok=True)
    with open(os.path.join(hero_dir(mid), "meshy.json"), "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def photos_dir():
    return os.environ.get("VBD_PHOTOS") or os.path.join(os.path.expanduser("~"), "Pictures", "Villiam Burginson Dorks")


def find_photo(mid):
    base = H.motion_owner(mid)  # a form uses its hero's photo
    for name in (mid, base):
        for ext in ("jpg", "jpeg", "png", "webp"):
            p = os.path.join(photos_dir(), "%s.%s" % (name, ext))
            if os.path.exists(p):
                return p
    return None


def still_alive(task):
    """Meshy keeps results for 3 days; a task id only works as an input until then."""
    exp = task.get("expires_at") or 0
    return exp and exp / 1000.0 > time.time() + 3600


def ids_from(args):
    ids = args.only.split(",") if args.only else H.all_ids()
    for i in ids:
        if i not in H.HEROES and i not in H.FORMS:
            die("Unknown hero '%s'. Known: %s" % (i, ", ".join(H.all_ids())))
    return ids


def confirm(args, what, credits):
    print("%s: about %d credits." % (what, credits))
    if not args.yes:
        print("Nothing was spent. Add --yes to go ahead.")
        sys.exit(0)


# --------------------------------------------------------------------------- steps
def concept_prompt(mid, photo):
    return H.concept_prompt(mid, bool(photo))


def run_concept(mid, args):
    state = load_state(mid)
    photo = find_photo(mid)
    body = {
        "ai_model": args.image_model,
        "prompt": concept_prompt(mid, photo),
        "generate_multi_view": True,
        "pose_mode": "a-pose",
    }
    kind = "text-to-image"
    if photo:
        kind = "image-to-image"
        body["reference_image_urls"] = [data_uri(photo)]
        print("  using the photo %s" % os.path.basename(photo))
    for _ in range(args.count):
        n = len(state["concepts"]) + 1
        task_id = call("POST", "/v1/" + kind, body)["result"]
        entry = {"n": n, "task": task_id, "kind": kind, "image_model": args.image_model,
                 "photo": bool(photo), "images": [], "status": "PENDING"}
        state["concepts"].append(entry)
        save_state(mid, state)
        finish_concept(mid, state, entry)


def finish_concept(mid, state, entry):
    t = wait_task(entry["kind"], entry["task"], "%s concept %d" % (mid, entry["n"]))
    entry["status"] = t.get("status")
    entry["credits"] = t.get("consumed_credits")
    entry["expires_at"] = t.get("expires_at")
    if t.get("status") == "SUCCEEDED":
        entry["images"] = []
        for i, url in enumerate(t.get("image_urls") or []):
            name = "concept_%d_%d.png" % (entry["n"], i)
            download(url, os.path.join(hero_dir(mid), name))
            entry["images"].append(name)
    save_state(mid, state)


def run_model(mid, args):
    state = load_state(mid)
    done = [c for c in state["concepts"] if c.get("status") == "SUCCEEDED" and c.get("images")]
    if not done:
        die("%s has no concept art yet. Run 'concept' first." % mid)
    if args.pick:
        picked = next((c for c in done if c["n"] == args.pick), None)
        if not picked:
            die("%s has no concept %d (has %s)." % (mid, args.pick, [c["n"] for c in done]))
    elif len(done) == 1:
        picked = done[0]
    else:
        die("%s has %d concepts; choose one with --pick N (%s)." % (mid, len(done), [c["n"] for c in done]))
    body = dict(MODEL_SETTINGS)
    body["target_polycount"] = args.polycount
    if still_alive(picked):
        body["input_task_id"] = picked["task"]
    else:
        body["image_urls"] = [data_uri(os.path.join(hero_dir(mid), n)) for n in picked["images"][:4]]
    kind = "multi-image-to-3d"
    task_id = call("POST", "/v1/" + kind, body)["result"]
    state["model"] = {"task": task_id, "kind": kind, "concept": picked["n"], "status": "PENDING",
                      "polycount": args.polycount}
    state["rig"] = None  # a new model needs a new rig
    save_state(mid, state)
    finish_model(mid, state)


def finish_model(mid, state):
    m = state["model"]
    t = wait_task(m["kind"], m["task"], "%s model" % mid)
    m["status"] = t.get("status")
    m["credits"] = t.get("consumed_credits")
    m["expires_at"] = t.get("expires_at")
    if t.get("status") == "SUCCEEDED":
        download(t["model_urls"]["glb"], os.path.join(hero_dir(mid), "model.glb"))
        for view, url in (t.get("thumbnail_urls") or {}).items():
            download(url, os.path.join(hero_dir(mid), "model_%s.png" % view))
        m["file"] = "model.glb"
    save_state(mid, state)


def run_rig(mid, args):
    state = load_state(mid)
    m = state.get("model")
    if not m or m.get("status") != "SUCCEEDED":
        die("%s has no finished 3D model yet. Run 'model' first." % mid)
    body = dict(RIG_SETTINGS)
    body["height_meters"] = H.spec(mid)["height"]
    if still_alive(m):
        body["input_task_id"] = m["task"]
    else:
        body["model_url"] = data_uri(os.path.join(hero_dir(mid), m["file"]))
    task_id = call("POST", "/v1/rigging", body)["result"]
    state["rig"] = {"task": task_id, "status": "PENDING", "height": body["height_meters"]}
    save_state(mid, state)
    finish_rig(mid, state)


def finish_rig(mid, state):
    r = state["rig"]
    t = wait_task("rigging", r["task"], "%s rig" % mid)
    r["status"] = t.get("status")
    r["credits"] = t.get("consumed_credits")
    r["expires_at"] = t.get("expires_at")
    if t.get("status") == "SUCCEEDED":
        res = t.get("result") or {}
        download(res["rigged_character_glb_url"], os.path.join(hero_dir(mid), "rigged.glb"))
        walk = (res.get("basic_animations") or {}).get("walking_glb_url")
        if walk:  # Meshy's own walk, kept as a fallback
            download(walk, os.path.join(hero_dir(mid), "meshy_walk.glb"))
        r["file"] = "rigged.glb"
    save_state(mid, state)


def run_fetch(mid, _args):
    state = load_state(mid)
    pending = False
    for c in state["concepts"]:
        if c.get("status") in ("PENDING", "IN_PROGRESS") or (c.get("status") == "SUCCEEDED" and not c.get("images")):
            pending = True
            finish_concept(mid, state, c)
    if state.get("model") and (state["model"].get("status") in ("PENDING", "IN_PROGRESS") or
                               (state["model"].get("status") == "SUCCEEDED" and not state["model"].get("file"))):
        pending = True
        finish_model(mid, state)
    if state.get("rig") and (state["rig"].get("status") in ("PENDING", "IN_PROGRESS") or
                             (state["rig"].get("status") == "SUCCEEDED" and not state["rig"].get("file"))):
        pending = True
        finish_rig(mid, state)
    if not pending:
        print("  %s: nothing running" % mid)


# --------------------------------------------------------------------------- commands
def cmd_plan(args):
    total = 0
    print("Photos folder: %s" % photos_dir())
    for mid in ids_from(args):
        s = load_state(mid)
        photo = find_photo(mid)
        concepts = [c for c in s["concepts"] if c.get("status") == "SUCCEEDED"]
        model_ok = s.get("model") and s["model"].get("status") == "SUCCEEDED"
        rig_ok = s.get("rig") and s["rig"].get("status") == "SUCCEEDED"
        todo = []
        cost = 0
        if not concepts:
            todo.append("concept x%d" % args.count)
            cost += args.count * IMAGE_COST.get(args.image_model, 9)
        if not model_ok:
            todo.append("model")
            cost += MODEL_COST
        if not rig_ok:
            todo.append("rig")
            cost += RIG_COST
        total += cost
        spent = sum((c.get("credits") or 0) for c in s["concepts"]) + \
            sum(((s.get(k) or {}).get("credits") or 0) for k in ("model", "rig"))
        print("%-11s photo: %-3s concepts: %d  model: %-3s rig: %-3s  to do: %-26s ~%3d credits (spent %d)" % (
            mid, "yes" if photo else "no", len(concepts), "yes" if model_ok else "no",
            "yes" if rig_ok else "no", ", ".join(todo) or "nothing", cost, spent))
    print("Total still to spend: about %d credits." % total)


def cmd_balance(_args):
    print("Meshy balance: %s credits" % call("GET", "/v1/balance").get("balance"))


def cmd_concept(args):
    ids = ids_from(args)
    confirm(args, "Concept art for %s (%d each, %s)" % (", ".join(ids), args.count, args.image_model),
            len(ids) * args.count * IMAGE_COST.get(args.image_model, 9))
    for mid in ids:
        run_concept(mid, args)
    cmd_balance(args)


def cmd_model(args):
    ids = ids_from(args)
    confirm(args, "3D models for %s" % ", ".join(ids), len(ids) * MODEL_COST)
    for mid in ids:
        run_model(mid, args)
    cmd_balance(args)


def cmd_rig(args):
    ids = ids_from(args)
    confirm(args, "Rigs for %s" % ", ".join(ids), len(ids) * RIG_COST)
    for mid in ids:
        run_rig(mid, args)
    cmd_balance(args)


def cmd_fetch(args):
    for mid in ids_from(args):
        run_fetch(mid, args)


def main():
    p = argparse.ArgumentParser(description="Detailed heroes with the Meshy API")
    p.add_argument("command", choices=["plan", "balance", "concept", "model", "rig", "fetch"])
    p.add_argument("--only", help="comma-separated hero/form ids (default: all)")
    p.add_argument("--count", type=int, default=2, help="concept: candidates per hero (default 2)")
    p.add_argument("--image-model", default="nano-banana-pro", help="concept: Meshy image model")
    p.add_argument("--pick", type=int, help="model: which concept to build (its number)")
    p.add_argument("--polycount", type=int, default=MODEL_SETTINGS["target_polycount"],
                   help="model: target triangles (default 30000)")
    p.add_argument("--yes", action="store_true", help="actually spend the credits")
    args = p.parse_args()
    {"plan": cmd_plan, "balance": cmd_balance, "concept": cmd_concept, "model": cmd_model,
     "rig": cmd_rig, "fetch": cmd_fetch}[args.command](args)


if __name__ == "__main__":
    main()
