extends Node3D
## The battle screen. Builds the 3D stage and the HUD, then replays the Battle's
## recorded events one by one with timing (animations, numbers, text), asks the
## player for each hero's move, and runs the after-fight screens (loot, upgrade
## picks, shop, random event) before loading the next fight.

enum State { STORY, PLAYING, INPUT, TARGETING, POPUP, OVER }

## Behind and above the heroes, looking across at the enemies; framed so the units
## sit above the bottom HUD strip.
## Lower angle (about 24 degrees down) so the arena behind the enemies shows.
const CAM_POS := Vector3(-1.3, 5.0, 11.0)
const CAM_LOOK := Vector3(0.2, -0.2, -0.6)
const CAM_FOV := 38.0
const DMG_COLORS := {
	"hit": Color.WHITE, "poison": Color("#7cff4f"), "bleed": Color("#ff4f6d"), "burn": Color("#ff9a1f"),
	"reflect": Color("#ff7ae0"), "boom": Color("#ffb627"),
}

var b: Battle
var views := {} ## uid -> UnitView
var hp_shown := {} ## uid -> hp as the HUD currently shows it
var hud: BattleHUD
var overlay: RunOverlay
var arena: Arena
var cam: Camera3D
var state := State.STORY
var cursor := 0
var wait := 0.0
var auto := false
var current_uid := -1
var pending_action := ""
var target_uids := []
var info := {}
var _shake := 0.0
var _front_used := 0
var _back_used := 0
var _enemy_slot := 0


func _ready() -> void:
	get_viewport().physics_object_picking = true
	auto = Game.auto_play
	var lines := []
	var arena_id := "office"
	var test := not Game.test_fight.is_empty()
	if test:
		var tf: Dictionary = Game.test_fight
		var heroes := []
		for id in tf.party:
			var s := Battle.hero_setup(id)
			s.max_hp = roundi(s.max_hp * 1.4)
			s.hp = s.max_hp
			s.atk *= 1.4
			for ab in HeroData.rankable(id):
				s.ranks[ab] = 2
			heroes.append(s)
		b = Battle.new(heroes, tf.enemies, randi())
		var first: String = tf.enemies[0].id
		arena_id = EnemyData.ENEMIES[first].get("arena", "office")
		lines = Story.BURGER_INTRO if first == "cashier" else Story.boss_intro(first, tf.enemies[0].remix)
		info = {"kind": "boss" if EnemyData.ENEMIES[first].get("boss", false) else "minion"}
	else:
		if Game.run.is_empty():
			Game.go_title()
			return
		info = Run.current_stage(Game.run)
		arena_id = "villiam_burginson" if info.kind == "bonus" else EnemyData.ENEMIES[info.boss].get("arena", "office")
		if not Game.run.get("pending", {}).is_empty():
			_build_world(arena_id)
			_post_fight({})
			return
		lines = Run.start_fight(Game.run, Game.meta).lines
		b = Run.build_battle(Game.run, Game.meta)
		Game.save()
	_build_world(arena_id)
	Audio.play_music(_battle_track(arena_id))
	if Game.ult_first:  # test option: every hero's ultimate is ready on the first turn
		for u in b.units:
			if u.side == "hero" and HeroData.HEROES.has(u.key):
				u.cd[HeroData.HEROES[u.key].ultimate] = 0
	for u in b.units:
		_add_unit(u)
	_refresh_statuses()
	hud.set_round("Round 1")
	hud.set_auto(auto)
	await _story(lines)
	if info.get("kind", "") == "boss" or info.get("kind", "") == "bonus":
		hud.banner(b.enemies()[0].name if info.kind == "boss" else "VILLIAM BURGINSON'S", "Boss fight!" if info.kind == "boss" else "Protect the sauce?")
		Audio.sfx("banner")
	state = State.PLAYING


## Boss fights and the burger joint get their own music.
func _battle_track(arena_id: String) -> String:
	if arena_id == "villiam_burginson" or info.get("kind", "") == "bonus":
		return "final"
	return "boss" if info.get("kind", "") == "boss" else "battle"


