class_name EnemyData
extends RefCounted
## Enemies: the office minions (ported from the original's src/data/enemies.ts)
## and the sequel's six bosses (docs/GAME_DESIGN.md §4). The original bosses are retired.
##
## skills are checked in order each turn; the first one off cooldown is used.
## Add a `use_skill` case for each skill. Boss gimmicks hook in through the
## on_* functions below, which Battle calls at the right moments.
##
## A boss with a `remix_name` has a remixed version for later cycles: pass
## {"remix": true} in its enemy setup. Remix behavior is checked with `u.remix`.

const ENEMIES := {
	# ------------------------------------------------------------ minions
	"energy_drink": {
		"name": "Energy Drink", "blurb": "300mg of caffeine with legs. Sometimes hits twice.",
		"hp": 34, "atk": 6, "dodge": 0.08, "style": "melee",
		"skills": [{"id": "rush", "name": "Caffeine Rush", "cd": 3, "first": 1}],
	},
	"tallboy": {
		"name": "Tallboy Energy", "blurb": "A 24oz can that hypes up its friends.",
		"hp": 52, "atk": 7, "style": "melee",
		"skills": [{"id": "sugar", "name": "Sugar Rush", "cd": 3, "first": 1}],
	},
	"nic_pouch": {
		"name": "Nicotine Pouch", "blurb": "Tucked in a lip somewhere. Its hits Poison.",
		"hp": 26, "atk": 5, "dodge": 0.1, "style": "melee",
		"skills": [{"id": "tuck", "name": "Lip Tuck", "cd": 2}],
	},
	"pouch_tin": {
		"name": "Pouch Tin", "blurb": "A whole tin of them. Sturdy, and it weakens the party.",
		"hp": 60, "atk": 6, "def": 0.15, "style": "melee",
		"skills": [{"id": "mint", "name": "Cool Mint Cloud", "cd": 4, "first": 1}],
	},
	"reply_all": {
		"name": "Reply-All Guy", "blurb": "Hits everyone, every time.",
		"hp": 42, "atk": 6, "style": "ranged", "color": "#ffffff",
		"quotes": ["Per my last email...", "Adding the whole team!", "Thanks all!!"],
		"skills": [{"id": "reply", "name": "Reply All", "cd": 2, "first": 1}],
	},
	"fish_guy": {
		"name": "Microwave Fish Guy", "blurb": "Reheats salmon in the break room. Poisons everyone.",
		"hp": 46, "atk": 5, "style": "ranged", "color": "#7cff4f",
		"quotes": ["It's just salmon!", "Lunch time"],
		"skills": [{"id": "salmon", "name": "Reheated Salmon", "cd": 3, "first": 1}],
	},
	"loud_typer": {
		"name": "Mechanical Keyboard Guy", "blurb": "CLACK CLACK CLACK. Can stun.",
		"hp": 38, "atk": 7, "style": "melee",
		"quotes": ["Blue switches, baby"],
		"skills": [{"id": "clack", "name": "CLACK CLACK", "cd": 3, "first": 1}],
	},
	"close_talker": {
		"name": "Close Talker", "blurb": "Way too close. Weakens whoever he corners.",
		"hp": 48, "atk": 7, "style": "melee",
		"quotes": ["So anyway...", "Got a sec?"],
		"skills": [{"id": "corner", "name": "Got a Sec?", "cd": 3}],
	},

	# ------------------------------------------------------------ bosses
	"trucker": {
		"name": "The Angry Trucker", "remix_name": "Night Shift Trucker", "boss": true, "arena": "parking_lot",
		"blurb": "A semi idling across four parking spaces. He's here about an invoice, and he has it out for Cole.",
		"hp": 280, "atk": 13, "def": 0.1, "style": "melee",
		"quotes": ["#@$%&!!", "$#!% @&#*!", "@#$%!! &*%$!!"],
		"skills": [
			{"id": "send_money", "name": "SEND MY MONEY NOW", "cd": 5, "first": 3, "ult": true},
			{"id": "jake_brake", "name": "Jake Brake", "cd": 3, "first": 2},
			{"id": "air_horn", "name": "Air Horn", "cd": 2, "first": 1},
		],
	},
	"sales_guy": {
		"name": "The Mystery Sales Guy", "remix_name": "Q4 Sales Guy", "boss": true, "arena": "desk_pods",
		"blurb": "Nobody knows his name, what he sells, or why there's a coffee stirrer over his ear. Mogs the whole team.",
		"hp": 260, "atk": 12, "dodge": 0.2, "style": "melee",
		"quotes": ["*aura*"],
		"skills": [
			{"id": "jawline", "name": "Jawline Reveal", "cd": 5, "first": 3, "ult": true},
			{"id": "stirrer_flick", "name": "Stirrer Flick", "cd": 3, "first": 2},
			{"id": "silent_stare", "name": "Silent Stare", "cd": 2, "first": 1},
		],
	},
	"copilot": {
		"name": "The Copilot Grim Reaper", "remix_name": "Copilot Pro Reaper", "boss": true, "arena": "meeting_room",
		"blurb": "A hooded figure with a glowing laptop and a scythe. He just wants to save you some time.",
		"hp": 290, "atk": 12, "style": "cast", "color": "#7fd4ff",
		"quotes": ["This is for your own good.", "We can save so much time if you just do this."],
		"skills": [
			{"id": "rollout", "name": "Mandatory Rollout", "cd": 6, "first": 4, "ult": true},
			{"id": "cowork", "name": "Cowork Skills Pop-Up", "cd": 3, "first": 2},
			{"id": "scythe", "name": "Scythe of Suggestions", "cd": 2, "first": 1},
		],
	},
	"guardian": {
		"name": "The Guardian of Tunes", "remix_name": "Holiday Playlist Guardian", "boss": true, "arena": "office_center",
		"blurb": "She controls the office speaker. She has one playlist. It is on repeat.",
		"hp": 220, "atk": 12, "style": "cast", "color": "#ff7ae0",
		"quotes": ["Maroon 5 makes really good songs.", "Don't you just love Justin Bieber for the 10th time today?"],
		"skills": [
			{"id": "baby", "name": "Baby (10th Play Today)", "cd": 5, "first": 3, "ult": true},
			{"id": "maroon5", "name": "Maroon 5 Deep Cut", "cd": 2, "first": 1},
		],
	},
	"boombox": {
		"name": "The Boombox", "blurb": "Break it to stop the music.", "inert": true,
		"hp": 60, "atk": 0, "style": "cast", "skills": [],
	},
	"ghost": {
		"name": "The Ghost of James Civelli", "remix_name": "Golf Trip Ghost", "boss": true, "arena": "james_desk",
		"blurb": "James's old-job self. The desk was never cleaned out, and he's still logged in.",
		"hp": 210, "atk": 12, "style": "melee", "color": "#a0c8ff",
		"quotes": ["My new irons are so sick", "Back from emails going through lunch"],
		"skills": [
			{"id": "back_from_emails", "name": "Back From Emails Going Through Lunch", "cd": 5, "first": 3, "ult": true},
			{"id": "new_irons", "name": "My New Irons Are So Sick", "cd": 2, "first": 1},
			{"id": "haunted_blackjack", "name": "Haunted Blackjack", "cd": 4, "first": 2},
			{"id": "spectral_rage", "name": "Spectral Rage", "cd": 4, "first": 3},
			{"id": "ghostly_reply_all", "name": "Ghostly Reply-All", "cd": 3, "first": 2},
		],
	},
	# The Villiam Burginson Crew: the three-person final boss of every cycle.
	"cashier": {
		"name": "The Cashier", "remix_name": "Late Night Cashier", "boss": true, "arena": "villiam_burginson",
		"blurb": "Guards the register. Silences whoever just tried something fancy.",
		"hp": 75, "atk": 8, "dodge": 0.08, "style": "ranged", "color": "#ffd23f",
		"quotes": ["That's not on the menu."],
		"skills": [{"id": "not_on_menu", "name": "That's Not on the Menu", "cd": 2, "first": 1}],
	},
	"grill_master": {
		"name": "The Grill Master", "remix_name": "Late Night Grill Master", "boss": true, "arena": "villiam_burginson",
		"blurb": "Runs the flat-top. Everything he touches Burns.",
		"hp": 85, "atk": 9, "style": "melee",
		"quotes": ["Order up!", "Behind!"],
		"skills": [
			{"id": "grease_splash", "name": "Grease Splash", "cd": 3, "first": 2},
			{"id": "flat_top_flare", "name": "Flat-Top Flare", "cd": 2, "first": 1},
		],
	},
	"sauce_keeper": {
		"name": "The Sauce Keeper", "remix_name": "Late Night Sauce Keeper", "boss": true, "arena": "villiam_burginson",
		"blurb": "Holds the Village Sauce. Patches up the crew and makes promises he won't keep.",
		"hp": 95, "atk": 7, "style": "ranged", "color": "#ff9a1f",
		"quotes": ["Yeah I'll bring you the sauce..."],
		"skills": [
			{"id": "bring_sauce", "name": "Yeah I'll Bring You the Sauce...", "cd": 5, "first": 3, "ult": true},
			{"id": "patch_up", "name": "Cover the Line", "cd": 3, "first": 1},
		],
	},
}

