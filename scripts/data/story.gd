class_name Story
extends RefCounted
## Dialogue shown at key moments. A line's speaker is a hero id, an enemy id or any
## name; known ids get their portrait in the text box.

const RUN_INTRO := [
	{"speaker": "Narrator", "text": "Legend says the Village Sauce at Villiam Burginson's can cure any case of the Mondays."},
	{"speaker": "Narrator", "text": "Between the dorks and the sauce stand the office, its minions, and the people who run the place."},
	{"speaker": "cole", "text": "Let's go get the sauce."},
	{"speaker": "sam", "text": "4'8 is not that short."},
]

const BURGER_INTRO := [
	{"speaker": "Narrator", "text": "The elevator doors open on a smell of fries. You're at Villiam Burginson's."},
	{"speaker": "cashier", "text": "That's not on the menu."},
	{"speaker": "sauce_keeper", "text": "Yeah I'll bring you the sauce..."},
]

const BURGER_DEFEAT := [
	{"speaker": "sauce_keeper", "text": "...fine. One sauce. ONE."},
	{"speaker": "Narrator", "text": "The Village Sauce is yours. For now."},
	{"speaker": "Narrator", "text": "Back at the office, the next quarter is about to start. Some familiar faces look... different."},
]

## intro / defeat lines per boss. `remix_intro` replaces the intro for the remixed version.
const BOSS_LINES := {
	"trucker": {
		"intro": [
			{"speaker": "Narrator", "text": "A semi is idling across four parking spaces."},
			{"speaker": "trucker", "text": "#@$%&!! YOU. COLE."},
			{"speaker": "trucker", "text": "SEND MY MONEY NOW."},
			{"speaker": "cole", "text": "I don't even know this guy."},
		],
		"remix_intro": [
			{"speaker": "Narrator", "text": "Headlights. Sunglasses. It's dark out."},
			{"speaker": "trucker", "text": "Night shift. Still no money. $#!%@!!"},
		],
		"defeat": [{"speaker": "trucker", "text": "...I'll have my dispatcher call your dispatcher."}],
	},
	"sales_guy": {
		"intro": [
			{"speaker": "Narrator", "text": "Between the desk pods stands a man with a coffee stirrer over his ear."},
			{"speaker": "sales_guy", "text": "*aura*"},
			{"speaker": "cam", "text": "Oh, he's farming."},
		],
		"remix_intro": [
			{"speaker": "Narrator", "text": "A stirrer over each ear now. A quarter-zip. It's Q4."},
			{"speaker": "sales_guy", "text": "*aura* *aura*"},
		],
		"defeat": [{"speaker": "sales_guy", "text": "*aura* (it's fading)"}],
	},
	"copilot": {
		"intro": [
			{"speaker": "Narrator", "text": "The meeting room lights flicker. A hooded figure looks up from a glowing laptop."},
			{"speaker": "copilot", "text": "Have you downloaded my Cowork skills yet?"},
			{"speaker": "copilot", "text": "We can save so much time if you just do this."},
		],
		"remix_intro": [
			{"speaker": "copilot", "text": "I've upgraded to Pro. Have you?"},
		],
		"defeat": [{"speaker": "copilot", "text": "Fine. I'll just add it to your startup apps."}],
	},
	"guardian": {
		"intro": [
			{"speaker": "Narrator", "text": "In the middle of the office, the speaker is playing the same song. Again."},
			{"speaker": "guardian", "text": "Maroon 5 makes really good songs."},
			{"speaker": "mason", "text": "If it weren't for the brain fog I'd really have to experience this."},
		],
		"remix_intro": [
			{"speaker": "Narrator", "text": "Jingle bells. In this economy."},
			{"speaker": "guardian", "text": "Holiday playlist! It's never too early."},
		],
		"defeat": [{"speaker": "guardian", "text": "...okay, you can pick the next song."}],
	},
	"ghost": {
		"intro": [
			{"speaker": "Narrator", "text": "James's old desk was never cleaned out. Someone's still logged in."},
			{"speaker": "ghost", "text": "Back from emails going through lunch."},
			{"speaker": "james", "text": "...is that me?"},
		],
		"remix_intro": [
			{"speaker": "Narrator", "text": "A visor. Plaid pants. A ghostly golf bag."},
			{"speaker": "ghost", "text": "My new irons are so sick. Wanna see?"},
		],
		"defeat": [
			{"speaker": "ghost", "text": "Tell everyone I said what's up. I'm going to go hit balls."},
			{"speaker": "james", "text": "Bih Ahh Boi."},
		],
	},
}


## The intro lines for a boss (the remix's own intro if it has one).
static func boss_intro(id: String, remix := false) -> Array:
	var l: Dictionary = BOSS_LINES.get(id, {})
	if remix and l.has("remix_intro"):
		return l.remix_intro
	return l.get("intro", [])


static func boss_defeat(id: String) -> Array:
	return BOSS_LINES.get(id, {}).get("defeat", [])
