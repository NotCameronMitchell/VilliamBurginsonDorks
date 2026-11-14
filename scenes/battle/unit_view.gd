class_name UnitView
extends Node3D
## One hero or enemy on the battle stage.
##
## If assets/models/<heroes|bosses|minions>/<model>.glb exists it's loaded and its
## animations are played by name (idle, attack, cast, hit, faint, victory... see
## docs/ART_PIPELINE.md). Until then a simple placeholder shape stands in.

signal clicked(uid: int)

## Placeholder looks for enemies: shape, color, size.
const ENEMY_LOOKS := {
	"energy_drink": {"shape": "can", "color": "#3ad1ff", "scale": 0.75},
	"tallboy": {"shape": "can", "color": "#c03ad1", "scale": 1.0},
	"nic_pouch": {"shape": "disc", "color": "#e8e8f0", "scale": 0.7},
	"pouch_tin": {"shape": "disc", "color": "#6fb3e0", "scale": 1.0},
	"reply_all": {"shape": "person", "color": "#9aa4c8", "scale": 0.95},
	"fish_guy": {"shape": "person", "color": "#8fd18f", "scale": 0.95},
	"loud_typer": {"shape": "person", "color": "#c8a46e", "scale": 0.95},
	"close_talker": {"shape": "person", "color": "#e09a7a", "scale": 0.95},
	"trucker": {"shape": "person", "color": "#c0392b", "scale": 1.45},
	"sales_guy": {"shape": "person", "color": "#34495e", "scale": 1.35},
	"copilot": {"shape": "person", "color": "#1b1b2f", "scale": 1.45},
	"guardian": {"shape": "person", "color": "#e056a0", "scale": 1.3},
	"boombox": {"shape": "box", "color": "#2d2d2d", "scale": 0.7},
	"ghost": {"shape": "ghost", "color": "#a0c8ff", "scale": 1.3},
	"cashier": {"shape": "person", "color": "#ffcc33", "scale": 1.15},
	"grill_master": {"shape": "person", "color": "#e74c3c", "scale": 1.2},
	"sauce_keeper": {"shape": "person", "color": "#e67e22", "scale": 1.2},
}
const SKIN := Color("#f1c7a5")
## Placeholder body colors per skin, so skins show before the real models exist.
const SKIN_TINTS := {
	"_suit": "#2c3e50", "_golden": "#d4af37", "_burger": "#e74c3c", "_holiday": "#1e8449",
	"_casual": "#3b5998", "_home": "#d01c2c", "_united": "#da291c", "_olemiss": "#14213d",
	"_kith": "#eeeeee", "_gym": "#555555", "_polo": "#2e86c1", "_hoodie": "#34495e",
	"_witch": "#1b1b2f", "_colorguard": "#8e44ad", "_newjob": "#2874a6", "_trucker": "#a04000",
	"_stirrer": "#6c3483", "_ghost": "#a0c8ff", "_throne": "#9b5cff", "_trucksmarter": "#f39c12",
	"_subaru": "#2e5cb8", "_ohio": "#bb0000", "_headphones": "",
}


## The placeholder body color for a hero wearing a skin.
static func skin_tint(hero_color: Color, model_key: String) -> Color:
	var k := model_key.split("~")[-1]
	for suffix in SKIN_TINTS:
		if k.ends_with(suffix) and SKIN_TINTS[suffix] != "":
			return Color(SKIN_TINTS[suffix])
	return hero_color

var uid := 0
var key := ""
var side := "hero"
var base_pos := Vector3.ZERO
var height := 1.4
var alive := true
var color := Color.WHITE
var bubble: Label3D ## the current speech bubble, so a new line replaces it
var float_stack := 0 ## floating numbers stack up when several land at once
var last_float_ms := 0
var _move_tween: Tween

var _root: Node3D ## the model (glb or placeholder), bobbed and animated
var _anim: AnimationPlayer
var _mats: Array[StandardMaterial3D] = []
var _bob_t := 0.0
var _ghostly := false


func setup(u: BattleUnit, pos: Vector3, look_at_pos: Vector3) -> void:
	uid = u.uid
	key = u.key
	side = u.side
	base_pos = pos
	position = pos
	_bob_t = randf() * TAU
	if u.side == "hero":
		color = Color(HeroData.HEROES[u.key].color)
	else:
		color = Color(ENEMY_LOOKS.get(u.key, {}).get("color", "#888888"))
	_ghostly = u.key == "ghost"
	set_model(u.model)
	look_at(Vector3(look_at_pos.x, position.y, look_at_pos.z), Vector3.UP)
	_add_click_area()
	if not u.alive:
		alive = false
		visible = false


