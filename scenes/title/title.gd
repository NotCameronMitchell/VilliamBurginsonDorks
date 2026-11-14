extends Node3D
## Title screen: the heroes on a rotating battle platform, a party picker (any 4 of
## the 6), and Continue / New Run. The full Suit Up screen (skins) comes later.
## Placeholder shapes until the Blender models land in assets/models/.

var _pivot := Node3D.new()
var _picked: Array = []
var _hero_buttons := {}
var _start: Button
var _note: Label
var _t := 0.0


func _ready() -> void:
	if not Game.test_fight.is_empty():
		Game.go_battle.call_deferred()
		return
	_picked = Game.default_party().duplicate()
	_build_world()
	_build_ui()
	if Game.auto_play:
		await get_tree().create_timer(1.0).timeout
		_on_start()


func _build_world() -> void:
	var env := WorldEnvironment.new()
	var e := Environment.new()
	e.background_mode = Environment.BG_COLOR
	e.background_color = Color("#8fd3ff")
	e.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	e.ambient_light_color = Color.WHITE
	e.ambient_light_energy = 0.6
	e.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	env.environment = e
	add_child(env)
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-50, -30, 0)
	sun.shadow_enabled = true
	add_child(sun)
	var cam := Camera3D.new()
	cam.position = Vector3(0, 3.0, 8.2)
	cam.rotation_degrees = Vector3(-14, 0, 0)
	cam.fov = 45
	add_child(cam)
	add_child(_pivot)
	var plat := MeshInstance3D.new()
	var cyl := CylinderMesh.new()
	cyl.top_radius = 3.4
	cyl.bottom_radius = 3.5
	cyl.height = 0.2
	plat.mesh = cyl
	plat.material_override = _mat(Color("#c9e7a7"))
	_pivot.add_child(plat)
	var ids: Array = HeroData.HERO_IDS
	for i in ids.size():
		var id: String = ids[i]
		var spot := Node3D.new()
		var a := TAU * i / ids.size()
		spot.position = Vector3(sin(a) * 2.5, 0.1, cos(a) * 2.5)
		_pivot.add_child(spot)
		var s := 0.8 if id == "sam" else (0.92 if id == "sarah" else 1.0)
		var body := MeshInstance3D.new()
		var cap := CapsuleMesh.new()
		cap.radius = 0.3 * s
		cap.height = 0.95 * s
		body.mesh = cap
		body.position.y = 0.5 * s
		body.material_override = _mat(Color(HeroData.HEROES[id].color))
		spot.add_child(body)
		var head := MeshInstance3D.new()
		var sph := SphereMesh.new()
		sph.radius = 0.24 * s
		sph.height = 0.48 * s
		head.mesh = sph
		head.position.y = 1.17 * s
		head.material_override = _mat(Color("#f1c7a5"))
		spot.add_child(head)
		var tag := Label3D.new()
		tag.text = HeroData.HEROES[id].name
		tag.position.y = 1.7 * s
		tag.billboard = BaseMaterial3D.BILLBOARD_ENABLED
		tag.font_size = 44
		tag.outline_size = 12
		spot.add_child(tag)


func _build_ui() -> void:
	var ui := CanvasLayer.new()
	add_child(ui)
	var root := Control.new()
	root.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	root.theme = UITheme.make()
	root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	ui.add_child(root)

	var title := UITheme.label("VILLIAM BURGINSON DORKS", 60, UITheme.ACCENT, 18)
	title.set_anchors_and_offsets_preset(Control.PRESET_CENTER_TOP)
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	title.offset_top = 28
	title.grow_horizontal = Control.GROW_DIRECTION_BOTH
	root.add_child(title)

	var panel := PanelContainer.new()
	panel.set_anchors_preset(Control.PRESET_CENTER_BOTTOM)
	panel.grow_horizontal = Control.GROW_DIRECTION_BOTH
	panel.grow_vertical = Control.GROW_DIRECTION_BEGIN
	panel.offset_bottom = -18
	root.add_child(panel)
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 8)
	panel.add_child(v)
	var hint := UITheme.label("Pick your party (4 of 6)", 20)
	hint.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	v.add_child(hint)
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 6)
	v.add_child(row)
	for id in HeroData.HERO_IDS:
		var b := Button.new()
		b.toggle_mode = true
		b.text = "%s\n%s" % [HeroData.HEROES[id].name, HeroData.HEROES[id].role]
		b.custom_minimum_size = Vector2(150, 64)
		b.add_theme_font_size_override("font_size", 17)
		b.button_pressed = _picked.has(id)
		b.toggled.connect(func(on): _toggle_hero(id, on))
		_hero_buttons[id] = b
		row.add_child(b)
	_note = UITheme.label("", 16, UITheme.MUTED)
	_note.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	v.add_child(_note)
	var actions := HBoxContainer.new()
	actions.alignment = BoxContainer.ALIGNMENT_CENTER
	actions.add_theme_constant_override("separation", 10)
	v.add_child(actions)
	if not Game.run.is_empty():
		var cont := Button.new()
		cont.text = "Continue run (stage %d)" % (Game.run.stage + 1)
		cont.custom_minimum_size = Vector2(300, 58)
		UITheme.tint_button(cont, UITheme.SUPPORT)
		cont.pressed.connect(func(): Game.go_battle())
		actions.add_child(cont)
	_start = Button.new()
	_start.text = "New run" if not Game.run.is_empty() else "Start"
	_start.custom_minimum_size = Vector2(240, 58)
	UITheme.tint_button(_start, UITheme.ACCENT)
	_start.pressed.connect(_on_start)
	actions.add_child(_start)
	var stats := UITheme.label("Village Sauce: %d   Runs: %d   Achievements: %d/%d" % [Game.meta.sauce, Game.meta.runs, Game.meta.achievements.size(), Achievements.LIST.size()], 15, UITheme.DARK)
	stats.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	v.add_child(stats)
	_sync()


func _toggle_hero(id: String, on: bool) -> void:
	if on and not _picked.has(id):
		if _picked.size() >= HeroData.PARTY_SIZE:
			_hero_buttons[id].set_pressed_no_signal(false)
			_note.text = "Party is full. Tap someone to swap them out."
			return
		_picked.append(id)
	elif not on:
		_picked.erase(id)
	_note.text = ""
	_sync()


func _sync() -> void:
	_start.disabled = _picked.size() != HeroData.PARTY_SIZE
	for id in _hero_buttons:
		UITheme.tint_button(_hero_buttons[id], Color(HeroData.HEROES[id].color) if _picked.has(id) else Color("#dddddd"))


func _on_start() -> void:
	if _picked.size() != HeroData.PARTY_SIZE:
		return
	Game.new_run(_picked)
	Game.go_battle()


func _process(delta: float) -> void:
	_t += delta
	_pivot.rotation.y += delta * 0.3


func _mat(c: Color) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = c
	m.roughness = 0.8
	return m
