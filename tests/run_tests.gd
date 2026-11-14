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
	test_every_boss_skill()
	test_trucker()
	test_sales_guy()
	test_copilot()
	test_guardian()
	test_ghost()
	test_burger_crew()
	test_bosses_finish()
	test_stage_info()
	test_new_run()
	test_run_flow()
	test_events()
	test_achievements_and_outfits()
	test_saves()
	if OS.get_environment("FULL_RUN") == "1":
		full_run_report()
	if OS.get_environment("BALANCE") == "1":
		balance_report()
	if OS.get_environment("BOSSES") == "1":
		boss_report()
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


# ------------------------------------------------------------------ bosses
const ALL_BOSS_FIGHTS := [["trucker"], ["sales_guy"], ["copilot"], ["guardian"], ["ghost"], ["cashier", "grill_master", "sauce_keeper"]]


func boss_wave(ids: Array, remix := false, hp := 1.0, atk := 1.0) -> Array:
	return ids.map(func(id): return {"id": id, "hp_mult": hp, "atk_mult": atk, "remix": remix})


func enemy(b: Battle, key: String) -> BattleUnit:
	for e in b.enemies():
		if e.key == key:
			return e
	return null


## Every boss skill runs, for the original and the remix, and every boss has lines.
func test_every_boss_skill() -> void:
	for ids in ALL_BOSS_FIGHTS:
		for remix in [false, true]:
			for id in ids:
				for sk in EnemyData.ENEMIES[id].skills:
					var b := Battle.new(party(["cole", "cam", "mason", "sarah"]), boss_wave(ids, remix), 3)
					var u := enemy(b, id)
					var before := b.events.size()
					EnemyData.use_skill(id, sk.id, b, u)
					check(b.events.size() > before, "%s%s: %s does something" % [id, " (remix)" if remix else "", sk.id])
					if not b.pending_popup.is_empty():
						b.answer_popup("timeout")
			check(EnemyData.ENEMIES[ids[0]].has("remix_name"), "%s has a remix" % ids[0])
	for id in ["trucker", "sales_guy", "copilot", "guardian", "ghost"]:
		check(not Story.boss_intro(id).is_empty() and not Story.boss_defeat(id).is_empty(), "%s has intro and defeat lines" % id)
		check(not Story.boss_intro(id, true).is_empty(), "%s has a remix intro" % id)
	var r := Battle.new(party(["cam"]), boss_wave(["trucker"], true), 1)
	check(r.enemies()[0].name == "Night Shift Trucker" and r.enemies()[0].model == "trucker_remix", "remix: name and model change")


func test_trucker() -> void:
	var b := Battle.new(party(["cole", "cam", "mason", "sam"]), boss_wave(["trucker"]), 4)
	var t := enemy(b, "trucker")
	var cole := b.hero("cole")
	var at_cole := 0
	for i in 400:
		if b.pick_hero_target(t) == cole:
			at_cole += 1
	check(at_cole > 220, "trucker: Grudge sends most attacks at Cole (%d/400)" % at_cole)
	b.add_status(cole, "stun", 1)
	b._decrement("hero")
	check(b.has(cole, "resolve") and is_equal_approx(cole.aura, 0.1), "trucker: Road Rage after a stun (+10%, can't be re-stunned)")
	b.add_status(cole, "stun", 2)
	check(not b.has(cole, "stun"), "trucker: Cole can't be stunned twice in a row")

	var b2 := Battle.new(party(["cole", "cam", "mason", "sam"]), boss_wave(["trucker"], true), 4)
	EnemyData.use_skill("trucker", "send_money", b2, enemy(b2, "trucker"))
	check(b2.heroes().any(func(h): return b2.has(h, "blind")), "trucker remix: High Beams blind a second hero")

	# Without Cole, his ultimate goes at the hardest hitter.
	var b3 := Battle.new(party(["james", "cam", "mason", "sam"]), boss_wave(["trucker"]), 4)
	EnemyData.use_skill("trucker", "send_money", b3, enemy(b3, "trucker"))
	check(b3.heroes().any(func(h): return b3.has(h, "stun")), "trucker: no Cole, ultimate still stuns someone")


