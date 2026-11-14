extends SceneTree
## Headless test runner for the combat engine.
##   godot --headless --path . --script res://tests/run_tests.gd
## Add BALANCE=1 to the environment for the balance report.

var _fails := 0
var _passes := 0


func _init() -> void:
	test_rng()
	test_data()
	test_every_ability_and_weapon()
	test_determinism()
	test_sam_mana()
	test_sarah_bleeds()
	test_exposed()
	test_boss_stun_diminishing()
	test_party_combos_win()
	if OS.get_environment("BALANCE") == "1":
		balance_report()
	print("\n%d passed, %d failed" % [_passes, _fails])
	quit(1 if _fails > 0 else 0)


func check(cond: bool, what: String) -> void:
	if cond:
		_passes += 1
	else:
		_fails += 1
		printerr("FAIL: " + what)


func party(ids: Array) -> Array:
	return ids.map(func(id): return Battle.hero_setup(id))


func wave(ids: Array, hp := 1.0, atk := 1.0) -> Array:
	return ids.map(func(id): return {"id": id, "hp_mult": hp, "atk_mult": atk})


## A stand-in boss until the real bosses are ported: a beefy Pouch Tin.
func fake_boss(b: Battle) -> BattleUnit:
	var e: BattleUnit = b.enemies()[0]
	e.boss = true
	return e


# ------------------------------------------------------------------ tests
func test_rng() -> void:
	var a := Rng.new(42)
	var b := Rng.new(42)
	var same := true
	var in_range := true
	for i in 1000:
		var x := a.next()
		if x != b.next():
			same = false
		if x < 0.0 or x >= 1.0:
			in_range = false
	check(same, "rng: same seed gives the same sequence")
	check(in_range, "rng: values are in [0, 1)")
	check(Rng.new(1).next() != Rng.new(2).next(), "rng: different seeds differ")


func test_data() -> void:
	check(HeroData.HERO_IDS.size() == 6, "data: 6 heroes")
	for id in HeroData.HERO_IDS:
		var d: Dictionary = HeroData.HEROES[id]
		for ab in HeroData.rankable(id):
			check(HeroData.ABILITIES.has(ab), "data: %s ability %s exists" % [id, ab])
			if HeroData.ABILITIES.has(ab):
				check(HeroData.ABILITIES[ab].hero == id, "data: %s belongs to %s" % [ab, id])
				for r in range(1, HeroData.MAX_RANK + 1):
					check(HeroData.describe(ab, r) != "", "data: %s r%d has a description" % [ab, r])
		check(d.weapons.size() == 3, "data: %s has 3 weapons" % id)
		for w in d.weapons:
			check(HeroData.WEAPONS.has(w) and HeroData.WEAPONS[w].hero == id, "data: weapon %s belongs to %s" % [w, id])
		check(d.weapons[0] == HeroData.STARTING_WEAPON[id], "data: %s starts with their first weapon" % id)


## Every ability and weapon runs at every rank without errors and affects the fight.
func test_every_ability_and_weapon() -> void:
	for id in HeroData.HERO_IDS:
		var d: Dictionary = HeroData.HEROES[id]
		for r in [1, 3, 5]:
			for ab in d.abilities + [d.ultimate]:
				var setup := Battle.hero_setup(id)
				setup.ranks = {ab: r}
				var b := Battle.new([setup, Battle.hero_setup("james")], wave(["pouch_tin", "reply_all", "close_talker"], 3.0), 7)
				var u: BattleUnit = b.heroes()[0]
				u.cd[ab] = 0
				u.mp = u.max_mp
				u.energy = u.max_energy
				var foe: BattleUnit = b.enemies()[0]
				b.dot(u, foe, "bleed", 0.5, 3) # so detonations have something to hit
				var before := b.events.size()
				var ok := b.act(u.uid, ab, foe.uid)
				check(ok, "%s can use %s (r%d)" % [id, ab, r])
				check(b.events.size() > before, "%s %s (r%d) does something" % [id, ab, r])
		for w in d.weapons:
			var setup := Battle.hero_setup(id, w)
			var b := Battle.new([setup], wave(["pouch_tin", "reply_all"], 3.0), 11)
			var u: BattleUnit = b.heroes()[0]
			var before := b.events.size()
			check(b.act(u.uid, "attack", b.enemies()[0].uid), "%s can attack with %s" % [id, w])
			check(b.events.size() > before, "%s's %s does something" % [id, w])


