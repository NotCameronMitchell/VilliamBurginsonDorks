# Villiam Burginson Dorks

The 3D sequel to [The Quest for Villiam Burginson](https://github.com/NotCameronMitchell/FirstProj).
Four friends fight their way out of the office to get the Village Sauce. It's a
turn-based party battler with a Pokemon-style 3D look.

- **Engine:** Godot 4.7
- **Models:** Blender, exported as glTF

## Getting started

1. Install [Godot 4.7](https://godotengine.org/download) and [Blender](https://www.blender.org/download/).
2. Run `git lfs install` once (models and `.blend` files use Git LFS).
3. Open Godot → **Import** → select `project.godot` in this folder → press **F5** to run.

## Docs

- [Game design](docs/GAME_DESIGN.md): bosses, balance, UI, achievements and skins
- [Art pipeline](docs/ART_PIPELINE.md): how to build and export models from Blender

## Layout

```
art/           Blender source files (.blend), ignored by Godot
assets/        exported models, textures, audio
docs/          design docs
scenes/        Godot scenes (title, overworld, battle, ui)
scripts/       shared game code (combat engine, data, saves)
```

## Playing

Press **F5** in Godot (or run the project). The main menu has:

- **Start / New run:** opens **Suit Up**. Pick 4 of the 6 heroes and flip through
  each hero's skins with `<` `>`. Wear the ones you own, buy Sauce skins, and see
  which achievement unlocks the rest.
- **Sauce Shop:** spend Village Sauce on permanent upgrades.
- **Achievements:** all 22, with the skins each one unlocks.
- **Hall of Fame:** your best runs.

**In the office (overworld):**
- **Walk** with WASD / arrows, a gamepad, or the on-screen joystick (phones), or tap
  where to go.
- **Pick an open area.** Its coworker spots you at the door for a fight; then talk to
  the boss at the back of the room.
- **Talk** with E / Space / Enter, the on-screen button, or by tapping someone.
- **After three bosses**, take the elevator in the lobby down to Villiam Burginson's.

In battle:

- **Tap a move** to use it. Moves that hit one enemy then ask you to tap a target
  (on the stage or on its name plate).
- **Hover over a move** (PC) or **long-press it** (phone) to read what it does.
- **Hero tabs** let you act in any order. **Wait** skips a hero.
- **Auto** lets the AI play, **1x/2x** speeds up the animations, and **Settings**
  has the Copilot pop-up timer (Normal / Long / Off), text speed, music and sounds. The
  office's **Menu** has music and sounds too.

**Heroes** are detailed, realistic models of the real people, built in Blender with free
tools:
- **Bodies and faces:** MakeHuman builds the bodies, faces, hair and rig, through the MPFB
  add-on.
- **Clothes:** generated from each hero's own body, so a skin is just data.
- **Motion:** NVIDIA Kimodo makes motion-captured animations from text prompts.

Build them with `powershell -File art/tools/heroes.ps1 assemble --makehuman`. See "Detailed
heroes" in [docs/ART_PIPELINE.md](docs/ART_PIPELINE.md).

**Everything else** is low-poly 3D models built in Blender by
`art/tools/make_models.py`:
- **Characters:** hero skins, bosses, remixes and minions, with idle, attack, cast, hit,
  stunned, faint, victory and ultimate animations.
- **Arenas:** all seven battle arenas.

Rebuild them with `powershell -File art/tools/run_blender.ps1`.

**Music and sounds** are made in code too, by `art/audio/make_audio.py`:
- **Music:** five original chiptune loops (menu, office, battle, boss, burger joint) and
  the victory and game-over jingles.
- **Sounds:** 29 sound effects for hits, heals, status effects, UI clicks and the office.

Remake them with `powershell -File art/audio/make_audio.ps1`. See "Music and sounds" in
[docs/ART_PIPELINE.md](docs/ART_PIPELINE.md).

**Test flags** (after `--`):
- **Fights:** `--fight=<boss id|crew|minions>`, `--party=a,b,c,d`, `--remix`.
- **Playback:** `--auto` (the AI plays, including walking the office), `--skip-story`,
  `--speed=3`.
- **Playtests:** `--auto-click` makes auto-play press the after-fight screens with real
  mouse clicks, like a player. A button that can't be clicked gets the playtest stuck and
  logs an error. `--ult-first` makes every hero's ultimate ready on the first turn.
- **Saves and screens:** `--save-dir=user://test/` (a separate save profile),
  `--continue` (resume the saved run), `--touch` (show the joystick), and
  `--shots=<dir>` to save screenshots.
- **Sound:** `--mute` turns off music and sounds.

For example:

```
godot --path . -- --fight=copilot --party=sam,sarah,cole,cam
```

## Tests and balance

```
godot --headless --path . --script res://tests/run_tests.gd
```

Set `BALANCE=1` for a balance report: every 4-of-6 party, simulated by the AI. Add
`BALANCE_DETAIL=<hero id>` to see where that hero's damage comes from. Set
`BOSSES=1` for every boss against every party, at the original's enemy scaling.
Set `FULL_RUN=1` (optionally `RUNS=100`) to simulate whole runs at four levels of
Village Sauce upgrades. This is the main balance check.

## Code

- `scripts/core/battle.gd`: the deterministic turn-based combat engine. It records
  events that the battle scene plays back.
- `scripts/data/hero_data.gd`: the six heroes, their abilities and weapons
- `scripts/data/enemy_data.gd`: minions, the six bosses, their remixes and gimmicks
- `scripts/data/story.gd`: the run intro, burger joint lines, and each boss's lines
- `scripts/game/battle_ai.gd`: the AI used by tests and the Auto button
- `scripts/game/run.gd`: the run loop: stages, enemy scaling, rewards, drafts and the shop
- `scripts/game/save_game.gd`: saves (meta progress, run in progress, Hall of Fame)
- `scripts/data/`: also `run_events.gd`, `achievements.gd`, `outfits.gd`, `meta_upgrades.gd`
- `scripts/game/game_state.gd`: the `Game` autoload (saves, settings, scene changes, test flags)
- `scripts/game/audio.gd`: the `Audio` autoload (music crossfades, sound effects, volumes)
- `scenes/battle/`: the battle screen: `battle_scene.gd` replays the engine's events;
  `battle_hud.gd` and `unit_plate.gd` are the UI; `unit_view.gd` and `arena.gd` the 3D stage
- `scenes/run/run_overlay.gd`: loot, upgrade cards, shop and event panels
- `scenes/menu/menu_panels.gd`: Suit Up, Sauce Shop, Achievements and Hall of Fame
- `scenes/overworld/`: the office: `overworld.gd` (walking, followers, coworkers,
  bosses, talking), `office_map.gd` (rooms, walls, doors, props, paths),
  `overworld_hud.gd` (progress, party health, dialogue, joystick)
- `scripts/ui/ui_theme.gd`: colors, fonts and the panel/button style

## Status

- [x] Design doc and boss designs
- [x] Project skeleton with a title screen and placeholder heroes
- [x] Combat engine and the 4 original heroes, ported from the original (with the balance changes)
- [x] Sam and Sarah, tuned with the simulator
- [x] The six new bosses and their remixes, with intro and defeat lines
- [x] Run loop: stages, scaling, drafts, shop, events, achievements, skins, saves
- [x] Battle scene and Pokemon-style HUD (placeholder models), with the run loop playable
  from the title: party pick, fights, upgrade picks, shop, events, game over
- [x] Main menu: Suit Up (party and skins), Sauce Shop, Achievements, Hall of Fame
- [x] Blender models for every hero, skin, boss, remix and minion (generated, animated)
- [x] Battle arenas built in Blender (all seven), with per-arena lighting and a lower Pokemon-style battle camera
- [ ] Hand-polished models and arenas
- [x] Overworld office map: walk the office, pick the boss order, coworker line-of-sight fights, elevator to the burger joint