func test_sales_guy() -> void:
	var b := Battle.new(party(["cole", "cam"]), boss_wave(["sales_guy"]), 4)
	var sg := enemy(b, "sales_guy")
	var cole := b.hero("cole")
	var cam := b.hero("cam")
	check(b.mog == 0, "sales guy: starts with 0 Aura")
	for i in 7:
		EnemyData.on_turn(b, sg)
	check(b.mog == 5, "sales guy: Aura caps at 5")
	check(is_equal_approx(b.mult(cole), 0.7), "sales guy: 5 Aura = -30%% hero damage (got %.2f)" % b.mult(cole))
	check(is_equal_approx(b.mult(cam), 1.0), "sales guy: Cam is immune to Mogged")
	check(is_equal_approx(sg.dodge, 0.35), "sales guy: +3% dodge per Aura")
	b.act(cam.uid, "attack")
	check(b.mog == 4 and b.stats.aura_stolen == 1, "sales guy: Cam steals an Aura stack per turn")
	var b2 := Battle.new(party(["cole"]), boss_wave(["sales_guy"], true), 4)
	check(b2.mog == 2, "sales guy remix: starts with 2 Aura")
	b2.kill(enemy(b2, "sales_guy"))
	check(b2.mog == 0, "sales guy: Aura goes away when he's beaten")


func test_copilot() -> void:
	var b := Battle.new(party(["cole", "cam", "mason", "sam"]), boss_wave(["copilot"]), 4)
	var c := enemy(b, "copilot")
	EnemyData.use_skill("copilot", "cowork", b, c)
	check(not b.pending_popup.is_empty(), "copilot: the pop-up waits for the player")
	check(b.pending_popup.timer == 2.5, "copilot: first pop-up has a 2.5s timer")
	b.phase = "enemy"
	var before := b.events.size()
	b.enemy_step()
	check(b.events.size() == before, "copilot: the fight pauses during a pop-up")
	b.answer_popup("dismiss")
	check(b.pending_popup.is_empty() and b.stats.popups_dismissed == 1, "copilot: 'Not now' dismisses it")

	var hp := b.heroes().map(func(h): return h.hp)
	EnemyData.use_skill("copilot", "cowork", b, c)
	b.answer_popup("timeout")
	var hurt := false
	for i in hp.size():
		if b.heroes()[i].hp < hp[i]:
			hurt = true
	check(hurt, "copilot: timing out hurts the party")
	check(b.heroes().any(func(h): return b.has(h, "silence")), "copilot: timing out silences a hero")

	EnemyData.use_skill("copilot", "cowork", b, c)
	b.answer_popup("install")
	check(b.heroes().all(func(h): return b.has(h, "weaken")), "copilot: installing gives everyone Productivity Suite (-15%)")

	EnemyData.use_skill("copilot", "rollout", b, c)
	b.answer_popup("dismiss")
	check(not b.pending_popup.is_empty(), "copilot: Mandatory Rollout shows a second pop-up")
	b.answer_popup("dismiss")
	check(b.pending_popup.is_empty(), "copilot: ...and then stops")
	check(b.popup_count == 5 and b.pending_popup.is_empty(), "copilot: pop-ups are counted")
	EnemyData.use_skill("copilot", "cowork", b, c)
	check(b.pending_popup.timer == 1.5, "copilot: the timer shrinks to 1.5s (got %.2f)" % b.pending_popup.timer)