## The sound for a status note ("Stunned", "Poison", "Damage Up"...), or "" for none.
func _status_sound(text: String) -> String:
	for kind in StatusInfo.INFO:
		var inf: Dictionary = StatusInfo.INFO[kind]
		if inf.label == text:
			match kind:
				"stun", "poison", "burn":
					return kind
			return "buff" if inf.good else "debuff"
	return ""


func _build_world(arena_id: String) -> void:
	arena = Arena.new()
	add_child(arena)
	arena.build(arena_id)
	cam = Camera3D.new()
	cam.fov = CAM_FOV
	add_child(cam)
	cam.position = CAM_POS
	cam.look_at(CAM_LOOK)
	var layer := CanvasLayer.new()
	add_child(layer)
	hud = BattleHUD.new()
	layer.add_child(hud)
	hud.action_picked.connect(_on_action)
	hud.hero_picked.connect(_select_hero)
	hud.wait_picked.connect(_on_wait)
	hud.back_picked.connect(_on_back)
	hud.plate_pressed.connect(_on_unit_tapped)
	hud.auto_toggled.connect(_on_auto)
	hud.popup_answered.connect(_on_popup_answer)
	var top := CanvasLayer.new()
	top.layer = 5
	add_child(top)
	overlay = RunOverlay.new()
	top.add_child(overlay)


func _add_unit(u: BattleUnit) -> void:
	var v := UnitView.new()
	add_child(v)
	var pos: Vector3
	if u.side == "hero":
		# Front-row heroes take the front spots (0, 1), back-row the back ones (2, 3).
		var spot: int
		if u.row == "front" and _front_used < 2:
			spot = _front_used
			_front_used += 1
		elif u.row != "front" and _back_used < 2:
			spot = 2 + _back_used
			_back_used += 1
		else:
			spot = _front_used if _front_used < 2 else 2 + _back_used
			if _front_used < 2:
				_front_used += 1
			else:
				_back_used += 1
		pos = Arena.HERO_SPOTS[spot % Arena.HERO_SPOTS.size()]
		v.setup(u, pos, Arena.ENEMY_CENTER)
	else:
		pos = Arena.ENEMY_SPOTS[_enemy_slot % Arena.ENEMY_SPOTS.size()]
		_enemy_slot += 1
		v.setup(u, pos, Arena.HERO_CENTER)
	v.clicked.connect(_on_unit_tapped)
	views[u.uid] = v
	hp_shown[u.uid] = u.hp
	hud.add_plate(u)


func _story(lines: Array) -> void:
	state = State.STORY
	if Game.skip_story:
		return
	for l in lines:
		var who: String = l.speaker
		var name := who
		if HeroData.HEROES.has(who):
			name = HeroData.HEROES[who].name
		elif EnemyData.ENEMIES.has(who):
			name = EnemyData.ENEMIES[who].name
		if who != "Narrator" and views.size() > 0:
			for id in views:
				if b and b.unit(id).key == who:
					_bubble(views[id], l.text)
		if auto:
			hud.message("[b]%s:[/b] %s" % [name, l.text] if who != "Narrator" else l.text)
			await get_tree().create_timer(1.3).timeout
		else:
			hud.dialog("" if who == "Narrator" else name, l.text)
			await hud.advanced
	hud.message("")


# ------------------------------------------------------------------ main loop
func _process(delta: float) -> void:
	_update_camera(delta)
	if state != State.PLAYING or b == null:
		return
	var speed: float = Game.settings.get("battle_speed", 1.0)
	if wait > 0:
		wait -= delta * speed
		return
	while cursor < b.events.size():
		var ev: Dictionary = b.events[cursor]
		cursor += 1
		wait = _play(ev)
		if state != State.PLAYING or wait > 0:
			return
	if b.outcome != "":
		state = State.OVER
		_on_over()
	elif not b.pending_popup.is_empty():
		return
	elif b.phase == "enemy":
		b.enemy_step()
	elif b.phase == "hero":
		_begin_input()


