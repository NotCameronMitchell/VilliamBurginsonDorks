extends Node3D
## Title / main menu: the heroes on a rotating battle platform (in their skins) and
## the menu: Continue, New run (Suit Up), Sauce Shop, Achievements, Hall of Fame.
## Placeholder shapes until the Blender models land in assets/models/.

var _pivot := Node3D.new()
var _menu: MenuPanels
var _buttons: VBoxContainer
var _stats: Label
var _confirm_new := false


func _ready() -> void:
	if not Game.test_fight.is_empty():
		Game.go_battle.call_deferred()
		return
	_build_world()
	_build_ui()
	if OS.get_cmdline_user_args().has("--continue") and not Game.run.is_empty():
		Game.continue_run.call_deferred()
	elif Game.auto_play:
		await get_tree().create_timer(1.0).timeout
		if not Game.run.is_empty():
			Game.continue_run()
		else:
			_start_run(Game.default_party())
	elif Game.open_menu != "":
		_open(Game.open_menu)


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
	cam.position = Vector3(1.6, 3.4, 8.6)
	cam.rotation_degrees = Vector3(-17, 0, 0)
	cam.fov = 45
	add_child(cam)
	_pivot.position = Vector3(-0.6, 0, 0)
	add_child(_pivot)
	_rebuild_heroes()


func _rebuild_heroes() -> void:
	for c in _pivot.get_children():
		c.queue_free()
	var plat := MeshInstance3D.new()
	var cyl := CylinderMesh.new()
	cyl.top_radius = 3.3
	cyl.bottom_radius = 3.4
	cyl.height = 0.2
	plat.mesh = cyl
	plat.material_override = _mat(Color("#c9e7a7"))
	_pivot.add_child(plat)
	var ids: Array = HeroData.HERO_IDS
	for i in ids.size():
		var id: String = ids[i]
		var spot := Node3D.new()
		var a := TAU * i / ids.size()
		spot.position = Vector3(sin(a) * 2.4, 0.1, cos(a) * 2.4)
		_pivot.add_child(spot)
		var o := Outfits.outfit_of(id, Game.meta.outfits)
		var v := UnitView.new()
		spot.add_child(v)
		v.setup_preview(id, Outfits.model_of(o))
		v.rotation.y = a + PI # face outward from the middle of the platform
		var tag := Label3D.new()
		tag.text = HeroData.HEROES[id].name
		tag.position.y = v.height + 0.25
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

	var title := UITheme.label("VILLIAM BURGINSON DORKS", 58, UITheme.ACCENT, 18)
	title.set_anchors_and_offsets_preset(Control.PRESET_CENTER_TOP)
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	title.offset_top = 24
	title.grow_horizontal = Control.GROW_DIRECTION_BOTH
	root.add_child(title)

	var panel := PanelContainer.new()
	panel.set_anchors_preset(Control.PRESET_CENTER_RIGHT)
	panel.offset_left = -400
	panel.offset_right = -36
	panel.offset_top = 30
	panel.offset_bottom = 30
	panel.grow_vertical = Control.GROW_DIRECTION_BOTH
	root.add_child(panel)
	_buttons = VBoxContainer.new()
	_buttons.add_theme_constant_override("separation", 10)
	panel.add_child(_buttons)

	_menu = MenuPanels.new()
	var top := CanvasLayer.new()
	top.layer = 3
	add_child(top)
	top.add_child(_menu)
	_menu.start_run.connect(_start_run)
	_menu.changed.connect(func():
		_rebuild_heroes()
		_build_buttons())
	_menu.closed.connect(_build_buttons)
	_build_buttons()


func _build_buttons() -> void:
	for c in _buttons.get_children():
		c.queue_free()
	_confirm_new = false
	if not Game.run.is_empty():
		var info := Run.current_stage(Game.run)
		_buttons.add_child(_menu_button("Continue run", "%s, stage %d" % [info.title, Game.run.stage + 1], UITheme.SUPPORT, func(): Game.continue_run()))
	var new_btn := _menu_button("New run" if not Game.run.is_empty() else "Start", "Pick your party and skins", UITheme.ACCENT, Callable())
	new_btn.pressed.connect(func():
		if not Game.run.is_empty() and not _confirm_new:
			_confirm_new = true
			new_btn.text = "Abandon current run?\nTap again to start fresh"
			return
		_open("suitup"))
	_buttons.add_child(new_btn)
	_buttons.add_child(_menu_button("Sauce Shop", "%d Village Sauce to spend" % Game.meta.sauce, Color("#ff9a1f"), func(): _open("shop")))
	_buttons.add_child(_menu_button("Achievements", "%d of %d unlocked" % [Game.meta.achievements.size(), Achievements.LIST.size()], Color("#c08aff"), func(): _open("achievements")))
	_buttons.add_child(_menu_button("Hall of Fame", "Best runs", Color("#6fd3ff"), func(): _open("hall")))


func _menu_button(text: String, sub: String, color: Color, cb: Callable) -> Button:
	var b := Button.new()
	b.text = "%s\n%s" % [text, sub]
	b.custom_minimum_size = Vector2(0, 74)
	b.add_theme_font_size_override("font_size", 20)
	b.add_theme_constant_override("line_spacing", -2)
	UITheme.tint_button(b, color, 8)
	if cb.is_valid():
		b.pressed.connect(cb)
	return b


func _open(which: String) -> void:
	match which:
		"suitup": _menu.open_suit_up()
		"shop": _menu.open_sauce_shop()
		"achievements": _menu.open_achievements()
		"hall": _menu.open_hall_of_fame()


func _start_run(party: Array) -> void:
	if party.size() != HeroData.PARTY_SIZE:
		return
	Game.new_run(party)
	Game.go_overworld()


func _process(delta: float) -> void:
	_pivot.rotation.y += delta * 0.3


func _mat(c: Color) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = c
	m.roughness = 0.8
	return m
