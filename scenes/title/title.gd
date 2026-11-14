extends Node3D
## Title screen: the four heroes on Pokemon-style battle platforms.
## The capsules are placeholders until the Blender models land in assets/models/
## (see docs/ART_PIPELINE.md).

const HEROES := [
	{"name": "Mason", "color": Color("#ff4f6d")},
	{"name": "James", "color": Color("#ffd23f")},
	{"name": "Cole", "color": Color("#ff9a1f")},
	{"name": "Cam", "color": Color("#4fc3ff")},
]

var _pivot := Node3D.new()
var _prompt: Label
var _t := 0.0


func _ready() -> void:
	_build_world()
	_build_ui()


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
	cam.position = Vector3(0, 3.2, 7.5)
	cam.rotation_degrees = Vector3(-18, 0, 0)
	cam.fov = 45
	add_child(cam)

	add_child(_pivot)
	for i in HEROES.size():
		var spot := Node3D.new()
		var a := TAU * i / HEROES.size()
		spot.position = Vector3(sin(a) * 2.2, 0, cos(a) * 2.2)
		_pivot.add_child(spot)

		var plat := MeshInstance3D.new()
		var cyl := CylinderMesh.new()
		cyl.top_radius = 0.75
		cyl.bottom_radius = 0.8
		cyl.height = 0.15
		plat.mesh = cyl
		plat.material_override = _mat(Color("#e8f5c8"))
		spot.add_child(plat)

		var body := MeshInstance3D.new()
		var cap := CapsuleMesh.new()
		cap.radius = 0.35
		cap.height = 1.3
		body.mesh = cap
		body.position.y = 0.75
		body.material_override = _mat(HEROES[i].color)
		spot.add_child(body)

		var tag := Label3D.new()
		tag.text = HEROES[i].name
		tag.position.y = 1.75
		tag.billboard = BaseMaterial3D.BILLBOARD_ENABLED
		tag.font_size = 48
		tag.outline_size = 12
		spot.add_child(tag)


func _build_ui() -> void:
	var ui := CanvasLayer.new()
	add_child(ui)

	var title := Label.new()
	title.text = "VILLIAM BURGINSON DORKS"
	title.add_theme_font_size_override("font_size", 64)
	title.add_theme_color_override("font_color", Color("#ffd23f"))
	title.add_theme_color_override("font_outline_color", Color("#1a1a2e"))
	title.add_theme_constant_override("outline_size", 18)
	title.set_anchors_and_offsets_preset(Control.PRESET_CENTER_TOP)
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	title.offset_top = 40
	title.grow_horizontal = Control.GROW_DIRECTION_BOTH
	ui.add_child(title)

	_prompt = Label.new()
	_prompt.text = "Press Start  (Enter)"
	_prompt.add_theme_font_size_override("font_size", 32)
	_prompt.add_theme_color_override("font_outline_color", Color("#1a1a2e"))
	_prompt.add_theme_constant_override("outline_size", 10)
	_prompt.set_anchors_and_offsets_preset(Control.PRESET_CENTER_BOTTOM)
	_prompt.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_prompt.offset_top = -80
	_prompt.grow_horizontal = Control.GROW_DIRECTION_BOTH
	ui.add_child(_prompt)


func _process(delta: float) -> void:
	_t += delta
	_pivot.rotation.y += delta * 0.35
	_prompt.modulate.a = 0.55 + 0.45 * sin(_t * 3.0)


func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("ui_accept"):
		print("Start pressed: the Suit Up screen comes next.")


func _mat(c: Color) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = c
	m.roughness = 0.8
	return m
