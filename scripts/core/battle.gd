class_name Battle
extends RefCounted
## A deterministic, turn-based fight, ported from the original's src/combat/battle.ts.
##
## Each round, every hero acts (in any order the player picks), then every enemy acts.
## Statuses tick at the start of their side's phase and count down at the end of it.
## The battle only records events (see `events`); the 3D battle scene plays them back.
##
## Event shapes (all Dictionaries with a "t" key):
##   beat {dur} · turn {side, round} · act {uid, to, style, pet, color}
##   dmg {uid, amount, hp, shield, crit, kind} · heal {uid, amount, hp} · shield {uid, shield}
##   miss {uid, text} · status {uid, text, color} · say {uid, text} · cast {uid, name, ult}
##   death {uid} · revive {uid, hp} · aoe {side, color} · shake {power} · banner {text, sub}
##   model {uid, model} · fx {kind, uid} · resource {uid, mp, energy}

const NO_TARGET := -1
## Detonations can take at most this share of a boss's max HP at once.
const DETONATE_BOSS_CAP := 0.35

var units: Array[BattleUnit] = []
var events: Array[Dictionary] = []
var rng: Rng
var round := 1
var phase := "hero" ## "hero", "enemy" or "over"
var outcome := "" ## "", "win" or "lose"
var acted := {} ## uid -> true: heroes who used their action this round
var buffed := {} ## uid -> true: heroes who used their one quick buff this round
var kills := 0
## Things that happened, for achievements.
var stats := {
	"we_go_next": false, "cole_revived": false, "blackjack": false, "titan_hits": 0,
	"rage_bait_crits": 0, "sam_damaged": false, "best_dab": 0,
	"cole_stunned": false, "aura_stolen": 0, "popups": 0, "popups_dismissed": 0,
	"boomboxes": 0, "james_possessed": false, "silenced": false,
}
## Boss state
var mog := 0 ## the Mystery Sales Guy's Aura stacks: -6% hero damage each (not Cam)
var pending_popup := {} ## a Cowork pop-up waiting for the player: {uid, left, timer, swap, pro}
var popup_count := 0 ## pop-ups shown this fight (the timer shrinks)
var last_ability_uid := NO_TARGET ## last hero to use an ability (the Cashier silences them)
var enemy_scale := {"hp_mult": 1.0, "atk_mult": 1.0} ## for mid-fight spawns
var goblin := 0 ## stun length of a pending Mind Goblin trap (0 = none)
var last_hero_hit := {} ## {uid, amount}: for High on Potenuse
var dmg_by := {} ## uid -> total damage dealt, for balance reports
var dmg_log := {} ## "hero key|action or dot kind" -> damage, for balance reports
var _action := "" ## the action being resolved, for dmg_log
var _queue: Array[int] = []
var _next_uid := 1


## heroes: Array of setups from Battle.hero_setup();
## enemies: Array of {id, hp_mult, atk_mult, suffix, remix}.
func _init(heroes: Array, enemies: Array, seed: int) -> void:
	rng = Rng.new(seed)
	for i in heroes.size():
		units.append(_make_hero(heroes[i], i))
	for i in enemies.size():
		units.append(_make_enemy(enemies[i], i))
	if not enemies.is_empty():
		enemy_scale = {"hp_mult": enemies[0].get("hp_mult", 1.0), "atk_mult": enemies[0].get("atk_mult", 1.0)}
	for e in enemies():
		EnemyData.on_fight_start(self, e)
	_begin_hero_phase(true)


## Adds an enemy mid-fight (the Guardian's Boombox). Emits a spawn event.
func add_enemy(id: String, owner: BattleUnit = null, hp_mult := 1.0) -> BattleUnit:
	var setup := enemy_scale.duplicate()
	setup.id = id
	setup.hp_mult = setup.hp_mult * hp_mult
	var u := _make_enemy(setup, enemies().size())
	if owner:
		u.owner_uid = owner.uid
	units.append(u)
	emit({"t": "spawn", "uid": u.uid, "key": u.key})
	return u