const MINIONS_EARLY := ["energy_drink", "nic_pouch", "reply_all", "close_talker"]
const MINIONS_LATE := ["tallboy", "pouch_tin", "fish_guy", "loud_typer"]
## Each cycle draws 3 of these at random.
const BOSS_POOL := ["trucker", "sales_guy", "copilot", "guardian", "ghost"]
## The final fight of every cycle.
const BURGER_CREW := ["cashier", "grill_master", "sauce_keeper"]

const EARWORM_STEP := 0.08


# ------------------------------------------------------------------ helpers
## Hits every hero for m x ATK. Returns the heroes hit at.
static func aoe(b: Battle, u: BattleUnit, m: float, color: String) -> Array:
	b.anim(u, null, "cast", {"color": "rgb(%s)" % color})
	b.aoe("hero", color)
	var hs := b.foes_of(u)
	for h in hs:
		b.hit(u, h, m)
	return hs


## Hits one hero. Returns them if the hit landed, else null.
static func single(b: Battle, u: BattleUnit, m: float, style := "melee", o := {}) -> BattleUnit:
	var t := b.pick_hero_target(u)
	if t == null:
		return null
	b.anim(u, t, style)
	return t if b.hit(u, t, m, o) > 0 else null


static func quip(b: Battle, u: BattleUnit, chance := 0.5) -> void:
	var q: Array = ENEMIES[u.key].get("quotes", [])
	if not q.is_empty() and b.rng.chance(chance):
		b.say(u, b.rng.pick(q))