func _process(delta: float) -> void:
	if _root and alive and _anim == null:
		_bob_t += delta * 2.2
		_root.position.y = sin(_bob_t) * 0.035 + (0.25 if _ghostly else 0.0)


## Head height in world space (for speech bubbles and numbers).
func head_pos() -> Vector3:
	return global_position + Vector3(0, height + 0.25, 0)


func center_pos() -> Vector3:
	return global_position + Vector3(0, height * 0.55, 0)


## A character shown outside battle (title screen, overworld): no unit, just a model.
func setup_preview(id: String, model_key: String, unit_side := "hero") -> void:
	key = id
	side = unit_side
	if unit_side == "hero":
		color = Color(HeroData.HEROES[id].color)
	else:
		color = Color(ENEMY_LOOKS.get(id, {}).get("color", "#888888"))
	_ghostly = id == "ghost"
	set_model(model_key)


## Plays a looping animation (walk, idle) without restarting it every frame.
func loop_anim(n: String) -> void:
	if _anim and _anim.current_animation != n:
		play(n)


# ------------------------------------------------------------------ models
const LOOPING := ["idle", "walk", "stunned", "victory"]
const ONE_SHOTS := ["attack", "cast", "hit", "ultimate"]

var _meshes: Array[MeshInstance3D] = []
var _flash_mat: StandardMaterial3D


## Model keys: "cole", "mason_suit", "trucker_remix", or "mason~mason_home" for a
## recolor. Tries the exact model, then the recolor's own file, then the base
## character, and finally a placeholder shape.
func set_model(model_key: String) -> void:
	if _root:
		_root.queue_free()
	_mats.clear()
	_meshes.clear()
	_anim = null
	var parts := model_key.split("~")
	var candidates: Array = [parts[-1], parts[0]] if parts.size() > 1 else [model_key]
	if not candidates.has(key):
		candidates.append(key)
	for name in candidates:
		for folder in ["heroes", "bosses", "minions"]:
			var path := "res://assets/models/%s/%s.glb" % [folder, name]
			if ResourceLoader.exists(path):
				_load_glb(path)
				return
	_root = _placeholder(model_key)
	add_child(_root)


func _load_glb(path: String) -> void:
	_root = (load(path) as PackedScene).instantiate()
	_root.rotation.y = PI # glTF faces +Z; units face -Z (look_at)
	add_child(_root)
	for mi in _root.find_children("*", "MeshInstance3D", true, false):
		_meshes.append(mi)
	var players := _root.find_children("*", "AnimationPlayer", true, false)
	if not players.is_empty():
		_anim = players[0]
		for n in LOOPING:
			if _anim.has_animation(n):
				_anim.get_animation(n).loop_mode = Animation.LOOP_LINEAR
		_anim.animation_finished.connect(func(n):
			if alive and n in ONE_SHOTS:
				play("idle"))
	play("idle")
	_anim_seek_random()
	height = _measure_height()


## Start idle at a random point so a lineup doesn't breathe in sync.
func _anim_seek_random() -> void:
	if _anim and _anim.current_animation != "":
		_anim.seek(randf() * _anim.current_animation_length, true)


func _measure_height() -> float:
	var top := 0.0
	for mi in _meshes:
		var a: AABB = mi.global_transform * mi.get_aabb()
		top = maxf(top, a.end.y - global_position.y)
	return top if top > 0.2 else 1.4


func play(anim: String) -> void:
	if _anim == null or not _anim.has_animation(anim):
		return
	# An ultimate isn't cut short by the cast/attack that follows it.
	if _anim.is_playing() and _anim.current_animation == "ultimate" and anim in ["cast", "attack"]:
		return
	_anim.play(anim, 0.12)


func set_stunned(on: bool) -> void:
	if _anim == null or not alive:
		return
	if on and _anim.current_animation != "stunned":
		play("stunned")
	elif not on and _anim.current_animation == "stunned":
		play("idle")