func has_enemy(key: String) -> bool:
	return enemies().any(func(e): return e.key == key and e.alive)


## A hero at base stats with the default weapon. Override fields as needed.
static func hero_setup(id: String, weapon := "") -> Dictionary:
	var d: Dictionary = HeroData.HEROES[id]
	return {
		"id": id, "hp": d.hp, "max_hp": d.hp, "atk": float(d.atk), "def": d.def,
		"crit": d.crit, "dodge": d.dodge, "ranks": {},
		"weapon": weapon if weapon != "" else HeroData.STARTING_WEAPON[id],
	}


# ------------------------------------------------------------------ setup
func _base(side: String, key: String, slot: int) -> BattleUnit:
	var u := BattleUnit.new()
	u.uid = _next_uid
	_next_uid += 1
	u.side = side
	u.key = key
	u.name = key
	u.model = key
	u.base_model = key
	u.slot = slot
	return u


func _make_hero(h: Dictionary, slot: int) -> BattleUnit:
	var d: Dictionary = HeroData.HEROES[h.id]
	var w: Dictionary = HeroData.WEAPONS[h.weapon]
	var u := _base("hero", h.id, slot)
	u.name = d.name
	u.row = d.row
	u.model = h.get("model", h.id)
	u.base_model = u.model
	u.alt_model = h.get("alt_model", "")
	u.max_hp = h.max_hp
	u.hp = clampi(h.hp, 1, h.max_hp)
	u.atk = h.atk
	u.def = h.def + w.get("def", 0.0)
	u.crit = h.crit
	u.dodge = h.dodge
	u.dmg_bonus = w.get("dmg_bonus", 0.0)
	u.ability_bonus = w.get("ability_bonus", 0.0)
	u.parry = w.get("parry", 0.0)
	u.ranks = h.ranks.duplicate()
	u.weapon = h.weapon
	u.shield = roundi(h.get("shield", 0))
	if d.has("max_mp"):
		u.max_mp = d.max_mp
		u.mp = d.start_mp
		u.mp_regen = w.get("mp_regen", 0.0)
	if d.has("max_energy"):
		u.max_energy = d.max_energy
	for id in d.abilities + [d.ultimate]:
		u.cd[id] = HeroData.ABILITIES[id].get("first", 0)
	return u


func _make_enemy(e: Dictionary, slot: int) -> BattleUnit:
	var d: Dictionary = EnemyData.ENEMIES[e.id]
	var u := _base("enemy", e.id, slot)
	var hp := roundi(d.hp * e.get("hp_mult", 1.0))
	u.remix = e.get("remix", false) and d.has("remix_name")
	u.name = d.remix_name if u.remix else d.name
	if e.has("suffix"):
		u.name = "%s (%s)" % [u.name, e.suffix]
	u.model = e.id + ("_remix" if u.remix else "")
	u.base_model = u.model
	u.boss = d.get("boss", false)
	u.inert = d.get("inert", false)
	u.max_hp = hp
	u.hp = hp
	u.atk = d.atk * e.get("atk_mult", 1.0)
	u.def = d.get("def", 0.0)
	u.dodge = d.get("dodge", 0.0)
	u.crit = d.get("crit", 0.05)
	for sk in d.skills:
		u.cd[sk.id] = sk.get("first", 0)
	return u


# ------------------------------------------------------------------ queries
func unit(uid: int) -> BattleUnit:
	for u in units:
		if u.uid == uid:
			return u
	return null


func heroes() -> Array:
	return units.filter(func(u): return u.side == "hero")


func enemies() -> Array:
	return units.filter(func(u): return u.side == "enemy")


func hero(id: String) -> BattleUnit:
	for u in units:
		if u.side == "hero" and u.key == id:
			return u
	return null


func targetable(u: BattleUnit) -> bool:
	return u.alive and not has(u, "away")


func foes_of(u: BattleUnit) -> Array:
	return units.filter(func(o): return o.side != u.side and targetable(o))


