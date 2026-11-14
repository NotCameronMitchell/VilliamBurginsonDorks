extends Node3D
## The office overworld. Walk the party around (WASD / arrows / gamepad, the
## on-screen joystick, or tap where to go), pick which open area to take on next,
## get spotted by its coworker for the minion fight, then talk to the boss at the
## back of the room. After three bosses the elevator goes down to Villiam Burginson's.

const SPEED := 4.6
const FOLLOW_GAP := 0.95 ## how far apart the party walks
const CAM_OFFSET := Vector3(0, 7.4, 6.0)
const CHAR_SCALE := 1.2 ## characters read a bit bigger in the overworld
const TALK_RANGE := 1.9

var run: Dictionary
var info: Dictionary
var map: OfficeMap
var leader: CharacterBody3D
var leader_view: UnitView
var followers: Array = [] ## UnitViews
var trail: Array = [] ## the leader's recent positions, newest first
var cam: Camera3D
var hud: OverworldHUD
## NPCs and the elevator: {kind: guard|boss|talk|elevator, name, pos, face, approach,
## area, boss, status, view (UnitView), body, lines}
var npcs: Array = []
var busy := true ## talking, a cutscene, or changing scenes: no walking
var path: Array = [] ## tap-to-move waypoints
var target_npc: Dictionary = {} ## talk to them when the path ends
var auto := false
var room := ""
var _facing := Vector3(1, 0, 0)
var _stuck_t := 0.0
var _last_dist := INF


func _ready() -> void:
	run = Game.run
	if run.is_empty():
		Game.go_title.call_deferred()
		return
	if not run.get("pending", {}).is_empty():
		Game.go_battle.call_deferred()
		return
	auto = Game.auto_play
	info = Run.current_stage(run)
	map = OfficeMap.new()
	add_child(map)
	map.build()
	cam = Camera3D.new()
	cam.fov = 45
	add_child(cam)
	var layer := CanvasLayer.new()
	add_child(layer)
	hud = OverworldHUD.new()
	layer.add_child(hud)
	hud.interact_pressed.connect(_interact_nearest)
	hud.quit_pressed.connect(_save_and_quit)
	_spawn_party()
	_spawn_npcs()
	_snap_camera()
	_refresh_hud()
	await hud.fade_in()
	if run.stage == 0 and not run.get("intro_seen", false):
		for l in Story.RUN_INTRO:
			await hud.say(_speaker_name(l.speaker), l.text)
		run.intro_seen = true
		Game.save()
	_update_room()
	busy = false


# ------------------------------------------------------------------ setup
func _spawn_party() -> void:
	var ow: Dictionary = run.get("overworld", {})
	var pos := OfficeMap.SPAWN
	_facing = Vector3(1, 0, 0)
	if ow.has("x") and int(ow.get("cycle", -1)) == int(info.cycle):
		var saved := Vector3(float(ow.x), 0, float(ow.z))
		if OfficeMap.room_at(saved) != "":
			pos = saved
			_facing = Vector3(float(ow.get("fx", 0.0)), 0, float(ow.get("fz", -1.0))).normalized()
	leader = CharacterBody3D.new()
	leader.motion_mode = CharacterBody3D.MOTION_MODE_FLOATING
	var shape := CollisionShape3D.new()
	var cap := CapsuleShape3D.new()
	cap.radius = 0.3
	cap.height = 1.2
	shape.shape = cap
	shape.position.y = 0.6
	leader.add_child(shape)
	add_child(leader)
	leader.global_position = pos
	leader_view = _hero_view(run.heroes[0].id, leader)
	_face(leader_view, _facing)
	trail.clear()
	for i in 60:
		trail.append(pos - _facing * (i * 0.12))
	followers.clear()
	for i in range(1, run.heroes.size()):
		var v := _hero_view(run.heroes[i].id, self)
		v.global_position = _trail_point(i * FOLLOW_GAP)
		_face(v, _facing)
		followers.append(v)


func _hero_view(id: String, parent: Node) -> UnitView:
	var v := UnitView.new()
	parent.add_child(v)
	v.setup_preview(id, Outfits.model_of(Outfits.outfit_of(id, run.get("outfits", {}))))
	v.scale = Vector3.ONE * CHAR_SCALE
	return v


