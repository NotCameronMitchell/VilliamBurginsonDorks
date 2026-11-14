class_name BattleHUD
extends Control
## The battle UI, laid out for a landscape phone or a PC window (1280x720 base):
##   enemy plates top-left, hero plates on the right, the text box bottom-left and
##   the move menu bottom-right (thumb reach), Auto / speed / settings top-right.
## It only shows things and reports what the player picked; BattleScene decides.

signal action_picked(action_id: String)
signal hero_picked(uid: int)
signal wait_picked
signal back_picked
signal plate_pressed(uid: int)
signal auto_toggled(on: bool)
signal popup_answered(choice: String)
signal advanced ## the player tapped through a line of dialogue

var plates := {} ## uid -> UnitPlate
var _enemy_box: VBoxContainer
var _hero_box: VBoxContainer
var _text: RichTextLabel
var _speaker: Label
var _more: Label
var _cmd_panel: PanelContainer
var _prompt: Label
var _tabs: HBoxContainer
var _grid: GridContainer
var _row: HBoxContainer
var _info: PanelContainer
var _info_text: RichTextLabel
var _banner: PanelContainer
var _banner_title: Label
var _banner_sub: Label
var _round: Label
var _flash: ColorRect
var _popup: PanelContainer
var _popup_bar: ProgressBar
var _popup_left := 0.0
var _popup_total := 0.0
var _settings: PanelContainer
var _auto_btn: Button
var _speed_btn: Button
var _dialog_mode := false
var _text_tween: Tween
var _long_press: Timer
var _suppress_press := false
var _press_btn: Button
var _press_info := ""


func _ready() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	theme = UITheme.make()
	_build()


# ------------------------------------------------------------------ layout
func _build() -> void:
	_flash = ColorRect.new()
	_flash.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_flash.color = Color(1, 1, 1, 0)
	_flash.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_flash)

	_enemy_box = VBoxContainer.new()
	_enemy_box.position = Vector2(16, 14)
	_enemy_box.add_theme_constant_override("separation", 6)
	add_child(_enemy_box)

	_hero_box = VBoxContainer.new()
	_hero_box.set_anchors_preset(Control.PRESET_TOP_RIGHT)
	_hero_box.offset_left = -316
	_hero_box.offset_right = -16
	_hero_box.offset_top = 150
	_hero_box.add_theme_constant_override("separation", 6)
	add_child(_hero_box)

	_round = UITheme.label("", 22, Color.WHITE, 8)
	_round.set_anchors_preset(Control.PRESET_CENTER_TOP)
	_round.offset_top = 14
	_round.grow_horizontal = Control.GROW_DIRECTION_BOTH
	_round.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	add_child(_round)

	var top_btns := HBoxContainer.new()
	top_btns.set_anchors_preset(Control.PRESET_TOP_RIGHT)
	top_btns.offset_left = -316
	top_btns.offset_right = -16
	top_btns.offset_top = 14
	top_btns.alignment = BoxContainer.ALIGNMENT_END
	add_child(top_btns)
	_auto_btn = _button("Auto", func(): auto_toggled.emit(_auto_btn.button_pressed))
	_auto_btn.toggle_mode = true
	top_btns.add_child(_auto_btn)
	_speed_btn = _button("1x", _toggle_speed)
	top_btns.add_child(_speed_btn)
	top_btns.add_child(_button("Settings", func(): _settings.visible = not _settings.visible))
	_sync_speed()

	# Bottom strip: text box + move menu.
	var bottom := HBoxContainer.new()
	bottom.set_anchors_preset(Control.PRESET_BOTTOM_WIDE)
	bottom.offset_top = -206
	bottom.offset_left = 12
	bottom.offset_right = -12
	bottom.offset_bottom = -12
	bottom.add_theme_constant_override("separation", 10)
	add_child(bottom)

	var text_panel := PanelContainer.new()
	text_panel.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	text_panel.size_flags_stretch_ratio = 1.15
	text_panel.mouse_filter = Control.MOUSE_FILTER_STOP
	text_panel.gui_input.connect(_on_text_input)
	bottom.add_child(text_panel)
	var tv := VBoxContainer.new()
	text_panel.add_child(tv)
	_speaker = UITheme.label("", 18, Color("#c0392b"))
	_speaker.visible = false
	tv.add_child(_speaker)
	_text = RichTextLabel.new()
	_text.bbcode_enabled = true
	_text.fit_content = false
	_text.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_text.mouse_filter = Control.MOUSE_FILTER_IGNORE
	tv.add_child(_text)
	_more = UITheme.label("tap to continue", 14, UITheme.MUTED)
	_more.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	_more.visible = false
	tv.add_child(_more)

	_cmd_panel = PanelContainer.new()
	_cmd_panel.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_cmd_panel.size_flags_stretch_ratio = 1.25
	_cmd_panel.add_theme_stylebox_override("panel", UITheme.box(UITheme.PANEL, UITheme.INK, 14, 4, 7))
	bottom.add_child(_cmd_panel)
	var cv := VBoxContainer.new()
	cv.add_theme_constant_override("separation", 4)
	_cmd_panel.add_child(cv)
	var head := HBoxContainer.new()
	cv.add_child(head)
	_prompt = UITheme.label("", 16)
	_prompt.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	head.add_child(_prompt)
	_tabs = HBoxContainer.new()
	_tabs.add_theme_constant_override("separation", 4)
	head.add_child(_tabs)
	_grid = GridContainer.new()
	_grid.columns = 2
	_grid.add_theme_constant_override("h_separation", 6)
	_grid.add_theme_constant_override("v_separation", 5)
	cv.add_child(_grid)
	_row = HBoxContainer.new()
	_row.add_theme_constant_override("separation", 6)
	cv.add_child(_row)
	_cmd_panel.visible = false

	_info = PanelContainer.new()
	_info.set_anchors_preset(Control.PRESET_BOTTOM_RIGHT)
	_info.offset_left = -560
	_info.offset_right = -12
	_info.offset_top = -330
	_info.offset_bottom = -214
	_info.visible = false
	_info.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_info)
	_info_text = RichTextLabel.new()
	_info_text.bbcode_enabled = true
	_info_text.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_info_text.add_theme_font_size_override("normal_font_size", 17)
	_info_text.add_theme_font_size_override("bold_font_size", 18)
	_info.add_child(_info_text)

	_long_press = Timer.new()
	_long_press.one_shot = true
	_long_press.wait_time = 0.45
	_long_press.timeout.connect(func():
		if is_instance_valid(_press_btn) and _press_btn.is_pressed():
			_suppress_press = true
			_show_info(_press_info))
	add_child(_long_press)

	_build_banner()
	_build_popup()
	_build_settings()