func allies_of(u: BattleUnit) -> Array:
	return units.filter(func(o): return o.side == u.side and targetable(o))


func status_of(u: BattleUnit, kind: String) -> Variant:
	for s in u.statuses:
		if s.kind == kind:
			return s
	return null


func has(u: BattleUnit, kind: String) -> bool:
	return status_of(u, kind) != null


func power(u: BattleUnit, kind: String) -> float:
	var total := 0.0
	for s in u.statuses:
		if s.kind == kind:
			total += s.power
	return total


func rank(u: BattleUnit, id: String) -> int:
	return u.ranks.get(id, 1)


## Damage multiplier from buffs, debuffs and passives; also scales DoTs and effects.
func mult(u: BattleUnit) -> float:
	var m := 1.0 + power(u, "empower") + u.dmg_bonus + u.aura - power(u, "weaken")
	if mog > 0 and u.side == "hero" and u.key != "cam":
		m -= 0.06 * mog
	return maxf(0.1, m)


## Heroes who can still take an action this phase.
func ready() -> Array:
	if phase != "hero":
		return []
	return heroes().filter(func(h): return h.alive and not acted.has(h.uid) and not has(h, "stun") and not has(h, "away"))


## The hero's menu: basic attack, then abilities and ultimate.
## Each: {id, name, kind, target, ready, cd_left, quick, rank, desc, cost, resource}
func actions(u: BattleUnit) -> Array[Dictionary]:
	var w: Dictionary = HeroData.WEAPONS[u.weapon]
	var silenced := has(u, "silence")
	var out: Array[Dictionary] = [{
		"id": "attack", "name": w.name, "kind": "attack", "target": w.target, "ready": true,
		"cd_left": 0, "quick": false, "rank": 0, "desc": w.desc, "cost": 0, "resource": "",
	}]
	var d: Dictionary = HeroData.HEROES[u.key]
	for id in d.abilities + [d.ultimate]:
		var ab: Dictionary = HeroData.ABILITIES[id]
		var r := rank(u, id)
		var cd_left: int = u.cd.get(id, 0)
		var cost := HeroData.ability_cost(id, r)
		var res: String = ab.get("resource", "")
		var affordable := cost <= 0 or (u.mp if res == "mp" else u.energy) >= cost
		var quick: bool = ab.get("quick", false)
		out.append({
			"id": id, "name": ab.name, "kind": "ultimate" if ab.kind == "ultimate" else "ability",
			"target": ab.target, "cd_left": cd_left, "quick": quick, "rank": r,
			"ready": not silenced and cd_left <= 0 and affordable and not (quick and buffed.has(u.uid)),
			"desc": HeroData.describe(id, r), "cost": cost, "resource": res,
		})
	return out


# ------------------------------------------------------------------ events
func emit(e: Dictionary) -> void:
	events.append(e)


func beat(dur := 0.45) -> void:
	emit({"t": "beat", "dur": dur})


func say(u: BattleUnit, text: String) -> void:
	emit({"t": "say", "uid": u.uid, "text": text})


func anim(u: BattleUnit, to: BattleUnit, style: String, extra := {}) -> void:
	var e := {"t": "act", "uid": u.uid, "to": to.uid if to else NO_TARGET, "style": style}
	e.merge(extra)
	emit(e)


func aoe(side: String, color: String) -> void:
	emit({"t": "aoe", "side": side, "color": color})


func shake(p: float) -> void:
	emit({"t": "shake", "power": p})


func note(u: BattleUnit, text: String, color := "#ffffff") -> void:
	emit({"t": "status", "uid": u.uid, "text": text, "color": color})


func _resource_event(u: BattleUnit) -> void:
	emit({"t": "resource", "uid": u.uid, "mp": u.mp, "energy": u.energy})


