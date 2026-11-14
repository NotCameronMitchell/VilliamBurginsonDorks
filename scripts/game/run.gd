class_name Run
extends RefCounted
## The run loop: stages, enemy scaling, rewards, upgrade drafts and the Break Room
## Shop. Ported from the original's src/game/run.ts. A run and the meta progress are
## plain Dictionaries so they save straight to JSON (see SaveGame).
##
## A cycle is minion fight, boss, three times over (3 of the 5 office bosses, drawn
## from the run's seed), then the Villiam Burginson Crew. Then the next cycle starts,
## tougher, and it never ends.
##
## Typical flow for the UI:
##   run = Run.new_run(meta, seed, party, outfits)
##   loop:
##     lines = Run.start_fight(run, meta).lines      # story to show first
##     battle = Run.build_battle(run, meta)          # play it
##     if lost: Run.use_second_wind(run, meta) or Run.game_over(run, meta)
##     result = Run.finish_fight(run, battle, meta)  # loot, heals, achievements
##     result.picks x Run.roll_draft / Run.apply_upgrade
##     Run.roll_shop / Run.buy_item
##     Run.advance(run, meta) -> maybe a random event to show

const VERSION := 1
const MINIONS_PER_BOSS := 1
const BOSSES_PER_CYCLE := 3
const STAGES_PER_CYCLE := BOSSES_PER_CYCLE * (MINIONS_PER_BOSS + 1) + 1
## The burger crew is scaled like this many stages into the cycle.
const BURGER_LEVEL := 3
## Bosses get this much of the stage's HP scaling (they were dragging on).
const BOSS_HP_MULT := 0.85
const REROLL_COST := 5
## Chance a boss you already met earlier in the run comes back as its remix.
const REMIX_CHANCE := 0.5

## Enemy scaling for stage index i in a cycle:
##   hp  = (HP_BASE + HP_STEP * i) * HP_CYCLE ^ cycle
##   atk = (ATK_BASE + ATK_STEP * i) * ATK_CYCLE ^ cycle
const HP_BASE := 0.8
const HP_STEP := 1.0
const HP_CYCLE := 2.1
const ATK_BASE := 1.4
const ATK_STEP := 0.85
const ATK_CYCLE := 1.9

const STAT_UPS := [
	{"stat": "hp", "amount": 0.15, "name": "Gym Membership"},
	{"stat": "atk", "amount": 0.12, "name": "Pre-Workout"},
	{"stat": "crit", "amount": 0.06, "name": "Lucky Socks"},
	{"stat": "dodge", "amount": 0.05, "name": "New Kicks"},
	{"stat": "def", "amount": 0.05, "name": "Ergonomic Chair"},
]
const PARTY_UPS := [
	{"stat": "hp", "amount": 0.07, "name": "Team Lunch"},
	{"stat": "atk", "amount": 0.06, "name": "Pizza Party"},
]


# ------------------------------------------------------------------ stages
## The bosses a run faces in a cycle: a random draw from the pool, fixed by the seed.
static func cycle_bosses(seed: int, cycle: int) -> Array:
	var rng := Rng.new((seed ^ Rng._imul(cycle + 1, 0x9E3779B1)) & Rng.MASK)
	return rng.shuffle(EnemyData.BOSS_POOL.duplicate()).slice(0, mini(BOSSES_PER_CYCLE, EnemyData.BOSS_POOL.size()))


## Whether a boss is its remix this cycle: only if you already met it earlier in the
## run, and then on a coin flip fixed by the seed.
static func is_remix(seed: int, cycle: int, boss: String) -> bool:
	if cycle == 0:
		return false
	var met := false
	for c in cycle:
		if cycle_bosses(seed, c).has(boss):
			met = true
	if not met:
		return false
	var rng := Rng.new((seed ^ Rng._imul(cycle + 7, 0x85EBCA6B) ^ boss.hash()) & Rng.MASK)
	return rng.chance(REMIX_CHANCE)


