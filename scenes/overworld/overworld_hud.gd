class_name OverworldHUD
extends Control
## The overworld UI: progress and party health (top-left), the objective and a
## location sign (top-center), Menu (top-right), the dialogue box (bottom), the
## context button for talking (bottom-right) and a virtual joystick on touch
## screens (bottom-left).

signal advanced ## tapped through a line of dialogue
signal interact_pressed
signal quit_pressed

var stick := Vector2.ZERO ## virtual joystick, -1..1 each axis
var _progress: Label
var _pto: Label
var _party: VBoxContainer
var _objective: Label
var _toast: PanelContainer
var _toast_label: Label
var _dialog: PanelContainer
var _speaker: Label
var _text: RichTextLabel
var _prompt: Button
var _fade: ColorRect
var _menu: PanelContainer
var _joystick: Joystick
var _dialog_open := false
var _text_tween: Tween


func _ready() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	theme = UITheme.make()
	_build()


func _build() -> void:
	# Top-left: progress and party
	var info := PanelContainer.new()
	info.position = Vector2(14, 12)
	info.custom_minimum_size = Vector2(270, 0)
	info.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(info)
	var iv := VBoxContainer.new()
	iv.add_theme_constant_override("separation", 3)
	info.add_child(iv)
	_progress = UITheme.label("", 18)
	iv.add_child(_progress)
	_pto = UITheme.label("", 14, UITheme.DARK)
	iv.add_child(_pto)
	_party = VBoxContainer.new()
	_party.add_theme_constant_override("separation", 2)
	iv.add_child(_party)

	_objective = UITheme.label("", 20, Color.WHITE, 8)
	_objective.set_anchors_and_offsets_preset(Control.PRESET_CENTER_TOP)
	_objective.offset_top = 14
	_objective.grow_horizontal = Control.GROW_DIRECTION_BOTH
	_objective.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	add_child(_objective)

	_toast = PanelContainer.new()
	_toast.add_theme_stylebox_override("panel", UITheme.box(UITheme.INK, UITheme.ACCENT, 12, 4, 10))
	_toast.set_anchors_and_offsets_preset(Control.PRESET_CENTER_TOP)
	_toast.offset_top = 52
	_toast.grow_horizontal = Control.GROW_DIRECTION_BOTH
	_toast.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_toast.modulate.a = 0.0
	add_child(_toast)
	_toast_label = UITheme.label("", 26, UITheme.ACCENT)
	_toast.add_child(_toast_label)

	var menu_btn := Button.new()
	menu_btn.text = "Menu"
	menu_btn.custom_minimum_size = Vector2(100, 46)
	menu_btn.set_anchors_and_offsets_preset(Control.PRESET_TOP_RIGHT)
	menu_btn.offset_left = -116
	menu_btn.offset_right = -16
	menu_btn.offset_top = 14
	menu_btn.offset_bottom = 60
	menu_btn.pressed.connect(func(): _menu.visible = not _menu.visible)
	add_child(menu_btn)

	# Bottom: dialogue
	_dialog = PanelContainer.new()
	_dialog.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_WIDE)
	_dialog.offset_left = 120
	_dialog.offset_right = -120
	_dialog.offset_top = -170
	_dialog.offset_bottom = -16
	_dialog.visible = false
	_dialog.gui_input.connect(func(ev):
		if ev is InputEventMouseButton and ev.pressed and ev.button_index == MOUSE_BUTTON_LEFT:
			_tap())
	add_child(_dialog)
	var dv := VBoxContainer.new()
	_dialog.add_child(dv)
	_speaker = UITheme.label("", 18, Color("#c0392b"))
	dv.add_child(_speaker)
	_text = RichTextLabel.new()
	_text.bbcode_enabled = true
	_text.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_text.mouse_filter = Control.MOUSE_FILTER_IGNORE
	dv.add_child(_text)
	var more := UITheme.label("tap to continue", 14, UITheme.MUTED)
	more.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	dv.add_child(more)

	# Bottom-right: context button
	_prompt = Button.new()
	_prompt.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_RIGHT)
	_prompt.offset_left = -330
	_prompt.offset_right = -18
	_prompt.offset_top = -86
	_prompt.offset_bottom = -18
	_prompt.add_theme_font_size_override("font_size", 20)
	UITheme.tint_button(_prompt, UITheme.ACCENT, 8)
	_prompt.visible = false
	_prompt.pressed.connect(func(): interact_pressed.emit())
	add_child(_prompt)

	# Bottom-left: joystick (touch screens)
	_joystick = Joystick.new()
	_joystick.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_LEFT)
	_joystick.offset_left = 24
	_joystick.offset_right = 224
	_joystick.offset_top = -224
	_joystick.offset_bottom = -24
	_joystick.visible = DisplayServer.is_touchscreen_available() or OS.get_cmdline_user_args().has("--touch")
	_joystick.moved.connect(func(v): stick = v)
	add_child(_joystick)

	_menu = PanelContainer.new()
	_menu.set_anchors_preset(Control.PRESET_CENTER)
	_menu.grow_horizontal = Control.GROW_DIRECTION_BOTH
	_menu.grow_vertical = Control.GROW_DIRECTION_BOTH
	_menu.visible = false
	add_child(_menu)
	var mv := VBoxContainer.new()
	mv.add_theme_constant_override("separation", 10)
	_menu.add_child(mv)
	mv.add_child(UITheme.label("Paused", 28))
	for row in SettingsRows.sound_rows():
		mv.add_child(row)
	var quit := Button.new()
	quit.text = "Save and quit to title"
	quit.custom_minimum_size = Vector2(320, 56)
	quit.pressed.connect(func(): quit_pressed.emit())
	mv.add_child(quit)
	var close := Button.new()
	close.text = "Back to the office"
	close.custom_minimum_size = Vector2(320, 56)
	close.pressed.connect(func(): _menu.visible = false)
	mv.add_child(close)

	_fade = ColorRect.new()
	_fade.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_fade.color = Color(0, 0, 0, 1)
	_fade.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_fade)