# ------------------------------------------------------------------ effects
func add_status(u: BattleUnit, kind: String, dur: int, pow := 0.0, src := NO_TARGET, quiet := false) -> void:
	if not u.alive or dur <= 0:
		return
	if kind == "stun" and has(u, "resolve"):
		note(u, "Resists")
		return
	if kind == "stun" and u.boss:
		# Diminishing returns: each stun after the first lasts a turn less (min 1).
		dur = maxi(1, dur - u.stuns_taken)
		u.stuns_taken += 1
	var cur = status_of(u, kind)
	if cur:
		cur.power = cur.power + pow if kind in StatusInfo.STACKING else maxf(cur.power, pow)
		cur.dur = maxi(cur.dur, dur)
		if src != NO_TARGET:
			cur.src = src
	else:
		u.statuses.append({"kind": kind, "dur": dur, "power": pow, "src": src})
	var info: Dictionary = StatusInfo.INFO[kind]
	if not quiet and not info.get("hidden", false):
		note(u, info.label, info.color)


func remove_status(u: BattleUnit, kind: String) -> void:
	u.statuses = u.statuses.filter(func(s): return s.kind != kind)


## Applies a damage-over-time effect scaled from the source's attack.
func dot(src: BattleUnit, tgt: BattleUnit, kind: String, atk_frac: float, dur: int) -> void:
	add_status(tgt, kind, dur, maxf(1.0, src.atk * atk_frac * mult(src)), src.uid)


func stun(tgt: BattleUnit, dur: int, chance := 1.0) -> bool:
	if not tgt.alive or not rng.chance(chance):
		return false
	add_status(tgt, "stun", dur)
	return true


func heal(u: BattleUnit, amount: float) -> int:
	if not u.alive:
		return 0
	var a := maxi(0, mini(u.max_hp - u.hp, roundi(amount)))
	u.hp += a
	if a > 0:
		emit({"t": "heal", "uid": u.uid, "amount": a, "hp": u.hp})
	return a


func shield_up(u: BattleUnit, amount: float) -> void:
	if not u.alive:
		return
	u.shield = mini(u.max_hp * 2, u.shield + roundi(amount))
	emit({"t": "shield", "uid": u.uid, "shield": u.shield})


func gain_energy(u: BattleUnit, amount: float) -> void:
	if u.max_energy <= 0:
		return
	u.energy = minf(u.max_energy, u.energy + amount)
	_resource_event(u)


## An attack from src to tgt. Returns the damage dealt (0 on a miss or block).
## Options: no_dodge, no_crit, flat (fixed damage), pierce (ignores armor), weapon,
## bonus (extra damage multiplier), crit_bonus.
func hit(src: BattleUnit, tgt: BattleUnit, m: float, o := {}) -> int:
	if not tgt.alive:
		return 0
	var weapon: bool = o.get("weapon", false)
	var flat = o.get("flat", null)
	var base: float = flat if flat != null else src.atk * m
	var mul: float = mult(src) + o.get("bonus", 0.0)
	mul += src.prep.get("lesson", 0.0) if weapon else src.ability_bonus
	var dmg := base * maxf(0.1, mul)
	var crit := false
	if has(src, "blind") and src != tgt and rng.chance(power(src, "blind")):
		emit({"t": "miss", "uid": tgt.uid, "text": "Blinded"})
		return 0
	if not o.get("no_crit", false) and flat == null and rng.chance(src.crit + power(src, "crit") + o.get("crit_bonus", 0.0)):
		dmg *= 1.6
		crit = true
	dmg *= 1.0 + power(tgt, "earworm")
	var exposed := has(tgt, "exposed")
	if exposed:
		dmg *= 1.0 + power(tgt, "exposed")
	var no_dodge: bool = o.get("no_dodge", false) or exposed or (weapon and src.prep.has("argue"))
	if not no_dodge and src != tgt and rng.chance(minf(0.6, tgt.dodge + power(tgt, "dodge"))):
		emit({"t": "miss", "uid": tgt.uid, "text": "Dodge"})
		return 0
	if tgt.parry > 0 and src != tgt and rng.chance(tgt.parry):
		emit({"t": "miss", "uid": tgt.uid, "text": "Parry"})
		return 0
	if not o.get("pierce", false):
		dmg *= 1.0 - minf(0.75, tgt.def + power(tgt, "guard"))
	var amount := maxi(1, roundi(dmg))
	var refl := power(tgt, "reflect")
	if has(tgt, "protect"):
		emit({"t": "miss", "uid": tgt.uid, "text": "Blocked"})
		if refl > 0 and src != tgt and src.alive:
			damage(src, maxi(1, roundi(amount * refl)), "reflect", false, tgt)
		return 0
	damage(tgt, amount, "hit", crit, src)
	if refl > 0 and src != tgt and src.alive:
		damage(src, maxi(1, roundi(amount * refl)), "reflect", false, tgt)
	if src.side == "hero" and tgt.side == "enemy":
		last_hero_hit = {"uid": src.uid, "amount": amount}
	if crit and o.get("rage_bait", false):
		stats.rage_bait_crits += 1
	EnemyData.on_hit(self, src, tgt, amount, crit)
	if weapon and src.alive:
		if src.prep.has("burn"):
			add_status(tgt, "burn", 3, src.prep.burn, src.uid)
		if src.prep.has("stun"):
			stun(tgt, 1, src.prep.stun)
	return amount


