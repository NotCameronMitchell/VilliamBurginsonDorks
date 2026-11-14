class_name SaveGame
extends RefCounted
## Saves to the device (user://): meta progress, the run in progress, and the
## Hall of Fame. Plain JSON, one file each. Every function fails quietly: if storage
## isn't available the game still plays, it just doesn't remember.

const DIR := "user://"
const META := "meta.json"
const RUN := "run.json"
const BOARD := "board.json"
const BOARD_SIZE := 25


static func fresh_meta() -> Dictionary:
	return {
		"version": 1, "sauce": 0, "total_sauce": 0, "upgrades": {}, "runs": 0, "best_stage": 0,
		"outfits": {}, "owned_outfits": [], "party": [], "achievements": [], "stats": {},
	}


static func load_meta(dir := DIR) -> Dictionary:
	var m := fresh_meta()
	var saved = _read(dir + META)
	if saved is Dictionary:
		m.merge(saved, true)
	return m


static func save_meta(meta: Dictionary, dir := DIR) -> void:
	_write(dir + META, meta)


## The run in progress, or {} if there isn't one (or it's from an older version).
static func load_run(dir := DIR) -> Dictionary:
	var r = _read(dir + RUN)
	return r if r is Dictionary and r.get("version", 0) == Run.VERSION else {}


static func save_run(run: Dictionary, dir := DIR) -> void:
	if run.is_empty():
		DirAccess.remove_absolute(dir + RUN)
	else:
		_write(dir + RUN, run)


static func load_board(dir := DIR) -> Array:
	var b = _read(dir + BOARD)
	return b if b is Array else []


## Adds a finished run to the Hall of Fame. Returns {board, rank} (rank -1 if it
## didn't make the cut).
static func record_run(run: Dictionary, dir := DIR) -> Dictionary:
	var entry := {"stage": run.stage, "fights": run.fights_won, "kills": run.kills,
		"sauce": run.sauce_earned, "date": int(Time.get_unix_time_from_system()),
		"party": run.heroes.map(func(h): return h.id)}
	var board := load_board(dir)
	board.append(entry)
	board.sort_custom(func(a, b): return a.stage > b.stage or (a.stage == b.stage and a.kills > b.kills))
	board = board.slice(0, BOARD_SIZE)
	_write(dir + BOARD, board)
	return {"board": board, "rank": board.find(entry)}


static func _read(path: String) -> Variant:
	if not FileAccess.file_exists(path):
		return null
	var f := FileAccess.open(path, FileAccess.READ)
	if f == null:
		return null
	var data = JSON.parse_string(f.get_as_text())
	return _ints(data) if data != null else null


static func _write(path: String, data: Variant) -> void:
	var f := FileAccess.open(path, FileAccess.WRITE)
	if f:
		f.store_string(JSON.stringify(data, "\t"))


## JSON has no integers, so whole numbers load back as floats (2 becomes 2.0).
## Turn them back into ints so stages, ranks and counters compare and index cleanly.
static func _ints(v: Variant) -> Variant:
	if v is float and v == floor(v) and absf(v) < 9.0e15:
		return int(v)
	if v is Array:
		return v.map(func(x): return _ints(x))
	if v is Dictionary:
		var out := {}
		for k in v:
			out[k] = _ints(v[k])
		return out
	return v