func _button(text: String, cb: Callable) -> Button:
	var b := Button.new()
	b.text = text
	b.custom_minimum_size = Vector2(0, 44)
	b.pressed.connect(cb)
	return b


func _build_banner() -> void:
	_banner = PanelContainer.new()
	_banner.add_theme_stylebox_override("panel", UITheme.box(UITheme.INK, UITheme.ACCENT, 18, 5, 16))
	_banner.set_anchors_preset(Control.PRESET_CENTER)
	_banner.grow_horizontal = Control.GROW_DIRECTION_BOTH
	_banner.grow_vertical = Control.GROW_DIRECTION_BOTH
	_banner.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_banner.visible = false
	add_child(_banner)
	var v := VBoxContainer.new()
	_banner.add_child(v)
	_banner_title = UITheme.label("", 48, UITheme.ACCENT, 6)
	_banner_title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	v.add_child(_banner_title)
	_banner_sub = UITheme.label("", 22, Color.WHITE)
	_banner_sub.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	v.add_child(_banner_sub)


func _build_popup() -> void:
	_popup = PanelContainer.new()
	_popup.add_theme_stylebox_override("panel", UITheme.box(Color("#f4f6fb"), Color("#1b1b2f"), 10, 4, 18))
	_popup.set_anchors_preset(Control.PRESET_CENTER)
	_popup.custom_minimum_size = Vector2(520, 0)
	_popup.grow_horizontal = Control.GROW_DIRECTION_BOTH
	_popup.grow_vertical = Control.GROW_DIRECTION_BOTH
	_popup.visible = false
	add_child(_popup)


func _build_settings() -> void:
	_settings = PanelContainer.new()
	_settings.set_anchors_preset(Control.PRESET_TOP_RIGHT)
	_settings.offset_left = -380
	_settings.offset_right = -16
	_settings.offset_top = 70
	_settings.visible = false
	add_child(_settings)
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 8)
	_settings.add_child(v)
	v.add_child(UITheme.label("Settings", 22))
	v.add_child(SettingsRows.option_row("Copilot pop-up timer", [["Normal", 1.0], ["Long", 1.6], ["Off", 0.0]], "popup_timer"))
	v.add_child(SettingsRows.option_row("Text speed", [["Normal", 1.0], ["Fast", 2.0]], "text_speed"))
	for row in SettingsRows.sound_rows():
		v.add_child(row)
	v.add_child(_button("Close", func(): _settings.visible = false))


func _toggle_speed() -> void:
	Game.settings.battle_speed = 2.0 if Game.settings.battle_speed < 2.0 else 1.0
	Game.save()
	_sync_speed()


func _sync_speed() -> void:
	_speed_btn.text = "%dx" % int(Game.settings.get("battle_speed", 1.0))