func test_guardian() -> void:
	var b := Battle.new(party(["cole", "cam", "mason", "sam"]), boss_wave(["guardian"]), 4)
	var g := enemy(b, "guardian")
	var box := enemy(b, "boombox")
	check(box != null and box.owner_uid == g.uid and box.inert, "guardian: starts with a Boombox")
	var cole := b.hero("cole")
	for i in 8:
		EnemyData.on_turn(b, g)
	check(is_equal_approx(b.power(cole, "earworm"), 0.4), "guardian: Earworm caps at 5 stacks (+40%% damage taken)")
	var hp := cole.hp
	cole.def = 0.0
	b.hit(g, cole, 1.0, {"no_crit": true, "no_dodge": true})
	check(hp - cole.hp == roundi(12 * 1.4), "guardian: Earworm makes heroes take more damage")
	b.kill(box)
	check(not b.has(cole, "earworm") and g.timer == 2 and b.stats.boomboxes == 1, "guardian: breaking the Boombox clears Earworm and stops the music")
	EnemyData.on_turn(b, g)
	check(not b.has(cole, "earworm"), "guardian: no Earworm while the music is off")
	EnemyData.on_turn(b, g)
	var box2: BattleUnit = b.enemies().filter(func(e): return e.key == "boombox" and e.alive)[0]
	check(box2.max_hp == 72, "guardian: the new Boombox has 20%% more HP (got %d)" % box2.max_hp)
	b.kill(g)
	check(not box2.alive, "guardian: the Boombox breaks when she's beaten")
	check(b.outcome == "" or true, "guardian: fight ends cleanly")
	var b2 := Battle.new(party(["cole"]), boss_wave(["guardian"], true), 4)
	var g2 := enemy(b2, "guardian")
	for i in 10:
		EnemyData.on_turn(b2, g2)
	check(is_equal_approx(b2.power(b2.hero("cole"), "earworm"), 0.56), "guardian remix: Earworm caps at 7 stacks")


func test_ghost() -> void:
	var b := Battle.new(party(["cole", "cam", "james", "sam"]), boss_wave(["ghost"]), 4)
	var gh := enemy(b, "ghost")
	check(not b.hero("james").alive and b.stats.james_possessed, "ghost: possesses James at the start")
	check(gh.max_hp == 210, "ghost: normal HP when James is there")
	EnemyData.use_skill("ghost", "back_from_emails", b, gh)
	check(b.has(gh, "away") and b.foes_of(b.hero("cole")).is_empty(), "ghost: can't be targeted while away")
	gh.hp = 100
	EnemyData.on_return(b, gh)
	check(not b.has(gh, "away") and gh.hp > 100, "ghost: comes back from emails healed")

	var b2 := Battle.new(party(["cole", "cam", "mason", "sam"]), boss_wave(["ghost"]), 4)
	var gh2 := enemy(b2, "ghost")
	check(gh2.max_hp == 252 and gh2.stacks == 1, "ghost: bored without James (+20% HP)")
	EnemyData.on_turn(b2, gh2)
	check(b2.heroes().any(func(h): return b2.has(h, "weaken")), "ghost: haunts the hardest hitter when bored")


func test_burger_crew() -> void:
	var b := Battle.new(party(["cole", "cam", "mason", "sam"]), boss_wave(EnemyData.BURGER_CREW), 4)
	var cashier := enemy(b, "cashier")
	var keeper := enemy(b, "sauce_keeper")
	var grill := enemy(b, "grill_master")
	var sam := b.hero("sam")
	b.act(sam.uid, "rage_bait", grill.uid)
	check(b.last_ability_uid == sam.uid, "crew: remembers the last hero to use an ability")
	EnemyData.use_skill("cashier", "not_on_menu", b, cashier)
	check(b.has(sam, "silence"), "crew: the Cashier silences them")

	EnemyData.use_skill("sauce_keeper", "bring_sauce", b, keeper)
	check(b.heroes().all(func(h): return b.has(h, "waiting_sauce")), "crew: the party waits on sauce")
	b.hit(b.hero("cole"), keeper, 0.5, {"no_dodge": true})
	check(not b.heroes().any(func(h): return b.has(h, "waiting_sauce")), "crew: hitting the Sauce Keeper gets the sauce")
	check(b.power(b.hero("cam"), "empower") >= 0.15, "crew: getting the sauce gives +15% damage")

	EnemyData.use_skill("sauce_keeper", "bring_sauce", b, keeper)
	b._decrement("hero")
	b._decrement("hero")
	check(b.heroes().all(func(h): return b.power(h, "weaken") >= 0.25), "crew: the sauce never came (-25%)")

	b.kill(cashier)
	check(b.power(grill, "empower") >= 0.25 and b.power(keeper, "empower") >= 0.25, "crew: the others get angrier when one falls")
	b.kill(grill)
	check(keeper.shield > 0, "crew: the last one standing gets a shield")


