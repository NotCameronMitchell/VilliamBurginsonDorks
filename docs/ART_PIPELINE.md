# Art pipeline: Blender → Godot

## Detailed heroes (in progress)

The six heroes and their two ultimate forms are being remade as detailed, Pokemon Scarlet/
Violet-style models of the real people, with motion-captured movement. Every tool is free:

| Step | Tool | Where it runs | Output |
|---|---|---|---|
| 1. Concept art | Google Gemini (photo + prompt) | gemini.google.com | `art/heroes/<id>/concept_front.png` (+ `_back`, `_left`) |
| 2. 3D model | Tencent Hunyuan 3D (20 free a day) | 3d.hunyuanglobal.com | `art/heroes/<id>/model.glb` |
| 3. Motions | NVIDIA Kimodo (text to motion) | this PC's GPU | `art/heroes/motion/<hero>/<anim>.npz` |
| 4. Rig, animate, export | `hero_assemble.py` (Blender) | this PC | `assets/models/heroes/<id>.glb` |

The look and motion prompts live in `art/tools/hero_specs.py`.

**Photos:** the reference photos stay out of the repo, in `Pictures/Villiam Burginson Dorks/<id>.jpg`
(or `$env:VBD_PHOTOS`).

```
powershell -File art/tools/heroes.ps1 prompts               # each hero's Gemini prompts
powershell -File art/tools/heroes.ps1 motions [--only cole] # generate Kimodo motions
powershell -File art/tools/heroes.ps1 assemble [--only cole] [--render C:\temp\previews]
```

**1. Concept art.** In Gemini, attach the hero's photo and paste their prompt from
`heroes.ps1 prompts`. In the same chat, ask for the back and left views with the follow-up
prompts. Save the images as `concept_front.png`, `concept_back.png`, `concept_left.png`.

**2. Model.** In Hunyuan 3D, choose Image to 3D, add the views (front first), generate, and
download the GLB as `art/heroes/<id>/model.glb`. The pose must be the A-pose from the concept
art; the auto-rigger depends on it.

**3. Motions.** Kimodo runs locally (see "Kimodo setup" below). Each hero has a prompt per
animation in `hero_specs.py` (`HERO_MOTIONS`, plus `SHARED_MOTIONS` for walk, hit, stunned and
faint). The forms reuse their hero's motions. Change a prompt or its `seed`, then rerun
`motions`: only changed motions are regenerated.

**4. Assemble.** For each hero, `hero_assemble.py`:
1. Takes the model.
2. **Auto-rigs it:** finds the joints by slicing the mesh, builds a Mixamo-named skeleton, and
   skins it with Blender's automatic weights on a solid voxel copy.
3. **Retargets every Kimodo motion onto it:** loops the looping ones and cuts the walk to one
   clean step cycle.
4. **Exports the game model.** It's scaled by `GAME_SCALE` (0.8), so the cast stands about as
   tall as the old chibi models.

If a hero already has a rig (`rigged.glb` or `rigged.fbx`, for example from Mixamo), that rig
is used instead. Two checks need no model:
- `--mannequin` puts the motions on a jointed stand-in.
- `--test-body` runs the auto-rigger on a smooth test figure.

With `--render DIR`, it saves a contact sheet: a row per animation.

**Kimodo setup** (once per PC):
1. Clone https://github.com/nv-tlabs/kimodo to `%LOCALAPPDATA%\VilliamBurginsonDorks\kimodo`, or
   set `$env:KIMODO_HOME`.
2. Make a Python 3.11 venv in `.venv`.
3. Install PyTorch with CUDA (`--index-url https://download.pytorch.org/whl/cu128` for RTX 50
   cards).
4. Install Kimodo with `SKIP_MOTION_CORRECTION_IN_SETUP=1 pip install -e .`. This skips
   Kimodo's optional C++ foot-skate cleanup, which needs a compiler.
