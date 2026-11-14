class_name Outfits
extends RefCounted
## Skins, picked on the Suit Up screen before a run (docs/GAME_DESIGN.md §7).
##
## An outfit is either a recolor (`palette`: a palette texture in
## assets/textures/skins/) or a separate mesh on the same rig (`model`: a .glb in
## assets/models/heroes/). `cost` sells it for Village Sauce; `achievement` unlocks
## it; with neither it's free from the start.

const LIST := [
	# Free from the start: 2 per hero
	{"id": "mason_classic", "hero": "mason", "name": "Classic", "desc": "Away kit, white pants, smartwatch."},
	{"id": "mason_home", "hero": "mason", "name": "Home Kit", "desc": "The red one.", "palette": "mason_home"},
	{"id": "james_classic", "hero": "james", "name": "Classic", "desc": "The brown matching set and the mustache."},
	{"id": "james_gym", "hero": "james", "name": "Gym Fit", "desc": "Tank top and lifting belt.", "model": "james_gym"},
	{"id": "cole_classic", "hero": "cole", "name": "Classic", "desc": "Patterned button-up and khaki shorts."},
	{"id": "cole_polo", "hero": "cole", "name": "Golf Polo", "desc": "Ready for the back nine.", "palette": "cole_polo"},
	{"id": "cam_classic", "hero": "cam", "name": "Classic", "desc": "Mind Goblin cap, shades, Cyberpunk tee."},
	{"id": "cam_hoodie", "hero": "cam", "name": "Gamer Hoodie", "desc": "One more game.", "model": "cam_hoodie"},
	{"id": "sam_classic", "hero": "sam", "name": "Classic", "desc": "The flowing black dress."},
	{"id": "sam_witch", "hero": "sam", "name": "Witch Hat", "desc": "Adds about a foot. Still not tall.", "model": "sam_witch"},
	{"id": "sarah_classic", "hero": "sarah", "name": "Classic", "desc": "Sweater, glasses, black leggings."},
	{"id": "sarah_colorguard", "hero": "sarah", "name": "Colorguard Uniform", "desc": "Flag not included.", "model": "sarah_colorguard"},
	# Suit & Tie
	{"id": "mason_suit", "hero": "mason", "name": "Suit & Tie", "desc": "Dressed for the board meeting.", "model": "mason_suit", "achievement": "promoted"},
	{"id": "james_suit", "hero": "james", "name": "Suit & Tie", "desc": "Still somehow looks like he just left the gym.", "model": "james_suit", "achievement": "performance_review"},
	{"id": "cole_suit", "hero": "cole", "name": "Suit & Tie", "desc": "Business on top, Ole Miss underneath.", "model": "cole_suit", "achievement": "lunch_break"},
	{"id": "cam_suit", "hero": "cam", "name": "Suit & Tie", "desc": "Cap and shades stay on. Non-negotiable.", "model": "cam_suit", "achievement": "secret_sauce"},
	# Signature skins
	{"id": "mason_united", "hero": "mason", "name": "Manchester United", "desc": "Red Devils home kit.", "model": "mason_united", "achievement": "glory_glory"},
	{"id": "cole_olemiss", "hero": "cole", "name": "Ole Miss", "desc": "Hotty Toddy.", "model": "cole_olemiss", "achievement": "hotty_toddy"},
	{"id": "james_newjob", "hero": "james", "name": "New Job James", "desc": "New lanyard, new James. Big smile.", "model": "james_newjob", "achievement": "new_job"},
	{"id": "cam_kith", "hero": "cam", "name": "Kith", "desc": "Box logo hoodie. Drip certified.", "model": "cam_kith", "achievement": "drip_check"},
	# Boss skins
	{"id": "cole_trucker", "hero": "cole", "name": "Trucker Hat", "desc": "Paid in full.", "model": "cole_trucker", "achievement": "paid_in_full"},
	{"id": "cam_stirrer", "hero": "cam", "name": "Coffee Stirrer", "desc": "Over the ear. Aura acquired.", "model": "cam_stirrer", "achievement": "out_auraed"},
	{"id": "mason_hoodie", "hero": "mason", "name": "Reaper Hoodie", "desc": "Not now.", "model": "mason_hoodie", "achievement": "not_now"},
	{"id": "james_ghost", "hero": "james", "name": "Ghost James", "desc": "Back from emails going through lunch.", "model": "james_ghost", "achievement": "who_you_gonna_call"},
	{"id": "sam_throne", "hero": "sam", "name": "Booster Seat Throne", "desc": "Finally, eye level.", "model": "sam_throne", "achievement": "i_hate_mason"},
	{"id": "sam_trucksmarter", "hero": "sam", "name": "TruckSmarter Escapee", "desc": "Hi-vis vest, broken badge.", "model": "sam_trucksmarter", "achievement": "four_eight"},
	{"id": "sarah_subaru", "hero": "sarah", "name": "Subaru Racing Jacket", "desc": "Clock it.", "model": "sarah_subaru", "achievement": "clock_it"},
	{"id": "sarah_ohio", "hero": "sarah", "name": "Ohio Hoodie", "desc": "The Great State.", "model": "sarah_ohio", "achievement": "stop_stealing"},
]

## Party-wide unlocks: one outfit per hero, generated below.
const PARTY_SKINS := [
	{"suffix": "headphones", "name": "Headphones", "desc": "Noise-cancelling. Finally.", "achievement": "skip_track"},
	{"suffix": "burger", "name": "Burger Uniform", "desc": "Paper hat and all.", "achievement": "extra_sauce"},
	{"suffix": "golden", "name": "Golden Suit", "desc": "Overtime pays.", "achievement": "overtime"},
]

## Transformed forms when the outfit doesn't define one: Cole's UW form, buff James.
const DEFAULT_ULT := {"cole": "cole_uw", "james": "james_buff"}


static func all() -> Array:
	var out := LIST.duplicate()
	for s in PARTY_SKINS:
		for id in HeroData.HERO_IDS:
			out.append({"id": "%s_%s" % [id, s.suffix], "hero": id, "name": s.name, "desc": s.desc,
				"model": "%s_%s" % [id, s.suffix], "achievement": s.achievement})
	return out


static func by_id(id: String) -> Dictionary:
	for o in all():
		if o.id == id:
			return o
	return {}


static func for_hero(hero: String) -> Array:
	return all().filter(func(o): return o.hero == hero)


static func default_for(hero: String) -> Dictionary:
	return for_hero(hero)[0]


## The outfit a hero wears, falling back to the default if the id is unknown.
static func outfit_of(hero: String, outfits: Dictionary) -> Dictionary:
	var o := by_id(outfits.get(hero, ""))
	return o if not o.is_empty() and o.hero == hero else default_for(hero)


## Model key for an outfit. Recolors are "<hero>~<palette>": the renderer loads the
## hero's model and swaps in the palette texture.
static func model_of(o: Dictionary) -> String:
	if o.has("model"):
		return o.model
	if o.has("palette"):
		return "%s~%s" % [o.hero, o.palette]
	return o.hero


static func ult_model_of(o: Dictionary) -> String:
	return o.get("ult_model", DEFAULT_ULT.get(o.hero, ""))


static func owns(meta: Dictionary, o: Dictionary) -> bool:
	if o.has("achievement") and not meta.achievements.has(o.achievement):
		return false
	return not o.has("cost") or meta.owned_outfits.has(o.id)


static func for_achievement(id: String) -> Array:
	return all().filter(func(o): return o.get("achievement", "") == id)
