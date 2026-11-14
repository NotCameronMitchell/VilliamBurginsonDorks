class_name BattleAI
extends RefCounted
## A simple policy that plays the heroes' turns. Used by the tests and balance
## simulations, and later by the in-game "Auto" button. Ported from src/game/ai.ts.

const ORDER := {
	"mason": ["wife_btw", "bite", "swipe", "headbutt", "lick"],
	"cole": ["transfer_uw", "ole_miss", "golf_lesson", "cft", "argue_sales"],
	"cam": ["nissan_titan", "iceland_story", "mind_goblin", "would_you_rather", "shopping_spree"],
}


static func _lowest(units: Array) -> BattleUnit:
	var best: BattleUnit = null
	for u in units:
		if best == null or u.hp < best.hp:
			best = u
	return best


## Total Bleed damage still waiting on the enemies.
static func pending_bleed(b: Battle, u: BattleUnit) -> float:
	var total := 0.0
	for e in b.foes_of(u):
		var s = b.status_of(e, "bleed")
		if s:
			total += s.power * s.dur
	return total


static func _order(b: Battle, u: BattleUnit, foes: Array) -> Array:
	var hp_frac := float(u.hp) / u.max_hp
	match u.key:
		"james":
			if hp_frac < 0.5:
				return ["fogo", "jimmytrains", "throat_punch", "peptide_rage", "daily_dollar"]
			return ["jimmytrains", "peptide_rage", "throat_punch", "daily_dollar"]
		"sam":
			var o := ["out_of_pocket"]
			if hp_frac < 0.5 and u.shield < u.max_hp * 0.1:
				o.append("ignore_emails")
			if foes.size() >= 2:
				o += ["burger_bomb", "energy_drinks_bad"]
			o.append("rage_bait")
			return o
		"sarah":
			var o := []
			if u.energy >= 60 or (foes.size() == 1 and foes[0].hp < foes[0].max_hp * 0.3):
				o.append("subaru_driveby")
			if pending_bleed(b, u) >= u.atk * 3:
				o.append("dab")
			o += ["catching_the_fish", "the_worm" if foes.size() >= 2 else "scuba", "scuba", "the_worm"]
			return o
	return ORDER.get(u.key, [])


## Picks one move for the hero: [action id, target uid].
static func choose_action(b: Battle, u: BattleUnit) -> Array:
	var opts := b.actions(u).filter(func(a): return a.ready)
	var foes := b.foes_of(u)
	var boss: BattleUnit = null
	for f in foes:
		if f.boss:
			boss = f
	var focus: BattleUnit = boss if boss and foes.size() <= 2 else _lowest(foes)
	# Break the Guardian's Boombox once the Earworm builds up.
	for f in foes:
		if f.key == "boombox" and b.power(u, "earworm") >= 0.24:
			focus = f
	# Hit the Sauce Keeper while the party is waiting on sauce.
	if b.has(u, "waiting_sauce"):
		for f in foes:
			if f.key == "sauce_keeper":
				focus = f
	var hp_frac := float(u.hp) / u.max_hp
	for id in _order(b, u, foes):
		if id == "transfer_uw" and hp_frac > 0.6 and foes.size() > 1:
			continue
		for o in opts:
			if o.id == id:
				return [id, _target_for(b, u, o, focus)]
	for o in opts:
		if o.id == "attack":
			return ["attack", _target_for(b, u, o, focus)]
	return ["attack", Battle.NO_TARGET]


static func _target_for(b: Battle, u: BattleUnit, o: Dictionary, focus: BattleUnit) -> int:
	if o.target == "enemy" and focus:
		return focus.uid
	if o.target == "ally":
		var a := _lowest(b.allies_of(u))
		return a.uid if a else Battle.NO_TARGET
	return Battle.NO_TARGET


## How a simulated player answers Cowork pop-ups: chance to click "Not now" in time,
## chance to click "Yes, install" by mistake. The rest time out.
const POPUP_DISMISS := 0.75
const POPUP_INSTALL := 0.1


static func answer_popup(b: Battle) -> void:
	var r := b.rng.next()
	if r < POPUP_DISMISS:
		b.answer_popup("dismiss")
	elif r < POPUP_DISMISS + POPUP_INSTALL:
		b.answer_popup("pro" if b.pending_popup.pro else "install")
	else:
		b.answer_popup("timeout")


## Plays a whole fight with the AI. Returns "win" or "lose".
static func auto_battle(b: Battle, max_rounds := 60) -> String:
	var guard := 0
	while b.outcome == "" and b.round <= max_rounds and guard < 5000:
		guard += 1
		if not b.pending_popup.is_empty():
			answer_popup(b)
		elif b.phase == "hero":
			var rdy := b.ready()
			if rdy.is_empty():
				break
			var u: BattleUnit = rdy[0]
			var pick := choose_action(b, u)
			if not b.act(u.uid, pick[0], pick[1]) and not b.act(u.uid, "attack"):
				b.pass_turn(u.uid)
		else:
			b.enemy_step()
	return b.outcome if b.outcome != "" else "lose"
