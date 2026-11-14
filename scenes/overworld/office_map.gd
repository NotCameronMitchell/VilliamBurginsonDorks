class_name OfficeMap
extends Node3D
## The office floor for the overworld: rooms, cubicle-height walls (so the camera
## always sees over them), doors with signs, props, and the lobby elevator. The floors,
## walls and furniture you see are a Blender model (art/tools/arenas.py, "overworld");
## the same layout is built here from boxes for collision (and as a fallback look).
##
##   z=-26 +-----------+-----------+-----------+
##         | Desk Pods | Middle of | Meeting   |
##         |           | the Office| Room      |
##   z=-8  +----[ ]----+----[ ]----+----[ ]----+
##         |              Hallway              |
##   z=0   +----[ ]----+---[   ]---+----[ ]----+
##         | Parking   |   Lobby   | James's   |
##         | Lot       | elevator  | Old Desk  |
##   z=16  +-----------+-----------+-----------+
##        x=-27      x=-9         x=9        x=27
##
## Each boss area has one door onto the hallway. Its coworker stands just inside the
## door watching it; the boss waits at the back of the room.

const WALL_H := 1.1
const WALL_T := 0.25
const DOOR_HALF := 2.0

## rect: Rect2(x, z, width, depth). door: where the room meets the hallway (x, z).
## tile: floor tile size in meters (a two-tone checker, like Pokemon interiors).
const ROOMS := {
	"hallway": {"rect": Rect2(-27, -8, 54, 8), "name": "Hallway", "floor": "#a99d86", "tile": 2.0},
	"lobby": {"rect": Rect2(-9, 0, 18, 16), "name": "Lobby", "floor": "#b48a63", "tile": 2.0, "door": Vector2(0, 0), "door_half": 3.0},
	"parking_lot": {"rect": Rect2(-27, 0, 18, 16), "name": "Parking Lot", "floor": "#4a4d55", "tile": 6.0, "door": Vector2(-18, 0)},
	"james_desk": {"rect": Rect2(9, 0, 18, 16), "name": "James's Old Desk", "floor": "#5f7396", "tile": 1.5, "door": Vector2(18, 0)},
	"desk_pods": {"rect": Rect2(-27, -26, 18, 18), "name": "Desk Pods", "floor": "#4f6a94", "tile": 1.5, "door": Vector2(-18, -8)},
	"office_center": {"rect": Rect2(-9, -26, 18, 18), "name": "Middle of the Office", "floor": "#7a5f9e", "tile": 1.5, "door": Vector2(0, -8)},
	"meeting_room": {"rect": Rect2(9, -26, 18, 18), "name": "Meeting Room", "floor": "#3f4566", "tile": 1.5, "door": Vector2(18, -8)},
}
## The five boss areas (EnemyData `arena` ids).
const AREAS := ["parking_lot", "desk_pods", "office_center", "meeting_room", "james_desk"]

const SPAWN := Vector3(-6.4, 0, 10.0) ## stepping out of the elevator
const ELEVATOR := Vector3(-8.7, 0, 10.0)
const ELEVATOR_FRONT := Vector3(-7.2, 0, 10.0)
const RECEPTIONIST := Vector3(4.0, 0, 6.7)
const RECEPTION_FRONT := Vector3(4.0, 0, 4.1)

const MODEL := "res://assets/models/arenas/overworld.glb"

var _signs := {} ## area -> Label3D
var _elevator_light: StandardMaterial3D
var _elevator_sign: Label3D
var _visual := true ## false while building collision only (the model shows the furniture)


func build() -> void:
	_environment()
	if ResourceLoader.exists(MODEL):
		add_child((load(MODEL) as PackedScene).instantiate())
		_visual = false
	else:
		_floors()
	_walls()
	_props()
	_visual = true
	_elevator()
	for id in ROOMS:
		if ROOMS[id].has("door") and id != "lobby":
			_sign(id, ROOMS[id].name, Color.WHITE)


# ------------------------------------------------------------------ geometry queries
static func room_at(p: Vector3) -> String:
	for id in ROOMS:
		var r: Rect2 = ROOMS[id].rect
		if p.x >= r.position.x and p.x < r.end.x and p.z >= r.position.y and p.z < r.end.y:
			return id
	return ""


static func room_name(id: String) -> String:
	return ROOMS[id].name if ROOMS.has(id) else ""


static func door_pos(room: String) -> Vector3:
	var d: Vector2 = ROOMS[room].door
	return Vector3(d.x, 0, d.y)