## What a stage is: {kind: minion|boss|bonus, cycle, index, boss, remix, title}.
static func stage_info(stage: int, seed := 0) -> Dictionary:
	var cycle := stage / STAGES_PER_CYCLE
	var index := stage % STAGES_PER_CYCLE
	if index == STAGES_PER_CYCLE - 1:
		return {"kind": "bonus", "cycle": cycle, "index": index, "boss": "", "remix": cycle > 0, "title": "Villiam Burginson's"}
	var group := MINIONS_PER_BOSS + 1
	var bosses := cycle_bosses(seed, cycle)
	var boss: String = bosses[(index / group) % bosses.size()]
	if index % group == MINIONS_PER_BOSS:
		var remix := is_remix(seed, cycle, boss)
		var d: Dictionary = EnemyData.ENEMIES[boss]
		return {"kind": "boss", "cycle": cycle, "index": index, "boss": boss, "remix": remix,
			"title": d.remix_name if remix else d.name}
	return {"kind": "minion", "cycle": cycle, "index": index, "boss": boss, "remix": false,
		"title": "The Office %d-%d" % [index / group + 1, index % group + 1]}


## Enemy stat multipliers for a stage: {hp, atk}.
static func scaling(stage: int) -> Dictionary:
	var info := stage_info(stage)
	var i: int = BURGER_LEVEL if info.kind == "bonus" else info.index
	return {
		"hp": (HP_BASE + HP_STEP * i) * pow(HP_CYCLE, info.cycle),
		"atk": (ATK_BASE + ATK_STEP * i) * pow(ATK_CYCLE, info.cycle),
	}


## Enemy ids for a stage. Bosses fight solo; the crew is the three-person final boss.
static func stage_enemies(stage: int, rng: Rng, seed := 0) -> Array:
	var info := stage_info(stage, seed)
	if info.kind == "bonus":
		return EnemyData.BURGER_CREW.duplicate()
	if info.kind == "boss":
		return [info.boss]
	var boss_num: int = info.index / (MINIONS_PER_BOSS + 1)
	var pool: Array = EnemyData.MINIONS_EARLY if boss_num < 2 and info.cycle == 0 else EnemyData.MINIONS_EARLY + EnemyData.MINIONS_LATE
	var n := mini(5, 2 + boss_num / 2 + (1 if info.cycle > 0 else 0))
	var out := []
	for i in n:
		out.append(rng.pick(pool))
	return out


# ------------------------------------------------------------------ run state
static func run_rng(run: Dictionary) -> Rng:
	return Rng.new(run.rng_state)


static func save_rng(run: Dictionary, rng: Rng) -> void:
	run.rng_state = rng.state


static func new_run(meta: Dictionary, seed: int, party: Array = HeroData.HERO_IDS.slice(0, HeroData.PARTY_SIZE), outfits := {}) -> Dictionary:
	var rng := Rng.new(seed)
	var heroes := []
	for id in party:
		var h := {"id": id, "hp": 0, "hp_mult": 1.0, "atk_mult": 1.0, "crit": 0.0, "dodge": 0.0, "def": 0.0,
			"atk_flat": 0.0, "ranks": {}, "weapon": HeroData.STARTING_WEAPON[id], "weapons": [HeroData.STARTING_WEAPON[id]]}
		for i in MetaUpgrades.level(meta, "mentor"):
			var opts := HeroData.rankable(id).filter(func(a): return h.ranks.get(a, 1) < HeroData.MAX_RANK)
			var a: String = rng.pick(opts)
			h.ranks[a] = h.ranks.get(a, 1) + 1
		heroes.append(h)
	var run := {
		"version": VERSION, "seed": seed, "rng_state": rng.state, "stage": 0, "heroes": heroes,
		"pto": 15 * MetaUpgrades.level(meta, "signing"), "kills": 0, "fights_won": 0, "sauce_earned": 0,
		"second_wind": MetaUpgrades.level(meta, "second_wind") > 0, "started_at": int(Time.get_unix_time_from_system()),
		"outfits": outfits.duplicate(), "next_fight": [], "rival_empowered": false, "events_seen": [],
	}
	for h in run.heroes:
		h.hp = hero_stats(h, meta).max_hp
	return run


static func hero_state(run: Dictionary, id: String) -> Dictionary:
	for h in run.heroes:
		if h.id == id:
			return h
	return {}


## A hero's stats this run: base x run upgrades x meta upgrades.
static func hero_stats(h: Dictionary, meta: Dictionary) -> Dictionary:
	var d: Dictionary = HeroData.HEROES[h.id]
	return {
		"max_hp": roundi(d.hp * h.hp_mult * (1.0 + MetaUpgrades.VET_HP * MetaUpgrades.level(meta, "vet"))),
		"atk": d.atk * h.atk_mult * (1.0 + MetaUpgrades.SAUCE_DMG * MetaUpgrades.level(meta, "sauce")) + h.get("atk_flat", 0.0),
		"def": minf(0.5, d.def + h.def),
		"crit": minf(0.6, d.crit + h.crit),
		"dodge": minf(0.4, d.dodge + h.dodge),
	}