5. **Text encoder:** Kimodo reads prompts with Meta's Llama 3 8B, a gated model. Accept its
   license at huggingface.co/meta-llama/Meta-Llama-3-8B-Instruct, then run
   `.venv\Scripts\hf.exe auth login`. On an 8 GB GPU the encoder runs on the CPU (needs about
   16 GB of RAM).

**Paid alternative:** `art/tools/meshy.py` does steps 1, 2 and the rig through Meshy's API
(about 45 credits a hero). Set `MESHY_API_KEY`, then use `heroes.ps1 meshy plan`.

**Licenses and credits:** Kimodo is Apache-2.0; its SOMA weights are under the NVIDIA Open
Model License (commercial use allowed). The Llama 3 text encoder is under Meta's Llama 3
license. Hunyuan 3D and Gemini outputs fall under those services' terms. That's fine for a free
game; check them before selling it.

## Generated models (what's in the game now)

Every character (85 models) is built by a Python script running in Blender:

- **Heroes:** the 6 heroes, their 2 ultimate forms and every skin.
- **Bosses and remixes.**
- **Minions.**

Each model is a low-poly chibi on a shared 8-bone skeleton, with all the animations
the game plays.

```
powershell -File art/tools/run_blender.ps1                      # rebuild everything
powershell -File art/tools/run_blender.ps1 --only cole,trucker  # just these
powershell -File art/tools/run_blender.ps1 --only sam --no-export --render C:\temp\previews
```

`run_blender.ps1` finds Blender on PATH, in `$env:BLENDER`, or the Microsoft Store
install. The script itself is `art/tools/make_models.py`, and you can also run it with
`blender --factory-startup -b -P art/tools/make_models.py -- <options>`.

- **`art/tools/characters.py`:** every character's look as data (colors, hair,
  proportions, accessories, skins, remixes). Change a color or swap a hat here, then
  rebuild.
- **`art/tools/chibi.py`:** the builder: body parts, accessories, skeleton and
  animations.
- **`art/characters.blend`:** the base heroes, bosses and minions in a lineup, with
  every animation as an NLA track. Open it to look around, or to start a hand-made
  version of a character.

**Replacing a generated model with a hand-made one:**
1. Model and rig it in Blender (see below).
2. Export it to the same path, e.g. `assets/models/heroes/cole.glb`.
3. Add its id to `HAND_MADE` in `characters.py`, so the generator never overwrites it.

The game only needs the animation names below, and it turns glTF models to face the
right way on its own.

**Skeleton (generated models):** `root → hips → torso → head`, `torso → arm.L / arm.R`,
`hips → leg.L / leg.R`. Hand-made models can use any skeleton, as long as the action
names match.

## Battle arenas

The seven battle arenas are built the same way, by `art/tools/arenas.py`: the generic
office, the five boss areas and Villiam Burginson's.

- **Output:** `assets/models/arenas/<id>.glb`, plus `art/arenas.blend` with all seven
  side by side.
- **Look:** each arena is one low-poly mesh: a tiled floor, a back wall with windows,
  and the props. Highlights:
  - **Parking Lot:** the Trucker's semi.
  - **Desk Pods:** cubicle pods.
  - **Meeting Room:** the big screen and the glass wall.
  - **Middle of the Office:** the Guardian's speaker towers and DJ table.
  - **James's Old Desk:** his desk, golf bag and putting green.
  - **Villiam Burginson's:** the counter, kitchen, booths and the glowing Village
    Sauce.
- **Lighting and platforms:** the battle screen adds per-arena lighting, fog, glow
  and battle platforms (`LOOKS` in `scenes/battle/arena.gd`).

```
powershell -File art/tools/run_blender.ps1 --arenas-only                 # all arenas
powershell -File art/tools/run_blender.ps1 --arenas-only --only parking_lot
```

**Where scenery shows on screen:**
- **The fight:** layouts use game coordinates. Keep props out of x -6.5..6.5 for
  z > -3.5, where the platforms are.
- **The backdrop:** the band behind the enemies (x about -3..7, z -4..-11) is what
  shows best.
- **The edges:** far left and right are mostly covered by the name plates.
- **Replacing an arena:** export a hand-made `.glb` over the generated one.