func _begin_input() -> void:
	var rdy := b.ready()
	if rdy.is_empty():
		return
	_refresh_statuses()
	if auto:
		var u: BattleUnit = rdy[0]
		var pick := BattleAI.choose_action(b, u)
		if not b.act(u.uid, pick[0], pick[1]) and not b.act(u.uid, "attack"):
			b.pass_turn(u.uid)
		return
	state = State.INPUT
	if not rdy.any(func(h): return h.uid == current_uid):
		current_uid = rdy[0].uid
	_show_commands()


func _show_commands() -> void:
	var rdy := b.ready()
	var u := b.unit(current_uid)
	for id in hud.plates:
		hud.plate(id).set_active(id == current_uid)
	hud.show_commands(b, u, rdy)
	hud.message("What will [b]%s[/b] do?" % u.name)


# ------------------------------------------------------------------ player input
func _select_hero(uid: int) -> void:
	if state != State.INPUT:
		return
	current_uid = uid
	_show_commands()


func _on_action(id: String) -> void:
	if state != State.INPUT:
		return
	var u := b.unit(current_uid)
	var opt: Dictionary = {}
	for o in b.actions(u):
		if o.id == id:
			opt = o
	if opt.is_empty() or not opt.ready:
		return
	if opt.target == "enemy":
		target_uids = b.foes_of(u).map(func(e): return e.uid)
		if target_uids.size() == 1:
			_do_act(id, target_uids[0])
			return
		_begin_targeting(id, "a target")
	elif opt.target == "ally":
		target_uids = b.allies_of(u).map(func(a): return a.uid)
		_begin_targeting(id, "an ally")
	else:
		_do_act(id, Battle.NO_TARGET)


func _begin_targeting(id: String, what: String) -> void:
	pending_action = id
	state = State.TARGETING
	hud.begin_targeting(target_uids, what)
	hud.message("Tap %s." % what)


func _on_unit_tapped(uid: int) -> void:
	if state == State.TARGETING and target_uids.has(uid):
		_do_act(pending_action, uid)
	elif state == State.INPUT:
		var u := b.unit(uid)
		if u and b.ready().has(u):
			_select_hero(uid)


func _on_back() -> void:
	if state != State.TARGETING:
		return
	hud.end_targeting()
	state = State.INPUT
	_show_commands()


func _on_wait() -> void:
	if state != State.INPUT:
		return
	hud.hide_commands()
	b.pass_turn(current_uid)
	state = State.PLAYING


func _do_act(id: String, target: int) -> void:
	hud.end_targeting()
	hud.hide_commands()
	for p in hud.plates:
		hud.plate(p).set_active(false)
	if not b.act(current_uid, id, target):
		hud.message("Can't do that right now.")
		state = State.INPUT
		_show_commands()
		return
	state = State.PLAYING


func _on_auto(on: bool) -> void:
	auto = on
	if on and (state == State.INPUT or state == State.TARGETING):
		hud.end_targeting()
		hud.hide_commands()
		state = State.PLAYING


func _on_popup_answer(choice: String) -> void:
	b.answer_popup(choice)
	var lines := {"dismiss": "Not now.", "install": "Installing Cowork skills... 4 onboarding videos queued.", "pro": "Upgraded to Pro. Oh no.", "timeout": "Too slow!"}
	hud.message(lines.get(choice, ""))
	state = State.PLAYING


