extends Node
## Autoload "Audio": music and sound effects (made by art/audio/make_audio.py).
## - play_music("battle") crossfades to a track. Loops repeat; the jingles (victory,
##   gameover) play once.
## - sfx("hit") plays a sound from a small pool, with a little pitch variety.
## - Every button clicks by itself.
## Volumes come from Game.settings (music_volume, sfx_volume: 0 to 1). The --mute test
## option silences everything (for playtests).

const MUSIC_DIR := "res://assets/audio/music/"
const SFX_DIR := "res://assets/audio/sfx/"
const LOOPS := ["title", "office", "battle", "boss", "final"]
const POOL := 12

var current := "" ## the track playing (or last played)
var _music: Array[AudioStreamPlayer] = []
var _active := 0
var _pool: Array[AudioStreamPlayer] = []
var _next := 0
var _cache := {}
var _last_played := {} ## sound -> msec, so one event doesn't stack the same sound


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	for bus in ["Music", "SFX"]:
		if AudioServer.get_bus_index(bus) < 0:
			AudioServer.add_bus()
			var i := AudioServer.bus_count - 1
			AudioServer.set_bus_name(i, bus)
			AudioServer.set_bus_send(i, "Master")
	for i in 2:
		var p := AudioStreamPlayer.new()
		p.bus = "Music"
		add_child(p)
		_music.append(p)
	for i in POOL:
		var p := AudioStreamPlayer.new()
		p.bus = "SFX"
		add_child(p)
		_pool.append(p)
	apply_volumes()
	get_tree().node_added.connect(_on_node_added)


## Applies the music and sound volumes from Game.settings (call after changing them).
func apply_volumes() -> void:
	AudioServer.set_bus_mute(0, "--mute" in OS.get_cmdline_user_args())
	_set_bus("Music", float(Game.settings.get("music_volume", 0.8)))
	_set_bus("SFX", float(Game.settings.get("sfx_volume", 1.0)))


func _set_bus(bus: String, v: float) -> void:
	var i := AudioServer.get_bus_index(bus)
	AudioServer.set_bus_mute(i, v <= 0.001)
	AudioServer.set_bus_volume_db(i, linear_to_db(maxf(v, 0.001)))


## Crossfades to `track` (a file in assets/audio/music). Same track: keeps playing.
func play_music(track: String, fade := 0.8) -> void:
	if track == current and _music[_active].playing:
		return
	var stream := _load(MUSIC_DIR + track + ".ogg")
	if stream == null:
		return
	if stream is AudioStreamOggVorbis:
		stream.loop = track in LOOPS
	current = track
	var old := _music[_active]
	_active = 1 - _active
	var p := _music[_active]
	p.stream = stream
	p.volume_db = -30.0 if fade > 0.0 else 0.0
	p.play()
	var tw := create_tween().set_parallel()
	if fade > 0.0:
		tw.tween_property(p, "volume_db", 0.0, fade)
	if old.playing:
		tw.tween_property(old, "volume_db", -40.0, maxf(fade, 0.05))
		tw.chain().tween_callback(old.stop)


func stop_music(fade := 0.8) -> void:
	current = ""
	var p := _music[_active]
	if not p.playing:
		return
	var tw := create_tween()
	tw.tween_property(p, "volume_db", -40.0, maxf(fade, 0.05))
	tw.tween_callback(p.stop)


## Plays a sound (a file in assets/audio/sfx). Quiet sounds: pass a negative volume_db.
func sfx(sound: String, volume_db := 0.0, pitch_jitter := 0.04) -> void:
	var now := Time.get_ticks_msec()
	if now - int(_last_played.get(sound, -1000)) < 40:
		return
	var stream := _load(SFX_DIR + sound + ".wav")
	if stream == null:
		return
	_last_played[sound] = now
	var p: AudioStreamPlayer = null
	for q in _pool:
		if not q.playing:
			p = q
			break
	if p == null:  # all busy: take over the oldest
		p = _pool[_next]
		_next = (_next + 1) % _pool.size()
	p.stream = stream
	p.volume_db = volume_db
	p.pitch_scale = 1.0 + randf_range(-pitch_jitter, pitch_jitter)
	p.play()


func _load(path: String) -> AudioStream:
	if not _cache.has(path):
		_cache[path] = load(path) if ResourceLoader.exists(path) else null
		if _cache[path] == null:
			push_warning("Audio: missing %s" % path)
	return _cache[path]


func _exit_tree() -> void:  # let go of the streams, so nothing is left over at exit
	for p in _music + _pool:
		p.stop()
		p.stream = null
	_cache.clear()


func _on_node_added(n: Node) -> void:
	if n is BaseButton and not n.has_meta("audio_hooked"):
		n.set_meta("audio_hooked", true)
		(n as BaseButton).pressed.connect(func(): sfx("click", -3.0, 0.02))