func _spawn_npcs() -> void:
	var today := []
	for area in OfficeMap.AREAS:
		var boss := _boss_in(area)
		if boss == "":
			continue
		var status := Run.area_status(run, boss)
		map.set_area_state(area, status, _boss_name(boss))
		if status == "closed":
			continue
		today.append("%s (%s)" % [_boss_name(boss), OfficeMap.room_name(area)])
		var g: Dictionary = Story.OVERWORLD.guards[area]
		var beaten := status in ["boss", "cleared"]
		var toward_door := -OfficeMap.inward(area)
		_add_npc({"kind": "guard", "area": area, "boss": boss, "key": g.model, "model": g.model,
			"name": EnemyData.ENEMIES[g.model].name, "status": status, "face": toward_door,
			"pos": OfficeMap.guard_aside(area) if beaten else OfficeMap.guard_spot(area)})
		var remix := Run.is_remix(run.seed, info.cycle, boss)
		_add_npc({"kind": "boss", "area": area, "boss": boss, "key": boss, "model": boss + ("_remix" if remix else ""),
			"name": _boss_name(boss), "status": status, "face": toward_door, "pos": OfficeMap.boss_spot(area)})
	var line: String = Story.OVERWORLD.receptionist_done if info.kind == "bonus" else Story.OVERWORLD.receptionist % ", ".join(today)
	_add_npc({"kind": "talk", "key": "reply_all", "model": "reply_all", "name": Story.OVERWORLD.receptionist_name,
		"pos": OfficeMap.RECEPTIONIST, "face": Vector3(0, 0, -1), "approach": OfficeMap.RECEPTION_FRONT, "lines": [line]})
	for r in Story.OVERWORLD.regulars:
		_add_npc({"kind": "talk", "key": r.model, "model": r.model, "name": EnemyData.ENEMIES[r.model].name,
			"pos": Vector3(r.pos[0], 0, r.pos[1]), "face": Vector3(r.face[0], 0, r.face[1]), "lines": r.lines})
	npcs.append({"kind": "elevator", "name": "Elevator", "pos": OfficeMap.ELEVATOR, "approach": OfficeMap.ELEVATOR_FRONT, "face": Vector3(1, 0, 0)})
	if info.kind == "bonus":
		map.set_elevator(true, "ELEVATOR\nB1: Villiam Burginson's")
	else:
		map.set_elevator(false, "ELEVATOR\n%d of 3 bosses" % _beaten())


func _add_npc(n: Dictionary) -> void:
	var v := UnitView.new()
	add_child(v)
	v.setup_preview(n.key, n.model, "enemy")
	v.scale = Vector3.ONE * CHAR_SCALE
	v.global_position = n.pos
	_face(v, n.face)
	n.view = v
	var body := StaticBody3D.new()
	var shape := CollisionShape3D.new()
	var cs := CylinderShape3D.new()
	cs.radius = 0.4
	cs.height = 1.4
	shape.shape = cs
	shape.position.y = 0.7
	body.add_child(shape)
	add_child(body)
	body.global_position = n.pos
	n.body = body
	if not n.has("approach"):
		n.approach = n.pos + n.face * 1.25
	npcs.append(n)


# ------------------------------------------------------------------ per frame
func _physics_process(delta: float) -> void:
	if leader == null:
		return
	_update_followers(delta)
	_update_camera(delta)
	if busy or hud.menu_open():
		leader.velocity = Vector3.ZERO
		leader_view.loop_anim("idle")
		hud.hide_prompt()
		return
	var input := Input.get_vector("move_left", "move_right", "move_up", "move_down")
	if hud.stick.length() > 0.15:
		input = hud.stick
	var dir := Vector3(input.x, 0, input.y)
	if dir.length() > 0.1:
		path.clear()
		target_npc = {}
	elif not path.is_empty():
		dir = _follow_path(delta)
	elif auto:
		_auto_step()
	var vel := dir.limit_length(1.0) * SPEED
	leader.velocity = vel
	leader.move_and_slide()
	leader.global_position.y = 0.0
	if vel.length() > 0.2:
		_facing = vel.normalized()
		leader_view.rotation.y = lerp_angle(leader_view.rotation.y, atan2(-_facing.x, -_facing.z), minf(1.0, delta * 14.0))
		leader_view.loop_anim("walk")
	else:
		leader_view.loop_anim("idle")
	_record_trail()
	if busy:
		return
	_check_vision()
	_update_room()
	_update_prompt()


func _follow_path(delta: float) -> Vector3:
	var p: Vector3 = path[0]
	var to := p - leader.global_position
	to.y = 0
	var d := to.length()
	if d < 0.25:
		path.pop_front()
		_stuck_t = 0.0
		_last_dist = INF
		if path.is_empty():
			_arrive()
			return Vector3.ZERO
		return _follow_path(delta)
	# Blocked by a desk or a person: skip to the next waypoint.
	_stuck_t = _stuck_t + delta if d >= _last_dist - 0.01 else 0.0
	_last_dist = d
	if _stuck_t > 0.8:
		path.pop_front()
		_stuck_t = 0.0
		_last_dist = INF
		if path.is_empty():
			_arrive()
		return Vector3.ZERO
	return to / d


