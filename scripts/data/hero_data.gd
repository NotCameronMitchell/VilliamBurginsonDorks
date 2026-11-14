class_name HeroData
extends RefCounted
## The heroes, their abilities and weapons. Ported from the original's
## src/data/heroes.ts, with the sequel's balance changes (docs/GAME_DESIGN.md §5)
## and the two new heroes, Sam and Sarah (§3b).
##
## To add a hero: add it to HERO_IDS and HEROES, its abilities to ABILITIES (plus a
## `describe` and `use` case), its weapons to WEAPONS (plus a `weapon_attack` case)
## and a STARTING_WEAPON.

const MAX_RANK := 5
const PARTY_SIZE := 4
const HERO_IDS := ["cole", "cam", "james", "mason", "sam", "sarah"]

const HEROES := {
	"mason": {
		"name": "Mason", "role": "Beastmaster", "row": "back", "color": "#ff4f6d",
		"blurb": "Commands his cats Bruno and Murphy, rages for AoE, and channels the power of marriage.",
		"hp": 95, "atk": 11, "def": 0.0, "crit": 0.08, "dodge": 0.05,
		"quotes": ["Wife BTW", "If it weren't for the brain fog I'd really have to experience this"],
		"abilities": ["headbutt", "lick", "swipe", "bite"], "ultimate": "wife_btw", "passive": "we_go_next",
		"weapons": ["soccer_ball", "trading_cards", "potenuse"],
	},
	"james": {
		"name": "James", "role": "Berserker", "row": "front", "color": "#ffd23f",
		"blurb": "Gym bro tank. Armors up, self-heals, and hits one target very hard.",
		"hp": 150, "atk": 12, "def": 0.12, "crit": 0.05, "dodge": 0.0,
		"quotes": ["Type Shi Nah FR", "Bih Ahh Boi"],
		"abilities": ["peptide_rage", "daily_dollar", "fogo", "throat_punch"], "ultimate": "jimmytrains", "passive": "uncrustable",
		"weapons": ["golf_club", "baseball_bat", "offsets"],
	},
	"cole": {
		"name": "Cole", "role": "Melee DPS", "row": "front", "color": "#ff9a1f",
		"blurb": "Stacks up his next attack with burns, poisons and stuns, then swings.",
		"hp": 110, "atk": 14, "def": 0.03, "crit": 0.12, "dodge": 0.1,
		"quotes": ["RIP Dallas Mavericks", "F*CK LANE KIFFIN"],
		"abilities": ["cft", "golf_lesson", "argue_sales", "ole_miss"], "ultimate": "transfer_uw", "passive": "nine_iron",
		"weapons": ["putter", "meme_barrage", "murray_mobile"],
	},
	"cam": {
		"name": "Cam", "role": "Caster / Support", "row": "back", "color": "#4fc3ff",
		"blurb": "Corny jokes and random BS that confuse, stun and hurt every enemy at once.",
		"hp": 90, "atk": 11, "def": 0.0, "crit": 0.06, "dodge": 0.05,
		"quotes": ["Wagwan", "SMH my head"],
		"abilities": ["mind_goblin", "iceland_story", "would_you_rather", "shopping_spree"], "ultimate": "nissan_titan", "passive": "aura_farming",
		"weapons": ["ai_slop", "new_fit", "new_pc"],
	},
	"sam": {
		"name": "Sam", "role": "Wizard", "row": "back", "color": "#9b5cff",
		"blurb": "Tiny glass cannon. No cooldowns: her spells run on mana, so she can cast back to back.",
		"hp": 75, "atk": 13, "def": 0.0, "crit": 0.08, "dodge": 0.05,
		"max_mp": 100.0, "start_mp": 40.0,
		"quotes": ["4'8 is not that short", "I hate Mason"],
		"abilities": ["ignore_emails", "rage_bait", "energy_drinks_bad", "burger_bomb"], "ultimate": "out_of_pocket", "passive": "desk_treadmill",
		"weapons": ["booster_seat", "trucksmarter_lor", "lampedusa_flag"],
	},
	"sarah": {
		"name": "Sarah", "role": "Rogue", "row": "front", "color": "#ff5fa2",
		"blurb": "Pure damage. Stacks Bleeds with her knives and dance moves, then detonates them.",
		"hp": 100, "atk": 12, "def": 0.0, "crit": 0.15, "dodge": 0.12,
		"max_energy": 100.0,
		"quotes": ["Clock it", "Stop stealing my leads"],
		"abilities": ["the_worm", "scuba", "dab", "catching_the_fish"], "ultimate": "subaru_driveby", "passive": "dance_rehearsal",
		"weapons": ["colorguard_gun", "tambourine", "great_state_of_ohio"],
	},
}