# ------------------------------------------------------------------ fights
## Call before each fight. Returns {lines: story to show, unlocked: new achievements}.
static func start_fight(run: Dictionary, meta: Dictionary) -> Dictionary:
	var info := stage_info(run.stage, run.seed)
	var lines := []
	if run.stage == 0:
		lines += Story.RUN_INTRO
	if info.kind == "boss":
		lines += Story.boss_intro(info.boss, info.remix)
	elif info.kind == "bonus":
		lines += Story.BURGER_INTRO
		Achievements.bump(meta, "burger_reached")
	meta.stats.best_cycle = maxi(int(meta.stats.get("best_cycle", 0)), info.cycle + 1)
	return {"lines": lines, "unlocked": Achievements.check_all({"meta": meta})}


## Builds the fight for the current stage. The run's rng isn't advanced, so a fight
## interrupted by closing the app replays the same way when the run is resumed.
static func build_battle(run: Dictionary, meta: Dictionary) -> Battle:
	var rng := run_rng(run)
	var info := stage_info(run.stage, run.seed)
	var s := scaling(run.stage)
	var enemies := []
	for id in stage_enemies(run.stage, rng, run.seed):
		var e := {"id": id, "hp_mult": s.hp * (BOSS_HP_MULT if info.kind == "boss" else 1.0), "atk_mult": s.atk, "remix": info.remix}
		if info.kind == "boss" and run.rival_empowered:
			e.hp_mult *= RunEvents.RIVAL_EMPOWERED.hp
			e.atk_mult *= RunEvents.RIVAL_EMPOWERED.atk
			e.suffix = "Empowered"
		enemies.append(e)
	var heroes := []
	for h in run.heroes:
		var o := Outfits.outfit_of(h.id, run.outfits)
		var st := hero_stats(h, meta)
		var hp_pct := 0.0
		var atk_add := 0.0
		var shield_pct := 0.0
		for m in run.next_fight:
			if m.hero == "all" or m.hero == h.id:
				hp_pct += m.get("hp_pct", 0.0)
				atk_add += m.get("atk", 0.0)
				shield_pct += m.get("shield_pct", 0.0)
		var max_hp := maxi(1, roundi(st.max_hp * (1.0 + hp_pct)))
		heroes.append({
			"id": h.id, "hp": mini(h.hp, max_hp), "max_hp": max_hp, "atk": maxf(1.0, st.atk + atk_add),
			"def": st.def, "crit": st.crit, "dodge": st.dodge, "shield": max_hp * shield_pct,
			"ranks": h.ranks, "weapon": h.weapon, "model": Outfits.model_of(o), "alt_model": Outfits.ult_model_of(o),
		})
	return Battle.new(heroes, enemies, rng.int_range(0, 2147483646))