## The direction from the door into the room.
static func inward(room: String) -> Vector3:
	return Vector3(0, 0, -1) if ROOMS[room].door.y < -1.0 else Vector3(0, 0, 1)


static func guard_spot(area: String) -> Vector3:
	return door_pos(area) + inward(area) * 3.0


## Where a beaten coworker steps aside to.
static func guard_aside(area: String) -> Vector3:
	return guard_spot(area) + Vector3(2.6, 0, 0)


static func boss_spot(area: String) -> Vector3:
	return door_pos(area) + inward(area) * 13.0


## Walking here puts you in the coworker's line of sight.
static func vision_point(area: String) -> Vector3:
	return door_pos(area) + inward(area) * 0.8


## The coworker watches the doorway: from a bit out in the hallway up to just in
## front of where they stand.
static func in_vision(area: String, p: Vector3) -> bool:
	var d := door_pos(area)
	var along := (p - d).dot(inward(area))
	return absf(p.x - d.x) < 1.5 and along > -1.5 and along < 2.3


## Waypoints through a room's door: just inside and just outside it.
static func door_waypoints(room: String, entering: bool) -> Array:
	var d := door_pos(room)
	var inside := d + inward(room) * 1.6
	var outside := d - inward(room) * 1.6
	return [outside, inside] if entering else [inside, outside]


## A walking path between two points: rooms are convex and all meet at the
## hallway, so it's straight lines through at most two doors.
static func path(from: Vector3, to: Vector3) -> Array:
	var a := room_at(from)
	var b := room_at(to)
	if a == "" or b == "" or a == b:
		return [to]
	var pts := []
	if a != "hallway":
		pts += door_waypoints(a, false)
	if b != "hallway":
		pts += door_waypoints(b, true)
	pts.append(to)
	return pts


# ------------------------------------------------------------------ state
## Doors and signs for this cycle. status: see Run.area_status.
func set_area_state(area: String, status: String, boss_name: String) -> void:
	match status:
		"closed":
			var d := door_pos(area)
			_box(Vector3(DOOR_HALF * 2.0, 1.9, 0.2), d, Color("#a93226"))
			_sign(area, "OUT OF OFFICE", Color("#ff6b6b"))
		"cleared":
			_sign(area, "%s\nCLEARED" % ROOMS[area].name, Color("#7dff8a"))
		_:
			_sign(area, ROOMS[area].name, Color.WHITE)


func set_elevator(active: bool, text: String) -> void:
	_elevator_light.albedo_color = Color("#3ddc84") if active else Color("#ff4d4d")
	_elevator_light.emission = _elevator_light.albedo_color
	_elevator_sign.text = text


# ------------------------------------------------------------------ building
func _environment() -> void:
	var env := WorldEnvironment.new()
	var e := Environment.new()
	var sky_mat := ProceduralSkyMaterial.new()
	sky_mat.sky_horizon_color = Color("#cfe8ff")
	sky_mat.sky_top_color = Color("#5d93d6")
	sky_mat.ground_horizon_color = Color("#cfe8ff")
	sky_mat.ground_bottom_color = Color("#6f8f5a")
	var sky := Sky.new()
	sky.sky_material = sky_mat
	e.background_mode = Environment.BG_SKY
	e.sky = sky
	e.reflected_light_source = Environment.REFLECTION_SOURCE_SKY
	e.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	e.ambient_light_color = Color("#f2f4ff")
	e.ambient_light_energy = 0.42
	e.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	e.glow_enabled = true  # screens and lamps glow a little
	e.glow_intensity = 0.5
	e.glow_hdr_threshold = 1.0
	e.adjustment_enabled = true  # the same light grade as the battle arenas (docs/STYLE.md)
	e.adjustment_contrast = 1.06
	e.adjustment_saturation = 1.1
	env.environment = e
	add_child(env)
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-58, -30, 0)
	sun.light_color = Color("#fff4e6")
	sun.light_energy = 0.95
	sun.shadow_enabled = true
	sun.directional_shadow_max_distance = 45.0
	add_child(sun)
	var rim := DirectionalLight3D.new()  # a cool back light, so the party stands out
	rim.rotation_degrees = Vector3(-25, 150, 0)
	rim.light_color = Color("#d6e4ff")
	rim.light_energy = 0.4
	rim.sky_mode = DirectionalLight3D.SKY_MODE_LIGHT_ONLY
	add_child(rim)
	var grass := MeshInstance3D.new()
	var plane := PlaneMesh.new()
	plane.size = Vector2(140, 140)
	grass.mesh = plane
	grass.material_override = _mat(Color("#86b86a"))
	grass.position.y = -0.06
	add_child(grass)