## kind: ability | ultimate | passive. target: enemy | enemies | self | ally | allies | none.
## cd: turns until usable again (cd_r4 overrides it at rank 4+). first: cooldown at fight start.
## quick: doesn't use up the turn (one quick buff per turn). cost/resource: Sam's MP or Sarah's Energy.
const ABILITIES := {
	# ---------------------------------------------------------------- Mason
	"headbutt": {"hero": "mason", "name": "Bruno: Headbutt", "kind": "ability", "cd": 2, "target": "enemy"},
	"lick": {"hero": "mason", "name": "Bruno: Lick", "kind": "ability", "cd": 2, "target": "enemy"},
	"swipe": {"hero": "mason", "name": "Murphy: Swipe", "kind": "ability", "cd": 3, "target": "enemies"},
	"bite": {"hero": "mason", "name": "Murphy: Bite", "kind": "ability", "cd": 3, "target": "enemy"},
	"we_go_next": {"hero": "mason", "name": "We Go Next", "kind": "passive", "cd": 0, "target": "none"},
	"wife_btw": {"hero": "mason", "name": "Wife BTW", "kind": "ultimate", "cd": 5, "first": 4, "target": "self"},
	# ---------------------------------------------------------------- James
	"peptide_rage": {"hero": "james", "name": "Peptide Rage", "kind": "ability", "cd": 3, "cd_r4": 2, "target": "self", "quick": true},
	"daily_dollar": {"hero": "james", "name": "Daily Dollar", "kind": "ability", "cd": 3, "target": "enemy"},
	"fogo": {"hero": "james", "name": "Dinner at Fogo", "kind": "ability", "cd": 3, "target": "self", "quick": true},
	"throat_punch": {"hero": "james", "name": "Throat Punch", "kind": "ability", "cd": 2, "target": "enemy"},
	"uncrustable": {"hero": "james", "name": "Uncrustable to the Esophagus", "kind": "passive", "cd": 0, "target": "none"},
	"jimmytrains": {"hero": "james", "name": "JimmyTrains", "kind": "ultimate", "cd": 5, "first": 4, "target": "self"},
	# ---------------------------------------------------------------- Cole
	"cft": {"hero": "cole", "name": "CFT (Cole from Texas)", "kind": "ability", "cd": 3, "target": "self", "quick": true},
	"golf_lesson": {"hero": "cole", "name": "Golf Lesson", "kind": "ability", "cd": 2, "target": "self", "quick": true},
	"argue_sales": {"hero": "cole", "name": "Argue with Sales", "kind": "ability", "cd": 3, "target": "self", "quick": true},
	"ole_miss": {"hero": "cole", "name": "Ole Miss Win", "kind": "ability", "cd": 4, "target": "self", "quick": true},
	"nine_iron": {"hero": "cole", "name": "9 Iron on Ciabatta", "kind": "passive", "cd": 0, "target": "none"},
	"transfer_uw": {"hero": "cole", "name": "Transfer to UW", "kind": "ultimate", "cd": 6, "first": 4, "target": "self", "quick": true},
	# ---------------------------------------------------------------- Cam
	"mind_goblin": {"hero": "cam", "name": "Mind Goblin", "kind": "ability", "cd": 4, "target": "enemies"},
	"iceland_story": {"hero": "cam", "name": "Iceland Story", "kind": "ability", "cd": 4, "target": "enemies"},
	"would_you_rather": {"hero": "cam", "name": "Would You Rather", "kind": "ability", "cd": 3, "target": "enemies"},
	"shopping_spree": {"hero": "cam", "name": "Shopping Spree", "kind": "ability", "cd": 4, "target": "allies"},
	"aura_farming": {"hero": "cam", "name": "Aura Farming", "kind": "passive", "cd": 0, "target": "none"},
	"nissan_titan": {"hero": "cam", "name": "Nissan Titan", "kind": "ultimate", "cd": 5, "first": 4, "target": "enemies"},
	# ---------------------------------------------------------------- Sam
	"ignore_emails": {"hero": "sam", "name": "Ignore Emails", "kind": "ability", "cd": 0, "target": "self", "cost": 35, "resource": "mp"},
	"rage_bait": {"hero": "sam", "name": "Rage Bait", "kind": "ability", "cd": 0, "target": "enemy", "cost": 30, "resource": "mp"},
	"energy_drinks_bad": {"hero": "sam", "name": "Energy Drinks Are Bad For You", "kind": "ability", "cd": 0, "target": "enemies", "cost": 25, "resource": "mp"},
	"burger_bomb": {"hero": "sam", "name": "Refrigerated Burger Bomb", "kind": "ability", "cd": 0, "target": "enemies", "cost": 45, "resource": "mp"},
	"desk_treadmill": {"hero": "sam", "name": "Desk Treadmill", "kind": "passive", "cd": 0, "target": "none"},
	"out_of_pocket": {"hero": "sam", "name": "Unexpected Out of Pocket Message", "kind": "ultimate", "cd": 5, "first": 4, "target": "enemies"},
	# ---------------------------------------------------------------- Sarah
	"the_worm": {"hero": "sarah", "name": "The Worm", "kind": "ability", "cd": 2, "target": "enemies"},
	"scuba": {"hero": "sarah", "name": "Scuba", "kind": "ability", "cd": 2, "target": "enemy"},
	"dab": {"hero": "sarah", "name": "Dab", "kind": "ability", "cd": 0, "target": "enemies", "cost": 50, "resource": "energy"},
	"catching_the_fish": {"hero": "sarah", "name": "Catching the Fish", "kind": "ability", "cd": 3, "target": "none"},
	"dance_rehearsal": {"hero": "sarah", "name": "Dance Rehearsal", "kind": "passive", "cd": 0, "target": "none"},
	"subaru_driveby": {"hero": "sarah", "name": "Subaru Drive-by", "kind": "ultimate", "cd": 5, "first": 4, "target": "enemies"},
}

