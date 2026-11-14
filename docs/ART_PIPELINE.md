# Art pipeline: Blender → Godot

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
UW form with hair), Cam

**Bosses:** Angry Trucker (plus the semi truck prop), Mystery Sales Guy (coffee stirrer!),
Copilot Grim Reaper (plus laptop and scythe), Guardian of Tunes (plus the Boombox),
Ghost of James Civelli (translucent material), Villiam Burginson Crew (Cashier, Grill
Master, Sauce Keeper)

**Minions:** Energy Drink, Tallboy, Nicotine Pouch, Pouch Tin, Reply-All Guy, Microwave
Fish Guy, Mechanical Keyboard Guy, Close Talker

**Arenas:** Parking Lot, Desk Pods, Meeting Room, Office Center, James's Old Desk,
Villiam Burginson's