func _floors() -> void:
	for id in ROOMS:
		var r: Rect2 = ROOMS[id].rect
		var mi := MeshInstance3D.new()
		var plane := PlaneMesh.new()
		plane.size = r.size
		mi.mesh = plane
		var base := Color(ROOMS[id].floor)
		var m := StandardMaterial3D.new()
		m.albedo_texture = _checker(base, base.darkened(0.12))
		m.texture_filter = BaseMaterial3D.TEXTURE_FILTER_NEAREST_WITH_MIPMAPS
		var tile: float = ROOMS[id].tile
		m.uv1_scale = Vector3(r.size.x / (tile * 2.0), r.size.y / (tile * 2.0), 1)
		m.roughness = 0.9
		mi.material_override = m
		mi.position = Vector3(r.get_center().x, 0.0, r.get_center().y)
		add_child(mi)


## A 2x2 checker texture: each texel is one floor tile.
static func _checker(a: Color, b: Color) -> ImageTexture:
	var img := Image.create(2, 2, false, Image.FORMAT_RGB8)
	img.set_pixel(0, 0, a)
	img.set_pixel(1, 1, a)
	img.set_pixel(1, 0, b)
	img.set_pixel(0, 1, b)
	return ImageTexture.create_from_image(img)


func _walls() -> void:
	var outer := Color("#c9c4ba")
	_wall_x(-26.0, -27.0, 27.0, [], 1.4, outer)
	_wall_x(16.0, -27.0, 27.0, [], 1.4, outer)
	_wall_z(-27.0, -26.0, 16.0, [], 1.4, outer)
	_wall_z(27.0, -26.0, 16.0, [], 1.4, outer)
	_wall_x(-8.0, -27.0, 27.0, [[-18.0, DOOR_HALF], [0.0, DOOR_HALF], [18.0, DOOR_HALF]])
	_wall_x(0.0, -27.0, 27.0, [[-18.0, DOOR_HALF], [0.0, 3.0], [18.0, DOOR_HALF]])
	for x in [-9.0, 9.0]:
		_wall_z(x, -26.0, -8.0, [])
		_wall_z(x, 0.0, 16.0, [])
	# Door posts
	for d in [Vector2(-18, -8), Vector2(0, -8), Vector2(18, -8), Vector2(-18, 0), Vector2(18, 0)]:
		for s in [-1, 1]:
			_box(Vector3(0.3, 1.6, 0.4), Vector3(d.x + s * (DOOR_HALF + 0.15), 0, d.y), Color("#8d8a84"))
	for s in [-1, 1]:
		_box(Vector3(0.3, 1.6, 0.4), Vector3(s * 3.15, 0, 0), Color("#8d8a84"))


## A wall along X at z, from x0 to x1, with gaps: [[center, half width], ...].
func _wall_x(z: float, x0: float, x1: float, gaps: Array, h := WALL_H, c := Color("#ebe7df")) -> void:
	var cuts := [x0]
	for g in gaps:
		cuts.append(g[0] - g[1])
		cuts.append(g[0] + g[1])
	cuts.append(x1)
	for i in range(0, cuts.size(), 2):
		var a: float = cuts[i]
		var b: float = cuts[i + 1]
		if b - a > 0.05:
			_box(Vector3(b - a, h, WALL_T), Vector3((a + b) / 2.0, 0, z), c)
			_box(Vector3(b - a, 0.06, WALL_T + 0.04), Vector3((a + b) / 2.0, h, z), Color("#6f6a62"), false)


## A wall along Z at x, from z0 to z1, with gaps.
func _wall_z(x: float, z0: float, z1: float, gaps: Array, h := WALL_H, c := Color("#ebe7df")) -> void:
	var cuts := [z0]
	for g in gaps:
		cuts.append(g[0] - g[1])
		cuts.append(g[0] + g[1])
	cuts.append(z1)
	for i in range(0, cuts.size(), 2):
		var a: float = cuts[i]
		var b: float = cuts[i + 1]
		if b - a > 0.05:
			_box(Vector3(WALL_T, h, b - a), Vector3(x, 0, (a + b) / 2.0), c)
			_box(Vector3(WALL_T + 0.04, 0.06, b - a), Vector3(x, h, (a + b) / 2.0), Color("#6f6a62"), false)


func _mat(c: Color, emit := 0.0) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = c
	m.roughness = 0.85
	if emit > 0:
		m.emission_enabled = true
		m.emission = c
		m.emission_energy_multiplier = emit
	return m