## Raw damage after mitigation: eats shield first, then health.
func damage(u: BattleUnit, amount: int, kind: String, crit := false, src: BattleUnit = null) -> void:
	if not u.alive:
		return
	var rest := amount
	if u.shield > 0:
		var ab := mini(u.shield, rest)
		u.shield -= ab
		rest -= ab
	u.hp = maxi(0, u.hp - rest)
	u.dmg_taken += amount
	if src:
		dmg_by[src.uid] = dmg_by.get(src.uid, 0) + amount
		var tag := "%s|%s" % [src.key, kind if kind in StatusInfo.DOTS and _action == "" else _action]
		dmg_log[tag] = dmg_log.get(tag, 0) + amount
	if u.key == "sam" and u.side == "hero":
		stats.sam_damaged = true
	emit({"t": "dmg", "uid": u.uid, "amount": amount, "hp": u.hp, "shield": u.shield, "crit": crit, "kind": kind})
	if src and src.side == "hero" and u.key == "sauce_keeper":
		EnemyData.sauce_keeper_hit(self, u)
	if u.hp <= 0:
		kill(u)


## Deals all of a target's remaining Bleed damage at once (times m) and removes it.
func detonate(src: BattleUnit, tgt: BattleUnit, m: float) -> int:
	var s = status_of(tgt, "bleed")
	if s == null or not tgt.alive:
		return 0
	var total: float = s.power * s.dur * m
	if tgt.boss:
		total = minf(total, tgt.max_hp * DETONATE_BOSS_CAP)
	remove_status(tgt, "bleed")
	var amount := maxi(1, roundi(total))
	note(tgt, "Detonate!", StatusInfo.INFO.bleed.color)
	damage(tgt, amount, "bleed", false, src)
	return amount


func kill(u: BattleUnit) -> void:
	if not u.alive:
		return
	u.alive = false
	u.hp = 0
	u.shield = 0
	u.statuses = []
	emit({"t": "death", "uid": u.uid})
	if u.side == "enemy":
		kills += 1
		EnemyData.on_death(self, u)
		for s in enemies():
			if s.owner_uid == u.uid and s.alive:
				kill(s)
	if u.key == "cole" and u.side == "hero" and not u.passive_used:
		u.passive_used = true
		u.revive_next = true
		note(u, "9 Iron on Ciabatta...", "#ffd23f")


# ------------------------------------------------------------------ turn flow
func _tick_side(side: String) -> void:
	for u in units:
		if u.side != side or not u.alive:
			continue
		for s in u.statuses.duplicate():
			if s.kind in StatusInfo.DOTS:
				var src: BattleUnit = unit(s.src) if s.src != NO_TARGET else null
				damage(u, maxi(1, roundi(s.power)), s.kind, false, src)
				if not u.alive:
					break
			elif s.kind == "regen":
				heal(u, s.power)
		for k in u.cd.keys():
			if u.cd[k] > 0:
				u.cd[k] -= 1