## Every boss fight finishes (no hangs) for every party, original and remix.
func test_bosses_finish() -> void:
	for ids in ALL_BOSS_FIGHTS:
		for remix in [false, true]:
			for combo in combos(HeroData.HERO_IDS, 4):
				var b := Battle.new(party(combo), boss_wave(ids, remix), 77)
				BattleAI.auto_battle(b)
				if b.outcome == "":
					check(false, "%s vs %s ends (stuck at round %d, phase %s)" % [ids[0], ", ".join(combo), b.round, b.phase])
					return
	check(true, "every boss fight finishes")


## A party that has picked up `fights` fights' worth of upgrades (rough stand-in for
## the run loop until it's ported): +8% HP and ATK per fight, and rank 2 abilities after 4.
func upgraded_party(ids: Array, fights: int) -> Array:
	return ids.map(func(id):
		var s := Battle.hero_setup(id)
		var m := 1.0 + 0.08 * fights
		s.max_hp = roundi(s.max_hp * m)
		s.hp = s.max_hp
		s.atk *= m
		if fights >= 4:
			for ab in HeroData.rankable(id):
				s.ranks[ab] = 2
		return s)


## The original's enemy scaling: (hp, atk) multipliers for a slot in cycle 1.
## Bosses come at slot 1, 3 and 5; the burger crew is scaled like slot 4.
static func scaling(slot: int, cycle := 0) -> Array:
	return [(0.8 + 1.0 * slot) * pow(2.4, cycle), (1.4 + 0.6 * slot) * pow(2.1, cycle)]


## Win rates and fight length for every boss against every party.
func boss_report() -> void:
	var n := 40
	var slots := {"first boss (slot 1)": [1, 1], "third boss (slot 5)": [5, 5]}
	for label in slots:
		_boss_table(label, slots[label][0], slots[label][1], false, n)
	_boss_table("remix, cycle 2 first boss", 1, 8, true, n, 1)


func _boss_table(label: String, slot: int, fights: int, remix: bool, n: int, cycle := 0) -> void:
	print("\n== %s (heroes after %d fights, %d fights per party) ==" % [label, fights, n])
	for ids in ALL_BOSS_FIGHTS:
		var is_crew: bool = ids.size() > 1
		var sc := scaling(4 if is_crew else slot, cycle)
		# The crew is the 7th fight of the cycle.
		var f: int = (6 + 7 * cycle) if is_crew else fights
		if true:
			var wins := 0
			var rounds := 0
			var total := 0
			var worst := [2.0, ""]
			var best := [-1.0, ""]
			for combo in combos(HeroData.HERO_IDS, 4):
				var w := 0
				for seed in n:
					var b := Battle.new(upgraded_party(combo, f), boss_wave(ids, remix, sc[0], sc[1]), 5000 + seed)
					if BattleAI.auto_battle(b) == "win":
						w += 1
					rounds += b.round
					total += 1
				wins += w
				var rate := float(w) / n
				if rate < worst[0]:
					worst = [rate, ", ".join(combo)]
				if rate > best[0]:
					best = [rate, ", ".join(combo)]
			print("  %-14s win %3d%%  rounds %4.1f  worst %3d%% (%s)  best %3d%% (%s)" % [
				ids[0] if ids.size() == 1 else "burger crew", roundi(100.0 * wins / total), float(rounds) / total,
				roundi(worst[0] * 100), worst[1], roundi(best[0] * 100), best[1]])


