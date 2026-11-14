# Art pipeline: Blender → Godot

## Detailed heroes

The six heroes and their two ultimate forms are realistic, Pokemon Scarlet/Violet-style
people, built in Blender with free tools. Bosses and minions are still the chibi models below.

| Step | Tool | Output |
|---|---|---|
| Body, face, hair, rig | MakeHuman, through MPFB 2 (a Blender add-on; CC0 assets) | built fresh each time |
| Clothes | `garments.py`, generated from each hero's own body | built fresh each time |
| Motions | NVIDIA Kimodo (text to motion) | `art/heroes/motion/<hero>/<anim>.npz` |
| Retarget and export | `hero_assemble.py` | `assets/models/heroes/<id>.glb` |

Each part lives in its own file:
- **Identity:** `art/tools/hero_mh.py` holds who each hero is: MakeHuman body and face sliders,
  skin, eye color, brows, lashes, hair and hair color. These were tuned by eye against each
  person's photo. The photos stay out of the repo, in `Pictures/Villiam Burginson Dorks/`.
- **Outfit:** `art/tools/hero_looks.py` holds what they wear: top, bottom, shoes, colors,
  prints, numbers, beard and accessories. A new skin is a new look entry.
- **Specs:** `art/tools/hero_specs.py` holds real heights, the Kimodo motion prompts and
  `GAME_SCALE` (0.95).

```
powershell -File art/tools/heroes.ps1 assemble --makehuman [--only cole] [--render C:\temp\previews]
powershell -File art/tools/heroes.ps1 assemble --makehuman --looks-only --render C:\temp\looks
powershell -File art/tools/heroes.ps1 motions [--only cole]
```
- `--looks-only` builds the models and renders a front view plus a face close-up of each, in
  about 4 seconds a hero. It runs no motions and writes no export.
- `--render` with a full build also saves a contact sheet, with a row per animation.
- `motions` runs Kimodo and needs its text encoder (see "Kimodo setup" below). It only remakes
  motions whose prompt, length or seed changed in `hero_specs.py`; `--force` remakes them all.
  Then run `assemble` again.

**One-time setup:** run `art/tools/makehuman_setup.py` in Blender
(`blender -b -P art/tools/makehuman_setup.py -- --log C:\temp\mh.log`). It installs MPFB into a
short-path extension repository, `~/.vbd/blender_ext`, because the Microsoft Store Blender's
AppData paths are longer than Windows' 260-character limit. It also unpacks MakeHuman's
system assets.

**How the clothes are made** (`garments.py`):
1. **Region:** a garment starts as a region of the body surface, picked by which bone each
   vertex follows.
2. **Shape:** the region is copied, smoothed, pushed outward and filled across hollows like
   fabric.
3. **Edges:** necklines, sleeves, hems and leg openings are cut cleanly, with planes or with a
   curved neckline that follows the neck. That neckline makes crew necks, V-necks and tank
   scoops. Necklines hug the neck.
4. **Bands:** collars, cuffs, hems and waistbands are bands laid along the cut edges.
5. **Rig and print:** the garment keeps the body's skin weights, so it moves with the rig. It
   also keeps the body's UVs, so prints and numbers land in the same spot on every hero.
6. **Hidden skin:** skin that a garment covers is removed, so nothing pokes through.
7. **Face and skin:** beards and stubble are painted into the hero's own copy of the skin
   texture, which is also tinted toward the look's skin color.
8. **Shoes and extras:** shoes are MakeHuman's, recolored. Caps, glasses, sunglasses and
   watches are built in code.

**Motions:** every animation is a Kimodo motion made from a text prompt in `hero_specs.py`.
- **Shared:** walk, hit, stunned and faint use the same prompt for everyone.
- **Per hero:** idle, attack, cast, victory and ultimate have their own prompts, such as Cole's
  golf-swing attack.
- **Forms:** the forms reuse their hero's motions.
- **Time:** the 54 motions take about 3 minutes on an RTX 5060, after the text encoder loads.
- **Fallback:** `art/tools/motion_keys.py` still writes keyframed stand-ins in the same format
  (`"model": "keyframed"` in their sidecar files), for a PC without Kimodo.

