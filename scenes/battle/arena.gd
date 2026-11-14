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
## glowing things bloom, and the battle platforms [rim, top]. Optional: "sky_top" (the
## sky's color overhead; the horizon is "sky"), "rim" (the back light's color) and
## "lights": colored pools of light by the glowing props, [x, y, z, color, energy, range].
const LOOKS := {
	"office": {"label": "The Office", "sky": "#a9c9e8", "sky_top": "#4f86cf", "ground": "#55657e", "sun": ["#fff4e0", 0.95, -50, -35],
		"ambient": ["#e8eeff", 0.36], "fog": 0.0015, "glow": true, "platform": ["#c9cfdb", "#8b9bb8"]},
	"parking_lot": {"label": "Parking Lot", "sky": "#ffc98f", "sky_top": "#6d83d0", "ground": "#4a4d55", "sun": ["#ffd2a0", 1.25, -30, -60],
		"ambient": ["#ffe2c4", 0.42], "fog": 0.002, "glow": true, "platform": ["#f5f5f0", "#5b5e68"], "rim": "#ffd9b8",
		"lights": [[-4.4, 3.7, -4.6, "#ffd59a", 2.0, 8.0]]},
	"desk_pods": {"label": "Desk Pods", "sky": "#b9d3f5", "sky_top": "#5b8fdb", "ground": "#435a80", "sun": ["#ffffff", 0.95, -55, -30],
		"ambient": ["#e8eeff", 0.36], "fog": 0.0015, "glow": true, "platform": ["#c9d3e6", "#7f95bf"]},
	"meeting_room": {"label": "Meeting Room", "sky": "#262b45", "sky_top": "#0d1024", "ground": "#454c72", "sun": ["#d6deff", 0.95, -60, -20],
		"ambient": ["#c4ceff", 0.5], "fog": 0.003, "glow": true, "platform": ["#a9b0cc", "#6a73a0"], "rim": "#9fb4ff",
		"lights": [[2.4, 1.8, -8.2, "#6fb0ff", 2.2, 7.5], [2.4, 1.0, -7.0, "#7fd4ff", 0.8, 3.5]]},
	"office_center": {"label": "Middle of the Office", "sky": "#f5bfe0", "sky_top": "#b57fd6", "ground": "#6a5090", "sun": ["#ffe6f5", 0.95, -50, -40],
		"ambient": ["#ffe0f5", 0.38], "fog": 0.0015, "glow": true, "platform": ["#e5c9f5", "#9b78c4"], "rim": "#ffd1f0",
		"lights": [[-1.4, 1.4, -4.6, "#ff5fa2", 2.4, 5.5], [6.4, 1.4, -4.6, "#4fc3ff", 2.4, 5.5], [2.5, 0.5, -8.6, "#ffd23f", 1.2, 4.5]]},
	"james_desk": {"label": "James's Old Desk", "sky": "#6f83a9", "sky_top": "#2c3958", "ground": "#4f6286", "sun": ["#b8c8ff", 0.75, -55, -25],
		"ambient": ["#a8b8e8", 0.34], "fog": 0.008, "glow": true, "platform": ["#b9c3d6", "#7487a8"], "rim": "#a9d4ff",
		"lights": [[3.3, 1.25, -6.1, "#ffd27a", 1.8, 4.0], [2.6, 1.0, -5.8, "#9fd3ff", 0.9, 3.0]]},
	"villiam_burginson": {"label": "Villiam Burginson's", "sky": "#ffd66b", "sky_top": "#ff9f45", "ground": "#c0392b", "sun": ["#ffe0b0", 1.05, -50, -30],
		"ambient": ["#fff0d0", 0.42], "fog": 0.002, "glow": true, "platform": ["#ffd23f", "#f4f1e8"], "rim": "#ffe6b0",
		"lights": [[2.0, 1.7, -10.6, "#ff5fa2", 2.0, 8.0], [3.6, 1.55, -7.4, "#ff8c42", 1.6, 4.0], [-1.9, 1.6, -6.0, "#ff7a1a", 1.2, 3.0]]},
}

var id := "office"


