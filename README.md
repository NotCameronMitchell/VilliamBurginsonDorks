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

## Tests and balance

```
godot --headless --path . --script res://tests/run_tests.gd
```

Set `BALANCE=1` for a balance report: every 4-of-6 party, simulated by the AI. Add
`BALANCE_DETAIL=<hero id>` to see where that hero's damage comes from. Set
`BOSSES=1` for every boss against every party, at the original's enemy scaling.

## Code

- `scripts/core/battle.gd`: the deterministic turn-based combat engine. It records
  events that the battle scene plays back.
- `scripts/data/hero_data.gd`: the six heroes, their abilities and weapons
- `scripts/data/enemy_data.gd`: minions, the six bosses, their remixes and gimmicks
- `scripts/data/story.gd`: the run intro, burger joint lines, and each boss's lines
- `scripts/game/battle_ai.gd`: the AI used by tests and the Auto button

## Status

- [x] Design doc and boss designs
- [x] Project skeleton with a title screen and placeholder heroes
- [x] Combat engine and the 4 original heroes, ported from the original (with the balance changes)
- [x] Sam and Sarah, tuned with the simulator
- [x] The six new bosses and their remixes, with intro and defeat lines
- [ ] Battle scene and Pokemon-style HUD
- [ ] First Blender models (heroes)
- [ ] Overworld office map
- [ ] Achievements, skins, saves
