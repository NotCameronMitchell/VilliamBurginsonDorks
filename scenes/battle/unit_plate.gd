class_name UnitPlate
extends PanelContainer
## A Pokemon-style name plate: name, HP bar that drains smoothly (green -> yellow ->
## red) with any shield shown past it, Sam's MP / Sarah's Energy, and status chips.

signal pressed(uid: int)


## A rounded bar drawn by hand so it can show HP and shield together.
class Bar extends Control:
	var frac := 1.0
	var extra := 0.0 ## shield, drawn after the fill
	var fill := UITheme.HP_GREEN
	var extra_color := UITheme.SHIELD

	func _draw() -> void:
		var r := Rect2(Vector2.ZERO, size)
		draw_rect(r, Color("#3a3d52"))
		var w := size.x * clampf(frac, 0.0, 1.0)
		if w > 0:
			draw_rect(Rect2(0, 0, w, size.y), fill)
			draw_rect(Rect2(0, 0, w, size.y * 0.35), fill.lightened(0.3))
		var e := size.x * clampf(extra, 0.0, 1.0 - clampf(frac, 0.0, 1.0))
		if e > 0:
			draw_rect(Rect2(w, 0, e, size.y), extra_color)
		draw_rect(r, UITheme.INK, false, 2.0)


var uid := 0
var max_hp := 1
var shown_hp := 0.0:
	set(v):
		shown_hp = v
		_refresh_hp()
var shield := 0
var _name: Label
var _tag: Label
var _hp_text: Label
var _bar: Bar
var _res_bar: Bar
var _chips: HBoxContainer
var _style: StyleBoxFlat
var _dead := false
var _active := false
var _target := false
var _pulse := 0.0


func setup(u: BattleUnit) -> void:
	uid = u.uid
	max_hp = u.max_hp
	custom_minimum_size = Vector2(300, 0)
	mouse_filter = Control.MOUSE_FILTER_STOP
	_style = UITheme.box(UITheme.PANEL, UITheme.INK, 12, 3, 8)
	add_theme_stylebox_override("panel", _style)
	_style.content_margin_top = 5
	_style.content_margin_bottom = 6
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 2)
	add_child(v)
	# Row 1: name, BOSS tag, status chips, HP numbers.
	var top := HBoxContainer.new()
	top.add_theme_constant_override("separation", 5)
	v.add_child(top)
	_name = UITheme.label(u.name, 18 if u.name.length() < 20 else 15)
	_name.clip_text = true
	_name.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	_name.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	top.add_child(_name)
	_tag = UITheme.label("BOSS" if u.boss else "", 12, Color("#c0392b"))
	_tag.visible = u.boss
	top.add_child(_tag)
	_chips = HBoxContainer.new()
	_chips.add_theme_constant_override("separation", 3)
	_chips.alignment = BoxContainer.ALIGNMENT_END
	top.add_child(_chips)
	_hp_text = UITheme.label("", 14, UITheme.DARK)
	_hp_text.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	top.add_child(_hp_text)
	# Row 2: HP bar (+ shield). Row 3: MP or Energy.
	_bar = Bar.new()
	_bar.custom_minimum_size = Vector2(0, 13)
	v.add_child(_bar)
	if u.max_mp > 0 or u.max_energy > 0:
		_res_bar = Bar.new()
		_res_bar.custom_minimum_size = Vector2(0, 6)
		_res_bar.fill = UITheme.MP if u.max_mp > 0 else UITheme.ENERGY
		v.add_child(_res_bar)
	shield = u.shield
	shown_hp = u.hp
	if u.max_mp > 0:
		set_resource(u.mp, u.max_mp)
	elif u.max_energy > 0:
		set_resource(u.energy, u.max_energy)
	set_dead(not u.alive)


func _gui_input(ev: InputEvent) -> void:
	if ev is InputEventMouseButton and ev.pressed and ev.button_index == MOUSE_BUTTON_LEFT:
		pressed.emit(uid)


func _process(delta: float) -> void:
	if _target:
		_pulse += delta * 6.0
		_style.border_color = UITheme.ACCENT.lerp(UITheme.INK, (sin(_pulse) + 1.0) * 0.25)


func set_hp(hp: int, new_shield: int, new_max := -1) -> void:
	if new_max > 0:
		max_hp = new_max
	shield = new_shield
	var tw := create_tween()
	tw.tween_property(self, "shown_hp", float(hp), 0.45).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)


func set_resource(value: float, max_value: float) -> void:
	if _res_bar:
		_res_bar.frac = value / maxf(1.0, max_value)
		_res_bar.queue_redraw()


func _refresh_hp() -> void:
	if _bar == null:
		return
	var f := shown_hp / maxf(1.0, max_hp)
	_bar.frac = f
	_bar.fill = UITheme.hp_color(f)
	_bar.extra = float(shield) / maxf(1.0, max_hp)
	_bar.queue_redraw()
	_hp_text.text = "%d/%d%s" % [roundi(shown_hp), max_hp, (" +%d" % shield) if shield > 0 else ""]


## chips: [{short, color, good}]
func set_statuses(chips: Array) -> void:
	for c in _chips.get_children():
		c.queue_free()
	for s in chips.slice(0, 4):
		var p := PanelContainer.new()
		var sb := UITheme.box(Color(s.color).lerp(Color.WHITE, 0.2) if s.good else Color(s.color), UITheme.INK, 6, 2, 2)
		sb.content_margin_left = 4
		sb.content_margin_right = 4
		sb.shadow_size = 0
		p.add_theme_stylebox_override("panel", sb)
		p.add_child(UITheme.label(s.short, 11))
		_chips.add_child(p)


func set_dead(dead: bool) -> void:
	_dead = dead
	modulate = Color(1, 1, 1, 0.45) if dead else Color.WHITE


func set_active(on: bool) -> void:
	_active = on
	_restyle()


func set_targetable(on: bool) -> void:
	_target = on and not _dead
	_restyle()


func _restyle() -> void:
	_style.bg_color = Color("#fff6d6") if _active else UITheme.PANEL
	_style.set_border_width_all(5 if (_active or _target) else 3)
	_style.border_color = UITheme.ACCENT if (_active or _target) else UITheme.INK
