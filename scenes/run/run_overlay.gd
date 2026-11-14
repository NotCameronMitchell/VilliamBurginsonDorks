class_name RunOverlay
extends Control
## Full-screen panels between fights: notices (loot, game over), upgrade cards, the
## Break Room Shop and random events. Each function shows its panel and returns when
## the player is done, so the caller can just `await` it.

signal _done(value: int)

var _dim: ColorRect
var _panel: PanelContainer
var _body: VBoxContainer


func _ready() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	theme = UITheme.make()
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	_dim = ColorRect.new()
	_dim.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_dim.color = Color(0.05, 0.05, 0.1, 0.6)
	_dim.visible = false
	add_child(_dim)
	_panel = PanelContainer.new()
	_panel.set_anchors_preset(Control.PRESET_CENTER)
	_panel.grow_horizontal = Control.GROW_DIRECTION_BOTH
	_panel.grow_vertical = Control.GROW_DIRECTION_BOTH
	_panel.custom_minimum_size = Vector2(760, 0)
	_panel.add_theme_stylebox_override("panel", UITheme.box(UITheme.PANEL, UITheme.INK, 20, 5, 22))
	_panel.visible = false
	add_child(_panel)
	_body = VBoxContainer.new()
	_body.add_theme_constant_override("separation", 12)
	_panel.add_child(_body)


func _open(title: String) -> void:
	for c in _body.get_children():
		c.queue_free()
	_dim.visible = true
	_panel.visible = true
	mouse_filter = Control.MOUSE_FILTER_STOP
	var t := UITheme.label(title, 34, UITheme.INK)
	t.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_body.add_child(t)


func _close() -> void:
	_dim.visible = false
	_panel.visible = false
	mouse_filter = Control.MOUSE_FILTER_IGNORE


func _big_button(text: String, value: int) -> Button:
	var b := Button.new()
	b.text = text
	b.custom_minimum_size = Vector2(0, 56)
	b.add_theme_font_size_override("font_size", 22)
	b.pressed.connect(func(): _done.emit(value))
	return b


func _auto(value: int) -> void:
	if Game.auto_play:
		await get_tree().create_timer(1.2).timeout
		if _panel.visible:
			_done.emit(value)


## A message with a Continue button.
func notice(title: String, lines: Array, button := "Continue") -> void:
	_open(title)
	for l in lines:
		var lb := UITheme.label(l, 22, UITheme.DARK)
		lb.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		lb.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		_body.add_child(lb)
	_body.add_child(_big_button(button, 0))
	_auto(0)
	await _done
	_close()


## Pick one of a few cards: [{title, desc, tag}]. Returns the index.
func choose(title: String, cards: Array) -> int:
	_open(title)
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 14)
	_body.add_child(row)
	for i in cards.size():
		var c: Dictionary = cards[i]
		var b := Button.new()
		b.custom_minimum_size = Vector2(230, 230)
		b.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		UITheme.tint_button(b, UITheme.SUPPORT if c.tag == "Stat" else UITheme.ACCENT)
		var v := VBoxContainer.new()
		v.set_anchors_preset(Control.PRESET_FULL_RECT)
		v.offset_left = 12
		v.offset_right = -12
		v.offset_top = 12
		v.offset_bottom = -12
		v.mouse_filter = Control.MOUSE_FILTER_IGNORE
		b.add_child(v)
		var tag := UITheme.label(c.tag.to_upper(), 14, UITheme.DARK)
		tag.mouse_filter = Control.MOUSE_FILTER_IGNORE
		v.add_child(tag)
		var t := UITheme.label(c.title, 22)
		t.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		t.mouse_filter = Control.MOUSE_FILTER_IGNORE
		v.add_child(t)
		var d := UITheme.label(c.desc, 16, UITheme.DARK)
		d.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		d.size_flags_vertical = Control.SIZE_EXPAND_FILL
		d.mouse_filter = Control.MOUSE_FILTER_IGNORE
		v.add_child(d)
		b.pressed.connect(func(): _done.emit(i))
		row.add_child(b)
	_auto(0)
	var picked: int = await _done
	_close()
	return picked


## The Break Room Shop. Buying applies right away; returns when the player leaves.
func shop(run: Dictionary, meta: Dictionary, items: Array) -> void:
	_open("Break Room Shop")
	var pto := UITheme.label("", 22, UITheme.DARK)
	pto.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_body.add_child(pto)
	var list := VBoxContainer.new()
	list.add_theme_constant_override("separation", 6)
	_body.add_child(list)
	var rows := []
	for item in items:
		var h := HBoxContainer.new()
		h.add_theme_constant_override("separation", 10)
		var v := VBoxContainer.new()
		v.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		v.add_child(UITheme.label(item.name, 20))
		var d := UITheme.label(item.desc, 15, UITheme.DARK)
		d.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		d.custom_minimum_size = Vector2(520, 0)
		v.add_child(d)
		h.add_child(v)
		var buy := Button.new()
		buy.custom_minimum_size = Vector2(130, 48)
		buy.pressed.connect(func():
			if Run.buy_item(run, meta, item):
				Game.save()
				_refresh_shop(run, rows, pto))
		h.add_child(buy)
		list.add_child(h)
		rows.append([item, buy])
	_refresh_shop(run, rows, pto)
	_body.add_child(_big_button("Back to work", 0))
	_auto(0)
	await _done
	_close()


func _refresh_shop(run: Dictionary, rows: Array, pto: Label) -> void:
	pto.text = "PTO Hours: %d" % run.pto
	for r in rows:
		var item: Dictionary = r[0]
		var b: Button = r[1]
		b.text = "Sold" if item.sold else "%d PTO" % item.cost
		b.disabled = item.sold or run.pto < item.cost


## A random event: shows the scene and the choices. Returns the choice index.
func event(ev: Dictionary) -> int:
	_open(ev.title)
	var t := UITheme.label(ev.text, 22, UITheme.DARK)
	t.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	t.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_body.add_child(t)
	for i in ev.choices.size():
		var b := _big_button(ev.choices[i].label, i)
		if ev.choices[i].get("style", "") == "accept":
			UITheme.tint_button(b, UITheme.SUPPORT)
		elif ev.choices[i].get("style", "") == "decline":
			UITheme.tint_button(b, UITheme.HP_RED)
		_body.add_child(b)
	_auto(0)
	var picked: int = await _done
	_close()
	return picked