func _arrive() -> void:
	if target_npc.is_empty():
		return
	var n := target_npc
	target_npc = {}
	if _in_range(n):
		_interact(n)


func _record_trail() -> void:
	var p := leader.global_position
	if trail.is_empty() or p.distance_to(trail[0]) > 0.1:
		trail.push_front(p)
		if trail.size() > 120:
			trail.pop_back()


## A point `dist` meters back along the leader's path.
func _trail_point(dist: float) -> Vector3:
	var prev := leader.global_position
	var left := dist
	for p in trail:
		var seg := prev.distance_to(p)
		if seg >= left and seg > 0.0001:
			return prev.lerp(p, left / seg)
		left -= seg
		prev = p
	return prev


func _update_followers(delta: float) -> void:
	for i in followers.size():
		var v: UnitView = followers[i]
		var target := _trail_point((i + 1) * FOLLOW_GAP)
		var move := target - v.global_position
		move.y = 0
		if move.length() > 0.03:
			v.global_position = v.global_position.lerp(target, minf(1.0, delta * 12.0))
			v.rotation.y = lerp_angle(v.rotation.y, atan2(-move.x, -move.z), minf(1.0, delta * 10.0))
			v.loop_anim("walk")
		else:
			v.loop_anim("idle")


func _snap_camera() -> void:
	cam.global_position = leader.global_position + CAM_OFFSET
	cam.look_at(leader.global_position + Vector3(0, 0.4, -0.6))


func _update_camera(delta: float) -> void:
	cam.global_position = cam.global_position.lerp(leader.global_position + CAM_OFFSET, minf(1.0, delta * 5.0))


func _check_vision() -> void:
	for n in npcs:
		if n.kind == "guard" and n.status in ["open", "in_progress"] and OfficeMap.in_vision(n.area, leader.global_position):
			_guard_challenge(n)
			return


func _update_room() -> void:
	var r := OfficeMap.room_at(leader.global_position)
	if r == "" or r == room:
		return
	room = r
	var name := OfficeMap.room_name(r)
	if r in OfficeMap.AREAS and Run.area_status(run, _boss_in(r)) == "cleared":
		name += "  (cleared)"
	hud.toast(name)


func _update_prompt() -> void:
	var n := _nearest_npc()
	if n.is_empty():
		hud.hide_prompt()
	elif n.kind == "elevator":
		hud.show_prompt("Take the elevator" if info.kind == "bonus" else "Elevator")
	else:
		hud.show_prompt("Talk to %s" % n.name)


func _in_range(n: Dictionary) -> bool:
	var p := leader.global_position
	return p.distance_to(n.approach) < 1.3 or p.distance_to(n.pos) < TALK_RANGE


func _nearest_npc() -> Dictionary:
	var best: Dictionary = {}
	var best_d := INF
	for n in npcs:
		if not _in_range(n):
			continue
		var d := leader.global_position.distance_to(n.pos)
		if d < best_d:
			best = n
			best_d = d
	return best


# ------------------------------------------------------------------ input
func _unhandled_input(ev: InputEvent) -> void:
	if busy or leader == null or hud.menu_open():
		return
	if ev.is_action_pressed("interact"):
		_interact_nearest()
		get_viewport().set_input_as_handled()
	elif ev is InputEventMouseButton and ev.pressed and ev.button_index == MOUSE_BUTTON_LEFT:
		_tap(ev.position)
		get_viewport().set_input_as_handled()


## Tap-to-move: tap a person to walk over and talk, or the floor to walk there.
func _tap(screen: Vector2) -> void:
	var o := cam.project_ray_origin(screen)
	var d := cam.project_ray_normal(screen)
	var best: Dictionary = {}
	var best_t := INF
	for n in npcs:
		var center: Vector3 = n.pos + Vector3(0, 0.8, 0)
		var t := (center - o).dot(d)
		if t > 0 and (o + d * t).distance_to(center) < 0.9 and t < best_t:
			best = n
			best_t = t
	if not best.is_empty():
		_go_to(best)
		return
	if absf(d.y) < 0.001:
		return
	var t := -o.y / d.y
	if t <= 0:
		return
	var p := o + d * t
	p.y = 0
	var r := OfficeMap.room_at(p)
	if r == "":
		return
	if r in OfficeMap.AREAS and Run.area_status(run, _boss_in(r)) == "closed":
		p = OfficeMap.door_pos(r) - OfficeMap.inward(r) * 1.4
		hud.toast("%s: Out of Office" % OfficeMap.room_name(r))
	_walk_to(p)
	_marker(p)


