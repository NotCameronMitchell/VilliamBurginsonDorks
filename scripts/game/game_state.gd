extends Node
## Autoload "Game": the meta progress, the run in progress and the settings, plus
## scene changes. Also handles the command-line test options:
##   --fight=<boss id|crew|minions>  jump straight into a test fight
##   --party=cole,cam,sam,sarah      the party for it (default: random 4)
##   --remix                         use the boss's remix
##   --auto                          the AI plays the heroes
##   --auto-click                    ...and clicks the after-fight screens like a player
##   --ult-first                     ultimates are ready from the first turn
##   --skip-story                    skip the dialogue before fights
##   --speed=<n>                     battle playback speed
##   --save-dir=<dir>                use a separate save profile (e.g. user://test/)
##   --menu=<suitup|shop|achievements|hall>  open that screen on the title
##   --shots=<dir> --shot-every=<s> --shot-count=<n>
##                                   save screenshots, then quit (for checking the UI)
##   --mute                          no music or sounds (for playtests)
## Pass them after "--", e.g.  godot --path . -- --fight=copilot --auto

const TITLE := "res://scenes/title/title.tscn"
const BATTLE := "res://scenes/battle/battle_scene.tscn"
const OVERWORLD := "res://scenes/overworld/overworld.tscn"
const DEFAULT_SETTINGS := {
	"popup_timer": 1.0, ## Copilot pop-up countdown multiplier; 0 = no timer
	"battle_speed": 1.0, ## 1 or 2
	"text_speed": 1.0,
	"music_volume": 0.8, ## 0 to 1
	"sfx_volume": 1.0, ## 0 to 1
}

var meta: Dictionary
var run: Dictionary
var settings: Dictionary
## A test fight from the command line: {enemies: [...], party: [...]}; empty in normal play.
var test_fight := {}
var auto_play := false
## --auto-click: auto-play presses on-screen buttons with real mouse clicks, like a player
## (so a button that can't be clicked gets the playtest stuck, as it would a person).
var auto_click := false
## --ult-first: ultimates are ready from the first turn (to test every hero's ultimate).
var ult_first := false
var skip_story := false
var save_dir := SaveGame.DIR
var open_menu := "" ## --menu=suitup|shop|achievements|hall opens that screen on the title

var _shots_dir := ""
var _shot_every := 1.5
var _shot_count := 12
var _shot_start := 0.0
var _shots_taken := 0


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--save-dir="):
			save_dir = a.trim_prefix("--save-dir=")
			DirAccess.make_dir_recursive_absolute(save_dir)
	_ensure_actions()
	meta = SaveGame.load_meta(save_dir)
	settings = DEFAULT_SETTINGS.duplicate()
	settings.merge(meta.get("settings", {}), true)
	run = SaveGame.load_run(save_dir)
	_parse_args()


func save() -> void:
	meta.settings = settings
	SaveGame.save_meta(meta, save_dir)
	SaveGame.save_run(run, save_dir)


func record_run() -> Dictionary:
	return SaveGame.record_run(run, save_dir)


func default_party() -> Array:
	var p: Array = meta.get("party", [])
	return p if p.size() == HeroData.PARTY_SIZE else HeroData.HERO_IDS.slice(0, HeroData.PARTY_SIZE)


func new_run(party: Array) -> void:
	meta.party = party
	var outfits := {}
	for id in party:
		var o := Outfits.outfit_of(id, meta.outfits)
		outfits[id] = o.id if Outfits.owns(meta, o) else Outfits.default_for(id).id
	run = Run.new_run(meta, randi(), party, outfits)
	meta.runs += 1
	save()


func go_title() -> void:
	get_tree().change_scene_to_file(TITLE)


func go_battle() -> void:
	get_tree().change_scene_to_file(BATTLE)


func go_overworld() -> void:
	get_tree().change_scene_to_file(OVERWORLD)