# ------------------------------------------------------------------ playback
## Plays one event and returns how long to wait before the next (at 1x speed).
func _play(ev: Dictionary) -> float:
	var v: UnitView = views.get(ev.get("uid", -1))
	match ev.t:
		"beat":
			return ev.dur * 0.75
		"turn":
			if ev.side == "hero":
				hud.set_round("Round %d" % ev.round)
				_refresh_statuses()
				return 0.15
			hud.set_round("Enemy turn")
			return 0.3
		"act":
			if v == null:
				return 0.0
			var to: UnitView = views.get(ev.get("to", -1))
			var c := Color(ev.get("color", "")) if ev.get("color", "") != "" and not str(ev.color).begins_with("rgb") else v.color
			match ev.style:
				"melee":
					Audio.sfx("swing")
					v.lunge(to.base_pos if to else (Arena.ENEMY_CENTER if v.side == "hero" else Arena.HERO_CENTER))
					return 0.17
				"ranged":
					Audio.sfx("throw")
					_projectile(v.center_pos(), to.center_pos() if to else _side_center(v.side, true), c)
					return 0.22
				"pet":
					Audio.sfx("throw")
					var dest := to.center_pos() if to else _side_center(v.side, true)
					_projectile(v.global_position + Vector3(0, 0.3, 0), dest, Color("#d9a066") if ev.get("pet", "") == "bruno" else Color("#555555"), 0.18)
					return 0.22
				_:
					Audio.sfx("magic")
					v.cast_pulse(c)
					if to and to != v:
						_projectile(v.center_pos(), to.center_pos(), c)
					return 0.28
		"dmg":
			hp_shown[ev.uid] = ev.hp
			Audio.sfx("crit" if ev.crit else {"poison": "poison", "burn": "burn", "boom": "boom"}.get(ev.kind, "hit"))
			var p := hud.plate(ev.uid)
			if p:
				p.set_hp(ev.hp, ev.shield)
			if v:
				v.hit_flash(ev.crit)
				var col: Color = DMG_COLORS.get(ev.kind, Color.WHITE)
				if ev.crit:
					col = Color("#ffd23f")
					_punch()
				_float(v, str(ev.amount) + ("!" if ev.crit else ""), col, 1.35 if ev.crit else 1.0)
			return 0.07
		"heal":
			hp_shown[ev.uid] = ev.hp
			Audio.sfx("heal")
			var p := hud.plate(ev.uid)
			if p:
				p.set_hp(ev.hp, p.shield)
			if v:
				_float(v, "+%d" % ev.amount, Color("#5effc8"))
			return 0.05
		"shield":
			Audio.sfx("shield")
			var p := hud.plate(ev.uid)
			if p:
				p.set_hp(hp_shown.get(ev.uid, 0), ev.shield)
			return 0.04
		"miss":
			Audio.sfx("miss")
			if v:
				_float(v, ev.text, Color("#c8cbe0"), 0.85)
			return 0.12
		"status":
			var snd := _status_sound(ev.text)
			if snd != "":
				Audio.sfx(snd)
			if v:
				_float(v, ev.text, Color(ev.color), 0.75)
				if ev.text == "Away":
					v.set_away(true)
			_refresh_chips(ev.uid)
			return 0.1
		"say":
			if v:
				_bubble(v, ev.text)
			var u := b.unit(ev.uid)
			hud.message("[b]%s:[/b] %s" % [u.name, ev.text])
			return 0.5
		"cast":
			var u := b.unit(ev.uid)
			hud.message("%s used [b]%s[/b]!" % [u.name, ev.name])
			if ev.ult:
				Audio.sfx("ult")
			if ev.ult and v:
				v.play("ultimate")
				_punch(0.8)
			return 0.6 if ev.ult else 0.42
		"death":
			var u := b.unit(ev.uid)
			Audio.sfx("faint")
			if v:
				v.faint()
			var p := hud.plate(ev.uid)
			if p:
				p.set_hp(0, 0)
				p.set_dead(true)
			hud.message("%s fainted!" % u.name)
			return 0.5
		"revive":
			Audio.sfx("revive")
			if v:
				v.revive()
			var p := hud.plate(ev.uid)
			if p:
				p.set_dead(false)
				p.set_hp(ev.hp, 0)
			hp_shown[ev.uid] = ev.hp
			return 0.4
		"aoe":
			Audio.sfx("aoe")
			var rgb: PackedStringArray = str(ev.color).split(",")
			if rgb.size() == 3:
				hud.flash(Color8(int(rgb[0]), int(rgb[1]), int(rgb[2])), 0.28)
			return 0.08
		"shake":
			_shake = maxf(_shake, ev.power * 0.025)
			return 0.0
		"banner":
			Audio.sfx("banner")
			hud.banner(ev.text, ev.get("sub", ""))
			return 1.0
		"model":
			if v:
				v.set_model(ev.model)
				v.set_away(false)
			return 0.2
		"fx":
			match ev.kind:
				"truck", "subaru":
					Audio.sfx("car")
					_drive_by(Color("#4fc3ff") if ev.kind == "truck" else Color("#2e5cb8"))
				"wife":
					Audio.sfx("hearts")
					if v:
						for i in 6:
							_float(v, "<3", Color("#ff7ae0"), 0.9)
			return 0.7
		"resource":
			var p := hud.plate(ev.uid)
			var u := b.unit(ev.uid)
			if p and u:
				p.set_resource(ev.mp if u.max_mp > 0 else ev.energy, u.max_mp if u.max_mp > 0 else u.max_energy)
			return 0.0
		"popup":
			Audio.sfx("popup")
			state = State.POPUP
			hud.hide_commands()
			hud.show_popup(ev, Game.settings.get("popup_timer", 1.0))
			if auto:
				_auto_popup()
			return 0.0
		"spawn":
			if views.has(ev.uid):
				return 0.0 # already on stage (spawned before the first frame)
			var u := b.unit(ev.uid)
			Audio.sfx("spawn")
			_add_unit(u)
			hud.message("%s appeared!" % u.name)
			return 0.4
	return 0.0