## target: enemy | enemies | allies. def/parry/dmg_bonus apply while equipped;
## ability_bonus and mp_regen are Sam's weapon stats.
const WEAPONS := {
	# Mason
	"soccer_ball": {"hero": "mason", "name": "Soccer Ball", "cost": 0, "target": "enemy", "desc": "Kicks one enemy for 130% ATK."},
	"trading_cards": {"hero": "mason", "name": "Pack of Trading Cards", "cost": 22, "target": "enemy", "desc": "Rips a pack: 30% to 210% ATK depending on the pull. A holo rare (1 in 20) deals double."},
	"potenuse": {"hero": "mason", "name": "High on Potenuse", "cost": 20, "target": "enemy", "desc": "Copies the last hit another hero landed, +1. (100% ATK if nobody's hit yet.)"},
	# James
	"golf_club": {"hero": "james", "name": "Regripped Golf Club", "cost": 0, "target": "enemy", "desc": "Ribbed for her pleasure. 140% ATK to one enemy and can't be dodged."},
	"baseball_bat": {"hero": "james", "name": "College Baseball Bat", "cost": 20, "target": "enemy", "parry": 0.2, "desc": "160% ATK to one enemy. While equipped James parries 20% of attacks."},
	"offsets": {"hero": "james", "name": "Offsets", "cost": 22, "target": "enemy", "desc": "140% ATK to one enemy, taunting it for 2 turns and pushing its next ability back a turn."},
	# Cole
	"putter": {"hero": "cole", "name": "New Putter", "cost": 0, "target": "enemy", "desc": "Hits one enemy 1-3 times for 70% ATK each."},
	"meme_barrage": {"hero": "cole", "name": "Meme Barrage", "cost": 20, "target": "enemies", "desc": "Sends 5 memes at random enemies for 30% ATK each, each one adding Poison."},
	"murray_mobile": {"hero": "cole", "name": "The Murray Mobile", "cost": 25, "target": "enemy", "def": 0.2, "desc": "Runs one enemy over for 170% ATK. While equipped Cole takes 20% less damage."},
	# Cam
	"ai_slop": {"hero": "cam", "name": "AI Slop", "cost": 0, "target": "enemies", "desc": "45% ATK to every enemy and Poison (20% ATK/turn)."},
	"new_fit": {"hero": "cam", "name": "New Fit", "cost": 20, "target": "enemy", "desc": "70% ATK to one enemy with a 40% chance to stun it, and Burn (30% ATK/turn)."},
	"new_pc": {"hero": "cam", "name": "New PC", "cost": 25, "target": "enemy", "dmg_bonus": 0.25, "desc": "110% ATK to one enemy. While equipped, all of Cam's damage and effects are 25% stronger."},
	# Sam
	"booster_seat": {"hero": "sam", "name": "Booster Seat", "cost": 0, "target": "enemy", "mp_regen": 15.0, "desc": "120% ATK to one enemy. +15 MP per turn. She needs it because she's short."},
	"trucksmarter_lor": {"hero": "sam", "name": "TruckSmarter LOR", "cost": 20, "target": "enemy", "mp_regen": 20.0, "ability_bonus": 0.15, "desc": "100% ATK. +20 MP per turn and abilities deal 15% more. She escaped TruckSmarter, but kept the power."},
	"lampedusa_flag": {"hero": "sam", "name": "Lampedusa Flag", "cost": 28, "target": "enemy", "mp_regen": 22.0, "ability_bonus": 0.3, "burn_chance": 0.3, "desc": "90% ATK. +22 MP per turn, abilities deal 30% more and have a 30% chance to Burn."},
	# Sarah
	"colorguard_gun": {"hero": "sarah", "name": "Colorguard Gun", "cost": 0, "target": "enemy", "desc": "130% ATK blunt hit with a 25% chance to detonate the target's Bleeds (75%). It's a prop."},
	"tambourine": {"hero": "sarah", "name": "Tambourine", "cost": 20, "target": "allies", "desc": "No damage: the whole party deals 15% more damage until the end of next turn. +15 Energy."},
	"great_state_of_ohio": {"hero": "sarah", "name": "The Great State of Ohio", "cost": 24, "target": "enemies", "desc": "40% ATK to every enemy, each with a 60% chance to Bleed and a 60% chance to Poison."},
}

const STARTING_WEAPON := {
	"mason": "soccer_ball", "james": "golf_club", "cole": "putter",
	"cam": "ai_slop", "sam": "booster_seat", "sarah": "colorguard_gun",
}


# ------------------------------------------------------------------ helpers
static func pct(n: float) -> String:
	return "%d%%" % roundi(n * 100)


static func atk(n: float) -> String:
	return "%d%% ATK" % roundi(n * 100)


static func roman(r: int) -> String:
	return ["", "I", "II", "III", "IV", "V"][r] if r >= 0 and r <= 5 else str(r)


static func ability_cd(id: String, r: int) -> int:
	var ab: Dictionary = ABILITIES[id]
	if ab.has("cd_r4") and r >= 4:
		return ab.cd_r4
	return ab.cd


## Resource cost at this rank: Sam's spells get 2 cheaper per rank; Dab drops to 40 at r4.
static func ability_cost(id: String, r: int) -> int:
	var ab: Dictionary = ABILITIES[id]
	if not ab.has("cost"):
		return 0
	if id == "dab":
		return 40 if r >= 4 else 50
	return ab.cost - 2 * (r - 1)


## Abilities that can be ranked up for a hero (abilities, ultimate and passive).
static func rankable(id: String) -> Array:
	var d: Dictionary = HEROES[id]
	return d.abilities + [d.ultimate, d.passive]


static func we_go_next_cap(boss: bool, r: int) -> float:
	return (0.25 if boss else 0.45) + 0.05 * (r - 1)


## Raised from 15% in the original so the passive actually fires.
static func we_go_next_threshold(r: int) -> float:
	return 0.25 + 0.02 * (r - 1)


## Picks n targets: the chosen one first, then random others.
static func spread(b: Battle, u: BattleUnit, t: BattleUnit, n: int) -> Array:
	var foes := b.foes_of(u)
	if foes.is_empty():
		return []
	var first: BattleUnit = t if t and foes.has(t) else foes[0]
	var rest := b.rng.shuffle(foes.filter(func(f): return f != first))
	return ([first] + rest).slice(0, n)


static func maybe_say(b: Battle, u: BattleUnit, chance := 0.35) -> void:
	if b.rng.chance(chance):
		b.say(u, b.rng.pick(HEROES[u.key].quotes))


static func strike(b: Battle, u: BattleUnit, t: BattleUnit, m: float, style: String, extra := {}) -> int:
	var e: BattleUnit = t if t and t.alive else null
	if e == null:
		var foes := b.foes_of(u)
		if foes.is_empty():
			return 0
		e = foes[0]
	b.anim(u, e, style, {"color": extra.get("color", "")})
	return b.hit(u, e, m, {"weapon": true, "no_dodge": extra.get("no_dodge", false)})


## Lampedusa Flag: Sam's abilities can Burn.
static func sam_burn(b: Battle, u: BattleUnit, e: BattleUnit) -> void:
	var chance: float = WEAPONS[u.weapon].get("burn_chance", 0.0)
	if chance > 0 and e.alive and b.rng.chance(chance):
		b.dot(u, e, "burn", 0.3, 3)


static func first_alive(b: Battle, u: BattleUnit, t: BattleUnit) -> BattleUnit:
	if t and t.alive:
		return t
	var foes := b.foes_of(u)
	return foes[0] if not foes.is_empty() else null