## A box standing on the floor at pos (bottom center). collide: blocks walking. While
## building collision only (_visual off), it adds no mesh and returns null.
func _box(size: Vector3, pos: Vector3, c: Color, collide := true, emit := 0.0, rot_y := 0.0) -> MeshInstance3D:
	var center := pos + Vector3(0, size.y / 2.0, 0)
	var mi: MeshInstance3D = null
	if _visual:
		mi = MeshInstance3D.new()
		var b := BoxMesh.new()
		b.size = size
		mi.mesh = b
		mi.material_override = _mat(c, emit)
		mi.position = center
		mi.rotation_degrees.y = rot_y
		add_child(mi)
	if collide:
		var body := StaticBody3D.new()
		var shape := CollisionShape3D.new()
		var bs := BoxShape3D.new()
		bs.size = size
		shape.shape = bs
		body.add_child(shape)
		body.position = center
		body.rotation_degrees.y = rot_y
		add_child(body)
	return mi


func _cyl(r: float, h: float, pos: Vector3, c: Color, collide := true, emit := 0.0) -> void:
	var center := pos + Vector3(0, h / 2.0, 0)
	if _visual:
		var mi := MeshInstance3D.new()
		var cm := CylinderMesh.new()
		cm.top_radius = r
		cm.bottom_radius = r
		cm.height = h
		mi.mesh = cm
		mi.material_override = _mat(c, emit)
		mi.position = center
		add_child(mi)
	if collide:
		var body := StaticBody3D.new()
		var shape := CollisionShape3D.new()
		var cs := CylinderShape3D.new()
		cs.radius = r
		cs.height = h
		shape.shape = cs
		body.add_child(shape)
		body.position = center
		add_child(body)


func _plant(x: float, z: float) -> void:
	_cyl(0.3, 0.45, Vector3(x, 0, z), Color("#a0522d"))
	if not _visual:
		return
	var leaves := MeshInstance3D.new()
	var s := SphereMesh.new()
	s.radius = 0.5
	s.height = 0.9
	leaves.mesh = s
	leaves.material_override = _mat(Color("#2e8b57"))
	leaves.position = Vector3(x, 0.85, z)
	add_child(leaves)


func _desk(x: float, z: float, facing_z := 1.0, c := Color("#d7c4a3")) -> void:
	_box(Vector3(2.4, 0.78, 1.2), Vector3(x, 0, z), c)
	_box(Vector3(0.8, 0.5, 0.06), Vector3(x, 0.78, z - facing_z * 0.35), Color("#1e272e"), false)
	_box(Vector3(0.6, 0.03, 0.2), Vector3(x, 0.78, z + facing_z * 0.1), Color("#dfe6e9"), false)


func _sign(area: String, text: String, color: Color) -> void:
	if _signs.has(area):
		_signs[area].queue_free()
	var l := Label3D.new()
	l.text = text
	l.font_size = 64
	l.pixel_size = 0.0055
	l.outline_size = 18
	l.outline_modulate = UITheme.INK
	l.modulate = color
	l.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	l.position = door_pos(area) + Vector3(0, 2.5, 0) - inward(area) * 0.3
	add_child(l)
	_signs[area] = l


