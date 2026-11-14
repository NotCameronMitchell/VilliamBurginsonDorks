class_name Arena
extends Node3D
## The battle stage: sky, ground, the two Pokemon-style battle platforms, and a few
## props per location. Built from primitives until the Blender arenas exist
## (assets/models/arenas/<id>.glb replaces the props when present).

const HERO_CENTER := Vector3(-2.6, 0, 2.4)
const ENEMY_CENTER := Vector3(2.4, 0, -0.9)

## Hero spots: front row first (closer to the enemies), then back row. Spread in x
## so nobody hides behind anyone from the camera's angle.
const HERO_SPOTS := [Vector3(-1.4, 0, 1.6), Vector3(-3.3, 0, 1.4), Vector3(-2.2, 0, 3.2), Vector3(-4.1, 0, 3.0)]
## Enemy spots: the middle first (where a solo boss stands), then around it.
const ENEMY_SPOTS := [Vector3(2.4, 0, -0.9), Vector3(1.0, 0, -0.3), Vector3(3.8, 0, -1.4), Vector3(1.7, 0, -2.1), Vector3(3.3, 0, 0.3)]

const LOOKS := {
	"office": {"sky": "#bfe3ff", "ground": "#7d8fa6", "label": "The Office"},
	"parking_lot": {"sky": "#ffd7a8", "ground": "#4a4d55", "label": "Parking Lot"},
	"desk_pods": {"sky": "#d9e8ff", "ground": "#6f7f99", "label": "Desk Pods"},
	"meeting_room": {"sky": "#2a2f4a", "ground": "#5b5f7a", "label": "Meeting Room"},
	"office_center": {"sky": "#ffd1ec", "ground": "#8a7fa6", "label": "Middle of the Office"},
	"james_desk": {"sky": "#9fb3d9", "ground": "#6a7489", "label": "James's Old Desk"},
	"villiam_burginson": {"sky": "#ffe08a", "ground": "#c0392b", "label": "Villiam Burginson's"},
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
	e.ambient_light_color = Color.WHITE
	e.ambient_light_energy = 0.55
	e.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	e.fog_enabled = true
	e.fog_light_color = Color(look.sky)
	e.fog_density = 0.012
	env.environment = e
	add_child(env)

	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-55, -35, 0)
	sun.light_energy = 1.1
	sun.shadow_enabled = true
	add_child(sun)

	var ground := MeshInstance3D.new()
	var plane := PlaneMesh.new()
	plane.size = Vector2(60, 60)
	ground.mesh = plane
	ground.material_override = _mat(Color(look.ground))
	add_child(ground)

	_platform(HERO_CENTER, Vector2(3.4, 2.3))
	_platform(ENEMY_CENTER, Vector2(3.6, 2.4))

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


## A Pokemon-style oval battle platform with a rim.
func _platform(center: Vector3, radii: Vector2) -> void:
	for layer in [[1.0, 0.06, "#e9e2c7"], [0.86, 0.075, "#c9e7a7"]]:
		var mi := MeshInstance3D.new()
		var c := CylinderMesh.new()
		c.top_radius = 1.0
		c.bottom_radius = 1.0
		c.height = layer[1]
		mi.mesh = c
		mi.material_override = _mat(Color(layer[2]))
		mi.scale = Vector3(radii.x * layer[0], 1, radii.y * layer[0])
		mi.position = center + Vector3(0, layer[1] / 2.0, 0)
		add_child(mi)


func _props() -> void:
	match id:
		"parking_lot":
			for x in range(-12, 14, 4):
				_box(Vector3(0.15, 0.01, 3.0), Vector3(x, 0, -8), Color("#f1c40f"))
			_box(Vector3(2.6, 2.6, 6.5), Vector3(7.0, 0, -9.0), Color("#c0392b"), 15) # the semi
			_box(Vector3(2.4, 2.0, 2.2), Vector3(6.2, 0, -5.0), Color("#a93226"), 15)
		"desk_pods", "office":
			for p in [Vector3(-7, 0, -9), Vector3(-3, 0, -10), Vector3(8, 0, -8), Vector3(9, 0, -2)]:
				_box(Vector3(2.6, 1.0, 1.4), p, Color("#d7c4a3"))
				_box(Vector3(2.6, 1.5, 0.08), p + Vector3(0, 1.0, -0.7), Color("#95a5a6"))
		"meeting_room":
			_box(Vector3(6.0, 0.9, 2.2), Vector3(1.0, 0, -9.0), Color("#5d4037"))
			_box(Vector3(5.0, 2.8, 0.1), Vector3(1.0, 0.6, -12.0), Color("#ecf0f1")) # the screen
		"office_center":
			_box(Vector3(1.0, 2.2, 1.0), Vector3(6.5, 0, -7.0), Color("#2d2d2d")) # the speaker
			_box(Vector3(1.0, 2.2, 1.0), Vector3(-4.5, 0, -8.0), Color("#2d2d2d"))
		"james_desk":
			_box(Vector3(3.0, 1.0, 1.5), Vector3(5.8, 0, -6.0), Color("#8d6e63"))
			_box(Vector3(1.1, 0.7, 0.08), Vector3(5.8, 1.0, -6.3), Color("#1e272e"))
		"villiam_burginson":
			_box(Vector3(9.0, 1.2, 1.2), Vector3(2.0, 0, -9.0), Color("#f39c12")) # the counter
			_box(Vector3(9.0, 1.6, 0.1), Vector3(2.0, 2.4, -10.5), Color("#2c3e50")) # menu board