## The hero hitting hardest right now.
static func strongest(b: Battle, u: BattleUnit) -> BattleUnit:
	var best: BattleUnit = null
	for h in b.foes_of(u):
		if best == null or h.atk * b.mult(h) > best.atk * b.mult(best):
			best = h
	return best


static func boss_of(b: Battle, key: String) -> BattleUnit:
	for e in b.enemies():
		if e.key == key and e.alive:
			return e
	return null


## Whether the most recent hit was a crit.
static func last_was_crit(b: Battle) -> bool:
	for i in range(b.events.size() - 1, -1, -1):
		if b.events[i].t == "dmg":
			return b.events[i].crit
	return false


# ------------------------------------------------------------------ gimmick hooks
## Called once for each enemy before the first turn.
static func on_fight_start(b: Battle, u: BattleUnit) -> void:
	match u.key:
		"sales_guy":
			b.mog = 2 if u.remix else 0
			_sync_aura(b, u)
		"guardian":
			b.add_enemy("boombox", u)
		"ghost":
			var james := b.hero("james")
			if james and james.alive:
				b.say(u, "Back from emails going through lunch.")
				b.say(james, "...is that me?")
				b.emit({"t": "banner", "text": "POSSESSED", "sub": "The ghost takes back his spot"})
				b.note(james, "Possessed", StatusInfo.INFO.possessed.color)
				b.stats.james_possessed = true
				b.kill(james)
			else:
				# Nobody to possess: he's bored, and it makes him stronger.
				u.stacks = 1
				u.max_hp = roundi(u.max_hp * 1.2)
				u.hp = u.max_hp
				u.atk *= 1.2


