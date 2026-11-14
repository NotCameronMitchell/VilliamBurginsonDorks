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


## Overworld lines. Each area has a coworker guarding the door (the minion fight) and
## a few office regulars to talk to. "%s" gets filled in where noted.
const OVERWORLD := {
	"guards": {
		"parking_lot": {"model": "loud_typer", "line": "Nobody leaves before 5. Not even to the parking lot. CLACK CLACK."},
		"desk_pods": {"model": "reply_all", "line": "Per my last email: nobody gets past the pods. Thanks all!!"},
		"meeting_room": {"model": "close_talker", "line": "Got a sec? The 2 o'clock is running long. Like, really long."},
		"office_center": {"model": "fish_guy", "line": "It's just salmon! Want some? No? Then fight me."},
		"james_desk": {"model": "reply_all", "line": "Nobody goes near James's old desk. Adding the whole team!"},
	},
	"guard_beaten": "Fine. Go on in. %s is waiting for you.", # boss name
	"guard_cleared": "Nice work in there. Bring me back some sauce?",
	"guard_waiting": "You're busy over in the %s. Finish that first.", # area name
	"boss_not_ready": "You'll have to get past my coworker first.",
	"boss_waiting": "Come back when you're done in the %s.", # area name
	"out_of_office": "%s is out of office today.", # boss name
	"receptionist_name": "Front Desk",
	"receptionist": "Morning! Today's bosses: %s. The elevator down to Villiam Burginson's opens once all three are dealt with.", # list
	"receptionist_done": "That's everyone! The elevator's waiting. Bring me back some sauce?",
	"elevator_locked": "The elevator only goes down once today's three bosses are beaten. (%d of 3 so far)",
	"elevator_go": "Going down to Villiam Burginson's...",
	"regulars": [
		{"model": "energy_drink", "pos": [-7.5, -6.6], "face": [0, 1], "lines": ["300mg of caffeine says hi.", "I've been awake since Tuesday."]},
		{"model": "nic_pouch", "pos": [7.5, -1.3], "face": [0, -1], "lines": ["Don't mind me. Just tucked in here.", "Cool mint. Always cool mint."]},
	],
}


## The intro lines for a boss (the remix's own intro if it has one).
static func boss_intro(id: String, remix := false) -> Array:
	var l: Dictionary = BOSS_LINES.get(id, {})
	if remix and l.has("remix_intro"):
		return l.remix_intro
	return l.get("intro", [])


static func boss_defeat(id: String) -> Array:
	return BOSS_LINES.get(id, {}).get("defeat", [])