func test_determinism() -> void:
	var run := func(seed: int) -> Array:
		var b := Battle.new(party(["sam", "sarah", "james", "cam"]), wave(["tallboy", "fish_guy", "loud_typer"], 2.0, 1.5), seed)
		var res := BattleAI.auto_battle(b)
		return [res, b.events.size(), b.round]
	check(run.call(123) == run.call(123), "determinism: same seed, same fight")


func test_sam_mana() -> void:
	var b := Battle.new(party(["sam"]), wave(["pouch_tin"], 20.0, 0.1), 5)
	var sam: BattleUnit = b.heroes()[0]
	check(sam.mp == 40.0, "sam: starts with 40 MP")
	check(b.act(sam.uid, "rage_bait", b.enemies()[0].uid), "sam: can cast Rage Bait")
	check(sam.mp == 10.0, "sam: Rage Bait costs 30 MP")
	check(sam.cd.get("rage_bait", 0) == 0, "sam: Rage Bait has no cooldown")
	b.enemy_step()
	b.enemy_step()
	check(b.phase == "hero" and b.round == 2, "sam: next round")
	check(sam.mp == 25.0, "sam: Booster Seat regenerates 15 MP")
	var rb: Dictionary = b.actions(sam).filter(func(a): return a.id == "rage_bait")[0]
	check(not rb.ready, "sam: can't cast Rage Bait without the MP")
	check(b.actions(sam).filter(func(a): return a.id == "energy_drinks_bad")[0].ready, "sam: can still afford a cheaper spell")
	check(HeroData.ability_cost("rage_bait", 5) == 22, "sam: ranks lower spell costs")


func test_sarah_bleeds() -> void:
	var b := Battle.new(party(["sarah"]), wave(["pouch_tin", "reply_all"], 20.0, 0.1), 9)
	var sarah: BattleUnit = b.heroes()[0]
	check(sarah.energy == 0.0, "sarah: starts with 0 energy")
	check(not b.actions(sarah).filter(func(a): return a.id == "dab")[0].ready, "sarah: can't Dab with no energy")
	b.act(sarah.uid, "scuba", b.enemies()[0].uid)
	check(sarah.energy > 0, "sarah: Scuba builds energy")
	var foe: BattleUnit = b.enemies()[0]
	check(b.has(foe, "bleed") or sarah.energy == 0, "sarah: Scuba bleeds the target")

	var b2 := Battle.new(party(["sarah"]), wave(["pouch_tin"], 20.0, 0.1), 3)
	var s2: BattleUnit = b2.heroes()[0]
	var f2: BattleUnit = b2.enemies()[0]
	s2.energy = 100
	b2.add_status(f2, "bleed", 3, 10.0, s2.uid)
	var hp := f2.hp
	b2.act(s2.uid, "dab")
	check(not b2.has(f2, "bleed"), "sarah: Dab removes the Bleed")
	check(hp - f2.hp == 38, "sarah: Dab detonates 10 x 3 turns x 125%% = 38 (got %d)" % (hp - f2.hp))
	check(s2.energy == 50, "sarah: Dab costs 50 energy")

	var b3 := Battle.new(party(["sarah"]), wave(["pouch_tin"], 20.0, 0.1), 3)
	var s3: BattleUnit = b3.heroes()[0]
	var boss := fake_boss(b3)
	b3.add_status(boss, "bleed", 3, 500.0, s3.uid)
	var dealt := b3.detonate(s3, boss, 2.0)
	check(dealt == roundi(boss.max_hp * Battle.DETONATE_BOSS_CAP), "sarah: detonations are capped at 35% of a boss's max HP")


func test_exposed() -> void:
	var b := Battle.new(party(["sam"]), wave(["energy_drink"], 50.0, 0.1), 1)
	var sam: BattleUnit = b.heroes()[0]
	var foe: BattleUnit = b.enemies()[0]
	foe.dodge = 0.6
	b.add_status(foe, "exposed", 5, 0.0)
	var misses := 0
	for i in 50:
		if b.hit(sam, foe, 0.1) == 0:
			misses += 1
	check(misses == 0, "exposed: can't dodge (%d misses)" % misses)