func set_auto(on: bool) -> void:
	_auto_btn.button_pressed = on


# ------------------------------------------------------------------ plates
func add_plate(u: BattleUnit) -> UnitPlate:
	var p := UnitPlate.new()
	(_hero_box if u.side == "hero" else _enemy_box).add_child(p)
	p.setup(u)
	p.pressed.connect(func(id): plate_pressed.emit(id))
	plates[u.uid] = p
	return p


func plate(uid: int) -> UnitPlate:
	return plates.get(uid)


# ------------------------------------------------------------------ text
## A battle line ("Cole used Golf Lesson!"). Doesn't wait for a tap.
func message(text: String) -> void:
	_dialog_mode = false
	_speaker.visible = false
	_more.visible = false
	_type(text)


## A line of story dialogue: waits for a tap (emits `advanced`).
func dialog(speaker: String, text: String) -> void:
	_dialog_mode = true
	_speaker.text = speaker
	_speaker.visible = speaker != ""
	_more.visible = true
	Audio.sfx("blip", -4.0)
	_type(text)


func _type(text: String) -> void:
	_text.text = text
	_text.visible_ratio = 0.0
	if _text_tween:
		_text_tween.kill()
	var speed: float = Game.settings.get("text_speed", 1.0)
	_text_tween = create_tween()
	_text_tween.tween_property(_text, "visible_ratio", 1.0, clampf(text.length() * 0.018 / speed, 0.1, 1.2))


func _on_text_input(ev: InputEvent) -> void:
	if ev is InputEventMouseButton and ev.pressed and ev.button_index == MOUSE_BUTTON_LEFT:
		_tap_text()


func _unhandled_input(ev: InputEvent) -> void:
	if _dialog_mode and (ev.is_action_pressed("ui_accept") or (ev is InputEventMouseButton and ev.pressed and ev.button_index == MOUSE_BUTTON_LEFT)):
		_tap_text()
		get_viewport().set_input_as_handled()


func _tap_text() -> void:
	if not _dialog_mode:
		return
	if _text.visible_ratio < 1.0:
		_text_tween.kill()
		_text.visible_ratio = 1.0
		return
	_dialog_mode = false
	_more.visible = false
	advanced.emit()


func set_round(text: String) -> void:
	_round.text = text


# ------------------------------------------------------------------ commands
const TYPE_COLOR := {"damage": UITheme.DAMAGE, "support": UITheme.SUPPORT, "ult": UITheme.ULT}


## Shows the move menu for one hero. ready_heroes: units that can still act.
func show_commands(b: Battle, u: BattleUnit, ready_heroes: Array) -> void:
	_cmd_panel.visible = true
	_info.visible = false
	_prompt.text = "What will %s do?" % u.name
	for c in _tabs.get_children() + _grid.get_children() + _row.get_children():
		c.queue_free()
	if ready_heroes.size() > 1:
		for h in ready_heroes:
			var t := Button.new()
			t.text = h.name
			t.custom_minimum_size = Vector2(0, 30)
			t.add_theme_font_size_override("font_size", 14)
			t.add_theme_stylebox_override("normal", UITheme.box(Color.WHITE, UITheme.INK, 10, 2, 4))
			if h == u:
				UITheme.tint_button(t, UITheme.ACCENT)
			t.pressed.connect(func(): hero_picked.emit(h.uid))
			_tabs.add_child(t)
	var opts := b.actions(u)
	for o in opts:
		if o.kind == "ability":
			_grid.add_child(_move_button(u, o))
	for o in opts:
		if o.kind != "ability":
			_row.add_child(_move_button(u, o))
	var wait := _button("Wait", func(): wait_picked.emit())
	wait.custom_minimum_size = Vector2(70, 42)
	wait.add_theme_font_size_override("font_size", 15)
	_row.add_child(wait)


func _move_button(u: BattleUnit, o: Dictionary) -> Button:
	var b := Button.new()
	b.custom_minimum_size = Vector2(0, 42)
	b.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	b.clip_text = true
	b.add_theme_font_size_override("font_size", 14)
	b.add_theme_constant_override("line_spacing", -3)
	var sub := ""
	if o.kind == "attack":
		sub = "Attack"
	elif not o.ready and o.cd_left > 0:
		sub = "%d turn%s" % [o.cd_left, "" if o.cd_left == 1 else "s"]
	elif o.cost > 0:
		sub = "%d %s" % [o.cost, "MP" if o.resource == "mp" else "Energy"]
	elif o.quick:
		sub = "Quick"
	b.text = "%s\n%s" % [o.name, sub] if sub != "" else o.name
	b.disabled = not o.ready
	var kind := "ult" if o.kind == "ultimate" else ("damage" if o.target in ["enemy", "enemies", "none"] else "support")
	UITheme.tint_button(b, TYPE_COLOR[kind])
	var info := "[b]%s[/b]%s\n%s" % [o.name, (" [color=#8a8fa8](rank %s)[/color]" % HeroData.roman(o.rank)) if o.rank > 0 else "", o.desc]
	b.mouse_entered.connect(func(): _show_info(info))
	b.mouse_exited.connect(func(): _info.visible = false)
	# Long-press shows the full description on touch screens without using the move.
	b.button_down.connect(func():
		_suppress_press = false
		_press_btn = b
		_press_info = info
		_long_press.start())
	b.button_up.connect(func(): _long_press.stop())
	b.pressed.connect(func():
		if _suppress_press:
			_suppress_press = false
			return
		_info.visible = false
		action_picked.emit(o.id))
	return b