**Retargeting:** Kimodo poses its SOMA skeleton with world rotations relative to a T-pose.
For each motion:
- Each rig bone is turned to point the way its SOMA bone points, then gets that bone's
  rotation each frame.
- The hips get the root motion, scaled by leg length.
- Looping clips are crossfaded, and the walk is cut to one clean step cycle.

**Export:** textures are scaled down and saved as WebP. Godot 4.7's glTF importer failed on
JPEG textures, so WebP is used instead.
- Sizes: 1024 for skin and tops, 512 for hair and shoes, 256 for eyes, brows and lashes.
- Normal maps are dropped, and only hair, brows, lashes and eyes keep transparency.
- A hero is about 2–3 MB.

**Kimodo setup** (once per PC):
1. Clone https://github.com/nv-tlabs/kimodo to `%LOCALAPPDATA%\VilliamBurginsonDorks\kimodo`, or
   set `$env:KIMODO_HOME`.
2. Make a Python 3.11 venv in `.venv`.
3. Install PyTorch with CUDA (`--index-url https://download.pytorch.org/whl/cu128` for RTX 50
   cards).
4. Install Kimodo with `SKIP_MOTION_CORRECTION_IN_SETUP=1 pip install -e .`. This skips
   Kimodo's optional C++ foot-skate cleanup, which needs a compiler.
5. **Text encoder:** run `powershell -File art/tools/heroes.ps1 motions --fetch-encoder`. It
   downloads about 16 GB into `~/.vbd/text_encoders` (or `$env:TEXT_ENCODERS_DIR`):
   - Llama 3 8B Instruct, from the public copy `NousResearch/Meta-Llama-3-8B-Instruct`. Meta's
     own repository is gated. Meta's Llama 3 license applies either way.
   - McGill-NLP's two LLM2Vec adapters.

   `kimodo_batch.py` finds the folder by itself. On an 8 GB GPU the encoder runs on the CPU,
   which needs about 16 GB of RAM. Loading it takes about 20 seconds.

**Earlier routes (kept, not used):**
- `hero_builder.py` builds procedural bodies (`--procedural`).
- `trellis.py` and `meshy.py` are AI image-to-3D clients. `meshy.py` is the paid one.
- The auto-rigger (`assemble` without `--makehuman`) rigs any `art/heroes/<id>/model.glb`.

**Licenses:**
- MakeHuman's system assets are CC0.
- MPFB is GPL. It's a tool only and isn't shipped with the game.
- Kimodo is Apache-2.0. Its SOMA weights are under the NVIDIA Open Model License, which allows
  commercial use.
- The Llama 3 text encoder is under Meta's Llama 3 license.

## Generated models (what's in the game now)

Every character (85 models) is built by a Python script running in Blender:

- **Hero skins.** The 6 base heroes and 2 forms are the detailed models above, so a full
  rebuild skips them unless you pass `--chibi-heroes`.
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

Every skin in `scripts/data/outfits.gd` is a detailed hero in a different outfit, built from
data. A skin is an entry in `SKINS` in `art/tools/hero_looks.py`: which hero it is, and what
changes from their usual look. Party-wide skins (headphones, burger, golden, casual, holiday)
are generated for every hero from `PARTY`. Build them with:

```
powershell -File art/tools/heroes.ps1 assemble --makehuman --skins all
powershell -File art/tools/heroes.ps1 assemble --makehuman --skins mason_suit,cam_kith --looks-only --render C:\temp\skins
```

Each skin is written to `assets/models/heroes/<skin id>.glb`, the model key the game
already looks for. Recolor skins (`mason~mason_home`) also find `<palette>.glb` first.

What the outfit generator knows:
- **Top types:** `tee`, `jersey` (V-neck, trims, number), `buttonup` (collar), `polo`,
  `sweatshirt`, `sweater`, `hoodie` (hood, drawstrings, pocket), `quarterzip` (stand collar,
  zipper), `jacket` (deep V, lapels, buttons), `vest`, `tank` and `dress`.
- **Layers:** `"under"` puts a second top beneath, such as a shirt and tie under a jacket or a
  tee under a hi-vis vest.
- **Prints and patterns:**
  - `number` (with `number_color`)
  - `print: cyber`
  - `text` in block capitals, optionally in a `text_box`
  - `tie`
  - `pattern`, one of `dots`, `stripes`, `holiday`, `sash` or `reflective`
  - `material: gold`