func test_boss_stun_diminishing() -> void:
	var b := Battle.new(party(["cam"]), wave(["pouch_tin"], 20.0, 0.1), 1)
	var boss := fake_boss(b)
	b.add_status(boss, "stun", 3)
	check(b.status_of(boss, "stun").dur == 3, "boss stun: first stun is full length")
	b.remove_status(boss, "stun")
	b.add_status(boss, "stun", 3)
	check(b.status_of(boss, "stun").dur == 2, "boss stun: second stun is a turn shorter")
	b.remove_status(boss, "stun")
	b.add_status(boss, "stun", 1)
	check(b.status_of(boss, "stun").dur == 1, "boss stun: never below 1 turn")


## Every 4-of-6 party can beat an early minion wave.
func test_party_combos_win() -> void:
	for combo in combos(HeroData.HERO_IDS, 4):
		var wins := 0
		for seed in 10:
			var b := Battle.new(party(combo), wave(["energy_drink", "nic_pouch", "reply_all"]), seed)
			if BattleAI.auto_battle(b) == "win":
				wins += 1
		check(wins >= 9, "party %s beats an early wave (%d/10)" % [", ".join(combo), wins])


# ------------------------------------------------------------------ balance
static func combos(items: Array, k: int) -> Array:
	if k == 0:
		return [[]]
	if items.size() < k:
		return []
	var out := []
	var head = items[0]
	var tail := items.slice(1)
	for c in combos(tail, k - 1):
		out.append([head] + c)
	out += combos(tail, k)
	return out


## Where one hero's damage comes from (BALANCE_DETAIL=<hero id>), over every party they're in.
func _detail(make_wave: Callable, boss: bool, hero_id: String) -> void:
	var log := {}
	var total := 0.0
	for combo in combos(HeroData.HERO_IDS, 4):
		if not combo.has(hero_id):
			continue
		for seed in 60:
			var b := Battle.new(party(combo), make_wave.call(), 1000 + seed)
			if boss:
				fake_boss(b)
			BattleAI.auto_battle(b)
			for k in b.dmg_log:
				if k.begins_with(hero_id + "|"):
					log[k] = log.get(k, 0) + b.dmg_log[k]
					total += b.dmg_log[k]
	print("  %s damage by source:" % hero_id)
	var keys := log.keys()
	keys.sort_custom(func(x, y): return log[x] > log[y])
	for k in keys:
		print("    %-28s %3d%%" % [k, roundi(100 * log[k] / total)])


func balance_report() -> void:
	var fights := {
		"minions (late, x2.2 HP)": func(): return wave(["tallboy", "pouch_tin", "fish_guy", "loud_typer"], 2.2, 1.6),
		"boss stand-in (x7 HP)": func(): return wave(["pouch_tin", "close_talker"], 7.0, 2.4),
	}
	for label in fights:
		print("\n== %s ==" % label)
		var share := {}
		var played := {}
		var by_party := []
		for combo in combos(HeroData.HERO_IDS, 4):
			var wins := 0
			var rounds := 0
			for seed in 60:
				var b := Battle.new(party(combo), fights[label].call(), 1000 + seed)
				if label.begins_with("boss"):
					fake_boss(b)
				if BattleAI.auto_battle(b) == "win":
					wins += 1
				rounds += b.round
				var total := 0.0
				for h in b.heroes():
					total += b.dmg_by.get(h.uid, 0)
				for h in b.heroes():
					share[h.key] = share.get(h.key, 0.0) + b.dmg_by.get(h.uid, 0) / maxf(1.0, total)
					played[h.key] = played.get(h.key, 0) + 1
			by_party.append([wins / 60.0, rounds / 60.0, ", ".join(combo)])
		by_party.sort_custom(func(x, y): return x[0] > y[0])
		for p in by_party:
			print("  win %3d%%  rounds %4.1f  %s" % [roundi(p[0] * 100), p[1], p[2]])
		if OS.get_environment("BALANCE_DETAIL") != "":
			_detail(fights[label], label.begins_with("boss"), OS.get_environment("BALANCE_DETAIL"))
		print("  avg share of party damage (fair share = 25%):")
		for id in HeroData.HERO_IDS:
			print("    %-6s %3d%%" % [id, roundi(100 * share[id] / played[id])])
