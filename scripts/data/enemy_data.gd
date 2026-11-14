class_name EnemyData
extends RefCounted
## Enemies. The minions are ported from the original's src/data/enemies.ts.
## The original bosses are retired; the sequel's six bosses (docs/GAME_DESIGN.md §4)
## get added here next.
##
## skills are checked in order each turn; the first one off cooldown is used.
## Add a `use_skill` case for each skill.

const ENEMIES := {
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
}

const MINIONS_EARLY := ["energy_drink", "nic_pouch", "reply_all", "close_talker"]
const MINIONS_LATE := ["tallboy", "pouch_tin", "fish_guy", "loud_typer"]


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
static func single(b: Battle, u: BattleUnit, m: float, style := "melee") -> BattleUnit:
	var t := b.pick_hero_target(u)
	if t == null:
		return null
	b.anim(u, t, style)
	return t if b.hit(u, t, m) > 0 else null


static func quip(b: Battle, u: BattleUnit, chance := 0.5) -> void:
	var q: Array = ENEMIES[u.key].get("quotes", [])
	if not q.is_empty() and b.rng.chance(chance):
		b.say(u, b.rng.pick(q))


# ------------------------------------------------------------------ skills
static func use_skill(enemy: String, skill: String, b: Battle, u: BattleUnit) -> void:
	match skill:
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
		_:
			push_error("Unknown enemy skill %s.%s" % [enemy, skill])