## Called at the start of each of the enemy's turns (if it isn't stunned).
static func on_turn(b: Battle, u: BattleUnit) -> void:
	match u.key:
		"sales_guy":
			if b.mog < 5:
				b.mog += 1
				_sync_aura(b, u)
				b.note(u, "Aura %d" % b.mog, "#e0d0ff")
			if b.rng.chance(0.5):
				b.say(u, "*aura*")
		"guardian":
			if u.timer > 0:
				u.timer -= 1
				if u.timer == 0:
					b.say(u, "...okay, new speaker.")
					b.add_enemy("boombox", u, 1.0 + 0.2 * u.stacks)
			elif _music_on(b, u):
				for h in b.foes_of(u):
					add_earworm(b, u, h, 1)
		"ghost":
			if u.stacks == 1:
				var t := strongest(b, u)
				if t:
					b.add_status(t, "weaken", 2, 0.15, Battle.NO_TARGET, true)
					b.note(t, "Haunted", StatusInfo.INFO.possessed.color)


## Called after any hit lands.
static func on_hit(b: Battle, src: BattleUnit, tgt: BattleUnit, amount: int, crit: bool) -> void:
	# The Trucker's Grudge: hits on Cole can stun him.
	if src.key == "trucker" and tgt.key == "cole" and tgt.side == "hero" and tgt.alive:
		if b.stun(tgt, 1, 0.35):
			b.stats.cole_stunned = true
	# Crits knock Aura off the Sales Guy.
	if crit and src.side == "hero" and b.mog > 0:
		var sg := boss_of(b, "sales_guy")
		if sg:
			b.mog -= 1
			_sync_aura(b, sg)
			b.note(sg, "Aura -1", "#9aa0b8")


## Cam out-auras the Sales Guy: every turn Cam takes steals a stack.
static func steal_aura(b: Battle, cam: BattleUnit) -> void:
	var sg := boss_of(b, "sales_guy")
	if sg and b.mog > 0:
		b.mog -= 1
		b.stats.aura_stolen += 1
		_sync_aura(b, sg)
		b.note(cam, "Out-aura'd him", "#4fc3ff")


static func _sync_aura(b: Battle, sg: BattleUnit) -> void:
	sg.dodge = ENEMIES.sales_guy.dodge + 0.03 * b.mog


static func on_death(b: Battle, u: BattleUnit) -> void:
	match u.key:
		"sales_guy":
			b.mog = 0
		"boombox":
			var g := b.unit(u.owner_uid)
			if g and g.alive:
				g.timer = 2
				g.stacks += 1
				b.stats.boomboxes += 1
				for h in b.heroes():
					b.remove_status(h, "earworm")
				b.say(g, "Hey! I was listening to that!")
		"cashier", "grill_master", "sauce_keeper":
			var left := b.enemies().filter(func(e): return e.alive and e.key in BURGER_CREW)
			for e in left:
				b.add_status(e, "empower", 99, 0.25)
			if left.size() == 1:
				var last: BattleUnit = left[0]
				b.shield_up(last, last.max_hp * 0.2)
				b.say(last, "PROTECT THE SAUCE!")


## The Ghost comes back from emails.
static func on_return(b: Battle, u: BattleUnit) -> void:
	b.remove_status(u, "away")
	b.emit({"t": "model", "uid": u.uid, "model": u.model})
	b.say(u, "Back from emails going through lunch.")
	b.heal(u, u.max_hp * 0.15)


## The player answered a Cowork pop-up.
static func resolve_popup(b: Battle, u: BattleUnit, choice: String) -> void:
	match choice:
		"dismiss":
			b.stats.popups_dismissed += 1
			b.note(u, "Not now", "#9aa0b8")
		"install", "pro":
			var dur := 5 if choice == "pro" else 3
			b.say(u, "Great choice! Starting onboarding...")
			for h in b.foes_of(u):
				b.add_status(h, "weaken", dur, 0.15, Battle.NO_TARGET, true)
				b.note(h, "Productivity Suite", "#7fd4ff")
		_: # timeout
			b.say(u, "Auto-installed.")
			b.shake(5)
			aoe(b, u, 1.5, "127,212,255")
			var hs := b.foes_of(u)
			if not hs.is_empty():
				b.add_status(b.rng.pick(hs), "silence", 1)


## A hero hit the Sauce Keeper: if the party was waiting on sauce, they got it.
static func sauce_keeper_hit(b: Battle, _u: BattleUnit) -> void:
	var got := false
	for h in b.heroes():
		if b.has(h, "waiting_sauce"):
			b.remove_status(h, "waiting_sauce")
			b.add_status(h, "empower", 2, 0.15, Battle.NO_TARGET, true)
			got = true
	if got:
		b.emit({"t": "banner", "text": "SAUCE SECURED", "sub": "+15% damage"})