func _walk_to(p: Vector3) -> void:
	path = OfficeMap.path(leader.global_position, p)
	target_npc = {}
	_stuck_t = 0.0
	_last_dist = INF


func _go_to(n: Dictionary) -> void:
	if _in_range(n):
		_interact(n)
		return
	_walk_to(n.approach)
	target_npc = n


func _interact_nearest() -> void:
	if busy:
		return
	var n := _nearest_npc()
	if not n.is_empty():
		_interact(n)


# ------------------------------------------------------------------ talking
func _interact(n: Dictionary) -> void:
	if busy:
		return
	busy = true
	path.clear()
	target_npc = {}
	hud.hide_prompt()
	if n.has("view"):
		_face(leader_view, n.pos - leader.global_position)
		_face(n.view, leader.global_position - n.pos)
	var started := false
	match n.kind:
		"guard":
			started = await _talk_guard(n)
		"boss":
			started = await _talk_boss(n)
		"elevator":
			started = await _use_elevator()
		_:
			await hud.say(n.name, n.lines[randi() % n.lines.size()])
	if not started:
		busy = false


func _talk_guard(n: Dictionary) -> bool:
	match Run.area_status(run, n.boss):
		"open", "in_progress":
			await _guard_challenge(n, false)
			return true
		"waiting":
			await hud.say(n.name, Story.OVERWORLD.guard_waiting % OfficeMap.room_name(_area_in_progress()))
		"boss":
			await hud.say(n.name, Story.OVERWORLD.guard_beaten % _boss_name(n.boss))
		_:
			await hud.say(n.name, Story.OVERWORLD.guard_cleared)
	return false


func _talk_boss(n: Dictionary) -> bool:
	match Run.area_status(run, n.boss):
		"boss":
			_exclaim(n.view)
			await get_tree().create_timer(0.5).timeout
			await _start_battle()
			return true
		"open", "in_progress":
			await hud.say(n.name, Story.OVERWORLD.boss_not_ready)
		"waiting":
			await hud.say(n.name, Story.OVERWORLD.boss_waiting % OfficeMap.room_name(_area_in_progress()))
		_:
			var lines := Story.boss_defeat(n.boss)
			await hud.say(n.name, lines[0].text if not lines.is_empty() else "...")
	return false


## The coworker spots you: "!", they walk up, say their line, and the fight starts.
func _guard_challenge(n: Dictionary, walk := true) -> void:
	busy = true
	path.clear()
	target_npc = {}
	hud.hide_prompt()
	if not Run.lock_area(run, n.boss):
		busy = false
		return
	_exclaim(n.view)
	await get_tree().create_timer(0.7).timeout
	if walk:
		var away: Vector3 = (n.view.global_position - leader.global_position)
		away.y = 0
		await _walk_npc(n, leader.global_position + away.normalized() * 1.3)
	_face(leader_view, n.view.global_position - leader.global_position)
	_face(n.view, leader.global_position - n.view.global_position)
	await hud.say(n.name, Story.OVERWORLD.guards[n.area].line)
	await _start_battle()


func _use_elevator() -> bool:
	if info.kind == "bonus":
		await hud.say("", Story.OVERWORLD.elevator_go)
		run.overworld = {} # the next cycle starts at the elevator
		await _start_battle(false)
		return true
	await hud.say("", Story.OVERWORLD.elevator_locked % _beaten())
	return false


func _walk_npc(n: Dictionary, target: Vector3) -> void:
	var v: UnitView = n.view
	var d := v.global_position.distance_to(target)
	if d < 0.2:
		return
	_face(v, target - v.global_position)
	v.loop_anim("walk")
	var tw := create_tween()
	tw.tween_property(v, "global_position", target, d / 3.5)
	await tw.finished
	v.loop_anim("idle")
	n.body.global_position = target


func _start_battle(keep_pos := true) -> void:
	busy = true
	if keep_pos:
		run.overworld = {"cycle": info.cycle, "x": leader.global_position.x, "z": leader.global_position.z,
			"fx": _facing.x, "fz": _facing.z}
	Game.save()
	await hud.fade_out()
	Game.go_battle()