## Applies a won fight to the run and the meta progress: health, PTO, Village Sauce,
## loot, stats and achievements. Returns
## {pto, sauce, weapon: {hero, id} or {}, full_heal, picks, unlocked}.
static func finish_fight(run: Dictionary, battle: Battle, meta: Dictionary) -> Dictionary:
	var rng := run_rng(run)
	var info := stage_info(run.stage, run.seed)
	var boss: bool = info.kind == "boss"
	run.next_fight = []
	if boss:
		run.rival_empowered = false
	var heal_pct := 0.2 + 0.08 * MetaUpgrades.level(meta, "benefits")
	for h in run.heroes:
		var u := battle.hero(h.id)
		var mx: int = hero_stats(h, meta).max_hp
		if boss:
			h.hp = mx
		else:
			h.hp = mini(mx, u.hp + roundi(mx * heal_pct)) if u.alive else roundi(mx * 0.3)
		# Possessed by his own ghost: James comes back at half health.
		if h.id == "james" and battle.stats.james_possessed:
			h.hp = roundi(mx * 0.5)
	run.kills += battle.kills
	run.fights_won += 1
	var pto: int = 30 + 8 * info.cycle if boss else (25 if info.kind == "bonus" else 9 + 2 * info.cycle)
	var sauce := 0
	if info.kind == "bonus":
		sauce = 20 + 10 * info.cycle + 5 * battle.heroes().filter(func(u): return u.alive).size()
		run.sauce_earned += sauce
	var weapon := {}
	# Bosses always drop a weapon (or extra PTO once you own them all); the burger joint sometimes does.
	if boss or (info.kind == "bonus" and rng.chance(0.6)):
		var opts := unowned_weapons(run)
		if not opts.is_empty():
			var id: String = rng.pick(opts)
			var h := hero_state(run, HeroData.WEAPONS[id].hero)
			h.weapons.append(id)
			weapon = {"hero": h.id, "id": id}
		elif boss:
			pto += 15
	run.pto += pto
	save_rng(run, rng)

	meta.sauce += sauce
	meta.total_sauce += sauce
	Achievements.bump(meta, "fights_won")
	if boss:
		Achievements.bump(meta, "bosses_beaten")
	if info.kind == "bonus":
		Achievements.bump(meta, "burger_won")
	Achievements.bump(meta, "sarah_boss_kills", battle.stats.sarah_boss_kills)
	var unlocked := Achievements.check_all({
		"meta": meta, "fight": battle.stats, "boss": info.boss if boss else "",
		"party": run.heroes.map(func(h): return h.id), "kind": info.kind,
	})
	return {"pto": pto, "sauce": sauce, "weapon": weapon, "full_heal": boss, "picks": 4 if boss else 3, "unlocked": unlocked}


## Moves to the next stage after the draft and shop. Returns a random event to show
## ({} for none); apply the player's choice with RunEvents.apply.
static func advance(run: Dictionary) -> Dictionary:
	run.stage += 1
	var rng := run_rng(run)
	var ev := RunEvents.roll(run, rng)
	save_rng(run, rng)
	return ev


## Revives the party after a wipe if Second Wind is still available.
static func use_second_wind(run: Dictionary, meta: Dictionary) -> bool:
	if not run.second_wind:
		return false
	run.second_wind = false
	for h in run.heroes:
		h.hp = roundi(hero_stats(h, meta).max_hp * 0.4)
	return true


## Ends a run. A wipe before the first burger fight is cleared gives a little
## Village Sauce so new players still make progress. Returns {catch_up}.
static func game_over(run: Dictionary, meta: Dictionary) -> Dictionary:
	meta.best_stage = maxi(meta.best_stage, run.stage)
	var catch_up := 0
	if run.stage < STAGES_PER_CYCLE:
		catch_up = 5
		meta.sauce += catch_up
		meta.total_sauce += catch_up
	return {"catch_up": catch_up}


## Weapons not yet owned by heroes in the party.
static func unowned_weapons(run: Dictionary) -> Array:
	var out := []
	for id in HeroData.WEAPONS:
		var h := hero_state(run, HeroData.WEAPONS[id].hero)
		if not h.is_empty() and not h.weapons.has(id):
			out.append(id)
	return out


# ------------------------------------------------------------------ upgrades
static func stat_text(stat: String, amount: float) -> String:
	var p := "+%d%%" % roundi(amount * 100)
	return {"hp": "%s max HP", "atk": "%s damage", "crit": "%s crit chance", "dodge": "%s dodge", "def": "%s damage reduction"}[stat] % p


static func _rank_options(run: Dictionary) -> Array:
	var out := []
	for h in run.heroes:
		for a in HeroData.rankable(h.id):
			if h.ranks.get(a, 1) < HeroData.MAX_RANK:
				out.append({"kind": "rank", "hero": h.id, "ability": a})
	return out


## Three choices: {kind: "rank", hero, ability} or {kind: "stat", hero, stat, amount, name}.
## The first pick after every win only offers ability upgrades; after a boss (four
## picks) the first two do.
static func roll_draft(run: Dictionary, rng: Rng, step: int, total := 3) -> Array:
	var ranks := rng.shuffle(_rank_options(run))
	var stats := []
	for h in run.heroes:
		for s in STAT_UPS:
			stats.append({"kind": "stat", "hero": h.id, "stat": s.stat, "amount": s.amount, "name": s.name})
	for s in PARTY_UPS:
		stats.append({"kind": "stat", "hero": "all", "stat": s.stat, "amount": s.amount, "name": s.name})
	rng.shuffle(stats)
	if (step == 0 or (total > 3 and step == 1)) and ranks.size() >= 3:
		return ranks.slice(0, 3)
	return rng.shuffle(ranks.slice(0, 2) + stats.slice(0, 3)).slice(0, 3)