func _decrement(side: String) -> void:
	for u in units:
		if u.side != side:
			continue
		var stunned := has(u, "stun")
		var waiting := has(u, "waiting_sauce")
		for s in u.statuses:
			s.dur -= 1
		u.statuses = u.statuses.filter(func(s): return s.dur > 0)
		if u.boss and stunned and not has(u, "stun"):
			u.statuses.append({"kind": "resolve", "dur": 2, "power": 0.0, "src": NO_TARGET})
		# Road Rage: against the Trucker, Cole can't be stunned twice in a row and hits harder each time.
		if u.key == "cole" and u.side == "hero" and u.alive and stunned and not has(u, "stun") and has_enemy("trucker"):
			u.statuses.append({"kind": "resolve", "dur": 1, "power": 0.0, "src": NO_TARGET})
			u.aura += 0.1
			note(u, "Road Rage!", "#ff5a3a")
		# The Sauce Keeper's promise ran out.
		if waiting and not has(u, "waiting_sauce") and u.alive:
			add_status(u, "weaken", 3, 0.25, NO_TARGET, true)
			note(u, "Sauce never came", "#c08aff")
		# James slims back down when JimmyTrains wears off.
		if u.key == "james" and u.alive and u.model != u.base_model and not has(u, "reflect"):
			u.model = u.base_model
			emit({"t": "model", "uid": u.uid, "model": u.model})


func _begin_hero_phase(first := false) -> void:
	if not first:
		round += 1
	phase = "hero"
	acted.clear()
	buffed.clear()
	emit({"t": "turn", "side": "hero", "round": round})
	for h in heroes():
		if h.revive_next:
			_revive_cole(h)
	_tick_side("hero")
	_round_passives()
	_check_we_go_next()
	if _check_end():
		return
	_skip_idle()


## Passives that fire at the start of each hero turn.
func _round_passives() -> void:
	var james := hero("james")
	if james and james.alive and round % 3 == 0:
		HeroData.use("uncrustable", self, james, null, rank(james, "uncrustable"))
	var sam := hero("sam")
	if sam and sam.alive:
		if round > 1:
			sam.mp = minf(sam.max_mp, sam.mp + sam.mp_regen)
			_resource_event(sam)
		HeroData.use("desk_treadmill", self, sam, null, rank(sam, "desk_treadmill"))
	var sarah := hero("sarah")
	if sarah and sarah.alive and round > 1:
		HeroData.use("dance_rehearsal", self, sarah, null, rank(sarah, "dance_rehearsal"))


func _revive_cole(u: BattleUnit) -> void:
	u.revive_next = false
	u.alive = true
	u.hp = u.max_hp
	emit({"t": "revive", "uid": u.uid, "hp": u.hp})
	HeroData.use("nine_iron", self, u, null, rank(u, "nine_iron"))
	beat(0.6)


## Stunned or removed heroes lose their action.
func _skip_idle() -> void:
	for h in heroes():
		if not h.alive or acted.has(h.uid):
			continue
		if has(h, "stun"):
			note(h, "Stunned", StatusInfo.INFO.stun.color)
			acted[h.uid] = true
		elif has(h, "away"):
			acted[h.uid] = true
	if ready().is_empty():
		_end_hero_phase()