func _props() -> void:
	# Lobby: reception desk, couch, plants, rug.
	_box(Vector3(7, 0.01, 7), Vector3(0, 0, 9), Color("#8e3b46"), false)
	_box(Vector3(4.6, 1.1, 1.2), Vector3(4.0, 0, 5.4), Color("#a1785c"))
	_box(Vector3(3.0, 0.7, 1.1), Vector3(-3.0, 0, 14.4), Color("#2e86c1"))
	_plant(-8.0, 15.0)
	_plant(8.0, 15.0)
	_plant(8.0, 1.0)
	# Hallway
	_cyl(0.3, 1.2, Vector3(-11.0, 0, -7.3), Color("#dfe6e9"))
	_cyl(0.22, 0.45, Vector3(-11.0, 1.2, -7.3), Color("#74b9ff"), false)
	_plant(11.0, -0.7)
	_plant(-26.0, -0.8)
	_plant(26.0, -7.2)
	# Parking lot: stall lines, the semi, a couple of cars, a lamp post.
	for x in [-25.6, -22.4, -13.6, -10.4]:
		_box(Vector3(0.12, 0.01, 3.4), Vector3(x, 0, 8.5), Color("#f1c40f"), false)
	_box(Vector3(2.6, 2.4, 2.4), Vector3(-24.0, 0, 4.4), Color("#c0392b"))
	_box(Vector3(1.9, 1.0, 0.1), Vector3(-24.0, 1.1, 3.15), Color("#9fd3ff"), false)
	_box(Vector3(2.7, 2.8, 7.6), Vector3(-24.0, 0, 10.5), Color("#ecf0f1"))
	_box(Vector3(1.9, 1.1, 3.8), Vector3(-12.0, 0, 4.2), Color("#2e86c1"))
	_box(Vector3(1.9, 1.1, 3.8), Vector3(-12.0, 0, 11.6), Color("#f39c12"))
	_cyl(0.12, 3.2, Vector3(-14.4, 0, 8.0), Color("#7f8c8d"))
	_box(Vector3(0.7, 0.2, 0.4), Vector3(-14.4, 3.2, 8.0), Color("#fff3b0"), false, 1.5)
	# James's old desk room: a few desks, and his old desk at the back.
	for p in [Vector2(12.5, 5), Vector2(12.5, 10), Vector2(23.5, 5), Vector2(23.5, 10)]:
		_desk(p.x, p.y)
	_desk(18.0, 15.0, -1.0, Color("#8d6e63"))
	_cyl(0.28, 1.0, Vector3(20.2, 0, 15.0), Color("#1e3799"))
	for dx in [-0.08, 0.0, 0.08]:
		_cyl(0.03, 0.4, Vector3(20.2 + dx, 1.0, 15.0), Color("#bdc3c7"), false)
	_plant(26.0, 1.0)
	# Desk pods: cubicles along both sides.
	for x in [-24.0, -12.0]:
		for z in [-12.0, -17.0, -22.0]:
			_desk(x, z, -1.0)
			_box(Vector3(2.8, 1.3, 0.1), Vector3(x, 0, z - 0.85), Color("#95a5a6"))
			_box(Vector3(0.1, 1.3, 1.8), Vector3(x + (1.45 if x < -18 else -1.45), 0, z - 0.1), Color("#95a5a6"))
	_box(Vector3(0.8, 1.5, 0.6), Vector3(-26.2, 0, -9.4), Color("#2d3436"))
	# Middle of the office: the speakers, couches, a rug.
	_box(Vector3(6, 0.01, 6), Vector3(0, 0, -21), Color("#e056a0"), false)
	for x in [-4.2, 4.2]:
		_box(Vector3(1.1, 2.3, 0.9), Vector3(x, 0, -23.6), Color("#2d2d2d"))
		_cyl(0.32, 0.05, Vector3(x, 1.2, -23.1), Color("#888888"), false)
	_box(Vector3(3.0, 0.7, 1.1), Vector3(-6.0, 0, -14.0), Color("#16a085"))
	_box(Vector3(3.0, 0.7, 1.1), Vector3(6.0, 0, -14.0), Color("#16a085"))
	_plant(-8.0, -25.0)
	_plant(8.0, -25.0)
	# Meeting room: the long table, chairs, the screen.
	_box(Vector3(2.2, 0.85, 7.0), Vector3(12.6, 0, -17.0), Color("#5d4037"))
	for z in [-19.5, -17.0, -14.5]:
		_box(Vector3(0.6, 0.55, 0.6), Vector3(10.9, 0, z), Color("#2c3e50"))
		_box(Vector3(0.6, 0.55, 0.6), Vector3(14.3, 0, z), Color("#2c3e50"))
	_box(Vector3(6.0, 2.4, 0.1), Vector3(18.0, 0.9, -25.8), Color("#7fd4ff"), false, 0.6)
	_plant(26.0, -9.2)


func _elevator() -> void:
	_box(Vector3(0.5, 2.9, 3.4), ELEVATOR, Color("#7f8c8d"))
	for s in [-1, 1]:
		var door := _box(Vector3(0.08, 2.4, 1.38), ELEVATOR + Vector3(0.3, 0, s * 0.71), Color("#bdc3c7"), false)
		(door.material_override as StandardMaterial3D).metallic = 0.6
	var light := _box(Vector3(0.1, 0.3, 0.9), ELEVATOR + Vector3(0.3, 2.5, 0), Color("#ff4d4d"), false, 2.0)
	_elevator_light = light.material_override
	_elevator_sign = Label3D.new()
	_elevator_sign.font_size = 56
	_elevator_sign.pixel_size = 0.005
	_elevator_sign.outline_size = 16
	_elevator_sign.outline_modulate = UITheme.INK
	_elevator_sign.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	_elevator_sign.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_elevator_sign.position = ELEVATOR + Vector3(0.6, 3.4, 0)
	add_child(_elevator_sign)