func _mat(c: Color, ghost := false) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = c
	m.roughness = 0.85
	if ghost:
		m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		m.albedo_color.a = 0.55
		m.emission_enabled = true
		m.emission = c * 0.4
	_mats.append(m)
	return m


func _mesh(mesh: Mesh, mat: Material, pos := Vector3.ZERO) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	mi.mesh = mesh
	mi.material_override = mat
	mi.position = pos
	return mi


func _placeholder(model_key: String) -> Node3D:
	var root := Node3D.new()
	var look: Dictionary = ENEMY_LOOKS.get(key, {})
	var shape: String = look.get("shape", "person")
	var s: float = look.get("scale", 1.0)
	if side == "hero":
		s = 0.8 if key == "sam" else (0.92 if key == "sarah" else 1.0)
		if model_key == "james_buff":
			s *= 1.25
	var body_c := color
	if model_key.ends_with("_remix"):
		body_c = color.darkened(0.35)
	elif side == "hero":
		body_c = skin_tint(color, model_key)
	match shape:
		"can":
			var c := CylinderMesh.new()
			c.top_radius = 0.28
			c.bottom_radius = 0.28
			c.height = 0.9
			root.add_child(_mesh(c, _mat(body_c), Vector3(0, 0.45, 0)))
			var lid := CylinderMesh.new()
			lid.top_radius = 0.24
			lid.bottom_radius = 0.28
			lid.height = 0.08
			root.add_child(_mesh(lid, _mat(Color("#cfd3dc")), Vector3(0, 0.94, 0)))
			height = 1.0
		"disc":
			var d := CylinderMesh.new()
			d.top_radius = 0.42
			d.bottom_radius = 0.42
			d.height = 0.22
			root.add_child(_mesh(d, _mat(body_c), Vector3(0, 0.3, 0)))
			height = 0.5
		"box":
			var b := BoxMesh.new()
			b.size = Vector3(0.9, 0.55, 0.35)
			root.add_child(_mesh(b, _mat(body_c), Vector3(0, 0.4, 0)))
			for x in [-0.25, 0.25]:
				var spk := CylinderMesh.new()
				spk.top_radius = 0.14
				spk.bottom_radius = 0.14
				spk.height = 0.05
				var mi := _mesh(spk, _mat(Color("#888888")), Vector3(x, 0.4, -0.18))
				mi.rotation_degrees.x = 90
				root.add_child(mi)
			height = 0.7
		_:
			var ghost := shape == "ghost"
			var body := CapsuleMesh.new()
			body.radius = 0.3
			body.height = 0.95
			root.add_child(_mesh(body, _mat(body_c, ghost), Vector3(0, 0.5, 0)))
			var head := SphereMesh.new()
			head.radius = 0.24
			head.height = 0.48
			root.add_child(_mesh(head, _mat(body_c.lightened(0.3) if ghost else SKIN, ghost), Vector3(0, 1.17, 0)))
			for x in [-0.08, 0.08]:
				var eye := SphereMesh.new()
				eye.radius = 0.035
				eye.height = 0.07
				root.add_child(_mesh(eye, _mat(Color("#1a1a2e")), Vector3(x, 1.2, -0.21)))
			_accessories(root, model_key)
			height = 1.42
	root.scale = Vector3.ONE * s
	height *= s
	return root


## Little touches so placeholders are recognizable.
func _accessories(root: Node3D, model_key: String) -> void:
	match key:
		"cole":
			if model_key == "cole_uw":
				var hair := SphereMesh.new()
				hair.radius = 0.26
				hair.height = 0.3
				root.add_child(_mesh(hair, _mat(Color("#6b3e1f")), Vector3(0, 1.32, 0.02)))
		"cam":
			var cap := CylinderMesh.new()
			cap.top_radius = 0.22
			cap.bottom_radius = 0.25
			cap.height = 0.12
			root.add_child(_mesh(cap, _mat(Color("#2ecc71")), Vector3(0, 1.36, 0)))
		"sam", "sarah", "guardian":
			var hair := CapsuleMesh.new()
			hair.radius = 0.2
			hair.height = 0.8
			root.add_child(_mesh(hair, _mat(Color("#2b1d14")), Vector3(0, 1.0, 0.12)))
		"trucker":
			var hat := CylinderMesh.new()
			hat.top_radius = 0.24
			hat.bottom_radius = 0.26
			hat.height = 0.14
			root.add_child(_mesh(hat, _mat(Color("#2c3e50")), Vector3(0, 1.38, 0)))
		"copilot":
			var hood := SphereMesh.new()
			hood.radius = 0.3
			hood.height = 0.5
			root.add_child(_mesh(hood, _mat(Color("#0d0d1a")), Vector3(0, 1.22, 0.06)))
			var scythe := BoxMesh.new()
			scythe.size = Vector3(0.05, 1.6, 0.05)
			root.add_child(_mesh(scythe, _mat(Color("#7f8c8d")), Vector3(0.45, 0.8, 0)))
		"sales_guy":
			var stirrer := BoxMesh.new()
			stirrer.size = Vector3(0.03, 0.03, 0.28)
			root.add_child(_mesh(stirrer, _mat(Color("#d35400")), Vector3(0.25, 1.22, 0)))


