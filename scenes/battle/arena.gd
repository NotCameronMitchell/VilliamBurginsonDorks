class_name Arena
extends Node3D
## The battle stage: the arena model (assets/models/arenas/<id>.glb, built in Blender
## by art/tools/arenas.py), its lighting and mood, and the two Pokemon-style battle
## platforms. Falls back to a few primitive props if an arena model is missing.

const HERO_CENTER := Vector3(-2.6, 0, 1.9)
const ENEMY_CENTER := Vector3(2.3, 0, -0.3)

## Hero spots: front row first (closer to the enemies), then back row. Spread in x
## so nobody hides behind anyone from the camera's angle.
const HERO_SPOTS := [Vector3(-1.4, 0, 1.1), Vector3(-3.3, 0, 0.9), Vector3(-2.2, 0, 2.7), Vector3(-4.1, 0, 2.5)]
## Enemy spots: the middle first (where a solo boss stands), then around it.
const ENEMY_SPOTS := [Vector3(2.3, 0, -0.3), Vector3(0.9, 0, 0.3), Vector3(3.7, 0, -0.8), Vector3(1.6, 0, -1.5), Vector3(3.2, 0, 0.9)]

## Per arena: sky / fog color, the floor color around the model, the sun
## [color, energy, pitch, yaw], ambient [color, energy], fog density, whether
## glowing things bloom, and the battle platforms [rim, top].
const LOOKS := {
	"office": {"label": "The Office", "sky": "#a9c9e8", "ground": "#55657e", "sun": ["#fff4e0", 0.95, -50, -35],
		"ambient": ["#e8eeff", 0.36], "fog": 0.0015, "glow": true, "platform": ["#c9cfdb", "#8b9bb8"]},
	"parking_lot": {"label": "Parking Lot", "sky": "#ffc98f", "ground": "#4a4d55", "sun": ["#ffd2a0", 1.25, -30, -60],
		"ambient": ["#ffe2c4", 0.42], "fog": 0.002, "glow": true, "platform": ["#f5f5f0", "#5b5e68"]},
	"desk_pods": {"label": "Desk Pods", "sky": "#b9d3f5", "ground": "#435a80", "sun": ["#ffffff", 0.95, -55, -30],
		"ambient": ["#e8eeff", 0.36], "fog": 0.0015, "glow": true, "platform": ["#c9d3e6", "#7f95bf"]},
	"meeting_room": {"label": "Meeting Room", "sky": "#262b45", "ground": "#454c72", "sun": ["#d6deff", 0.95, -60, -20],
		"ambient": ["#c4ceff", 0.5], "fog": 0.003, "glow": true, "platform": ["#a9b0cc", "#6a73a0"]},
	"office_center": {"label": "Middle of the Office", "sky": "#f5bfe0", "ground": "#6a5090", "sun": ["#ffe6f5", 0.95, -50, -40],
		"ambient": ["#ffe0f5", 0.38], "fog": 0.0015, "glow": true, "platform": ["#e5c9f5", "#9b78c4"]},
	"james_desk": {"label": "James's Old Desk", "sky": "#6f83a9", "ground": "#4f6286", "sun": ["#b8c8ff", 0.75, -55, -25],
		"ambient": ["#a8b8e8", 0.34], "fog": 0.008, "glow": true, "platform": ["#b9c3d6", "#7487a8"]},
	"villiam_burginson": {"label": "Villiam Burginson's", "sky": "#ffd66b", "ground": "#c0392b", "sun": ["#ffe0b0", 1.05, -50, -30],
		"ambient": ["#fff0d0", 0.42], "fog": 0.002, "glow": true, "platform": ["#ffd23f", "#f4f1e8"]},
}

var id := "office"


func build(arena_id: String) -> void:
	id = arena_id if LOOKS.has(arena_id) else "office"
	var look: Dictionary = LOOKS[id]
	var env := WorldEnvironment.new()
	var e := Environment.new()
	e.background_mode = Environment.BG_COLOR
	e.background_color = Color(look.sky)
	e.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	e.ambient_light_color = Color(look.ambient[0])
	e.ambient_light_energy = look.ambient[1]
	e.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	e.fog_enabled = true
	e.fog_light_color = Color(look.sky)
	e.fog_density = look.fog
	if look.glow:
		e.glow_enabled = true
		e.glow_intensity = 0.7
		e.glow_bloom = 0.05
		e.glow_hdr_threshold = 1.0
	env.environment = e
	add_child(env)

	var sun := DirectionalLight3D.new()
	sun.light_color = Color(look.sun[0])
	sun.light_energy = look.sun[1]
	sun.rotation_degrees = Vector3(look.sun[2], look.sun[3], 0)
	sun.shadow_enabled = true
	add_child(sun)

	var ground := MeshInstance3D.new()
	var plane := PlaneMesh.new()
	plane.size = Vector2(80, 80)
	ground.mesh = plane
	ground.material_override = _mat(Color(look.ground))
	ground.position.y = -0.03
	add_child(ground)

	_platform(HERO_CENTER, Vector2(3.4, 2.3), look.platform)
	_platform(ENEMY_CENTER, Vector2(3.6, 2.4), look.platform)

	var glb := "res://assets/models/arenas/%s.glb" % id
	if ResourceLoader.exists(glb):
		add_child((load(glb) as PackedScene).instantiate())
	else:
		_props()


func _mat(c: Color) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = c
	m.roughness = 0.9
	return m


func _box(size: Vector3, pos: Vector3, c: Color, rot_y := 0.0) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	var b := BoxMesh.new()
	b.size = size
	mi.mesh = b
	mi.material_override = _mat(c)
	mi.position = pos + Vector3(0, size.y / 2.0, 0)
	mi.rotation_degrees.y = rot_y
	add_child(mi)
	return mi


## A Pokemon-style oval battle platform: a rim and a raised top.
func _platform(center: Vector3, radii: Vector2, colors: Array) -> void:
	for layer in [[1.0, 0.05, colors[0]], [0.86, 0.065, colors[1]]]:
		var mi := MeshInstance3D.new()
		var c := CylinderMesh.new()
		c.top_radius = 1.0
		c.bottom_radius = 1.0
		c.height = layer[1]
		c.radial_segments = 48
		mi.mesh = c
		mi.material_override = _mat(Color(layer[2]))
		mi.scale = Vector3(radii.x * layer[0], 1, radii.y * layer[0])
		mi.position = center + Vector3(0, layer[1] / 2.0, 0)
		add_child(mi)


## Fallback scenery if an arena model hasn't been built.
func _props() -> void:
	match id:
		"parking_lot":
			for x in range(-12, 14, 4):
				_box(Vector3(0.15, 0.01, 3.0), Vector3(x, 0, -8), Color("#f1c40f"))
			_box(Vector3(2.6, 2.6, 6.5), Vector3(7.0, 0, -9.0), Color("#c0392b"), 15)
		"villiam_burginson":
			_box(Vector3(9.0, 1.2, 1.2), Vector3(2.0, 0, -9.0), Color("#f39c12"))
		_:
			for p in [Vector3(-7, 0, -9), Vector3(-3, 0, -10), Vector3(8, 0, -8)]:
				_box(Vector3(2.6, 1.0, 1.4), p, Color("#d7c4a3"))