## Folders

- `art/`: Blender source files (`.blend`). Godot ignores this folder (`art/.gdignore`).
- `assets/models/`: exported `.glb` files. This is what the game loads.
- `assets/textures/`: shared palette textures.

Both `.blend` and `.glb` go through **Git LFS** (see `.gitattributes`). Run
`git lfs install` once on each machine.

## Style

- **Low-poly chibi:** big heads (about 1/3 of total height), short limbs, readable
  silhouettes. Think Pokemon trainer models.
- **Budget:** heroes and bosses about 3-5k triangles, minions about 1.5k, props as low
  as possible.
- **Colors:** one shared 256×256 palette texture. UV each face onto a color square
  (gradient mapping), so every model shares one material and recolor skins are
  just a different palette image.
- Flat or soft shading, with no normal maps. Outlines come from a shader in Godot.

## Scale and orientation

- 1 Blender unit = 1 meter. Heroes are about 1.3 m tall (chibi), bosses 1.6-2.2 m.
- Facing **-Y** in Blender (front view), origin at the feet.
- Apply all transforms (Ctrl+A → All Transforms) before exporting.

## Rig and animations

- Every human character uses the **same base armature** (`art/rigs/base_humanoid.blend`),
  so animations and skins are shared.
- Name the actions exactly like this (the battle code plays them by name):

| Action | Used for |
|---|---|
| `idle` | Standing in battle (loop) |
| `walk` | Overworld (loop) |
| `attack` | Weapon attack |
| `cast` | Abilities and buffs |
| `hit` | Taking damage |
| `stunned` | Stun / skipped turn (loop) |
| `faint` | KO |
| `victory` | Winning a fight (loop) |
| `ultimate` | Ultimate cut-in |

- Bosses add their own actions as `skill_<id>` (for example `skill_air_horn`).

## Exporting

File → Export → glTF 2.0:

- Format: **glTF Binary (.glb)**
- Include: Selected Objects off, Custom Properties on
- Transform: +Y Up on
- Mesh: Apply Modifiers on
- Animation: on, with "Group by NLA Track" off and "Export all actions" on

Save to `assets/models/<group>/<name>.glb`, for example `assets/models/heroes/cole.glb`
or `assets/models/bosses/angry_trucker.glb`.

## Skins

- **Recolor skins:** a new palette PNG in `assets/textures/skins/<hero>_<skin>.png`.
  No new model.
- **New-outfit skins** (suit, burger uniform): a separate mesh in the hero's `.blend`,
  weighted to the same armature, exported as `assets/models/heroes/<hero>_<skin>.glb`.

## Model checklist

**Heroes:** Mason (plus cats Bruno and Murphy), James (plus a buff form), Cole (plus the
UW form with hair), Cam, Sam (the shortest model: about 0.9× hero height, plus the
booster seat), Sarah (plus knives and the Subaru for her ultimate)

**Bosses:** Angry Trucker (plus the semi truck prop), Mystery Sales Guy (coffee stirrer!),
Copilot Grim Reaper (plus laptop and scythe), Guardian of Tunes (plus the Boombox),
Ghost of James Civelli (translucent material), Villiam Burginson Crew (Cashier, Grill
Master, Sauce Keeper)

**Boss remixes** (each is the same model with a palette swap plus 1-2 accessory meshes
on the same rig):
- Night Shift Trucker: hi-vis vest, sunglasses
- Q4 Sales Guy: second stirrer, quarter-zip
- Copilot Pro Reaper: gold robe palette, second laptop
- Holiday Playlist Guardian: Santa hat, sweater palette, jingle speaker
- Golf Trip Ghost: visor, plaid palette, golf bag
- Late Night Crew: paper hats

**Minions:** Energy Drink, Tallboy, Nicotine Pouch, Pouch Tin, Reply-All Guy, Microwave
Fish Guy, Mechanical Keyboard Guy, Close Talker

**Arenas:** Parking Lot, Desk Pods, Meeting Room, Office Center, James's Old Desk,
Villiam Burginson's