# ------------------------------------------------------------------ descriptions
static func describe(id: String, r: int) -> String:
	match id:
		"headbutt":
			return "Bruno charges for %s damage%s." % [atk(1.4 * (1 + 0.15 * (r - 1))), (" to %d enemies" % (3 if r >= 5 else 2)) if r >= 3 else ""]
		"lick":
			return "Bruno licks %s for %s and poisons for %s a turn (3 turns)." % ["every enemy" if r >= 5 else ("2 enemies" if r >= 3 else "one enemy"), atk(0.5), atk(0.35 * (1 + 0.3 * (r - 1)))]
		"swipe":
			return "Murphy swipes all enemies %dx for %s, each adding Bleed (%s/turn)." % [1 + (r - 1) / 2, atk(0.55 * (1 + 0.1 * (r - 1))), atk(0.2)]
		"bite":
			return "Murphy bites %dx for %s each, inflicting Bleed (%s/turn)." % [1 + (r - 1) / 2, atk(1.9 * (1 + 0.1 * (r - 1))), atk(0.35)]
		"we_go_next":
			return "If every hero is below %s HP, Mason blows himself up for %s of the damage he has taken, to all enemies. Capped at %s of each enemy's max HP (%s for bosses)." % [pct(we_go_next_threshold(r)), pct(2 + 0.5 * (r - 1)), pct(we_go_next_cap(false, r)), pct(we_go_next_cap(true, r))]
		"wife_btw":
			return "Mason channels the power of being married: a shield worth %s max HP and +%s damage for 3 turns." % [pct(1 + 0.15 * (r - 1)), pct(0.2 + 0.1 * (r - 1))]
		"peptide_rage":
			return "Quick. +%s damage and -%s damage taken for 2 turns. Stacks.%s" % [pct(0.1 + 0.03 * (r - 1)), pct(0.15 + 0.03 * (r - 1)), " Cooldown 2." if r >= 4 else ""]
		"daily_dollar":
			return "Blackjack on his phone (%s to win). Win: %s, can't be dodged. Lose: he loses %s max HP." % [pct(minf(0.75, 0.5 + 0.05 * (r - 1))), atk(2.2 + 0.4 * (r - 1)), pct(maxf(0.01, 0.05 - 0.01 * (r - 1)))]
		"fogo":
			var w := maxf(0.0, 0.1 - 0.025 * (r - 1))
			return "Quick. Heals %s max HP and blocks %s of damage for 2 turns%s." % [pct(0.2 + 0.05 * (r - 1)), pct(0.3), (", but -%s damage this turn (meat sweats)" % pct(w)) if w > 0 else ""]
		"throat_punch":
			return "%s damage with a %s chance to stun for a turn.%s%s" % [atk(1.8 * (1 + 0.15 * (r - 1))), pct(minf(0.9, 0.5 + 0.1 * (r - 1))), " Also Bleeds." if r >= 4 else "", " And Burns." if r >= 5 else ""]
		"uncrustable":
			return "Every 3rd turn James devours an Uncrustable: heals %s max HP and +%s damage for a turn." % [pct(0.1 + 0.03 * (r - 1)), pct(0.05 + 0.03 * (r - 1))]
		"jimmytrains":
			return "Posts a new reel: taunts all enemies for 3 turns, takes no damage, and reflects %s of what he would have taken.%s" % [pct(0.2 + 0.1 * (r - 1)), " Enemies deal 15% less damage." if r >= 3 else ""]
		"cft":
			return "Quick. +20%% dodge for 3 turns (stacks). His next attack Burns for %s a turn." % atk(0.4 * (1 + 0.25 * (r - 1)))
		"golf_lesson":
			return "Quick. His next attack deals +%s damage with a %s chance to stun." % [pct(0.15 + 0.1 * (r - 1)), pct(0.3 + 0.05 * (r - 1))]
		"argue_sales":
			return "Quick. His next attack can't be dodged and poisons every enemy for %s a turn.%s" % [atk(0.3 * (1 + 0.25 * (r - 1))), (" Also hits all enemies now for %s." % atk(0.3 * (r - 1))) if r >= 2 else ""]
		"ole_miss":
			return "Quick. His team won: +%s damage for %d turns." % [pct(0.2 + 0.05 * (r - 1)), 2 + r / 2]
		"nine_iron":
			return "Once per fight, if Cole dies he comes back next turn at full HP with a %s max HP shield%s." % [pct(0.1 + 0.1 * (r - 1)), (" and +%s damage" % pct(0.1 * (r - 1))) if r >= 2 else ""]
		"transfer_uw":
			return "Quick. Cole evolves: regrows his hair, heals to full, gets a 50%% max HP shield and deals double damage for %d turns.%s" % [3 if r >= 3 else 2, (" +%s dodge." % pct(0.1 * (r - 1))) if r >= 2 else ""]
		"mind_goblin":
			return "Poisons every enemy for %s a turn (stacks). The next enemy to use an ability is stunned for %d turns instead." % [atk(0.25 * (1 + 0.3 * (r - 1))), 3 if r >= 3 else 2]
		"iceland_story":
			return "Stuns all enemies for a turn and deals %s.%s%s" % [atk(0.4 * (1 + 0.2 * (r - 1))), " -15% enemy damage for 2 turns." if r >= 3 else "", " Burns them too." if r >= 5 else ""]
		"would_you_rather":
			return "Each enemy has a %s chance to be Confused and attack itself%s." % [pct(minf(0.9, 0.5 + 0.08 * (r - 1))), (" for +%s damage" % pct(0.15 * (r - 1))) if r >= 2 else ""]
		"shopping_spree":
			return "Every ally gets 3 random buffs for 2 turns (+%s strength), with a %s chance to block all damage for 2 turns." % [pct(0.25 * (r - 1)), pct(0.1 + 0.05 * (r - 1))]
		"aura_farming":
			return "Every turn Cam takes, he gains +%s damage and effect strength until the fight ends." % pct(0.03 + 0.01 * (r - 1))
		"nissan_titan":
			return "A spectral Nissan Titan runs everyone over: %s to all enemies and stuns them for 2 turns." % atk(3 * (1 + 0.25 * (r - 1)))
		"ignore_emails":
			return "Sam ignores every email: a shield worth %s max HP, and she reflects %s of the damage aimed at her for 2 turns." % [pct(0.25 + 0.05 * (r - 1)), pct(0.2 + 0.05 * (r - 1))]
		"rage_bait":
			return "A fireball at one enemy: %s, and it's Weakened 20%% for a turn. +25%% crit chance if Mason is in the party." % atk(2.2 * (1 + 0.15 * (r - 1)))
		"energy_drinks_bad":
			return "Scolds every enemy for %s (+50%% vs energy drinks). They're Exposed and can't dodge for 2 turns%s." % [atk(0.45 * (1 + 0.1 * (r - 1))), " and take 10% more damage" if r >= 3 else ""]
		"burger_bomb":
			return "%sThrows a cold burger: %s to all enemies and Poison (%s/turn, 3 turns)." % ["" if r >= 5 else "Takes a bite (poisons herself for 4% max HP a turn, 2 turns). ", atk(0.8 * (1 + 0.15 * (r - 1))), atk(0.3)]
		"desk_treadmill":
			return "Heals %s max HP every turn. Healing past full HP becomes a shield, up to 10%% max HP." % pct(0.05 + 0.01 * (r - 1))
		"out_of_pocket":
			return "Says something so heinous it deals %s to every enemy and stuns them for 2 turns." % atk(2.4 * (1 + 0.2 * (r - 1)))
		"the_worm":
			return "Does the worm, throwing %d knives at random enemies: %s each, each hit Bleeds (%s/turn). +8 Energy per hit." % [knives(r), atk(0.3), atk(0.2)]
		"scuba":
			return "Slashes one enemy %d times for %s each, adding a Bleed stack (%s/turn) per hit. +10 Energy per hit." % [knives(r) - 1, atk(0.4), atk(0.15)]
		"dab":
			return "Hits a mean dab: detonates every Bleed on every enemy at %s." % pct(1.25 + 0.25 * (r - 1))
		"catching_the_fish":
			return "Reels in the highest-HP enemy and stabs it: %s and Bleed (%s/turn). +20 Energy." % [atk(1.5 * (1 + 0.15 * (r - 1))), atk(0.3)]
		"dance_rehearsal":
			return "Rehearses during enemy turns: +%s damage every round, up to +30%%." % pct(0.03 + 0.01 * (r - 1))
		"subaru_driveby":
			return "Drives by every enemy for %s and a Bleed, then detonates every Bleed at %s +0.5%% per Energy spent. Spends all Energy." % [atk(1.0), pct(0.5 + 0.2 * (r - 1))]
	return ""


