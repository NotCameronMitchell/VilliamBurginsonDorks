class_name MetaUpgrades
extends RefCounted
## Permanent upgrades bought with Village Sauce between runs.
## Secret Sauce and Seasoned Veterans are flatter than the original's
## (+3% / +4% per level, from +5% / +6%) so maxed meta doesn't trivialize the game.

const LIST := [
	{"id": "vet", "name": "Seasoned Veterans", "max": 10},
	{"id": "sauce", "name": "Secret Sauce", "max": 10},
	{"id": "signing", "name": "Signing Bonus", "max": 5},
	{"id": "benefits", "name": "Better Benefits", "max": 5},
	{"id": "mentor", "name": "Mentorship Program", "max": 3},
	{"id": "menu", "name": "Expanded Menu", "max": 2},
	{"id": "second_wind", "name": "Second Wind", "max": 1},
]

const VET_HP := 0.04 ## max HP per level
const SAUCE_DMG := 0.03 ## damage per level


static func level(meta: Dictionary, id: String) -> int:
	return int(meta.upgrades.get(id, 0))


static func describe(id: String, l: int) -> String:
	match id:
		"vet": return "Heroes start with +%d%% max HP." % roundi(l * VET_HP * 100)
		"sauce": return "Heroes deal +%d%% damage." % roundi(l * SAUCE_DMG * 100)
		"signing": return "Start each run with %d PTO Hours." % (l * 15)
		"benefits": return "Heal an extra %d%% after every fight." % (l * 8)
		"mentor": return "Each hero starts with %d random ability rank-up%s." % [l, "" if l == 1 else "s"]
		"menu": return "The shop stocks %d extra item%s." % [l, "" if l == 1 else "s"]
		"second_wind": return "Once per run, a party wipe revives everyone at 40% HP."
	return ""


static func cost(id: String, l: int) -> int:
	match id:
		"vet", "sauce": return 8 + 8 * l
		"signing", "benefits": return 6 + 6 * l
		"mentor": return 20 + 20 * l
		"menu": return 15 + 12 * l
		"second_wind": return 40
	return 0


static func max_level(id: String) -> int:
	for u in LIST:
		if u.id == id:
			return u.max
	return 0


## Buys the next level. Returns false if maxed or not enough sauce.
static func buy(meta: Dictionary, id: String) -> bool:
	var l := level(meta, id)
	var c := cost(id, l)
	if l >= max_level(id) or meta.sauce < c:
		return false
	meta.sauce -= c
	meta.upgrades[id] = l + 1
	return true