func _auto_popup() -> void:
	await get_tree().create_timer(0.9).timeout
	if hud.popup_open():
		hud._answer("dismiss" if randf() < BattleAI.POPUP_DISMISS else "timeout")


func _side_center(side: String, opposite: bool) -> Vector3:
	var hero_side := (side == "hero") != opposite
	return (Arena.HERO_CENTER if hero_side else Arena.ENEMY_CENTER) + Vector3(0, 0.8, 0)


func _refresh_statuses() -> void:
	for id in hud.plates:
		_refresh_chips(id)


func _refresh_chips(uid: int) -> void:
	var u := b.unit(uid) if b else null
	var p := hud.plate(uid)
	if u == null or p == null:
		return
	var chips := []
	for s in u.statuses:
		var inf: Dictionary = StatusInfo.INFO.get(s.kind, {})
		if inf.is_empty() or inf.get("hidden", false):
			continue
		chips.append({"short": inf.short, "color": inf.color, "good": inf.good})
	if u.key == "sales_guy" and b.mog > 0:
		chips.push_front({"short": "AURA %d" % b.mog, "color": "#e0d0ff", "good": true})
	p.set_statuses(chips)
	var v: UnitView = views.get(uid)
	if v:
		v.set_stunned(b.has(u, "stun"))


# ------------------------------------------------------------------ effects
func _float(v: UnitView, text: String, color: Color, size := 1.0) -> void:
	var l := Label3D.new()
	l.text = text
	l.font_size = int(64 * size)
	l.outline_size = 16
	l.outline_modulate = UITheme.INK
	l.modulate = color
	l.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	l.no_depth_test = true
	l.pixel_size = 0.006
	add_child(l)
	# Stack numbers that land close together so they don't overlap: each new one
	# goes higher and alternates sides. Far-away units need bigger steps.
	var now := Time.get_ticks_msec()
	if now - v.last_float_ms > 600:
		v.float_stack = 0
	v.last_float_ms = now
	var step := 0.35 + 0.05 * cam.global_position.distance_to(v.global_position) / 4.0
	var side := -1.0 if v.float_stack % 2 == 0 else 1.0
	l.global_position = v.head_pos() + Vector3(side * 0.25 * mini(v.float_stack, 1), step * v.float_stack, 0)
	v.float_stack = (v.float_stack + 1) % 4
	var tw := create_tween().set_parallel()
	tw.tween_property(l, "global_position:y", l.global_position.y + 0.9, 0.9).set_ease(Tween.EASE_OUT)
	tw.tween_property(l, "modulate:a", 0.0, 0.9).set_delay(0.35)
	tw.chain().tween_callback(l.queue_free)