## The Worm throws 4 knives (+1 at r3 and r5); Scuba slashes one fewer.
static func knives(r: int) -> int:
	return 4 + (1 if r >= 3 else 0) + (1 if r >= 5 else 0)


# ------------------------------------------------------------------ abilities
static func use(id: String, b: Battle, u: BattleUnit, t: BattleUnit, r: int) -> void:
	match id:
		# ------------------------------------------------------------ Mason
		"headbutt":
			for e in spread(b, u, t, 3 if r >= 5 else (2 if r >= 3 else 1)):
				b.anim(u, e, "pet", {"pet": "bruno"})
				b.hit(u, e, 1.4 * (1 + 0.15 * (r - 1)))
		"lick":
			var ts := b.foes_of(u) if r >= 5 else spread(b, u, t, 2 if r >= 3 else 1)
			for e in ts:
				b.anim(u, e, "pet", {"pet": "bruno"})
				if b.hit(u, e, 0.5) > 0:
					b.dot(u, e, "poison", 0.35 * (1 + 0.3 * (r - 1)), 3)
		"swipe":
			var n := 1 + (r - 1) / 2
			for i in n:
				b.anim(u, null, "pet", {"pet": "murphy"})
				b.aoe("enemy", "255,79,109")
				for e in b.foes_of(u):
					if b.hit(u, e, 0.55 * (1 + 0.1 * (r - 1))) > 0:
						b.dot(u, e, "bleed", 0.2, 3)
				if i < n - 1:
					b.beat(0.25)
		"bite":
			var n := 1 + (r - 1) / 2
			for i in n:
				var e := first_alive(b, u, t)
				if e == null:
					return
				b.anim(u, e, "pet", {"pet": "murphy"})
				if b.hit(u, e, 1.9 * (1 + 0.1 * (r - 1))) > 0:
					b.dot(u, e, "bleed", 0.35, 3)
				if i < n - 1:
					b.beat(0.25)
		"we_go_next":
			u.passive_used = true
			b.stats.we_go_next = true
			var dmg := maxi(1, roundi(u.dmg_taken * (2 + 0.5 * (r - 1))))
			b.say(u, "We go next.")
			b.emit({"t": "banner", "text": "WE GO NEXT", "sub": "Mason"})
			b.beat(0.6)
			b.kill(u)
			b.shake(8)
			b.aoe("enemy", "255,154,31")
			for e in b.foes_of(u):
				b.damage(e, mini(dmg, maxi(1, roundi(e.max_hp * we_go_next_cap(e.boss, r)))), "boom", false, u)
			b.beat(0.6)
		"wife_btw":
			b.emit({"t": "fx", "kind": "wife", "uid": u.uid})
			b.beat(0.9)
			b.say(u, "Wife BTW")
			b.anim(u, null, "cast", {"color": "#ff7ae0"})
			b.shield_up(u, u.max_hp * (1 + 0.15 * (r - 1)))
			b.add_status(u, "empower", 4, 0.2 + 0.1 * (r - 1))
		# ------------------------------------------------------------ James
		"peptide_rage":
			b.anim(u, null, "cast", {"color": "#ff5a3a"})
			b.add_status(u, "empower", 3, 0.1 + 0.03 * (r - 1))
			b.add_status(u, "guard", 3, 0.15 + 0.03 * (r - 1))
			maybe_say(b, u, 0.25)
		"daily_dollar":
			if t == null:
				return
			var win := b.rng.chance(minf(0.75, 0.5 + 0.05 * (r - 1)))
			var dealer := b.rng.int_range(17, 20)
			if win:
				var me := 21 if b.rng.chance(0.3) else b.rng.int_range(dealer + 1, 21)
				b.note(u, "BLACKJACK!" if me == 21 else "%d vs %d: WIN" % [me, dealer], "#ffd23f")
				if me == 21:
					b.stats.blackjack = true
				b.beat(0.35)
				b.anim(u, t, "melee")
				b.hit(u, t, 2.2 + 0.4 * (r - 1), {"no_dodge": true})
				maybe_say(b, u, 0.3)
			else:
				var bust := b.rng.chance(0.5)
				b.note(u, ("%d: BUST" % b.rng.int_range(22, 26)) if bust else ("%d vs %d: LOSE" % [b.rng.int_range(12, dealer - 1), dealer]), "#9aa0b8")
				b.beat(0.35)
				b.damage(u, maxi(1, roundi(u.max_hp * maxf(0.01, 0.05 - 0.01 * (r - 1)))), "hit")
		"fogo":
			b.anim(u, null, "cast", {"color": "#7cff4f"})
			b.heal(u, u.max_hp * (0.2 + 0.05 * (r - 1)))
			b.add_status(u, "guard", 3, 0.3)
			var w := maxf(0.0, 0.1 - 0.025 * (r - 1))
			if w > 0:
				b.add_status(u, "weaken", 1, w, Battle.NO_TARGET, true)
		"throat_punch":
			if t == null:
				return
			b.anim(u, t, "melee")
			if b.hit(u, t, 1.8 * (1 + 0.15 * (r - 1))) > 0:
				b.stun(t, 1, minf(0.9, 0.5 + 0.1 * (r - 1)))
				if r >= 4:
					b.dot(u, t, "bleed", 0.4, 3)
				if r >= 5:
					b.dot(u, t, "burn", 0.4, 3)
		"uncrustable":
			b.note(u, "Uncrustable!", "#c08aff")
			b.heal(u, u.max_hp * (0.1 + 0.03 * (r - 1)))
			b.add_status(u, "empower", 1, 0.05 + 0.03 * (r - 1), Battle.NO_TARGET, true)
		"jimmytrains":
			b.say(u, "New reel just dropped")
			b.anim(u, null, "cast", {"color": "#ffd23f"})
			u.model = u.alt_model if u.alt_model != "" else "james_buff"
			b.emit({"t": "model", "uid": u.uid, "model": u.model})
			b.add_status(u, "protect", 4, 0.0)
			b.add_status(u, "reflect", 4, 0.2 + 0.1 * (r - 1), Battle.NO_TARGET, true)
			for e in b.foes_of(u):
				b.add_status(e, "taunt", 3, 0.0, u.uid, true)
				if r >= 3:
					b.add_status(e, "weaken", 3, 0.15, Battle.NO_TARGET, true)
			b.aoe("enemy", "255,90,58")
		# ------------------------------------------------------------ Cole
		"cft":
			b.anim(u, null, "cast", {"color": "#ff9a1f"})
			b.add_status(u, "dodge", 4, 0.2)
			u.prep.burn = u.prep.get("burn", 0.0) + u.atk * 0.4 * (1 + 0.25 * (r - 1)) * b.mult(u)
		"golf_lesson":
			b.anim(u, null, "cast", {"color": "#7cff4f"})
			u.prep.lesson = u.prep.get("lesson", 0.0) + 0.15 + 0.1 * (r - 1)
			u.prep.stun = maxf(u.prep.get("stun", 0.0), 0.3 + 0.05 * (r - 1))
			b.note(u, "Lesson learned", "#7cff4f")
		"argue_sales":
			b.anim(u, null, "cast", {"color": "#c08aff"})
			u.prep.argue = u.prep.get("argue", 0.0) + u.atk * 0.3 * (1 + 0.25 * (r - 1)) * b.mult(u)
			if r >= 2:
				b.aoe("enemy", "192,138,255")
				for e in b.foes_of(u):
					b.hit(u, e, 0.3 * (r - 1), {"no_dodge": true})
			if b.rng.chance(0.3):
				b.say(u, "F*CK LANE KIFFIN")
		"ole_miss":
			b.anim(u, null, "cast", {"color": "#ff4f6d"})
			b.add_status(u, "empower", 2 + r / 2, 0.2 + 0.05 * (r - 1))
			b.say(u, "Hotty Toddy!")
		"nine_iron":
			b.note(u, "9 Iron on Ciabatta!", "#ffd23f")
			b.stats.cole_revived = true
			b.shield_up(u, u.max_hp * (0.1 + 0.1 * (r - 1)))
			if r >= 2:
				b.add_status(u, "empower", 3, 0.1 * (r - 1), Battle.NO_TARGET, true)
		"transfer_uw":
			b.emit({"t": "banner", "text": "TRANSFER TO UW", "sub": "Cole is evolving!"})
			b.shake(4)
			b.beat(0.6)
			u.model = u.alt_model if u.alt_model != "" else "cole_uw"
			b.emit({"t": "model", "uid": u.uid, "model": u.model})
			b.heal(u, u.max_hp)
			b.shield_up(u, u.max_hp * 0.5)
			b.add_status(u, "empower", 3 if r >= 3 else 2, 1.0)
			if r >= 2:
				b.add_status(u, "dodge", 4, 0.1 * (r - 1), Battle.NO_TARGET, true)
			b.say(u, "Hair's back, baby!")
		# ------------------------------------------------------------ Cam
		"mind_goblin":
			b.anim(u, null, "cast", {"color": "#7cff4f"})
			b.aoe("enemy", "124,255,79")
			b.goblin = 3 if r >= 3 else 2
			for e in b.foes_of(u):
				b.dot(u, e, "poison", 0.25 * (1 + 0.3 * (r - 1)), 3)
		"iceland_story":
			b.anim(u, null, "cast", {"color": "#a0f0ff"})
			b.say(u, "So there I was, in Iceland...")
			b.aoe("enemy", "160,240,255")
			for e in b.foes_of(u):
				b.hit(u, e, 0.4 * (1 + 0.2 * (r - 1)), {"no_dodge": true})
				b.stun(e, 1)
				if r >= 3:
					b.add_status(e, "weaken", 2, 0.15, Battle.NO_TARGET, true)
				if r >= 5:
					b.dot(u, e, "burn", 0.3, 3)
		"would_you_rather":
			b.anim(u, null, "cast", {"color": "#ff7ae0"})
			b.say(u, b.rng.pick(["Would you rather fight one horse-sized duck...", "Would you rather have no elbows or no knees?"]))
			for e in b.foes_of(u):
				if b.rng.chance(minf(0.9, 0.5 + 0.08 * (r - 1))):
					b.add_status(e, "confuse", 1, 0.15 * (r - 1), u.uid)
				else:
					b.note(e, "Unbothered", "#9aa0b8")
		"shopping_spree":
			b.anim(u, null, "cast", {"color": "#ffd23f"})
			var s := 1 + 0.25 * (r - 1)
			var lucky := b.rng.chance(0.1 + 0.05 * (r - 1))
			for a in b.allies_of(u):
				var picks: Array = b.rng.shuffle(["empower", "guard", "dodge", "crit", "regen"]).slice(0, 3)
				for k in picks:
					if k == "regen":
						b.add_status(a, "regen", 3, a.max_hp * 0.06 * s)
					else:
						b.add_status(a, k, 3, (0.2 if k == "crit" else 0.15) * s)
				if lucky:
					b.add_status(a, "protect", 3, 0.0)
			if lucky:
				b.say(u, "Everything was on sale")
		"nissan_titan":
			b.emit({"t": "banner", "text": "NISSAN TITAN", "sub": "Beep beep"})
			b.anim(u, null, "cast", {"color": "#4fc3ff"})
			b.beat(0.4)
			b.emit({"t": "fx", "kind": "truck", "uid": u.uid})
			b.beat(0.45)
			b.shake(10)
			b.aoe("enemy", "79,195,255")
			var hits := 0
			for e in b.foes_of(u):
				if b.hit(u, e, 3 * (1 + 0.25 * (r - 1)), {"no_dodge": true}) > 0:
					hits += 1
				b.stun(e, 2)
			b.stats.titan_hits = maxi(b.stats.titan_hits, hits)
		# ------------------------------------------------------------ Sam
		"ignore_emails":
			b.anim(u, null, "cast", {"color": "#9b5cff"})
			b.note(u, "Marked all as read", "#9b5cff")
			b.shield_up(u, u.max_hp * (0.25 + 0.05 * (r - 1)))
			b.add_status(u, "reflect", 3, 0.2 + 0.05 * (r - 1))
		"rage_bait":
			var e := first_alive(b, u, t)
			if e == null:
				return
			var mason := b.hero("mason")
			var bonus := 0.25 if mason else 0.0
			if mason and b.rng.chance(0.3):
				b.say(u, "I hate Mason")
			b.anim(u, e, "cast", {"color": "#ff5a1f"})
			if b.hit(u, e, 2.2 * (1 + 0.15 * (r - 1)), {"crit_bonus": bonus, "rage_bait": true}) > 0:
				b.add_status(e, "weaken", 1, 0.2)
				sam_burn(b, u, e)
		"energy_drinks_bad":
			b.anim(u, null, "cast", {"color": "#ffb347"})
			b.say(u, "Energy drinks are bad for you.")
			b.aoe("enemy", "255,179,71")
			for e in b.foes_of(u):
				var m := 0.45 * (1 + 0.1 * (r - 1)) * (1.5 if e.key in ["energy_drink", "tallboy"] else 1.0)
				b.hit(u, e, m)
				b.add_status(e, "exposed", 2, 0.1 if r >= 3 else 0.0)
				sam_burn(b, u, e)
		"burger_bomb":
			if r < 5:
				b.note(u, "Cold burger...", "#7cff4f")
				b.add_status(u, "poison", 3, maxf(1.0, u.max_hp * 0.04), u.uid)
			b.anim(u, null, "cast", {"color": "#7cff4f"})
			b.aoe("enemy", "124,255,79")
			for e in b.foes_of(u):
				if b.hit(u, e, 0.8 * (1 + 0.15 * (r - 1))) > 0:
					b.dot(u, e, "poison", 0.3, 3)
					sam_burn(b, u, e)
		"desk_treadmill":
			var amount := u.max_hp * (0.05 + 0.01 * (r - 1))
			var healed := b.heal(u, amount)
			var over := roundi(amount) - healed
			var cap := roundi(u.max_hp * 0.1)
			if over > 0 and u.shield < cap:
				b.shield_up(u, mini(over, cap - u.shield))
		"out_of_pocket":
			b.emit({"t": "banner", "text": "OUT OF POCKET", "sub": "Sam said WHAT?"})
			b.anim(u, null, "cast", {"color": "#9b5cff"})
			b.beat(0.5)
			b.shake(8)
			b.aoe("enemy", "155,92,255")
			for e in b.foes_of(u):
				b.hit(u, e, 2.4 * (1 + 0.2 * (r - 1)), {"no_dodge": true})
				b.stun(e, 2)
				sam_burn(b, u, e)
		# ------------------------------------------------------------ Sarah
		"the_worm":
			b.anim(u, null, "melee", {"color": "#ff5fa2"})
			b.note(u, "The Worm", "#ff5fa2")
			for i in knives(r):
				var foes := b.foes_of(u)
				if foes.is_empty():
					return
				var e: BattleUnit = b.rng.pick(foes)
				b.anim(u, e, "ranged", {"color": "#d0d0e0"})
				if b.hit(u, e, 0.3) > 0:
					b.dot(u, e, "bleed", 0.2, 3)
					b.gain_energy(u, 8)
				b.beat(0.1)
		"scuba":
			for i in knives(r) - 1:
				var e := first_alive(b, u, t)
				if e == null:
					return
				b.anim(u, e, "melee")
				if b.hit(u, e, 0.4) > 0:
					b.dot(u, e, "bleed", 0.15, 3)
					b.gain_energy(u, 10)
				b.beat(0.15)
		"dab":
			b.anim(u, null, "cast", {"color": "#ff5fa2"})
			b.say(u, "Clock it.")
			var total := 0
			for e in b.foes_of(u):
				total += b.detonate(u, e, 1.25 + 0.25 * (r - 1))
			b.stats.best_dab = maxi(b.stats.best_dab, total)
		"catching_the_fish":
			var foes := b.foes_of(u)
			if foes.is_empty():
				return
			foes.sort_custom(func(x, y): return x.hp > y.hp)
			var e: BattleUnit = foes[0]
			b.note(u, "Reeling it in...", "#4fc3ff")
			b.anim(u, e, "melee")
			if b.hit(u, e, 1.5 * (1 + 0.15 * (r - 1))) > 0:
				b.dot(u, e, "bleed", 0.3, 3)
			b.gain_energy(u, 20)
		"dance_rehearsal":
			u.aura = minf(0.3, u.aura + 0.03 + 0.01 * (r - 1))
		"subaru_driveby":
			b.emit({"t": "banner", "text": "SUBARU DRIVE-BY", "sub": "Stop stealing my leads"})
			b.emit({"t": "fx", "kind": "subaru", "uid": u.uid})
			b.beat(0.45)
			b.shake(8)
			var spent := u.energy
			u.energy = 0.0
			b.emit({"t": "resource", "uid": u.uid, "mp": u.mp, "energy": u.energy})
			for e in b.foes_of(u):
				if b.hit(u, e, 1.0, {"no_dodge": true}) > 0:
					b.dot(u, e, "bleed", 0.4, 3)
			b.beat(0.3)
			for e in b.foes_of(u):
				b.detonate(u, e, 0.5 + spent / 200.0 + 0.2 * (r - 1))