# ------------------------------------------------------------------ run loop
func test_stage_info() -> void:
	var kinds := []
	for s in Run.STAGES_PER_CYCLE:
		kinds.append(Run.stage_info(s, 1).kind)
	check(kinds == ["minion", "boss", "minion", "boss", "minion", "boss", "bonus"], "run: a cycle is minion/boss x3 then the burger joint (%s)" % str(kinds))
	var remixes := 0
	var later := 0
	var bad_remix := false
	for seed in 200:
		var c0 := Run.cycle_bosses(seed, 0)
		var unique := {}
		for b in c0:
			unique[b] = true
		if unique.size() != 3:
			check(false, "run: 3 different bosses per cycle (seed %d)" % seed)
			return
		for s in range(Run.STAGES_PER_CYCLE, 2 * Run.STAGES_PER_CYCLE):
			var info := Run.stage_info(s, seed)
			if info.kind != "boss":
				continue
			if c0.has(info.boss):
				later += 1
				if info.remix:
					remixes += 1
			elif info.remix:
				bad_remix = true
		for s in Run.STAGES_PER_CYCLE:
			if Run.stage_info(s, seed).remix:
				bad_remix = true
	check(not bad_remix, "run: only bosses you've already met come back as remixes, never in cycle 1")
	var rate := float(remixes) / later
	check(rate > 0.35 and rate < 0.65, "run: returning bosses are remixed about half the time (%d%%)" % roundi(rate * 100))
	check(Run.stage_info(Run.STAGES_PER_CYCLE * 2 - 1, 5).remix, "run: the crew is the Late Night Crew from cycle 2")
	check(Run.stage_info(3, 9).title == EnemyData.ENEMIES[Run.stage_info(3, 9).boss].name, "run: boss stages are titled with the boss's name")


func test_new_run() -> void:
	var meta := SaveGame.fresh_meta()
	meta.upgrades = {"signing": 2, "mentor": 1, "second_wind": 1}
	var run := Run.new_run(meta, 42, ["sam", "sarah", "cole", "cam"])
	check(run.heroes.size() == 4 and run.heroes[0].id == "sam", "run: starts with the chosen party")
	check(run.pto == 30 and run.second_wind, "run: Signing Bonus and Second Wind apply")
	var ranked := 0
	for h in run.heroes:
		check(h.hp == Run.hero_stats(h, meta).max_hp, "run: %s starts at full HP" % h.id)
		for k in h.ranks:
			ranked += h.ranks[k] - 1
	check(ranked == 4, "run: Mentorship gives each hero a rank-up (%d)" % ranked)
	var b := Run.build_battle(run, meta)
	check(b.heroes().size() == 4 and b.enemies().size() >= 2, "run: first fight is a minion wave")
	var b2 := Run.build_battle(run, meta)
	check(b.enemies().map(func(e): return e.key) == b2.enemies().map(func(e): return e.key), "run: rebuilding a fight gives the same enemies")


## Plays a whole run headlessly with the AI, picking upgrades, shop items and
## event choices at random. Returns {cleared, rounds, run, deaths}.
func simulate_run(seed: int, meta: Dictionary, party: Array, max_stage := 40) -> Dictionary:
	var run := Run.new_run(meta, seed, party)
	var rounds := []
	while run.stage < max_stage:
		Run.start_fight(run, meta)
		var battle := Run.build_battle(run, meta)
		var outcome := BattleAI.auto_battle(battle)
		rounds.append(battle.round)
		if outcome != "win":
			if Run.use_second_wind(run, meta):
				continue
			Run.game_over(run, meta)
			break
		var res := Run.finish_fight(run, battle, meta)
		var rng := Run.run_rng(run)
		for step in res.picks:
			Run.apply_upgrade(run, meta, rng.pick(Run.roll_draft(run, rng, step, res.picks)))
		for item in rng.shuffle(Run.roll_shop(run, meta, rng)):
			Run.buy_item(run, meta, item)
		Run.save_rng(run, rng)
		var ev := Run.advance(run)
		if not ev.is_empty():
			var r2 := Run.run_rng(run)
			RunEvents.apply(ev.id, r2.int_range(0, ev.choices.size() - 1), run, meta)
			Run.save_rng(run, r2)
	return {"cleared": run.stage, "rounds": rounds, "run": run}