- **Bottoms:** `pants`, `joggers`, `shorts`, `leggings` and `skirt`.
- **Accessories (`acc`):**
  - `cap` (with `"cap": {"color", "front"}` for a trucker cap), `glasses`, `sunglasses`
    and `watch`
  - `headphones`, `witch_hat`, `paper_hat`, `crown`, `cape`, `lanyard`, `belt` and
    `stirrer` (`art/tools/accessories.py`)
- **Ghost:** `"ghost": True` makes everything pale, glowing and see-through.

## Trailer

`art/trailer/` makes the game's cinematic trailer in Blender: a frozen office at night and
the Ghost of James Civelli on a throne of office chairs. Then the heroes, the game's own
models, clock in to fight him. All lines are original.

```
powershell -File art/trailer/make_trailer.ps1                      # everything, to Videos\VilliamBurginsonDorks_trailer
powershell -File art/trailer/make_trailer.ps1 -Res 1920x1080        # sharper (slower)
powershell -File art/trailer/make_trailer.ps1 -Step stills          # one still per shot, to check
```

- **`timeline.py`:** the shot list, narration, on-screen text and the music's hits.
- **`voice.py`:** speaks the narration with Kokoro, an open-source text-to-speech model
  (Apache-2.0) that runs on the CPU through kokoro-onnx. The voice is `bm_george`; pick
  another with `-Voice`, or blend voices with `"bm_george:0.7,am_fenrir:0.3"`. Without Kokoro,
  Windows' built-in voice is used.
- **`music.py`:** synthesizes the soundtrack (drones, choir, music box, strings, taiko,
  brass, risers) and mixes in the narration.

**Kokoro setup** (once per PC):
1. Make a venv in `~\.vbd\kokoro\.venv` (or set `$env:KOKORO_HOME`).
2. Run `pip install kokoro-onnx soundfile` in it.
3. Put `kokoro-v1.0.onnx` and `voices-v1.0.bin` in `~\.vbd\kokoro\models\`. Both are in the
   `model-files-v1.0` release of github.com/thewh1teagle/kokoro-onnx.
- **`trailer.py`:** builds the set and the ghost, and animates the heroes with their game
  animations. It renders the frames, then cuts in the titles, subtitles, fades and sound
  with Blender's video editor.

## Music and sounds

`art/audio/make_audio.py` writes all of the game's audio from code, with numpy and scipy,
so it can be changed and remade like the models. Every piece is original.

```
powershell -File art/audio/make_audio.ps1                 # everything
powershell -File art/audio/make_audio.ps1 --only boss,hit  # just these
```

| Track | Plays | Style |
|---|---|---|
| `title` | main menu | bouncy, heroic chiptune, C major, 128 BPM |
| `office` | the office | swing elevator jazz: vibraphone, electric piano, walking bass |
| `battle` | coworker fights | driving chiptune, A minor, 150 BPM |
| `boss` | boss fights | heavier: saw lead, gritty bass, brass stabs, D minor, 160 BPM |
| `final` | Villiam Burginson's | the menu tune as a minor-key anthem, with organ and brass |
| `victory`, `gameover` | after a fight | a fanfare, and a sad trombone |

- **Loops:** each loop is a whole number of bars. Anything still ringing at the end
  (reverb, held notes) is folded back to the start, so the loop point is seamless.
- **Music files:** OGG Vorbis in `assets/audio/music/`, encoded by Blender
  (`art/audio/to_ogg.py`), so no extra tools are needed.
- **Sounds:** 29 mono WAVs in `assets/audio/sfx/`: hits, crits, heals, buffs, debuffs,
  shields, stuns, poison and burn, ultimates, faints, UI clicks, dialogue blips, the "!"
  alert, the elevator ding and more.
- **In the game:** the `Audio` autoload (`scripts/game/audio.gd`) plays them.
  `play_music(track)` crossfades, and `sfx(name)` plays from a pool with a little pitch
  variety. Buttons click by themselves.
- **Adding a sound:** add a function and a `SFX` entry in `make_audio.py`, then call
  `Audio.sfx("name")`. `tests/run_tests.gd` checks that every sound the code plays exists.

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