# ------------------------------------------------------------------ weapons
static func weapon_attack(id: String, b: Battle, u: BattleUnit, t: BattleUnit) -> void:
	match id:
		"soccer_ball":
			strike(b, u, t, 1.3, "ranged", {"color": "#ffffff"})
		"trading_cards":
			var roll := b.rng.int_range(1, 20)
			b.note(u, "HOLO RARE!" if roll == 20 else ("All commons..." if roll <= 3 else "Pulled a %d" % roll), "#ffd23f" if roll == 20 else "#ffffff")
			strike(b, u, t, (0.2 + roll * 0.1) * (2 if roll == 20 else 1), "ranged", {"color": "#ffd23f"})
		"potenuse":
			var last: int = b.last_hero_hit.amount if not b.last_hero_hit.is_empty() and b.last_hero_hit.uid != u.uid else 0
			var e := first_alive(b, u, t)
			if e == null:
				return
			b.anim(u, e, "ranged", {"color": "#c08aff"})
			if last > 0:
				b.hit(u, e, 0.0, {"flat": float(last + 1), "pierce": true, "weapon": true})
			else:
				b.hit(u, e, 1.0, {"weapon": true})
		"golf_club":
			strike(b, u, t, 1.4, "melee", {"no_dodge": true})
		"baseball_bat":
			strike(b, u, t, 1.6, "melee")
		"offsets":
			var e := first_alive(b, u, t)
			if e and strike(b, u, e, 1.4, "melee") > 0:
				b.add_status(e, "taunt", 2, 0.0, u.uid)
				for k in e.cd.keys():
					e.cd[k] += 1
				b.note(e, "-20% mana", "#4fc3ff")
		"putter":
			var n := b.rng.int_range(1, 3)
			for i in n:
				strike(b, u, t, 0.7, "melee")
				if i < n - 1:
					b.beat(0.18)
		"meme_barrage":
			for i in 5:
				var foes := b.foes_of(u)
				if foes.is_empty():
					return
				var e: BattleUnit = b.rng.pick(foes)
				b.anim(u, e, "ranged", {"color": "#7cff4f"})
				if b.hit(u, e, 0.3, {"weapon": true}) > 0:
					b.dot(u, e, "poison", 0.15, 3)
				b.beat(0.12)
		"murray_mobile":
			strike(b, u, t, 1.7, "melee")
		"ai_slop":
			b.anim(u, null, "cast", {"color": "#7cff4f"})
			b.aoe("enemy", "124,255,79")
			for e in b.foes_of(u):
				if b.hit(u, e, 0.45, {"weapon": true}) > 0:
					b.dot(u, e, "poison", 0.2, 3)
		"new_fit":
			var e := first_alive(b, u, t)
			if e and strike(b, u, e, 0.7, "ranged", {"color": "#ff9a1f"}) > 0:
				b.stun(e, 1, 0.4)
				b.dot(u, e, "burn", 0.3, 3)
		"new_pc":
			strike(b, u, t, 1.1, "ranged", {"color": "#4fc3ff"})
		"booster_seat":
			strike(b, u, t, 1.2, "ranged", {"color": "#9b5cff"})
		"trucksmarter_lor":
			strike(b, u, t, 1.0, "ranged", {"color": "#9b5cff"})
		"lampedusa_flag":
			strike(b, u, t, 0.9, "ranged", {"color": "#9b5cff"})
		"colorguard_gun":
			var e := first_alive(b, u, t)
			if e and strike(b, u, e, 1.3, "melee") > 0 and b.rng.chance(0.25):
				b.detonate(u, e, 0.75)
		"tambourine":
			b.anim(u, null, "cast", {"color": "#ffd23f"})
			b.note(u, "Shake shake", "#ffd23f")
			for a in b.allies_of(u):
				b.add_status(a, "empower", 2, 0.15, Battle.NO_TARGET, true)
			b.gain_energy(u, 15)
		"great_state_of_ohio":
			b.anim(u, null, "cast", {"color": "#ff4f6d"})
			b.aoe("enemy", "255,79,109")
			for e in b.foes_of(u):
				if b.hit(u, e, 0.4, {"weapon": true}) > 0:
					if b.rng.chance(0.6):
						b.dot(u, e, "bleed", 0.25, 3)
					if b.rng.chance(0.6):
						b.dot(u, e, "poison", 0.25, 3)