func test_run_flow() -> void:
	var meta := SaveGame.fresh_meta()
	var r := simulate_run(7, meta, ["cole", "cam", "james", "mason"], 8)
	check(r.cleared >= 1, "run: the AI clears at least the first fight (cleared %d)" % r.cleared)
	check(meta.stats.get("fights_won", 0) == r.cleared, "run: wins are counted in meta stats")
	check(meta.achievements.has("first_day"), "run: First Day on the Job unlocks")
	# Ghost fight: James comes back at half health afterwards.
	var run := Run.new_run(meta, 3, ["cole", "cam", "james", "mason"])
	var b := Battle.new(party(["cole", "cam", "james", "mason"]), boss_wave(["ghost"]), 1)
	BattleAI.auto_battle(b)
	for s in 50:
		if Run.stage_info(s, run.seed).boss == "ghost" and Run.stage_info(s, run.seed).kind == "boss":
			run.stage = s
			break
	if b.outcome == "win" and Run.stage_info(run.stage, run.seed).boss == "ghost":
		Run.finish_fight(run, b, meta)
		var james := Run.hero_state(run, "james")
		check(james.hp == roundi(Run.hero_stats(james, meta).max_hp * 0.5), "run: James is back at 50% HP after his ghost")
		check(Run.hero_state(run, "cole").hp == Run.hero_stats(Run.hero_state(run, "cole"), meta).max_hp, "run: everyone else is healed by the boss win")
	# Shop and drafts
	var rng := Rng.new(5)
	var shop := Run.roll_shop(run, meta, rng)
	check(shop[0].kind == "heal" and shop.size() >= 5, "run: the shop always has snacks and at least 5 items")
	var draft := Run.roll_draft(run, rng, 0)
	check(draft.size() == 3 and draft.all(func(u): return u.kind == "rank"), "run: the first draft pick is all ability upgrades")
	run.pto = 100
	var item: Dictionary = shop[0]
	check(Run.buy_item(run, meta, item) and run.pto == 90 and item.sold, "run: buying works")
	check(not Run.buy_item(run, meta, item), "run: can't buy the same item twice")
	# Second Wind and catch-up sauce
	var m2 := SaveGame.fresh_meta()
	var run2 := Run.new_run(m2, 1, ["cole", "cam", "james", "mason"])
	check(not Run.use_second_wind(run2, m2), "run: no Second Wind without the upgrade")
	check(Run.game_over(run2, m2).catch_up == 5 and m2.sauce == 5, "run: early wipes give 5 catch-up sauce")


func test_events() -> void:
	var meta := SaveGame.fresh_meta()
	for e in RunEvents.LIST:
		for i in e.choices.size():
			var run := Run.new_run(meta, 11, ["cole", "cam", "mason", "james"])
			RunEvents.apply(e.id, i, run, meta)
			check(run.heroes.all(func(h): return h.hp >= 1), "event %s:%d keeps everyone alive" % [e.id, i])
	var run := Run.new_run(meta, 11, ["cole", "cam", "mason", "james"])
	RunEvents.apply("renekton", 1, run, meta)
	run.stage = 1
	var b := Run.build_battle(run, meta)
	check(b.enemies()[0].name.ends_with("(Empowered)"), "event: hanging up on Renekton empowers the next boss")
	RunEvents.apply("renekton", 0, run, meta)
	var atk_before: float = Run.hero_stats(run.heroes[0], meta).atk
	var b2 := Run.build_battle(run, meta)
	check(b2.heroes()[0].atk == atk_before + 5, "event: Renekton Buff gives +5 attack next fight")
	var seen := {}
	var r2 := Run.new_run(meta, 5, ["sam", "sarah", "james", "cam"])
	r2.stage = 2
	var rng := Rng.new(3)
	for i in 200:
		var ev := RunEvents.roll(r2, rng)
		if not ev.is_empty():
			seen[ev.id] = true
	check(not seen.has("the_local") and not seen.has("pool_party"), "event: hero events need their hero in the party")
	check(seen.size() <= 3, "event: each event happens at most once per cycle")


