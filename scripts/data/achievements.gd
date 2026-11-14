class_name Achievements
extends RefCounted
## Achievements (docs/GAME_DESIGN.md §6 and §3b). Checked after a won fight and after
## an event choice, against all-time counters in meta.stats and the fight's stats.
## An achievement can unlock skins: give the outfit an `achievement` (scripts/data/outfits.gd).
##
## Check context: {meta, fight (Battle.stats), boss (enemy id or ""), party (hero ids),
## kind ("minion"/"boss"/"bonus"), event ("<event id>:<choice>")}.

const LIST := [
	{"id": "first_day", "name": "First Day on the Job", "desc": "Win your first fight."},
	{"id": "promoted", "name": "Promoted", "desc": "Beat a boss."},
	{"id": "performance_review", "name": "Performance Review", "desc": "Beat 5 bosses (all-time)."},
	{"id": "lunch_break", "name": "Lunch Break", "desc": "Make it to Villiam Burginson's."},
	{"id": "secret_sauce", "name": "Secret Sauce", "desc": "Beat the Villiam Burginson Crew."},
	{"id": "glory_glory", "name": "Glory Glory", "desc": "Win a fight where Mason's We Go Next goes off."},
	{"id": "hotty_toddy", "name": "Hotty Toddy", "desc": "Win after 9 Iron on Ciabatta brings Cole back."},
	{"id": "new_job", "name": "New Job, Who Dis?", "desc": "Hit blackjack on James's Daily Dollar and win the fight."},
	{"id": "drip_check", "name": "Drip Check", "desc": "Hit 3 or more enemies with one Nissan Titan and win the fight."},
	{"id": "paid_in_full", "name": "Paid in Full", "desc": "Beat the Angry Trucker without Cole getting stunned."},
	{"id": "out_auraed", "name": "Out-Aura'd", "desc": "Have Cam steal 5 Aura from the Mystery Sales Guy in one fight, and win."},
	{"id": "not_now", "name": "Not Now", "desc": "Dismiss every Cowork pop-up in a Copilot Grim Reaper fight, and win."},
	{"id": "skip_track", "name": "Skip Track", "desc": "Break 3 Boomboxes in one Guardian of Tunes fight, and win."},
	{"id": "who_you_gonna_call", "name": "Who You Gonna Call", "desc": "Beat the Ghost of James Civelli."},
	{"id": "extra_sauce", "name": "Extra Sauce", "desc": "Beat the Villiam Burginson Crew without anyone being Silenced."},
	{"id": "i_hate_mason", "name": "I Hate Mason", "desc": "Crit with Rage Bait 3 times in one fight with Mason in the party."},
	{"id": "four_eight", "name": "4'8 Is Not That Short", "desc": "Win a boss fight without Sam taking any damage."},
	{"id": "clock_it", "name": "Clock It", "desc": "Detonate 150+ damage with one Dab."},
	{"id": "stop_stealing", "name": "Stop Stealing My Leads", "desc": "Land the killing blow on 3 bosses with Sarah (all-time)."},
	{"id": "answered", "name": "Answered the Call", "desc": "Pick up when Renekton calls."},
	{"id": "ten_toes", "name": "Ten Toes Down", "desc": "Win 25 fights (all-time)."},
	{"id": "overtime", "name": "Overtime", "desc": "Reach the third cycle in a single run."},
]


static func by_id(id: String) -> Dictionary:
	for a in LIST:
		if a.id == id:
			return a
	return {}


static func _stat(c: Dictionary, key: String) -> int:
	return int(c.meta.stats.get(key, 0))


static func check(id: String, c: Dictionary) -> bool:
	var f: Dictionary = c.get("fight", {})
	var boss: String = c.get("boss", "")
	var party: Array = c.get("party", [])
	match id:
		"first_day": return _stat(c, "fights_won") >= 1
		"promoted": return _stat(c, "bosses_beaten") >= 1
		"performance_review": return _stat(c, "bosses_beaten") >= 5
		"lunch_break": return _stat(c, "burger_reached") >= 1
		"secret_sauce": return _stat(c, "burger_won") >= 1
		"glory_glory": return f.get("we_go_next", false)
		"hotty_toddy": return f.get("cole_revived", false)
		"new_job": return f.get("blackjack", false)
		"drip_check": return f.get("titan_hits", 0) >= 3
		"paid_in_full": return boss == "trucker" and party.has("cole") and not f.get("cole_stunned", true)
		"out_auraed": return boss == "sales_guy" and f.get("aura_stolen", 0) >= 5
		"not_now": return boss == "copilot" and f.get("popups", 0) > 0 and f.popups_dismissed == f.popups
		"skip_track": return boss == "guardian" and f.get("boomboxes", 0) >= 3
		"who_you_gonna_call": return boss == "ghost"
		"extra_sauce": return c.get("kind", "") == "bonus" and not f.get("silenced", true)
		"i_hate_mason": return party.has("mason") and f.get("rage_bait_crits", 0) >= 3
		"four_eight": return c.get("kind", "") == "boss" and party.has("sam") and not f.get("sam_damaged", true)
		"clock_it": return f.get("best_dab", 0) >= 150
		"stop_stealing": return _stat(c, "sarah_boss_kills") >= 3
		"answered": return c.get("event", "") == "renekton:0"
		"ten_toes": return _stat(c, "fights_won") >= 25
		"overtime": return _stat(c, "best_cycle") >= 3
	return false


## Unlocks every achievement whose condition now holds. Returns the new ones.
static func check_all(c: Dictionary) -> Array:
	var got := []
	for a in LIST:
		if c.meta.achievements.has(a.id) or not check(a.id, c):
			continue
		c.meta.achievements.append(a.id)
		got.append(a)
	return got


static func bump(meta: Dictionary, key: String, by := 1) -> void:
	meta.stats[key] = int(meta.stats.get(key, 0)) + by