## The player's move for one hero. Returns false if it isn't allowed.
func act(uid: int, action_id: String, target_uid := NO_TARGET) -> bool:
	var u := unit(uid)
	if u == null or not ready().has(u):
		return false
	var opt: Dictionary = {}
	for a in actions(u):
		if a.id == action_id:
			opt = a
	if opt.is_empty() or not opt.ready:
		return false
	var t: BattleUnit = unit(target_uid) if target_uid != NO_TARGET else null
	if opt.target == "enemy" and (t == null or not foes_of(u).has(t)):
		var foes := foes_of(u)
		t = foes[0] if not foes.is_empty() else null
	if opt.target == "ally" and (t == null or not allies_of(u).has(t)):
		t = u
	if opt.target == "enemy" and t == null:
		return false

	if has(u, "confuse") and not opt.quick and rng.chance(0.5):
		note(u, "Confused!", StatusInfo.INFO.confuse.color)
		var others := allies_of(u).filter(func(a): return a != u)
		var victim: BattleUnit = rng.pick(others) if not others.is_empty() else u
		anim(u, victim, "melee")
		hit(u, victim, 1.0, {"no_crit": true})
		acted[uid] = true
		beat()
		_after_action()
		return true

	_action = action_id
	if action_id == "attack":
		HeroData.weapon_attack(u.weapon, self, u, t)
		if u.key == "cole":
			_finish_prep(u)
	else:
		var ab: Dictionary = HeroData.ABILITIES[action_id]
		var r := rank(u, action_id)
		u.cd[action_id] = HeroData.ability_cd(action_id, r)
		if opt.cost > 0:
			if opt.resource == "mp":
				u.mp -= opt.cost
			else:
				u.energy -= opt.cost
			_resource_event(u)
		emit({"t": "cast", "uid": u.uid, "name": ab.name, "ult": ab.kind == "ultimate"})
		HeroData.use(action_id, self, u, t, r)
		last_ability_uid = u.uid
	_action = ""
	if u.key == "cam" and not opt.quick:
		u.aura += 0.03 + 0.01 * (rank(u, "aura_farming") - 1)
		EnemyData.steal_aura(self, u)
	if opt.quick:
		buffed[uid] = true
	else:
		acted[uid] = true
	beat()
	_after_action()
	return true


## Skips a hero's action (the "Wait" button: for when nothing can be targeted).
func pass_turn(uid: int) -> bool:
	var u := unit(uid)
	if u == null or not ready().has(u):
		return false
	note(u, "Waiting", "#9aa0b8")
	acted[uid] = true
	_after_action()
	return true


func _finish_prep(u: BattleUnit) -> void:
	if u.prep.has("argue"):
		for e in foes_of(u):
			add_status(e, "poison", 3, u.prep.argue, u.uid)
		aoe("enemy", "124,255,79")
	u.prep = {}


func _after_action() -> void:
	_check_we_go_next()
	if _check_end():
		return
	if phase == "hero" and ready().is_empty():
		_end_hero_phase()


func _end_hero_phase() -> void:
	_decrement("hero")
	phase = "enemy"
	emit({"t": "turn", "side": "enemy", "round": round})
	_tick_side("enemy")
	_check_we_go_next()
	if _check_end():
		return
	_queue.clear()
	for e in enemies():
		if e.alive and not e.inert:
			_queue.append(e.uid)


## Shows a Cowork pop-up; the fight waits until answer_popup() is called.
## count > 1 queues more (Mandatory Rollout). The UI shows the "Not now" and
## "Yes, install" buttons (plus "Upgrade to Pro" if pro), swapped if swap, with a
## countdown of `timer` seconds (players can lengthen it in Settings).
func show_popup(boss: BattleUnit, count: int) -> void:
	popup_count += 1
	stats.popups += 1
	pending_popup = {
		"uid": boss.uid, "left": count - 1, "pro": boss.remix and rng.chance(0.4),
		"timer": maxf(1.5, 2.5 - 0.25 * (popup_count - 1)), "swap": rng.chance(0.5),
	}
	var text: String = "Have you downloaded my Cowork skills yet?" if popup_count == 1 else rng.pick([
		"Have you downloaded my Cowork skills yet?", "Seriously. It'll save so much time.", "Just one quick install."])
	emit({"t": "popup", "uid": boss.uid, "text": text,
		"timer": pending_popup.timer, "swap": pending_popup.swap, "pro": pending_popup.pro})