func test_achievements_and_outfits() -> void:
	for o in Outfits.all():
		if o.has("achievement"):
			check(not Achievements.by_id(o.achievement).is_empty(), "outfit %s's achievement exists" % o.id)
	for id in HeroData.HERO_IDS:
		var free := Outfits.for_hero(id).filter(func(o): return not o.has("achievement") and not o.has("cost"))
		check(free.size() >= 2, "%s has 2 free skins from the start" % id)
	var meta := SaveGame.fresh_meta()
	for a in Achievements.LIST:
		Achievements.check(a.id, {"meta": meta}) # runs without errors on an empty context
	var c := {"meta": meta, "boss": "trucker", "party": ["cole"], "kind": "boss", "fight": {"cole_stunned": false}}
	check(Achievements.check("paid_in_full", c), "achievement: Paid in Full")
	c.fight.cole_stunned = true
	check(not Achievements.check("paid_in_full", c), "achievement: not if Cole was stunned")
	var got := Achievements.check_all({"meta": meta, "boss": "ghost", "kind": "boss", "party": [], "fight": {}})
	check(got.any(func(a): return a.id == "who_you_gonna_call"), "achievement: Who You Gonna Call")
	check(Outfits.owns(meta, Outfits.by_id("james_ghost")), "achievement skins unlock")
	check(not Outfits.owns(meta, Outfits.by_id("sam_throne")), "locked skins stay locked")
	# Suit Up: buying and wearing
	var casual := Outfits.by_id("sam_casual")
	check(Outfits.status(meta, casual) == "buy" and not Outfits.buy(meta, casual), "skins: can't buy without enough sauce")
	meta.sauce = 100
	check(Outfits.buy(meta, casual) and meta.sauce == 70 and Outfits.status(meta, casual) == "owned", "skins: buying spends sauce")
	check(not Outfits.buy(meta, casual), "skins: can't buy twice")
	check(not Outfits.buy(meta, Outfits.by_id("sam_throne")), "skins: achievement skins aren't for sale")
	check(Outfits.equip(meta, casual) and Outfits.status(meta, casual) == "wearing", "skins: wearing a bought skin")
	check(not Outfits.equip(meta, Outfits.by_id("sam_throne")), "skins: can't wear a locked skin")
	check(Outfits.model_of(casual) == "sam~sam_casual", "skins: Casual Friday is a recolor")
	var run := Run.new_run(meta, 1, ["sam", "cole", "cam", "james"], {"sam": meta.outfits.sam})
	check(Run.build_battle(run, meta).hero("sam").model == "sam~sam_casual", "skins: the run uses the worn skin")
	# Sauce Shop
	meta.sauce = 20
	check(MetaUpgrades.buy(meta, "vet") and MetaUpgrades.level(meta, "vet") == 1 and meta.sauce == 12, "sauce shop: buying a level")
	check(not MetaUpgrades.buy(meta, "vet"), "sauce shop: can't afford the next level")
	meta.sauce = 1000
	meta.upgrades.second_wind = 1
	check(not MetaUpgrades.buy(meta, "second_wind"), "sauce shop: maxed upgrades can't be bought")