func build(arena_id: String) -> void:
	id = arena_id if LOOKS.has(arena_id) else "office"
	var look: Dictionary = LOOKS[id]
	var env := WorldEnvironment.new()
	var e := Environment.new()
	# A sky with a gradient and a sun (through the windows, or overhead outside) instead of
	# one flat color; it also gives shiny things something to reflect.
	var sky_mat := ProceduralSkyMaterial.new()
	var horizon := Color(look.sky)
	sky_mat.sky_horizon_color = horizon.lightened(0.12)
	sky_mat.sky_top_color = Color(look.get("sky_top", horizon.darkened(0.3).to_html()))
	sky_mat.ground_horizon_color = horizon
	sky_mat.ground_bottom_color = Color(look.ground).darkened(0.4)
	sky_mat.sun_angle_max = 25.0
	var sky := Sky.new()
	sky.sky_material = sky_mat
	e.background_mode = Environment.BG_SKY
	e.sky = sky
	e.reflected_light_source = Environment.REFLECTION_SOURCE_SKY
	e.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	e.ambient_light_color = Color(look.ambient[0])
	e.ambient_light_energy = look.ambient[1]
	e.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	e.fog_enabled = true
	e.fog_light_color = Color(look.sky)
	e.fog_density = look.fog
	e.fog_sky_affect = 0.3
	if look.glow:
		e.glow_enabled = true
		e.glow_intensity = 0.7
		e.glow_bloom = 0.05
		e.glow_hdr_threshold = 1.0
	# A light grade: a touch more contrast and color, for the bright Pokemon-style look.
	e.adjustment_enabled = true
	e.adjustment_contrast = 1.06
	e.adjustment_saturation = 1.12
	env.environment = e
	add_child(env)

	var sun := DirectionalLight3D.new()
	sun.light_color = Color(look.sun[0])
	sun.light_energy = look.sun[1]
	sun.rotation_degrees = Vector3(look.sun[2], look.sun[3], 0)
	sun.shadow_enabled = true
	sun.directional_shadow_max_distance = 40.0  # crisper shadows on the stage
	add_child(sun)
	# A cool rim light from behind the stage, toward the camera: it outlines the characters
	# so they stand out from the background.
	var rim := DirectionalLight3D.new()
	rim.light_color = Color(look.get("rim", "#d6e4ff"))
	rim.light_energy = 0.55
	rim.rotation_degrees = Vector3(-22, 170, 0)
	rim.shadow_enabled = false
	rim.sky_mode = DirectionalLight3D.SKY_MODE_LIGHT_ONLY  # no second sun in the sky
	add_child(rim)
	# Colored light spilling from the glowing props (screens, neon, lamps). No shadows:
	# they're cheap on phones that way.
	for l in look.get("lights", []):
		var o := OmniLight3D.new()
		o.position = Vector3(l[0], l[1], l[2])
		o.light_color = Color(l[3])
		o.light_energy = l[4]
		o.omni_range = l[5]
		o.omni_attenuation = 1.4
		o.shadow_enabled = false
		add_child(o)

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


## A Pokemon-style oval battle platform: a rim and a raised top, a thin ring of the rim's
## color inset on the top, and a soft shadow around the base.
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
	var ring := MeshInstance3D.new()
	var torus := TorusMesh.new()
	torus.inner_radius = 0.96
	torus.outer_radius = 1.0
	torus.rings = 64
	ring.mesh = torus
	ring.material_override = _mat(Color(colors[0]))
	ring.scale = Vector3(radii.x * 0.74, 0.5, radii.y * 0.74)
	ring.position = center + Vector3(0, 0.065, 0)
	add_child(ring)
	var shadow := MeshInstance3D.new()
	var plane := PlaneMesh.new()
	plane.size = Vector2(2, 2)
	shadow.mesh = plane
	var g := Gradient.new()
	g.offsets = PackedFloat32Array([0.0, 0.8, 1.0])
	g.colors = PackedColorArray([Color(0, 0, 0, 0.32), Color(0, 0, 0, 0.32), Color(0, 0, 0, 0)])
	var tex := GradientTexture2D.new()
	tex.gradient = g
	tex.fill = GradientTexture2D.FILL_RADIAL
	tex.fill_from = Vector2(0.5, 0.5)
	tex.fill_to = Vector2(1.0, 0.5)
	var m := StandardMaterial3D.new()
	m.albedo_texture = tex
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	shadow.material_override = m
	shadow.scale = Vector3(radii.x * 1.16, 1, radii.y * 1.16)
	shadow.position = center + Vector3(0, 0.004, 0)
	add_child(shadow)


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