static func upgrade_text(u: Dictionary) -> Dictionary:
	if u.kind == "stat":
		var who: String = "Whole party" if u.hero == "all" else HeroData.HEROES[u.hero].name
		return {"title": u.name, "desc": "%s: %s" % [who, stat_text(u.stat, u.amount)]}
	return {"title": HeroData.ABILITIES[u.ability].name, "desc": HeroData.describe(u.ability, 1)}


static func apply_stat(run: Dictionary, meta: Dictionary, hero: String, stat: String, amount: float) -> void:
	for h in run.heroes:
		if hero != "all" and h.id != hero:
			continue
		var before: int = hero_stats(h, meta).max_hp
		match stat:
			"hp": h.hp_mult += amount
			"atk": h.atk_mult += amount
			_: h[stat] += amount
		h.hp += hero_stats(h, meta).max_hp - before


static func apply_upgrade(run: Dictionary, meta: Dictionary, u: Dictionary) -> void:
	if u.kind == "stat":
		apply_stat(run, meta, u.hero, u.stat, u.amount)
	else:
		var h := hero_state(run, u.hero)
		h.ranks[u.ability] = mini(HeroData.MAX_RANK, h.ranks.get(u.ability, 1) + 1)


# ------------------------------------------------------------------ shop
## Items: {kind: heal|weapon|rank|stat, name, desc, cost, hero, weapon, ability, stat, amount, sold}.
static func roll_shop(run: Dictionary, meta: Dictionary, rng: Rng) -> Array:
	var items := [{"kind": "heal", "name": "Break Room Snacks", "desc": "Heal the whole party 40%.", "cost": 10, "sold": false}]
	var weapons := rng.shuffle(unowned_weapons(run)).slice(0, 2)
	var cycle: int = stage_info(run.stage, run.seed).cycle
	for id in weapons:
		var w: Dictionary = HeroData.WEAPONS[id]
		items.append({"kind": "weapon", "name": w.name, "desc": "%s's weapon. %s" % [HeroData.HEROES[w.hero].name, w.desc],
			"cost": w.cost + 3 * cycle, "hero": w.hero, "weapon": id, "sold": false})
	var extras := 3 + MetaUpgrades.level(meta, "menu") - weapons.size() + 1
	for i in extras:
		var h: Dictionary = rng.pick(run.heroes)
		var roll := rng.next()
		if roll < 0.35:
			var opts := HeroData.rankable(h.id).filter(func(a): return h.ranks.get(a, 1) < HeroData.MAX_RANK)
			if not opts.is_empty():
				var a: String = rng.pick(opts)
				var r: int = h.ranks.get(a, 1)
				items.append({"kind": "rank", "name": "Training: %s" % HeroData.ABILITIES[a].name,
					"desc": "%s: rank %s -> %s" % [HeroData.HEROES[h.id].name, HeroData.roman(r), HeroData.roman(r + 1)],
					"cost": 22, "hero": h.id, "ability": a, "sold": false})
				continue
		var s: Dictionary = rng.pick(STAT_UPS)
		var amount: float = s.amount * 0.8
		items.append({"kind": "stat", "name": s.name, "desc": "%s: %s" % [HeroData.HEROES[h.id].name, stat_text(s.stat, amount)],
			"cost": 14, "hero": h.id, "stat": s.stat, "amount": amount, "sold": false})
	return items


static func buy_item(run: Dictionary, meta: Dictionary, item: Dictionary) -> bool:
	if item.sold or run.pto < item.cost:
		return false
	match item.kind:
		"rank":
			var h := hero_state(run, item.hero)
			if h.ranks.get(item.ability, 1) >= HeroData.MAX_RANK:
				return false
			h.ranks[item.ability] = h.ranks.get(item.ability, 1) + 1
		"stat":
			apply_stat(run, meta, item.hero, item.stat, item.amount)
		"weapon":
			var h := hero_state(run, item.hero)
			if not h.weapons.has(item.weapon):
				h.weapons.append(item.weapon)
			h.weapon = item.weapon
		_:
			for h in run.heroes:
				var mx: int = hero_stats(h, meta).max_hp
				h.hp = mini(mx, h.hp + roundi(mx * 0.4))
	run.pto -= item.cost
	item.sold = true
	return true