func _add_click_area() -> void:
	var area := Area3D.new()
	var shape := CollisionShape3D.new()
	var cap := CapsuleShape3D.new()
	cap.radius = 0.5
	cap.height = maxf(1.0, height + 0.3)
	shape.shape = cap
	shape.position.y = cap.height / 2.0
	area.add_child(shape)
	area.input_event.connect(func(_cam, ev, _pos, _n, _idx):
		if ev is InputEventMouseButton and ev.pressed and ev.button_index == MOUSE_BUTTON_LEFT:
			clicked.emit(uid))
	add_child(area)


# ------------------------------------------------------------------ animations
func lunge(target: Vector3) -> void:
	play("attack")
	var dir := (target - base_pos)
	dir.y = 0
	var dest := base_pos + dir.normalized() * minf(dir.length() * 0.45, 2.2)
	if _move_tween and _move_tween.is_valid():
		_move_tween.kill()
	_move_tween = create_tween()
	_move_tween.tween_property(self, "position", dest, 0.14).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
	_move_tween.tween_property(self, "position", base_pos, 0.24).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_IN_OUT)


func hop() -> void:
	var tw := create_tween()
	tw.tween_property(self, "position:y", base_pos.y + 0.3, 0.12)
	tw.tween_property(self, "position:y", base_pos.y, 0.15)


func cast_pulse(c: Color) -> void:
	play("cast")
	var ring := MeshInstance3D.new()
	var torus := TorusMesh.new()
	torus.inner_radius = 0.45
	torus.outer_radius = 0.55
	ring.mesh = torus
	var m := StandardMaterial3D.new()
	m.albedo_color = c
	m.emission_enabled = true
	m.emission = c
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	ring.material_override = m
	ring.position.y = 0.08
	add_child(ring)
	var tw := create_tween().set_parallel()
	tw.tween_property(ring, "scale", Vector3.ONE * 2.2, 0.5)
	tw.tween_property(m, "albedo_color:a", 0.0, 0.5)
	tw.chain().tween_callback(ring.queue_free)
	hop()


func hit_flash(crit := false) -> void:
	play("hit")
	for m in _mats:
		var orig := m.albedo_color
		m.emission_enabled = true
		m.emission = Color.WHITE
		m.emission_energy_multiplier = 1.5
		var tw := create_tween()
		tw.tween_interval(0.08)
		tw.tween_callback(func():
			m.emission = orig * 0.4 if _ghostly else Color.BLACK
			m.emission_enabled = _ghostly)
	# Real models: a white overlay that fades out.
	if not _meshes.is_empty():
		if _flash_mat == null:
			_flash_mat = StandardMaterial3D.new()
			_flash_mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
			_flash_mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		_flash_mat.albedo_color = Color(1, 1, 1, 0.85)
		for mi in _meshes:
			mi.material_overlay = _flash_mat
		var tf := create_tween()
		tf.tween_property(_flash_mat, "albedo_color:a", 0.0, 0.18)
		tf.tween_callback(func():
			for mi in _meshes:
				if is_instance_valid(mi):
					mi.material_overlay = null)
	var tw2 := create_tween()
	var off := Vector3(0.12 if crit else 0.07, 0, 0)
	tw2.tween_property(self, "position", base_pos + off, 0.04)
	tw2.tween_property(self, "position", base_pos - off, 0.05)
	tw2.tween_property(self, "position", base_pos, 0.05)