static func _music_on(b: Battle, g: BattleUnit) -> bool:
	return b.enemies().any(func(e): return e.key == "boombox" and e.alive and e.owner_uid == g.uid)


static func add_earworm(b: Battle, g: BattleUnit, h: BattleUnit, n: int) -> void:
	var cap := EARWORM_STEP * (7 if g.remix else 5)
	var cur := b.power(h, "earworm")
	var add := minf(cap - cur, EARWORM_STEP * n)
	if add > 0.001:
		b.add_status(h, "earworm", 99, add, g.uid, true)
		b.note(h, "Earworm %d" % roundi((cur + add) / EARWORM_STEP), StatusInfo.INFO.earworm.color)


# ------------------------------------------------------------------ skills
static func use_skill(enemy: String, skill: String, b: Battle, u: BattleUnit) -> void:
	match skill:
		# -------------------------------------------------------- minions
		"rush":
			single(b, u, 0.8)
			b.beat(0.2)
			single(b, u, 0.8)
		"sugar":
			b.anim(u, null, "cast", {"color": "#ffd23f"})
			for a in b.allies_of(u):
				b.add_status(a, "empower", 2, 0.25)
		"tuck":
			var t := single(b, u, 0.9)
			if t:
				b.dot(u, t, "poison", 0.5, 3)
		"mint":
			for h in aoe(b, u, 0.4, "160,240,255"):
				b.add_status(h, "weaken", 2, 0.15, Battle.NO_TARGET, true)
		"reply":
			quip(b, u, 0.4)
			aoe(b, u, 0.6, "255,255,255")
		"salmon":
			quip(b, u, 0.5)
			for h in aoe(b, u, 0.2, "124,255,79"):
				b.dot(u, h, "poison", 0.4, 3)
		"clack":
			quip(b, u, 0.3)
			var t := single(b, u, 0.9)
			if t:
				b.stun(t, 1, 0.6)
		"corner":
			quip(b, u, 0.5)
			var t := single(b, u, 1.0)
			if t:
				b.add_status(t, "weaken", 2, 0.25)
		# -------------------------------------------------------- The Angry Trucker
		"send_money":
			var cole := b.hero("cole")
			var t: BattleUnit = cole if cole and b.targetable(cole) else strongest(b, u)
			if t == null:
				return
			b.say(u, "SEND MY MONEY NOW")
			b.shake(6)
			b.anim(u, t, "melee", {"color": "#ff5a3a"})
			if b.hit(u, t, 1.6) > 0 and b.stun(t, 2) and t.key == "cole":
				b.stats.cole_stunned = true
			if u.remix:
				var others := b.foes_of(u).filter(func(h): return h != t)
				if not others.is_empty():
					var v: BattleUnit = b.rng.pick(others)
					b.add_status(v, "blind", 2, 0.3)
					b.note(v, "High beams!", StatusInfo.INFO.blind.color)
		"jake_brake":
			quip(b, u, 0.5)
			var t := single(b, u, 1.2)
			if t and t.side == "hero":
				var ult: String = HeroData.HEROES[t.key].ultimate
				t.cd[ult] = t.cd.get(ult, 0) + 1
				b.note(t, "Ultimate delayed", "#9aa0b8")
		"air_horn":
			b.shake(3)
			aoe(b, u, 0.7, "255,90,58")
		# -------------------------------------------------------- The Mystery Sales Guy
		"jawline":
			b.say(u, "*aura*")
			b.emit({"t": "banner", "text": "JAWLINE REVEAL", "sub": "He slowly turns to the side"})
			for h in b.foes_of(u):
				if b.rng.chance(0.35):
					b.add_status(h, "stun", 1)
					b.note(h, "Staring", "#e0d0ff")
				else:
					b.add_status(h, "weaken", 2, 0.2)
		"stirrer_flick":
			var hs := b.rng.shuffle(b.foes_of(u)).slice(0, 2)
			b.anim(u, null, "cast", {"color": "#e0d0ff"})
			for h in hs:
				b.hit(u, h, 0.6)
		"silent_stare":
			var t := single(b, u, 1.2)
			if t and last_was_crit(b) and b.mog < 5:
				b.mog += 1
				_sync_aura(b, u)
				b.note(u, "Aura %d" % b.mog, "#e0d0ff")
		# -------------------------------------------------------- The Copilot Grim Reaper
		"rollout":
			b.say(u, "This is for your own good.")
			b.show_popup(u, 2)
		"cowork":
			quip(b, u, 0.4)
			b.show_popup(u, 1)
		"scythe":
			aoe(b, u, 0.6, "127,212,255")
		# -------------------------------------------------------- The Guardian of Tunes
		"baby":
			b.say(u, "Don't you just love Justin Bieber for the 10th time today?")
			if _music_on(b, u):
				for h in b.foes_of(u):
					add_earworm(b, u, h, 2)
			for h in b.rng.shuffle(b.foes_of(u)).slice(0, 2):
				b.add_status(h, "confuse", 1, 0.0, u.uid)
		"maroon5":
			quip(b, u, 0.4)
			var music := _music_on(b, u)
			for h in aoe(b, u, 0.6, "255,122,224"):
				if music:
					add_earworm(b, u, h, 1)
		# -------------------------------------------------------- The Ghost of James Civelli
		"back_from_emails":
			b.say(u, "Checking my emails real quick.")
			b.add_status(u, "away", 2)
		"new_irons":
			b.say(u, "My new irons are so sick")
			for i in (2 if u.remix else 1):
				var t := b.pick_hero_target(u)
				if t == null:
					return
				b.anim(u, t, "melee", {"color": "#a0c8ff"})
				b.hit(u, t, 1.7, {"no_dodge": true})
				b.beat(0.2)
		"haunted_blackjack":
			var hs := b.foes_of(u)
			if hs.is_empty():
				return
			var t: BattleUnit = b.rng.pick(hs)
			if b.rng.chance(0.55):
				b.note(u, "BLACKJACK!", "#a0c8ff")
				b.damage(t, maxi(1, roundi(t.max_hp * 0.12)), "hit", false, u)
			else:
				b.note(u, "BUST", "#9aa0b8")
				b.damage(u, maxi(1, roundi(u.max_hp * 0.05)), "hit")
		"spectral_rage":
			b.anim(u, null, "cast", {"color": "#a0c8ff"})
			b.add_status(u, "empower", 2, 0.2)
			b.add_status(u, "guard", 2, 0.15)
		"ghostly_reply_all":
			for h in aoe(b, u, 0.5, "160,200,255"):
				b.dot(u, h, "poison", 0.3, 3)
		# -------------------------------------------------------- The Villiam Burginson Crew
		"not_on_menu":
			var t := b.unit(b.last_ability_uid)
			if t == null or not b.targetable(t) or t.side != "hero":
				var hs := b.foes_of(u)
				if hs.is_empty():
					return
				t = b.rng.pick(hs)
			b.say(u, "That's not on the menu.")
			b.anim(u, t, "ranged", {"color": "#ffd23f"})
			b.add_status(t, "silence", 2)
			b.stats.silenced = true
			if u.remix:
				for h in b.foes_of(u):
					if absi(h.slot - t.slot) == 1:
						b.add_status(h, "silence", 2)
						break
		"grease_splash":
			for h in aoe(b, u, 0.5, "255,154,31"):
				b.dot(u, h, "burn", 0.3, 3)
		"flat_top_flare":
			var t := single(b, u, 1.0)
			if t:
				b.dot(u, t, "burn", 0.5, 3)
		"bring_sauce":
			b.say(u, "Yeah I'll bring you the sauce...")
			for h in b.foes_of(u):
				b.add_status(h, "waiting_sauce", 2)
		"patch_up":
			var crew := b.allies_of(u)
			var hurt: BattleUnit = null
			for a in crew:
				if hurt == null or float(a.hp) / a.max_hp < float(hurt.hp) / hurt.max_hp:
					hurt = a
			b.anim(u, null, "cast", {"color": "#5effc8"})
			if hurt:
				b.heal(hurt, hurt.max_hp * 0.15)
			for a in crew:
				b.shield_up(a, a.max_hp * 0.1)
		_:
			push_error("Unknown enemy skill %s.%s" % [enemy, skill])