## The player's answer to a pop-up: "dismiss", "install", "pro" or "timeout".
func answer_popup(choice: String) -> void:
	if pending_popup.is_empty():
		return
	var boss := unit(pending_popup.uid)
	var left: int = pending_popup.left
	pending_popup = {}
	if boss and boss.alive:
		EnemyData.resolve_popup(self, boss, choice)
	if not _check_end() and left > 0 and boss and boss.alive:
		show_popup(boss, left)


## Plays the next enemy's turn (one per call so the renderer can keep up).
## Does nothing while a pop-up is waiting for an answer.
func enemy_step() -> void:
	if phase != "enemy" or not pending_popup.is_empty():
		return
	while not _queue.is_empty():
		var u := unit(_queue.pop_front())
		if not u.alive:
			continue
		_enemy_act(u)
		beat()
		_check_we_go_next()
		_check_end()
		return
	_decrement("enemy")
	_begin_hero_phase()


func _enemy_act(u: BattleUnit) -> void:
	if has(u, "away"):
		EnemyData.on_return(self, u)
	if has(u, "stun"):
		note(u, "Stunned", StatusInfo.INFO.stun.color)
		return
	EnemyData.on_turn(self, u)
	if not u.alive or outcome != "":
		return
	if has(u, "confuse") and rng.chance(0.75):
		note(u, "Confused!", StatusInfo.INFO.confuse.color)
		anim(u, u, "melee")
		hit(u, u, 1.0 + power(u, "confuse"), {"no_dodge": true, "no_crit": true})
		return
	var d: Dictionary = EnemyData.ENEMIES[u.key]
	for sk in d.skills:
		if u.cd.get(sk.id, 0) > 0:
			continue
		u.cd[sk.id] = sk.cd
		if goblin > 0:
			var cam := hero("cam")
			emit({"t": "cast", "uid": u.uid, "name": sk.name, "ult": false})
			note(u, "Mind Goblin!", "#7cff4f")
			if cam and cam.alive:
				say(cam, rng.pick(["Wagwan", "SMH my head"]))
			add_status(u, "stun", goblin)
			goblin = 0
			return
		var ult: bool = sk.get("ult", false)
		emit({"t": "cast", "uid": u.uid, "name": sk.name, "ult": ult})
		if ult:
			emit({"t": "banner", "text": sk.name, "sub": u.name})
		EnemyData.use_skill(u.key, sk.id, self, u)
		return
	var t := pick_hero_target(u)
	if t == null:
		return
	anim(u, t, d.style, {"color": d.get("color", "")})
	hit(u, t, 1.0)


## Taunts win; otherwise front-liners draw more attacks.
func pick_hero_target(u: BattleUnit) -> BattleUnit:
	var taunt = status_of(u, "taunt")
	if taunt and taunt.src != NO_TARGET:
		var src := unit(taunt.src)
		if src and targetable(src):
			return src
	var hs := foes_of(u)
	if hs.is_empty():
		return null
	# The Angry Trucker's Grudge: half his attacks go at Cole.
	if u.key == "trucker":
		var cole := hero("cole")
		if cole and targetable(cole) and rng.chance(0.5):
			return cole
	return rng.weighted(hs, func(h): return 1.6 if h.row == "front" else 1.0)


func _check_we_go_next() -> void:
	var m := hero("mason")
	if m == null or not m.alive or m.passive_used or phase == "over":
		return
	var alive := heroes().filter(func(h): return h.alive)
	var th := HeroData.we_go_next_threshold(rank(m, "we_go_next"))
	if alive.is_empty() or not alive.all(func(h): return h.hp < h.max_hp * th):
		return
	HeroData.use("we_go_next", self, m, null, rank(m, "we_go_next"))


func _check_end() -> bool:
	if phase == "over":
		return true
	if not enemies().any(func(e): return e.alive):
		phase = "over"
		outcome = "win"
		return true
	if not heroes().any(func(h): return h.alive or h.revive_next):
		phase = "over"
		outcome = "lose"
		return true
	return false
