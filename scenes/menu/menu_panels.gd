class_name MenuPanels
extends Control
## The main-menu screens, shown over the title: Suit Up (party and skins), the
## Sauce Shop (permanent upgrades), Achievements and the Hall of Fame.

signal start_run(party: Array)
signal closed
signal changed ## something was bought or worn: the title refreshes its heroes

var _dim: ColorRect
var _panel: PanelContainer
var _body: VBoxContainer
var _sauce_label: Label
var _party: Array = []
var _preview := {} ## hero id -> index of the outfit being looked at
var _cards: GridContainer
var _start_btn: Button
var _party_label: Label


func _ready() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	theme = UITheme.make()
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	_dim = ColorRect.new()
	_dim.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_dim.color = Color(0.05, 0.05, 0.12, 0.55)
	_dim.visible = false
	add_child(_dim)
	_panel = PanelContainer.new()
	_panel.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_panel.offset_left = 24
	_panel.offset_right = -24
	_panel.offset_top = 20
	_panel.offset_bottom = -20
	_panel.add_theme_stylebox_override("panel", UITheme.box(UITheme.PANEL, UITheme.INK, 20, 5, 16))
	_panel.visible = false
	add_child(_panel)
	_body = VBoxContainer.new()
	_body.add_theme_constant_override("separation", 10)
	_panel.add_child(_body)


func is_open() -> bool:
	return _panel.visible


## Common frame: title on the left, Village Sauce and Back on the right.
func _open(title: String) -> void:
	for c in _body.get_children():
		c.queue_free()
	_dim.visible = true
	_panel.visible = true
	mouse_filter = Control.MOUSE_FILTER_STOP
	var head := HBoxContainer.new()
	head.add_theme_constant_override("separation", 12)
	_body.add_child(head)
	var t := UITheme.label(title, 32)
	t.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	head.add_child(t)
	_sauce_label = UITheme.label("", 20, Color("#c0392b"))
	head.add_child(_sauce_label)
	var back := Button.new()
	back.text = "Back"
	back.custom_minimum_size = Vector2(110, 46)
	back.pressed.connect(close)
	head.add_child(back)
	_sync_sauce()


func close() -> void:
	_dim.visible = false
	_panel.visible = false
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	closed.emit()


func _sync_sauce() -> void:
	if _sauce_label:
		_sauce_label.text = "Village Sauce: %d" % Game.meta.sauce


func _scroll() -> VBoxContainer:
	var sc := ScrollContainer.new()
	sc.size_flags_vertical = Control.SIZE_EXPAND_FILL
	sc.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	_body.add_child(sc)
	var v := VBoxContainer.new()
	v.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	v.add_theme_constant_override("separation", 8)
	sc.add_child(v)
	return v


func _row_panel(bg := Color.WHITE) -> PanelContainer:
	var p := PanelContainer.new()
	p.add_theme_stylebox_override("panel", UITheme.box(bg, UITheme.INK, 12, 3, 10))
	return p


# ------------------------------------------------------------------ Suit Up
## Party (any 4 of 6) and skins. Start begins a new run with them.
func open_suit_up() -> void:
	_open("Suit Up")
	_party = Game.default_party().duplicate()
	_cards = GridContainer.new()
	_cards.columns = 3
	_cards.add_theme_constant_override("h_separation", 10)
	_cards.add_theme_constant_override("v_separation", 10)
	_cards.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_body.add_child(_cards)
	for id in HeroData.HERO_IDS:
		var list := Outfits.for_hero(id)
		var worn := Outfits.outfit_of(id, Game.meta.outfits)
		_preview[id] = maxi(0, list.find(worn))
	var foot := HBoxContainer.new()
	foot.add_theme_constant_override("separation", 12)
	_body.add_child(foot)
	_party_label = UITheme.label("", 20, UITheme.DARK)
	_party_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	foot.add_child(_party_label)
	_start_btn = Button.new()
	_start_btn.text = "Start run"
	_start_btn.custom_minimum_size = Vector2(260, 56)
	_start_btn.add_theme_font_size_override("font_size", 24)
	UITheme.tint_button(_start_btn, UITheme.ACCENT)
	_start_btn.pressed.connect(func():
		close()
		start_run.emit(_party))
	foot.add_child(_start_btn)
	_refresh_suit_up()


func _refresh_suit_up() -> void:
	for c in _cards.get_children():
		c.queue_free()
	for id in HeroData.HERO_IDS:
		_cards.add_child(_hero_card(id))
	_party_label.text = "Party: %s  (%d of 4)" % [", ".join(_party.map(func(p): return HeroData.HEROES[p].name)), _party.size()]
	_start_btn.disabled = _party.size() != HeroData.PARTY_SIZE
	_sync_sauce()