# ------------------------------------------------------------------ info
func set_progress(cycle: int, beaten: int, pto: int) -> void:
	_progress.text = "Cycle %d    Bosses %d/3" % [cycle + 1, beaten]
	_pto.text = "PTO Hours: %d" % pto


func set_party(run: Dictionary, meta: Dictionary) -> void:
	for c in _party.get_children():
		c.queue_free()
	for h in run.heroes:
		var row := HBoxContainer.new()
		row.add_theme_constant_override("separation", 6)
		var n := UITheme.label(HeroData.HEROES[h.id].name, 14)
		n.custom_minimum_size = Vector2(56, 0)
		row.add_child(n)
		var bar := UnitPlate.Bar.new()
		var mx: int = Run.hero_stats(h, meta).max_hp
		bar.frac = float(h.hp) / maxf(1.0, mx)
		bar.fill = UITheme.hp_color(bar.frac)
		bar.custom_minimum_size = Vector2(130, 10)
		bar.size_flags_vertical = Control.SIZE_SHRINK_CENTER
		row.add_child(bar)
		row.add_child(UITheme.label("%d/%d" % [h.hp, mx], 12, UITheme.DARK))
		_party.add_child(row)


func set_objective(text: String) -> void:
	_objective.text = text


## A location sign that slides in when you enter a room.
func toast(text: String) -> void:
	_toast_label.text = text
	var tw := create_tween()
	tw.tween_property(_toast, "modulate:a", 1.0, 0.2)
	tw.tween_interval(1.6)
	tw.tween_property(_toast, "modulate:a", 0.0, 0.4)


func show_prompt(text: String) -> void:
	_prompt.text = text
	_prompt.visible = true


func hide_prompt() -> void:
	_prompt.visible = false


func menu_open() -> bool:
	return _menu.visible


# ------------------------------------------------------------------ dialogue
## Shows a line and returns when the player taps through it.
func say(speaker: String, text: String) -> void:
	_dialog.visible = true
	_dialog_open = true
	_speaker.text = speaker
	_speaker.visible = speaker != ""
	_text.text = text
	_text.visible_ratio = 0.0
	Audio.sfx("blip", -4.0)
	if _text_tween:
		_text_tween.kill()
	var speed: float = Game.settings.get("text_speed", 1.0)
	_text_tween = create_tween()
	_text_tween.tween_property(_text, "visible_ratio", 1.0, clampf(text.length() * 0.018 / speed, 0.1, 1.2))
	if Game.auto_play:
		await get_tree().create_timer(1.1).timeout
	else:
		await advanced
	_dialog_open = false
	_dialog.visible = false


func dialog_open() -> bool:
	return _dialog_open


func _unhandled_input(ev: InputEvent) -> void:
	if not _dialog_open:
		return
	var tap: bool = ev is InputEventMouseButton and ev.pressed and ev.button_index == MOUSE_BUTTON_LEFT
	if tap or ev.is_action_pressed("ui_accept") or ev.is_action_pressed("interact"):
		_tap()
		get_viewport().set_input_as_handled()


func _tap() -> void:
	if not _dialog_open:
		return
	if _text.visible_ratio < 1.0:
		_text_tween.kill()
		_text.visible_ratio = 1.0
		return
	advanced.emit()


# ------------------------------------------------------------------ fades
func fade_in() -> void:
	var tw := create_tween()
	tw.tween_property(_fade, "color:a", 0.0, 0.4)
	await tw.finished


func fade_out() -> void:
	var tw := create_tween()
	tw.tween_property(_fade, "color:a", 1.0, 0.35)
	await tw.finished


## A virtual joystick: drag inside the circle.
class Joystick extends Control:
	signal moved(v: Vector2)
	var _v := Vector2.ZERO
	var _active := false

	func _ready() -> void:
		mouse_filter = Control.MOUSE_FILTER_STOP

	func _gui_input(ev: InputEvent) -> void:
		if ev is InputEventMouseButton and ev.button_index == MOUSE_BUTTON_LEFT:
			_active = ev.pressed
			if ev.pressed:
				_track(ev.position)
			else:
				_apply(Vector2.ZERO)
			accept_event()
		elif ev is InputEventMouseMotion and _active:
			_track(ev.position)
			accept_event()

	func _track(p: Vector2) -> void:
		var c := size / 2.0
		var v := (p - c) / (size.x / 2.0)
		_apply(v.limit_length(1.0))

	func _apply(v: Vector2) -> void:
		_v = v
		moved.emit(v)
		queue_redraw()

	func _draw() -> void:
		var c := size / 2.0
		var r := size.x / 2.0
		draw_circle(c, r, Color(1, 1, 1, 0.25))
		draw_arc(c, r, 0, TAU, 48, Color(0.1, 0.1, 0.18, 0.6), 3.0)
		draw_circle(c + _v * r * 0.6, r * 0.38, Color(1, 1, 1, 0.75))