## A burst of sparks where a hit lands; crits get a bigger, brighter one.
func impact(c: Color, big := false) -> void:
	var p := CPUParticles3D.new()
	p.one_shot = true
	p.explosiveness = 1.0
	p.amount = 26 if big else 14
	p.lifetime = 0.45 if big else 0.35
	p.direction = Vector3(0, 0.4, 0)
	p.spread = 180.0
	p.initial_velocity_min = 2.5 if big else 1.6
	p.initial_velocity_max = 5.0 if big else 3.2
	p.gravity = Vector3(0, -6.0, 0)
	p.damping_min = 2.0
	p.damping_max = 4.0
	p.scale_amount_min = 0.6
	p.scale_amount_max = 1.4
	var curve := Curve.new()
	curve.add_point(Vector2(0, 1))
	curve.add_point(Vector2(1, 0))
	p.scale_amount_curve = curve
	var q := QuadMesh.new()
	q.size = Vector2(0.09, 0.09) * (1.3 if big else 1.0)
	var m := StandardMaterial3D.new()
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	m.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
	m.billboard_mode = BaseMaterial3D.BILLBOARD_PARTICLES
	m.albedo_texture = _glow_texture()
	m.albedo_color = c.lightened(0.25)
	m.vertex_color_use_as_albedo = true
	q.material = m
	p.mesh = q
	add_child(p)
	p.global_position = center_pos()
	p.emitting = true
	get_tree().create_timer(p.lifetime + 0.3).timeout.connect(p.queue_free)


## A star-shaped glint, just before an enemy strikes, so the player can read it coming.
func glint() -> void:
	var star := Node3D.new()
	var m := StandardMaterial3D.new()
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	m.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
	m.billboard_mode = BaseMaterial3D.BILLBOARD_ENABLED
	m.no_depth_test = true
	m.albedo_texture = _glow_texture()
	m.albedo_color = Color(1.0, 0.97, 0.85)
	for s in [Vector2(0.9, 0.12), Vector2(0.12, 0.9), Vector2(0.42, 0.42)]:  # two beams and a core
		var mi := MeshInstance3D.new()
		var q := QuadMesh.new()
		q.size = s
		mi.mesh = q
		mi.material_override = m
		star.add_child(mi)
	add_child(star)
	star.global_position = head_pos() + Vector3(0.22, -0.12, 0.25)
	star.scale = Vector3.ONE * 0.1
	var tw := create_tween()
	tw.tween_property(star, "scale", Vector3.ONE * 1.1, 0.1).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	tw.parallel().tween_property(star, "rotation:z", 0.6, 0.28)
	tw.tween_property(m, "albedo_color:a", 0.0, 0.18)
	tw.tween_callback(star.queue_free)


var _glow_tex: Texture2D  # per unit, so nothing outlives the battle


## A soft round glow (made once per unit): the sprite for sparks and glints.
func _glow_texture() -> Texture2D:
	if _glow_tex == null:
		var g := Gradient.new()
		g.set_color(0, Color(1, 1, 1, 1))
		g.set_color(1, Color(1, 1, 1, 0))
		g.add_point(0.25, Color(1, 1, 1, 0.85))
		var t := GradientTexture2D.new()
		t.gradient = g
		t.fill = GradientTexture2D.FILL_RADIAL
		t.fill_from = Vector2(0.5, 0.5)
		t.fill_to = Vector2(1.0, 0.5)
		t.width = 64
		t.height = 64
		_glow_tex = t
	return _glow_tex


func faint() -> void:
	alive = false
	play("faint")
	for m in _mats:
		m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	var tw := create_tween().set_parallel()
	# Real models play their fall first, then sink out of sight.
	var delay := 0.8 if _anim else 0.0
	tw.tween_property(self, "position:y", base_pos.y - 0.9, 0.6).set_ease(Tween.EASE_IN).set_delay(delay)
	for m in _mats:
		tw.tween_property(m, "albedo_color:a", 0.0, 0.6)
	tw.chain().tween_callback(func(): visible = false)


func revive() -> void:
	alive = true
	visible = true
	position = base_pos
	for m in _mats:
		m.albedo_color.a = 0.55 if _ghostly else 1.0
	play("idle")
	hop()


func celebrate() -> void:
	if alive:
		play("victory")


func set_away(away: bool) -> void:
	var tw := create_tween()
	tw.tween_property(self, "scale", Vector3.ONE * (0.01 if away else 1.0), 0.3)