func _bubble(v: UnitView, text: String) -> void:
	if is_instance_valid(v.bubble):
		v.bubble.queue_free()
	var l := Label3D.new()
	v.bubble = l
	l.text = text
	l.font_size = 42
	l.outline_size = 14
	l.outline_modulate = UITheme.INK
	l.modulate = Color.WHITE
	l.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	l.no_depth_test = true
	l.pixel_size = 0.005
	l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	l.width = 520
	add_child(l)
	l.global_position = v.head_pos() + Vector3(0, 0.45, 0)
	var tw := create_tween()
	tw.tween_interval(1.8)
	tw.tween_property(l, "modulate:a", 0.0, 0.3)
	tw.tween_callback(l.queue_free)


func _projectile(from: Vector3, to: Vector3, color: Color, radius := 0.12) -> void:
	var m := MeshInstance3D.new()
	var s := SphereMesh.new()
	s.radius = radius
	s.height = radius * 2
	m.mesh = s
	var mat := StandardMaterial3D.new()
	mat.albedo_color = color
	mat.emission_enabled = true
	mat.emission = color
	mat.emission_energy_multiplier = 1.5
	m.material_override = mat
	add_child(m)
	m.global_position = from
	var tw := create_tween()
	tw.tween_property(m, "global_position", to, 0.2).set_trans(Tween.TRANS_SINE)
	tw.tween_callback(m.queue_free)


## Nissan Titan / Subaru Drive-by: a car tears across the enemy side.
func _drive_by(color: Color) -> void:
	var car := Node3D.new()
	var body := MeshInstance3D.new()
	var bm := BoxMesh.new()
	bm.size = Vector3(2.2, 0.9, 1.1)
	body.mesh = bm
	var mat := StandardMaterial3D.new()
	mat.albedo_color = color
	mat.emission_enabled = true
	mat.emission = color * 0.4
	body.material_override = mat
	body.position.y = 0.6
	car.add_child(body)
	add_child(car)
	var z := Arena.ENEMY_CENTER.z + 0.8
	car.global_position = Vector3(-9, 0, z)
	var tw := create_tween()
	tw.tween_property(car, "global_position:x", 12.0, 0.7)
	tw.tween_callback(car.queue_free)
	_shake = maxf(_shake, 0.2)


func _punch(strength := 1.0) -> void:
	var tw := create_tween()
	tw.tween_property(cam, "fov", CAM_FOV - 4 * strength, 0.06)
	tw.tween_property(cam, "fov", CAM_FOV, 0.25)


func _update_camera(delta: float) -> void:
	if cam == null:
		return
	_shake = maxf(0.0, _shake - delta * 0.6)
	var t := Time.get_ticks_msec() / 1000.0
	var sway := Vector3(sin(t * 0.3) * 0.12, sin(t * 0.23) * 0.05, 0)
	var jitter := Vector3(randf_range(-1, 1), randf_range(-1, 1), 0) * _shake
	cam.position = CAM_POS + sway + jitter