## Continue the saved run: back to the office, or to the after-fight screens if the
## app was closed in the middle of them.
func continue_run() -> void:
	if not run.get("pending", {}).is_empty():
		go_battle()
	else:
		go_overworld()


## Movement and interact controls: keyboard (WASD / arrows, E / Space / Enter) and
## gamepad (left stick / d-pad, A).
func _ensure_actions() -> void:
	var keys := {
		"move_left": [KEY_A, KEY_LEFT], "move_right": [KEY_D, KEY_RIGHT],
		"move_up": [KEY_W, KEY_UP], "move_down": [KEY_S, KEY_DOWN],
		"interact": [KEY_E, KEY_SPACE, KEY_ENTER],
	}
	var pads := {
		"move_left": [JOY_BUTTON_DPAD_LEFT], "move_right": [JOY_BUTTON_DPAD_RIGHT],
		"move_up": [JOY_BUTTON_DPAD_UP], "move_down": [JOY_BUTTON_DPAD_DOWN], "interact": [JOY_BUTTON_A],
	}
	var axes := {"move_left": [JOY_AXIS_LEFT_X, -1.0], "move_right": [JOY_AXIS_LEFT_X, 1.0],
		"move_up": [JOY_AXIS_LEFT_Y, -1.0], "move_down": [JOY_AXIS_LEFT_Y, 1.0]}
	for action in keys:
		if InputMap.has_action(action):
			continue
		InputMap.add_action(action, 0.25)
		for k in keys[action]:
			var ev := InputEventKey.new()
			ev.physical_keycode = k
			InputMap.action_add_event(action, ev)
		for btn in pads.get(action, []):
			var jb := InputEventJoypadButton.new()
			jb.button_index = btn
			InputMap.action_add_event(action, jb)
		if axes.has(action):
			var jm := InputEventJoypadMotion.new()
			jm.axis = axes[action][0]
			jm.axis_value = axes[action][1]
			InputMap.action_add_event(action, jm)


# ------------------------------------------------------------------ test options
func _parse_args() -> void:
	var args := {}
	for a in OS.get_cmdline_user_args():
		var kv := a.trim_prefix("--").split("=", true, 1)
		args[kv[0]] = kv[1] if kv.size() > 1 else "true"
	auto_play = args.has("auto")
	auto_click = args.has("auto-click")
	ult_first = args.has("ult-first")
	skip_story = args.has("skip-story")
	open_menu = args.get("menu", "")
	if args.has("speed"):
		settings.battle_speed = float(args.speed)
	if args.has("fight"):
		var f: String = args.fight
		var remix: bool = args.has("remix")
		var ids: Array
		if f == "crew":
			ids = EnemyData.BURGER_CREW.duplicate()
		elif f == "minions":
			ids = ["reply_all", "energy_drink", "close_talker"]
		else:
			ids = [f]
		var party: Array
		if args.has("party"):
			party = Array(args.party.split(","))
		else:
			party = HeroData.HERO_IDS.duplicate()
			party.shuffle()
			party = party.slice(0, 4)
		# Cycle-1 third-boss scaling, with the heroes a bit stronger to match.
		test_fight = {"party": party, "enemies": ids.map(func(id): return {"id": id, "hp_mult": 3.0, "atk_mult": 2.6, "remix": remix})}
	if args.has("shots"):
		_shots_dir = args.shots
		_shot_every = float(args.get("shot-every", "1.5"))
		_shot_count = int(args.get("shot-count", "12"))
		_shot_start = float(args.get("shot-start", "0"))
		DirAccess.make_dir_recursive_absolute(_shots_dir)
		_shoot_loop()


func _shoot_loop() -> void:
	if _shot_start > 0:
		await get_tree().create_timer(_shot_start).timeout
	while _shots_taken < _shot_count:
		await get_tree().create_timer(_shot_every).timeout
		await RenderingServer.frame_post_draw
		var img := get_viewport().get_texture().get_image()
		img.save_png("%s/shot_%02d.png" % [_shots_dir, _shots_taken])
		_shots_taken += 1
	get_tree().quit()