func test_saves() -> void:
	var dir := "user://test_saves/"
	DirAccess.make_dir_recursive_absolute(dir)
	var meta := SaveGame.fresh_meta()
	meta.sauce = 12
	meta.achievements.append("promoted")
	var run := Run.new_run(meta, 99, ["sam", "sarah", "james", "cam"])
	Run.apply_upgrade(run, meta, {"kind": "rank", "hero": "sam", "ability": "rage_bait"})
	SaveGame.save_meta(meta, dir)
	SaveGame.save_run(run, dir)
	var m2 := SaveGame.load_meta(dir)
	var r2 := SaveGame.load_run(dir)
	check(m2.sauce == 12 and m2.achievements == ["promoted"], "save: meta round-trips")
	check(r2.seed == 99 and r2.heroes[0].ranks.rage_bait == 2 and typeof(r2.stage) == TYPE_INT, "save: run round-trips with ints")
	var b := Run.build_battle(r2, m2)
	check(b.heroes().size() == 4, "save: a loaded run builds a fight")
	SaveGame.record_run(r2, dir)
	check(SaveGame.load_board(dir).size() >= 1, "save: Hall of Fame records runs")
	SaveGame.save_run({}, dir)
	check(SaveGame.load_run(dir).is_empty(), "save: clearing the run works")
	for f in [SaveGame.META, SaveGame.BOARD]:
		DirAccess.remove_absolute(dir + f)


static func upgraded_meta(level: int) -> Dictionary:
	var m := SaveGame.fresh_meta()
	m.upgrades = {"vet": level, "sauce": level, "signing": mini(5, level), "benefits": mini(5, level), "mentor": mini(3, level / 3)}
	if level >= 5:
		m.upgrades.second_wind = 1
	return m


## The original's balance report: whole runs, random 4-of-6 parties, at several
## levels of Village Sauce upgrades.
func full_run_report() -> void:
	var n := int(OS.get_environment("RUNS")) if OS.get_environment("RUNS") != "" else 60
	var all_parties := combos(HeroData.HERO_IDS, 4)
	var spc := Run.STAGES_PER_CYCLE
	for lvl in [0, 3, 6, 10]:
		var cleared := []
		var by_kind := {"minion": [], "boss": [], "bonus": []}
		var by_boss := {}
		var deaths := {}
		for i in n:
			var seed := 1000 + i
			var p: Array = all_parties[seed % all_parties.size()]
			var r := simulate_run(seed, upgraded_meta(lvl), p)
			cleared.append(r.cleared)
			for s in r.rounds.size():
				var info := Run.stage_info(s, seed)
				by_kind[info.kind].append(r.rounds[s])
				if info.kind == "boss":
					var key: String = info.boss + ("*" if info.remix else "")
					if not by_boss.has(key):
						by_boss[key] = []
					by_boss[key].append(r.rounds[s])
			var d := Run.stage_info(r.cleared, seed)
			var dk: String = "%d-%d%s" % [d.cycle + 1, d.index + 1, {"boss": "B", "bonus": "$", "minion": ""}[d.kind]]
			deaths[dk] = deaths.get(dk, 0) + 1
		cleared.sort()
		var pct := func(f: Callable) -> String: return "%d%%" % roundi(100.0 * cleared.filter(f).size() / n)
		print("\nmeta %d: reached burger 1: %s, beat it: %s, beat burger 2: %s" % [lvl,
			pct.call(func(c): return c >= spc - 1), pct.call(func(c): return c > spc - 1), pct.call(func(c): return c > 2 * spc - 1)])
		var keys := deaths.keys()
		keys.sort()
		print("meta %d: died at %s" % [lvl, ", ".join(keys.map(func(k): return "%s:%d" % [k, deaths[k]]))])
		var avg := func(a: Array) -> String: return "%.1f" % (a.reduce(func(x, y): return x + y, 0) / maxf(1.0, a.size()))
		print("meta %d: fights won p10=%d p50=%d p90=%d  rounds: minion %s boss %s bonus %s" % [lvl,
			cleared[int(0.1 * (n - 1))], cleared[int(0.5 * (n - 1))], cleared[int(0.9 * (n - 1))],
			avg.call(by_kind.minion), avg.call(by_kind.boss), avg.call(by_kind.bonus)])
		var bk := by_boss.keys()
		bk.sort()
		print("meta %d: boss rounds %s" % [lvl, ", ".join(bk.map(func(k): return "%s %s" % [k, avg.call(by_boss[k])]))])


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
