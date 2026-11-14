class_name RunEvents
extends RefCounted
## Random events between fights, after the shop. Each shows a little scene, then
## one or more choices. Ported from the original's src/data/events.ts.
## Hanging up on Renekton now empowers your *next* boss (the original's rival boss
## is retired).

const EVENT_CHANCE := 0.35
const RIVAL_EMPOWERED := {"hp": 1.5, "atk": 1.3}

## art: {phone: id} | {hero: id} | {party: true}. requires: heroes that must be in the party.
const LIST := [
	{
		"id": "renekton", "title": "Renekton is calling",
		"text": "A phone lights up. The caller ID shows a humanoid alligator.",
		"art": {"phone": "renekton"},
		"choices": [
			{"label": "Accept", "style": "accept", "result": "Renekton Buff! Every hero gets +5 attack for the next fight."},
			{"label": "Hang up", "style": "decline", "result": "You hung up on Renekton. Somewhere, your next boss gets stronger: +50% health and +30% damage."},
		],
	},
	{
		"id": "the_local", "title": "Trip to The Local",
		"text": "Cole wants to go to The Local. Are you coming?",
		"art": {"hero": "cole"}, "requires": ["cole"],
		"choices": [
			{"label": "Let's go", "style": "accept", "result": "Good times. The whole party heals to full and starts the next fight with a 5% shield."},
			{"label": "Not tonight", "style": "decline", "result": "Cole goes alone and loses 5% of his health."},
		],
	},
	{
		"id": "pool_party", "title": "AM Pool Party",
		"text": "There's a pool party this morning. Do you go?",
		"art": {"hero": "mason"}, "requires": ["mason"],
		"choices": [
			{"label": "Cannonball", "style": "accept", "result": "Refreshing. Every hero gets +5% max health for the rest of the run."},
			{"label": "Skip it", "style": "decline", "result": "Mason stays home and channels it: +10 attack for the rest of the run."},
		],
	},
	{
		"id": "otr_raffle", "title": "OTR Raffle Drawing",
		"text": "The OTR raffle is drawn... and Cole wins!",
		"art": {"hero": "cole"}, "requires": ["cole"],
		"choices": [
			{"label": "Collect the prize", "result": "Cole gets +20 attack for the next fight. Everyone else loses 5% health from the jealousy."},
		],
	},
	{
		"id": "rift", "title": "Cam on the Rift",
		"text": "Cam queued up a few games last night. It did not go well.",
		"art": {"hero": "cam"}, "requires": ["cam"],
		"choices": [
			{"label": "SMH my head", "result": "Cam is Tilted: -5% max health and -5 attack for the next fight."},
		],
	},
	{
		"id": "holiday_party", "title": "Holiday Party",
		"text": "The office holiday party is in full swing. What do you do?",
		"art": {"party": true},
		"choices": [
			{"label": "Search the women's bathroom", "result": "You find some suspicious white powder. Every hero gets +15 attack for the next fight."},
			{"label": "Hit the open bar", "result": "Free drinks all night. Every hero gets +5% max health for the rest of the run."},
		],
	},
]


static func by_id(id: String) -> Dictionary:
	for e in LIST:
		if e.id == id:
			return e
	return {}


## Maybe picks an event before the next fight; each event happens at most once per cycle.
static func roll(run: Dictionary, rng: Rng) -> Dictionary:
	if run.stage == 0 or not rng.chance(EVENT_CHANCE):
		return {}
	var cycle: int = Run.stage_info(run.stage, run.seed).cycle
	var party: Array = run.heroes.map(func(h): return h.id)
	var options := LIST.filter(func(e):
		return not run.events_seen.has("%d:%s" % [cycle, e.id]) and e.get("requires", []).all(func(id): return party.has(id)))
	if options.is_empty():
		return {}
	var e: Dictionary = rng.pick(options)
	run.events_seen.append("%d:%s" % [cycle, e.id])
	return e


## Applies choice i of an event to the run.
static func apply(id: String, choice: int, run: Dictionary, meta: Dictionary) -> void:
	match "%s:%d" % [id, choice]:
		"renekton:0":
			_next_fight(run, {"hero": "all", "atk": 5})
		"renekton:1":
			run.rival_empowered = true
		"the_local:0":
			for h in run.heroes:
				h.hp = Run.hero_stats(h, meta).max_hp
			_next_fight(run, {"hero": "all", "shield_pct": 0.05})
		"the_local:1":
			_hurt(run, meta, "cole", 0.05)
		"pool_party:0":
			Run.apply_stat(run, meta, "all", "hp", 0.05)
		"pool_party:1":
			var m := Run.hero_state(run, "mason")
			m.atk_flat = m.get("atk_flat", 0.0) + 10.0
		"otr_raffle:0":
			_next_fight(run, {"hero": "cole", "atk": 20})
			for h in run.heroes:
				if h.id != "cole":
					_hurt(run, meta, h.id, 0.05)
		"rift:0":
			_next_fight(run, {"hero": "cam", "hp_pct": -0.05, "atk": -5})
		"holiday_party:0":
			_next_fight(run, {"hero": "all", "atk": 15})
		"holiday_party:1":
			Run.apply_stat(run, meta, "all", "hp", 0.05)


static func _next_fight(run: Dictionary, mod: Dictionary) -> void:
	run.next_fight.append(mod)


## Lose a share of max HP from current HP (never below 1).
static func _hurt(run: Dictionary, meta: Dictionary, id: String, pct: float) -> void:
	var h := Run.hero_state(run, id)
	h.hp = maxi(1, h.hp - roundi(Run.hero_stats(h, meta).max_hp * pct))