# ------------------------------------------------------------------ after the fight
func _on_over() -> void:
	hud.hide_commands()
	hud.set_round("")
	var win := b.outcome == "win"
	Audio.play_music("victory" if win else "gameover", 0.0)
	hud.banner("VICTORY!" if win else "DEFEATED", "", UITheme.ACCENT if win else UITheme.HP_RED)
	for id in views:
		var won_side := "hero" if win else "enemy"
		if views[id].side == won_side:
			views[id].celebrate()
	await get_tree().create_timer(1.4).timeout
	if not Game.test_fight.is_empty():
		await overlay.notice("Victory!" if win else "Defeated", ["Test fight over. %d rounds." % b.round])
		Game.test_fight = {}
		Game.go_title()
		return
	var run := Game.run
	var meta := Game.meta
	if not win:
		if Run.use_second_wind(run, meta):
			Game.save()
			await overlay.notice("Second Wind!", ["The party gets back up at 40% health."])
			Game.go_battle()
			return
		var over := Run.game_over(run, meta)
		var rec := Game.record_run()
		Game.run = {}
		Game.save()
		var lines := ["Made it to %s (stage %d)." % [info.title, run.stage + 1], "Fights won: %d   Kills: %d" % [run.fights_won, run.kills],
			"Village Sauce earned this run: %d" % run.sauce_earned]
		if over.catch_up > 0:
			lines.append("+%d Village Sauce for trying." % over.catch_up)
		if rec.rank >= 0:
			lines.append("Hall of Fame: #%d" % (rec.rank + 1))
		await overlay.notice("Game Over", lines, "Back to title")
		Game.go_title()
		return
	var res := Run.finish_fight(run, b, meta)
	var rng := Run.run_rng(run)
	run.pending = {"kind": "draft", "step": 0, "total": res.picks, "options": Run.roll_draft(run, rng, 0, res.picks)}
	Run.save_rng(run, rng)
	Game.save()
	_post_fight(res)


## Loot, upgrade picks, the shop and maybe a random event. Resumable: each step is
## saved in run.pending, so closing the app mid-way picks up where it left off.
func _post_fight(res: Dictionary) -> void:
	state = State.OVER
	var run := Game.run
	var meta := Game.meta
	if not res.is_empty():
		var lines := ["+%d PTO Hours" % res.pto]
		if res.sauce > 0:
			lines.append("+%d Village Sauce!" % res.sauce)
		if not res.weapon.is_empty():
			lines.append("New weapon for %s: %s" % [HeroData.HEROES[res.weapon.hero].name, HeroData.WEAPONS[res.weapon.id].name])
		if res.full_heal:
			lines.append("The party is healed to full.")
		for a in res.unlocked:
			lines.append("Achievement: %s" % a.name)
			for o in Outfits.for_achievement(a.id):
				lines.append("   New skin: %s (%s)" % [o.name, HeroData.HEROES[o.hero].name])
		await overlay.notice("Victory!", lines)
	while run.get("pending", {}).get("kind", "") == "draft":
		var p: Dictionary = run.pending
		var opts: Array = p.options
		var cards := opts.map(func(u):
			var t := Run.upgrade_text(u)
			return {"title": t.title, "desc": t.desc, "tag": "Ability" if u.kind == "rank" else "Stat"})
		var i: int = await overlay.choose("Pick an upgrade (%d of %d)" % [p.step + 1, p.total], cards)
		Run.apply_upgrade(run, meta, opts[i])
		var rng := Run.run_rng(run)
		if p.step + 1 < p.total:
			run.pending = {"kind": "draft", "step": p.step + 1, "total": p.total, "options": Run.roll_draft(run, rng, p.step + 1, p.total)}
		else:
			run.pending = {"kind": "shop", "items": Run.roll_shop(run, meta, rng)}
		Run.save_rng(run, rng)
		Game.save()
	if run.get("pending", {}).get("kind", "") == "shop":
		await overlay.shop(run, meta, run.pending.items)
		var ev := Run.advance(run)
		run.pending = {"kind": "event", "id": ev.id} if not ev.is_empty() else {}
		Game.save()
	if run.get("pending", {}).get("kind", "") == "event":
		var ev := RunEvents.by_id(run.pending.id)
		var i: int = await overlay.event(ev)
		RunEvents.apply(ev.id, i, run, meta)
		var lines := [ev.choices[i].result]
		for a in Achievements.check_all({"meta": meta, "event": "%s:%d" % [ev.id, i]}):
			lines.append("Achievement: %s" % a.name)
		run.pending = {}
		Game.save()
		await overlay.notice(ev.title, lines)
	run.pending = {}
	Game.save()
	Game.go_overworld()
