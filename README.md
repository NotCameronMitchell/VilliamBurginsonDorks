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

## Status

- [x] Design doc and boss designs
- [x] Project skeleton with a title screen and placeholder heroes
- [ ] Port the combat engine and hero data from the original
- [ ] Battle scene and Pokemon-style HUD
- [ ] First Blender models (heroes)
- [ ] Overworld office map
- [ ] New bosses
- [ ] Achievements, skins, saves