func _hero_card(id: String) -> Control:
	var d: Dictionary = HeroData.HEROES[id]
	var in_party := _party.has(id)
	var list := Outfits.for_hero(id)
	var o: Dictionary = list[_preview[id]]
	var st := Outfits.status(Game.meta, o)
	var card := PanelContainer.new()
	card.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	card.size_flags_vertical = Control.SIZE_EXPAND_FILL
	card.add_theme_stylebox_override("panel", UITheme.box(Color("#fff6d6") if in_party else Color.WHITE,
		UITheme.ACCENT if in_party else UITheme.INK, 14, 5 if in_party else 3, 10))
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 5)
	card.add_child(v)

	var top := HBoxContainer.new()
	v.add_child(top)
	var swatch := ColorRect.new()
	swatch.custom_minimum_size = Vector2(34, 34)
	swatch.color = UnitView.skin_tint(Color(d.color), Outfits.model_of(o))
	top.add_child(swatch)
	var names := VBoxContainer.new()
	names.add_theme_constant_override("separation", -4)
	names.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	names.add_child(UITheme.label(d.name, 22))
	names.add_child(UITheme.label(d.role, 14, UITheme.MUTED))
	top.add_child(names)
	var pick := Button.new()
	pick.text = "In party" if in_party else "Add"
	pick.custom_minimum_size = Vector2(104, 40)
	pick.add_theme_font_size_override("font_size", 16)
	if in_party:
		UITheme.tint_button(pick, UITheme.SUPPORT)
	pick.disabled = not in_party and _party.size() >= HeroData.PARTY_SIZE
	pick.pressed.connect(func():
		if _party.has(id):
			_party.erase(id)
		elif _party.size() < HeroData.PARTY_SIZE:
			_party.append(id)
		_refresh_suit_up())
	top.add_child(pick)

	# Skin picker: < name >
	var skin := HBoxContainer.new()
	v.add_child(skin)
	var prev := Button.new()
	prev.text = "<"
	prev.custom_minimum_size = Vector2(44, 40)
	prev.pressed.connect(func():
		_preview[id] = (_preview[id] - 1 + list.size()) % list.size()
		_refresh_suit_up())
	skin.add_child(prev)
	var sn := UITheme.label(o.name, 19)
	sn.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	sn.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	sn.clip_text = true
	skin.add_child(sn)
	var next := Button.new()
	next.text = ">"
	next.custom_minimum_size = Vector2(44, 40)
	next.pressed.connect(func():
		_preview[id] = (_preview[id] + 1) % list.size()
		_refresh_suit_up())
	skin.add_child(next)
	var count := UITheme.label("Skin %d of %d" % [_preview[id] + 1, list.size()], 13, UITheme.MUTED)
	count.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	v.add_child(count)

	var desc := UITheme.label(o.desc, 15, UITheme.DARK)
	desc.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	desc.size_flags_vertical = Control.SIZE_EXPAND_FILL
	v.add_child(desc)

	var act := Button.new()
	act.custom_minimum_size = Vector2(0, 44)
	act.add_theme_font_size_override("font_size", 16)
	match st:
		"wearing":
			act.text = "Wearing"
			act.disabled = true
		"owned":
			act.text = "Wear"
			UITheme.tint_button(act, UITheme.SUPPORT)
			act.pressed.connect(func():
				Outfits.equip(Game.meta, o)
				Game.save()
				changed.emit()
				_refresh_suit_up())
		"buy":
			act.text = "Buy for %d Sauce" % o.cost
			UITheme.tint_button(act, UITheme.ACCENT)
			act.disabled = Game.meta.sauce < o.cost
			act.pressed.connect(func():
				if Outfits.buy(Game.meta, o):
					Outfits.equip(Game.meta, o)
					Game.save()
					changed.emit()
				_refresh_suit_up())
		_:
			var a := Achievements.by_id(o.achievement)
			act.text = "Locked: %s" % a.name
			act.tooltip_text = a.desc
			act.disabled = true
			desc.text = "%s\nUnlock: %s" % [o.desc, a.desc]
	v.add_child(act)
	return card


# ------------------------------------------------------------------ Sauce Shop
func open_sauce_shop() -> void:
	_open("Sauce Shop")
	var hint := UITheme.label("Village Sauce comes from beating the crew at Villiam Burginson's. These upgrades last forever.", 16, UITheme.DARK)
	hint.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_body.add_child(hint)
	var list := _scroll()
	for u in MetaUpgrades.LIST:
		list.add_child(_upgrade_row(u.id))


