class_name SettingsRows
extends RefCounted
## Rows for the settings panels (battle Settings, the office pause menu). Kept apart from
## UITheme because these use the Game and Audio autoloads, which the headless tests
## don't load.


## A title and toggle buttons, one per [label, value]. Picking one saves Game.settings[key]
## and applies the volumes.
static func option_row(title: String, options: Array, key: String, default := 1.0) -> Control:
	var v := VBoxContainer.new()
	v.add_child(UITheme.label(title, 16, UITheme.DARK))
	var h := HBoxContainer.new()
	var group := ButtonGroup.new()
	for o in options:
		var b := Button.new()
		b.text = o[0]
		b.toggle_mode = true
		b.button_group = group
		b.custom_minimum_size = Vector2(90, 40)
		b.button_pressed = is_equal_approx(float(Game.settings.get(key, default)), o[1])
		b.pressed.connect(func():
			Game.settings[key] = o[1]
			Audio.apply_volumes()
			Game.save())
		h.add_child(b)
	v.add_child(h)
	return v


## The Music and Sounds rows.
static func sound_rows() -> Array[Control]:
	return [option_row("Music", [["On", 0.8], ["Quiet", 0.4], ["Off", 0.0]], "music_volume", 0.8),
		option_row("Sounds", [["On", 1.0], ["Quiet", 0.5], ["Off", 0.0]], "sfx_volume", 1.0)]