func _save_and_quit() -> void:
	busy = true
	run.overworld = {"cycle": info.cycle, "x": leader.global_position.x, "z": leader.global_position.z,
		"fx": _facing.x, "fz": _facing.z}
	Game.save()
	await hud.fade_out()
	Game.go_title()


# ------------------------------------------------------------------ auto-play (tests)
## Walks to the next thing to do: the boss, the coworker in the picked area, the
## first open area, or the elevator.
func _auto_step() -> void:
	if info.kind == "bonus":
		for n in npcs:
			if n.kind == "elevator":
				_go_to(n)
		return
	for n in npcs:
		if n.kind == "boss" and Run.area_status(run, n.boss) == "boss":
			_go_to(n)
			return
	for n in npcs:
		if n.kind == "guard" and Run.area_status(run, n.boss) == "in_progress":
			_walk_to(OfficeMap.vision_point(n.area))
			return
	for b in Run.cycle_order(run.seed, info.cycle, Run.locked_areas(run)):
		for n in npcs:
			if n.kind == "guard" and n.boss == b and Run.area_status(run, b) == "open":
				_walk_to(OfficeMap.vision_point(n.area))
				return


# ------------------------------------------------------------------ helpers
func _refresh_hud() -> void:
	hud.set_progress(info.cycle, _beaten(), run.pto)
	hud.set_party(run, Game.meta)
	hud.set_objective(_objective())


func _objective() -> String:
	if info.kind == "bonus":
		return "Take the elevator down to Villiam Burginson's"
	for area in OfficeMap.AREAS:
		var b := _boss_in(area)
		var s := Run.area_status(run, b)
		if s == "boss":
			return "Talk to %s in the %s" % [_boss_name(b), OfficeMap.room_name(area)]
		if s == "in_progress":
			return "Head into the %s" % OfficeMap.room_name(area)
	var open := []
	for area in OfficeMap.AREAS:
		if Run.area_status(run, _boss_in(area)) == "open":
			open.append(OfficeMap.room_name(area))
	return "Pick an area: %s" % ", ".join(open)


func _beaten() -> int:
	return 3 if info.kind == "bonus" else int(info.index) / (Run.MINIONS_PER_BOSS + 1)


func _area_in_progress() -> String:
	for area in OfficeMap.AREAS:
		if Run.area_status(run, _boss_in(area)) in ["in_progress", "boss"]:
			return area
	return ""


static func _boss_in(area: String) -> String:
	for b in EnemyData.BOSS_POOL:
		if EnemyData.ENEMIES[b].get("arena", "") == area:
			return b
	return ""


func _boss_name(boss: String) -> String:
	var d: Dictionary = EnemyData.ENEMIES[boss]
	return d.remix_name if Run.is_remix(run.seed, info.cycle, boss) and d.has("remix_name") else d.name


static func _speaker_name(who: String) -> String:
	if HeroData.HEROES.has(who):
		return HeroData.HEROES[who].name
	if EnemyData.ENEMIES.has(who):
		return EnemyData.ENEMIES[who].name
	return "" if who == "Narrator" else who


## Turns a model to face a direction (UnitViews face -Z).
static func _face(v: Node3D, dir: Vector3) -> void:
	dir.y = 0
	if dir.length_squared() > 0.0001:
		v.rotation.y = atan2(-dir.x, -dir.z)


func _exclaim(v: UnitView) -> void:
	var l := Label3D.new()
	l.text = "!"
	l.font_size = 140
	l.outline_size = 28
	l.outline_modulate = UITheme.INK
	l.modulate = Color("#ffd23f")
	l.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	l.no_depth_test = true
	l.pixel_size = 0.01
	add_child(l)
	l.global_position = v.global_position + Vector3(0, v.height * CHAR_SCALE + 0.55, 0)
	l.scale = Vector3.ONE * 0.2
	var tw := create_tween()
	tw.tween_property(l, "scale", Vector3.ONE, 0.15).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	tw.tween_interval(1.0)
	tw.tween_callback(l.queue_free)


## A ring where you tapped.
func _marker(p: Vector3) -> void:
	var m := MeshInstance3D.new()
	var t := TorusMesh.new()
	t.inner_radius = 0.25
	t.outer_radius = 0.35
	m.mesh = t
	var mat := StandardMaterial3D.new()
	mat.albedo_color = UITheme.ACCENT
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	m.material_override = mat
	add_child(m)
	m.global_position = p + Vector3(0, 0.05, 0)
	var tw := create_tween()
	tw.tween_property(mat, "albedo_color:a", 0.0, 0.6)
	tw.tween_callback(m.queue_free)