func _upgrade_row(id: String) -> Control:
	var p := _row_panel()
	var h := HBoxContainer.new()
	h.add_theme_constant_override("separation", 12)
	p.add_child(h)
	var l := MetaUpgrades.level(Game.meta, id)
	var mx := MetaUpgrades.max_level(id)
	var v := VBoxContainer.new()
	v.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	h.add_child(v)
	var name := ""
	for u in MetaUpgrades.LIST:
		if u.id == id:
			name = u.name
	var title := HBoxContainer.new()
	title.add_child(UITheme.label(name, 21))
	var lv := UITheme.label("   Level %d / %d" % [l, mx], 16, UITheme.MUTED)
	title.add_child(lv)
	v.add_child(title)
	var now := "Now: %s" % (MetaUpgrades.describe(id, l) if l > 0 else "nothing yet")
	var nxt := "   Next: %s" % MetaUpgrades.describe(id, l + 1) if l < mx else "   Maxed out"
	var d := UITheme.label(now + nxt, 15, UITheme.DARK)
	d.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	v.add_child(d)
	var pips := HBoxContainer.new()
	pips.add_theme_constant_override("separation", 3)
	for i in mx:
		var pip := ColorRect.new()
		pip.custom_minimum_size = Vector2(22, 8)
		pip.color = UITheme.ACCENT if i < l else Color("#dddddd")
		pips.add_child(pip)
	v.add_child(pips)
	var buy := Button.new()
	buy.custom_minimum_size = Vector2(170, 52)
	if l >= mx:
		buy.text = "Maxed"
		buy.disabled = true
	else:
		var c := MetaUpgrades.cost(id, l)
		buy.text = "%d Sauce" % c
		buy.disabled = Game.meta.sauce < c
		UITheme.tint_button(buy, UITheme.ACCENT)
		buy.pressed.connect(func():
			if MetaUpgrades.buy(Game.meta, id):
				Game.save()
				changed.emit()
				open_sauce_shop())
	h.add_child(buy)
	return p


# ------------------------------------------------------------------ Achievements
func open_achievements() -> void:
	var got: Array = Game.meta.achievements
	_open("Achievements  %d / %d" % [got.size(), Achievements.LIST.size()])
	var list := _scroll()
	for a in Achievements.LIST:
		var done := got.has(a.id)
		var p := _row_panel(Color("#eafbe9") if done else Color("#f2f2f5"))
		var h := HBoxContainer.new()
		h.add_theme_constant_override("separation", 12)
		p.add_child(h)
		var mark := UITheme.label("✓" if done else "?", 26, UITheme.HP_GREEN.darkened(0.3) if done else UITheme.MUTED)
		mark.custom_minimum_size = Vector2(30, 0)
		mark.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		h.add_child(mark)
		var v := VBoxContainer.new()
		v.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		v.add_theme_constant_override("separation", 0)
		h.add_child(v)
		v.add_child(UITheme.label(a.name, 20, UITheme.INK if done else UITheme.DARK))
		v.add_child(UITheme.label(a.desc, 15, UITheme.DARK))
		var skins := Outfits.for_achievement(a.id)
		if not skins.is_empty():
			var names := {}
			for o in skins:
				names[o.name] = names.get(o.name, []) + [HeroData.HEROES[o.hero].name]
			var parts := []
			for n in names:
				parts.append("%s (%s)" % [n, "everyone" if names[n].size() >= HeroData.HERO_IDS.size() else ", ".join(names[n])])
			var r := UITheme.label("Unlocks: " + "; ".join(parts), 14, Color("#8e44ad"))
			r.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
			v.add_child(r)
		list.add_child(p)


# ------------------------------------------------------------------ Hall of Fame
func open_hall_of_fame() -> void:
	_open("Hall of Fame")
	var meta: Dictionary = Game.meta
	_body.add_child(UITheme.label("Each run is listed by how far it got.", 15, UITheme.MUTED))
	var stats := UITheme.label("Runs: %d    Best: stage %d    Village Sauce earned all-time: %d" % [meta.runs, meta.best_stage + 1 if meta.runs > 0 else 0, meta.total_sauce], 17, UITheme.DARK)
	_body.add_child(stats)
	var board := SaveGame.load_board(Game.save_dir)
	var list := _scroll()
	if board.is_empty():
		list.add_child(UITheme.label("No finished runs yet. Go get the sauce.", 20, UITheme.MUTED))
		return
	for i in board.size():
		var e: Dictionary = board[i]
		var p := _row_panel(Color("#fff6d6") if i == 0 else Color.WHITE)
		var h := HBoxContainer.new()
		h.add_theme_constant_override("separation", 16)
		p.add_child(h)
		var rank := UITheme.label("#%d" % (i + 1), 24)
		rank.custom_minimum_size = Vector2(54, 0)
		h.add_child(rank)
		var info := Run.stage_info(int(e.stage))
		var where := UITheme.label("Cycle %d, %s" % [info.cycle + 1, "Villiam Burginson's" if info.kind == "bonus" else ("boss %d" % (info.index / 2 + 1) if info.kind == "boss" else "office %d" % (info.index / 2 + 1))], 19)
		where.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		h.add_child(where)
		var party: Array = e.get("party", [])
		h.add_child(UITheme.label(", ".join(party.map(func(id): return HeroData.HEROES[id].name if HeroData.HEROES.has(id) else id)), 15, UITheme.DARK))
		h.add_child(UITheme.label("%d fights  %d kills  %d sauce" % [e.fights, e.kills, e.sauce], 15, UITheme.DARK))
		h.add_child(UITheme.label(Time.get_date_string_from_unix_time(int(e.date)), 14, UITheme.MUTED))
		list.add_child(p)