func _show_info(text: String) -> void:
	_info_text.text = text
	_info.visible = true


func hide_commands() -> void:
	_cmd_panel.visible = false
	_info.visible = false


## Targeting: shows a Back button and highlights the plates of valid targets.
func begin_targeting(uids: Array, what: String) -> void:
	_prompt.text = "Choose %s" % what
	for c in _grid.get_children() + _row.get_children() + _tabs.get_children():
		c.queue_free()
	var back := _button("Back", func(): back_picked.emit())
	back.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_row.add_child(back)
	for id in plates:
		plates[id].set_targetable(uids.has(id))


func end_targeting() -> void:
	for id in plates:
		plates[id].set_targetable(false)


# ------------------------------------------------------------------ effects
func banner(title: String, sub := "", color := UITheme.ACCENT) -> void:
	_banner_title.text = title
	_banner_title.add_theme_color_override("font_color", color)
	_banner_sub.text = sub
	_banner_sub.visible = sub != ""
	_banner.visible = true
	_banner.pivot_offset = _banner.size / 2.0
	_banner.scale = Vector2(0.6, 0.6)
	_banner.modulate.a = 0.0
	var tw := create_tween()
	tw.set_parallel()
	tw.tween_property(_banner, "scale", Vector2.ONE, 0.18).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	tw.tween_property(_banner, "modulate:a", 1.0, 0.12)
	tw.chain().tween_interval(0.9 / Game.settings.get("battle_speed", 1.0))
	tw.chain().tween_property(_banner, "modulate:a", 0.0, 0.2)
	tw.chain().tween_callback(func(): _banner.visible = false)


func flash(color: Color, strength := 0.35) -> void:
	_flash.color = Color(color, strength)
	var tw := create_tween()
	tw.tween_property(_flash, "color:a", 0.0, 0.25)


# ------------------------------------------------------------------ Copilot pop-up
## ev: the battle's popup event. timer_mult: the player's setting (0 = no timer).
func show_popup(ev: Dictionary, timer_mult: float) -> void:
	for c in _popup.get_children():
		c.queue_free()
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 10)
	_popup.add_child(v)
	var head := HBoxContainer.new()
	v.add_child(head)
	head.add_child(UITheme.label("Copilot", 16, Color("#5b6b8c")))
	var t := UITheme.label(ev.text, 24, UITheme.INK)
	t.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	v.add_child(t)
	_popup_bar = ProgressBar.new()
	_popup_bar.show_percentage = false
	_popup_bar.custom_minimum_size = Vector2(0, 12)
	_popup_bar.max_value = 1.0
	_popup_bar.value = 1.0
	v.add_child(_popup_bar)
	var buttons := HBoxContainer.new()
	buttons.add_theme_constant_override("separation", 10)
	v.add_child(buttons)
	var dismiss := _button("Not now", func(): _answer("dismiss"))
	var install := _button("Yes, install", func(): _answer("install"))
	UITheme.tint_button(install, Color("#4f8cff"))
	var pair := [install, dismiss] if ev.swap else [dismiss, install]
	if ev.get("pro", false):
		var pro := _button("Upgrade to Pro", func(): _answer("pro"))
		UITheme.tint_button(pro, Color("#ffcc00"))
		pair.insert(1, pro)
	for b in pair:
		b.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		b.custom_minimum_size = Vector2(0, 56)
		buttons.add_child(b)
	_popup_total = ev.timer * timer_mult
	_popup_left = _popup_total
	_popup_bar.visible = _popup_total > 0
	_popup.visible = true
	_popup.pivot_offset = _popup.size / 2.0


func popup_open() -> bool:
	return _popup.visible


func _answer(choice: String) -> void:
	if not _popup.visible:
		return
	_popup.visible = false
	popup_answered.emit(choice)


func _process(delta: float) -> void:
	if _popup.visible and _popup_total > 0:
		_popup_left -= delta
		_popup_bar.value = _popup_left / _popup_total
		if _popup_left <= 0:
			_answer("timeout")
