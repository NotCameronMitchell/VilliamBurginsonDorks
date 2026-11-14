"""
The detailed heroes: how each one looks and moves.

- **Look:** concept_prompt() writes the prompt that turns a hero's photo into concept art
  (Gemini), which Hunyuan 3D then builds into a model. Edit an outfit here, then make new
  concept art.
- **Moves:** the Kimodo prompts below. Edit one, then regenerate that hero's motions.

docs/ART_PIPELINE.md ("Detailed heroes") has the steps. Plain data only: kimodo_batch.py
(Kimodo's Python), hero_assemble.py (Blender's Python) and meshy.py all import this file.
"""

# Every concept image gets this style, so the whole cast matches.
STYLE = (
    "Style: a 3D-rendered game character model, like the trainer characters in Pokemon Scarlet and "
    "Violet, with stylized anime proportions (about six heads tall), smooth clean shapes, soft 3D "
    "shading with no black outlines (not a flat 2D drawing), bright saturated colors and a "
    "friendly, expressive face. "
    "Pose: standing in a neutral A-pose, arms straight and angled about 45 degrees away from the "
    "body, hands open and empty, feet shoulder-width apart, facing the camera. "
    "Show the whole body from head to toe, centered, on a plain light gray background with even "
    "studio lighting, no shadows and no text."
)

# With a photo, the concept keeps the person recognizable.
PHOTO_PROMPT = (
    "Turn the person in the attached photo into a full-body 3D video game character. Keep their "
    "face, hairstyle, hair color, facial hair and skin tone recognizable. "
)

# Follow-up prompts in the same Gemini chat: extra views help Hunyuan 3D build the back.
EXTRA_VIEWS = {
    "back": "Now show the exact same character from directly behind, in the same A-pose, on the "
            "same plain light gray background. Same outfit, same proportions.",
    "left": "Now show the exact same character from its left side (side view, profile), in the "
            "same A-pose, on the same plain light gray background. Same outfit, same proportions.",
}

# Heights are real life, in meters. The game shows every hero at GAME_SCALE: realistic
# proportions (small heads) read smaller than the chibi models did at the same height, so
# the cast stands a little taller than them; Sam is still the shortest.
GAME_SCALE = 0.95

# person: face, hair and build, used only when there's no photo.
# extra:  notes the concept should follow even with a photo.
HEROES = {
    "mason": {
        "name": "Mason",
        "height": 1.80,
        "person": "A friendly man in his late 20s with short, tousled light-brown hair, clean-shaven.",
        "outfit": "a white soccer away jersey with red and green trim on the collar and sleeves, light "
                  "cream chino pants, white sneakers, and a black smartwatch on his left wrist.",
    },
    "james": {
        "name": "James",
        "height": 1.78,
        "person": "A man in his late 20s with short dark-brown hair and a thick dark mustache.",
        "extra": "He is stocky and broad-shouldered.",
        "outfit": "a matching brown sweatsuit (a crewneck sweatshirt with a small yellow number on the "
                  "chest, and jogger pants) and white sneakers.",
    },
    "cole": {
        "name": "Cole",
        "height": 1.83,
        "person": "A lean man in his late 20s with short brown hair, a noticeably receding hairline "
                  "and light stubble.",
        "outfit": "a navy-blue short-sleeve button-up shirt with a small white pattern, khaki shorts, "
                  "and off-white sneakers.",
    },
    "cam": {
        "name": "Cam",
        "height": 1.80,
        "person": "A slim man in his late 20s with short hair.",
        "outfit": "a black baseball cap, black sunglasses, a dark charcoal graphic t-shirt with a "
                  "neon-yellow futuristic print, tan chino pants, and brown leather shoes.",
    },
    "sam": {
        "name": "Sam",
        "height": 1.42,  # 4'8", the shortest of the crew by far
        "person": "A young Italian woman with long, straight, dark-brown hair past her shoulders.",
        "extra": "She is very short (4 feet 8 inches tall) and has a confident smirk.",
        "outfit": "a flowing black dress that reaches just below her knees, and simple black flats.",
    },
    "sarah": {
        "name": "Sarah",
        "height": 1.57,
        "person": "A young woman with long, wavy dark-brown hair and glasses.",
        "extra": "Keep her glasses.",
        "outfit": "a cozy pink knit sweater, black leggings, and dark sneakers.",
    },
}

# Transformed forms get their own model (from their hero's photo) and reuse the hero's motions.
FORMS = {
    "cole_uw": {
        "base": "cole",
        "name": "Cole (Transfer to UW)",
        "height": 1.83,
        "person": HEROES["cole"]["person"],
        "extra": "Give him a full head of thick hair and a triumphant grin.",
        "outfit": "a purple athletic jersey with a gold number, purple athletic pants, and white sneakers.",
    },
    "james_buff": {
        "base": "james",
        "name": "James (JimmyTrains)",
        "height": 1.85,
        "person": HEROES["james"]["person"],
        "extra": "Make him a huge, muscular bodybuilder.",
        "outfit": "a tight sleeveless brown tank top, brown jogger pants, and white sneakers.",
    },
}


def concept_prompt(model_id, photo=True):
    """The prompt that turns a hero's photo (or, without one, a description) into concept art."""
    s = spec(model_id)
    who = PHOTO_PROMPT if photo else "A full-body 3D video game character. " + s["person"] + " "
    extra = (s["extra"] + " ") if s.get("extra") else ""
    return who + extra + "Outfit: " + s["outfit"] + " " + STYLE

# --------------------------------------------------------------------------- motions
# The animations the game plays (docs/ART_PIPELINE.md, "Rig and animations"), plus "run",
# which only the trailer uses (the heroes charge the throne).
ANIMS = ["idle", "walk", "attack", "cast", "hit", "stunned", "faint", "victory", "ultimate", "run"]

# Motion spec keys:
#   prompt    what Kimodo should do. Plain physical words work best ("A person ...").
#   seconds   how long to generate (Kimodo's limit is 10).
#   loop      the game loops it: the end is blended back into the start.
#   cycle     (walk) cut one clean step cycle out of the clip, then loop it.
#   root      "inplace": no drifting across the floor. "free": keep steps and falls.
#   seed      change it to get a different take on the same prompt.

SHARED_MOTIONS = {
    "walk": {
        "prompt": "A person walks forward at a relaxed, steady pace.",
        "seconds": 6.0, "loop": True, "cycle": True, "root": "inplace", "seed": 11,
    },
    "hit": {
        "prompt": "A person gets hit hard in the chest, flinches and staggers one step backward, "
                  "then regains their balance.",
        "seconds": 1.6, "root": "free", "seed": 12,
    },
    "stunned": {
        "prompt": "A dizzy person sways unsteadily in place, wobbling from side to side with their "
                  "head drooping.",
        "seconds": 4.0, "loop": True, "root": "inplace", "seed": 13,
    },
    "faint": {
        "prompt": "A person loses consciousness, their knees buckle, and they collapse backward "
                  "onto the floor and lie still.",
        "seconds": 3.0, "root": "free", "seed": 14,
    },
    "run": {
        "prompt": "A person sprints forward at full speed, charging into battle.",
        "seconds": 4.0, "loop": True, "cycle": True, "root": "inplace", "seed": 15,
    },
}

HERO_MOTIONS = {
    "mason": {  # Beastmaster: soccer ball, cats Bruno and Murphy, Wife BTW
        "idle": {"prompt": "A person stands relaxed in place, lightly bouncing on the balls of their "
                           "feet like a soccer player waiting for a pass.",
                 "seconds": 4.0, "loop": True, "root": "inplace"},
        "attack": {"prompt": "A person takes a quick step and kicks a ball forward hard with their "
                             "right foot.", "seconds": 1.6, "root": "free"},
        "cast": {"prompt": "A person crouches slightly and points forward with one arm, commanding "
                           "their pet to attack.", "seconds": 2.0, "root": "free"},
        "victory": {"prompt": "A person celebrates a goal, pumping both fists and then raising both "
                              "arms high in the air.", "seconds": 4.0, "loop": True, "root": "inplace"},
        "ultimate": {"prompt": "A person proudly raises their left hand to show off a wedding ring, "
                               "points at it with their right hand, and nods.", "seconds": 3.5,
                     "root": "free"},
    },
    "james": {  # Berserker: golf club, Peptide Rage, JimmyTrains
        "idle": {"prompt": "A person stands in a boxer's stance with fists raised, bouncing slightly "
                           "and rolling their shoulders.", "seconds": 4.0, "loop": True,
                 "root": "inplace"},
        "attack": {"prompt": "A person swings a golf club hard with both hands in a full golf swing.",
                   "seconds": 1.8, "root": "free"},
        "cast": {"prompt": "A person clenches their fists, flexes both arms and roars with rage.",
                 "seconds": 2.0, "root": "free"},
        "victory": {"prompt": "A person flexes both biceps in a bodybuilder pose, then switches to "
                              "another flexing pose.", "seconds": 4.0, "loop": True, "root": "inplace"},
        "ultimate": {"prompt": "A person pounds their chest with both fists, then crouches and flexes "
                               "every muscle in a powerful bodybuilder pose.", "seconds": 3.5,
                     "root": "free"},
    },
    "cole": {  # Melee DPS: putter, Argue with Sales, Transfer to UW
        "idle": {"prompt": "A person stands confidently with their weight on one leg, swinging their "
                           "arms a little and looking around.", "seconds": 4.0, "loop": True,
                 "root": "inplace"},
        "attack": {"prompt": "A person putts a golf ball, making two short, careful putting strokes "
                             "with a club held in both hands.", "seconds": 1.8, "root": "free"},
        "cast": {"prompt": "A person argues, gesturing emphatically with both hands and pointing "
                           "forward angrily.", "seconds": 2.2, "root": "free"},
        "victory": {"prompt": "A person pumps their fist and does a little celebratory dance.",
                    "seconds": 4.0, "loop": True, "root": "inplace"},
        "ultimate": {"prompt": "A person throws both arms out wide, spins around once, and strikes a "
                               "triumphant pose.", "seconds": 3.0, "root": "free"},
    },
    "cam": {  # Caster: AI Slop, Iceland Story, Nissan Titan
        "idle": {"prompt": "A person stands relaxed and cool with their hands in their pockets, "
                           "nodding their head slowly to a beat.", "seconds": 4.0, "loop": True,
                 "root": "inplace"},
        "attack": {"prompt": "A person thrusts both hands forward as if throwing a magic blast at "
                             "someone.", "seconds": 1.6, "root": "free"},
        "cast": {"prompt": "A person tells an animated story, waving their hands around "
                           "expressively.", "seconds": 2.2, "root": "free"},
        "victory": {"prompt": "A person gives two thumbs up, then crosses their arms and nods coolly.",
                    "seconds": 4.0, "loop": True, "root": "inplace"},
        "ultimate": {"prompt": "A person grips an imaginary steering wheel with both hands and steers "
                               "hard, then throws both arms up in excitement.", "seconds": 3.5,
                     "root": "free"},
    },
    "sam": {  # Wizard: Booster Seat, spells, Out of Pocket Message
        "idle": {"prompt": "A person stands with their arms crossed, impatiently tapping one foot.",
                 "seconds": 4.0, "loop": True, "root": "inplace"},
        "attack": {"prompt": "A person lifts a heavy object over their head with both hands and slams "
                             "it down in front of them.", "seconds": 1.8, "root": "free"},
        "cast": {"prompt": "A person raises both arms, then thrusts both palms forward as if casting "
                           "a spell.", "seconds": 2.0, "root": "free"},
        "victory": {"prompt": "A person flips their hair over their shoulder, then puts their hands on "
                              "their hips proudly.", "seconds": 4.0, "loop": True, "root": "inplace"},
        "ultimate": {"prompt": "A person quickly types on a phone held in both hands, then throws both "
                               "arms forward in a big dramatic gesture.", "seconds": 3.5,
                     "root": "free"},
    },
    "sarah": {  # Rogue: Colorguard Gun, Dab, Subaru Drive-by
        "idle": {"prompt": "A person bounces rhythmically in place, ready to dance.",
                 "seconds": 4.0, "loop": True, "root": "inplace"},
        "attack": {"prompt": "A person spins around and strikes forward with both hands as if "
                             "swinging a stick.", "seconds": 1.6, "root": "free"},
        "cast": {"prompt": "A person does a dab, ducking their head into one bent elbow while the "
                           "other arm points up and out.", "seconds": 1.8, "root": "free"},
        "victory": {"prompt": "A person does a celebratory dance with shoulder shimmies and hip "
                              "shakes.", "seconds": 4.0, "loop": True, "root": "inplace"},
        "ultimate": {"prompt": "A person grips an imaginary steering wheel and leans into a sharp "
                               "turn, then leans out and waves.", "seconds": 3.5, "root": "free"},
    },
}


# --------------------------------------------------------------------------- bosses
# Detailed bosses, built like the heroes (hero_mh.py, hero_looks.py) and exported to
# assets/models/bosses. They're a bit larger than life, like Pokemon gym leaders.
# "<boss>_remix" (cycle 2+) reuses its boss's body and motions with a changed outfit.
BOSSES = {
    "trucker": {"name": "The Angry Trucker", "height": 1.98},
    "sales_guy": {"name": "The Mystery Sales Guy", "height": 1.93},
    "guardian": {"name": "The Guardian of Tunes", "height": 1.74},
    "ghost": {"name": "The Ghost of James Civelli", "height": 1.95},  # James's old-job self
    "copilot": {"name": "The Copilot Grim Reaper", "height": 2.05},
    "cashier": {"name": "The Cashier", "height": 1.66},  # the burger crew (the final fight)
    "grill_master": {"name": "The Grill Master", "height": 1.84},
    "sauce_keeper": {"name": "The Sauce Keeper", "height": 1.80},
}

# The office coworkers you fight on the way (exported to assets/models/minions). The object
# minions (energy drink, tallboy, nicotine pouch, pouch tin) stay chibi: they aren't people.
MINIONS = {
    "reply_all": {"name": "Reply-All Guy", "height": 1.78},
    "fish_guy": {"name": "Microwave Fish Guy", "height": 1.76},
    "loud_typer": {"name": "Mechanical Keyboard Guy", "height": 1.74},
    "close_talker": {"name": "Close Talker", "height": 1.79},
}

BOSS_MOTIONS = {
    "trucker": {  # Honk, Road Rage, Nissan-sized semi
        "idle": {"prompt": "A big angry man stands with his arms crossed, shifting his weight and "
                           "shaking his head in annoyance.", "seconds": 4.0, "loop": True, "root": "inplace"},
        "attack": {"prompt": "A man steps forward and throws a big right hook punch with his whole body.",
                   "seconds": 1.6, "root": "free"},
        "cast": {"prompt": "A man angrily shakes his fist and yells, then points forward.",
                 "seconds": 2.0, "root": "free"},
        "victory": {"prompt": "A man pumps his fist in the air, then crosses his arms with a satisfied "
                              "nod.", "seconds": 4.0, "loop": True, "root": "inplace"},
        "ultimate": {"prompt": "A man stomps forward, raises both fists over his head and slams them "
                               "down hard.", "seconds": 3.0, "root": "free"},
    },
    "sales_guy": {  # aura farming, the pitch, coffee stirrer
        "idle": {"prompt": "A confident man stands tall, straightening his tie and smoothing his "
                           "jacket.", "seconds": 4.0, "loop": True, "root": "inplace"},
        "attack": {"prompt": "A man jabs his finger forward repeatedly while making a point.",
                   "seconds": 1.6, "root": "free"},
        "cast": {"prompt": "A man spreads both arms wide like a showman presenting a deal.",
                 "seconds": 2.0, "root": "free"},
        "victory": {"prompt": "A man claps his hands once, points with both hands and winks.",
                    "seconds": 4.0, "loop": True, "root": "inplace"},
        "ultimate": {"prompt": "A man slowly raises both arms, then spins around once and strikes a "
                               "dramatic pose.", "seconds": 3.0, "root": "free"},
    },
    "guardian": {  # earworms, the boombox
        "idle": {"prompt": "A woman bobs her head and sways her hips to music.", "seconds": 4.0,
                 "loop": True, "root": "inplace"},
        "attack": {"prompt": "A woman swings her arm forward as if throwing something.", "seconds": 1.6,
                   "root": "free"},
        "cast": {"prompt": "A woman raises both arms over her head and dances.", "seconds": 2.0,
                 "root": "free"},
        "victory": {"prompt": "A woman dances happily, waving her arms.", "seconds": 4.0, "loop": True,
                    "root": "inplace"},
        "ultimate": {"prompt": "A woman raises both arms and dances energetically in place, then strikes a "
                               "big pose facing forward.", "seconds": 3.0, "root": "free"},
    },
    "ghost": {  # possession, the old job
        "idle": {"prompt": "A man stands perfectly still with his arms crossed, slowly turning his head "
                           "from side to side.", "seconds": 4.0, "loop": True, "root": "inplace"},
        "attack": {"prompt": "A man lunges forward with both arms outstretched, trying to grab someone.",
                   "seconds": 1.6, "root": "free"},
        "cast": {"prompt": "A man slowly raises both arms high above his head.", "seconds": 2.0,
                 "root": "free"},
        "victory": {"prompt": "A man laughs, leaning back with his hands on his belly.", "seconds": 4.0,
                    "loop": True, "root": "inplace"},
        "ultimate": {"prompt": "A man spreads his arms wide and throws his head back.", "seconds": 3.0,
                     "root": "free"},
    },
    "copilot": {  # the scythe, the laptop, the pop-ups
        # The arm pose is spelled out: Kimodo knows nothing about props, and with "holding a
        # staff" alone it let the arm hang, which held the scythe out sideways.
        "idle": {"prompt": "A tall person stands perfectly still and menacing, the right elbow bent and the right "
                           "fist held in front of the chest as if gripping a tall staff upright, the left arm "
                           "hanging at the side, slowly turning their head.", "seconds": 4.0, "loop": True,
                 "root": "inplace"},
        "attack": {"prompt": "A person swings a long scythe in a wide horizontal arc with both hands.",
                   "seconds": 1.8, "root": "free"},
        "cast": {"prompt": "A person raises their left hand and points forward menacingly.", "seconds": 2.0,
                 "root": "free"},
        "victory": {"prompt": "A person plants a staff on the ground and slowly spreads their free arm wide.",
                    "seconds": 4.0, "loop": True, "root": "inplace"},
        "ultimate": {"prompt": "A person lifts a long staff high over their head with both hands and slams it "
                               "down hard.", "seconds": 3.0, "root": "free"},
    },
    "cashier": {
        "idle": {"prompt": "A bored person stands shifting their weight from foot to foot, tapping their fingers.",
                 "seconds": 4.0, "loop": True, "root": "inplace"},
        "attack": {"prompt": "A person throws something forward hard with one arm.", "seconds": 1.6, "root": "free"},
        "cast": {"prompt": "A person impatiently waves their hand, then points at someone.", "seconds": 2.0,
                 "root": "free"},
        "victory": {"prompt": "A person claps their hands and does a little happy hop.", "seconds": 4.0,
                    "loop": True, "root": "inplace"},
        "ultimate": {"prompt": "A person raises both arms and throws them forward with a big shout.",
                     "seconds": 3.0, "root": "free"},
    },
    "grill_master": {
        "idle": {"prompt": "A man stands with his feet apart, flipping a spatula in his right hand.",
                 "seconds": 4.0, "loop": True, "root": "inplace"},
        "attack": {"prompt": "A man raises a spatula overhead and smacks it down hard.", "seconds": 1.6,
                   "root": "free"},
        "cast": {"prompt": "A man wipes his forehead with his arm, then points forward.", "seconds": 2.0,
                 "root": "free"},
        "victory": {"prompt": "A man flexes both arms proudly.", "seconds": 4.0, "loop": True, "root": "inplace"},
        "ultimate": {"prompt": "A man tosses something high into the air, catches it, and strikes a pose facing "
                               "forward.", "seconds": 3.0, "root": "free"},
    },
    "sauce_keeper": {
        "idle": {"prompt": "A man stands hugging something to his chest, looking around suspiciously.",
                 "seconds": 4.0, "loop": True, "root": "inplace"},
        "attack": {"prompt": "A man thrusts both hands forward as if squeezing a bottle at someone.",
                   "seconds": 1.6, "root": "free"},
        "cast": {"prompt": "A man raises a bottle high over his head with one hand.", "seconds": 2.0,
                 "root": "free"},
        "victory": {"prompt": "A man pumps his fist and nods.", "seconds": 4.0, "loop": True, "root": "inplace"},
        "ultimate": {"prompt": "A man sweeps his arms around in a big circle, then thrusts both hands forward.",
                     "seconds": 3.0, "root": "free"},
    },
}

MINION_MOTIONS = {
    "reply_all": {
        "idle": {"prompt": "A person stands holding a laptop under one arm, impatiently tapping their foot.",
                 "seconds": 4.0, "loop": True, "root": "inplace"},
        "attack": {"prompt": "A person jabs their finger forward repeatedly while lecturing.", "seconds": 1.6,
                   "root": "free"},
        "cast": {"prompt": "A person types quickly on an imaginary keyboard, then hits a key dramatically.",
                 "seconds": 2.0, "root": "free"},
        "victory": {"prompt": "A person nods smugly with their arms crossed.", "seconds": 4.0, "loop": True,
                    "root": "inplace"},
        "ultimate": {"prompt": "A person throws both arms up and waves them wildly.", "seconds": 3.0,
                     "root": "free"},
    },
    "fish_guy": {
        "idle": {"prompt": "A person stands holding something in one hand, sniffing it and looking around.",
                 "seconds": 4.0, "loop": True, "root": "inplace"},
        "attack": {"prompt": "A person swings their arm overhead like a club and smacks down.", "seconds": 1.6,
                   "root": "free"},
        "cast": {"prompt": "A person holds something out at arm's length toward someone.", "seconds": 2.0,
                 "root": "free"},
        "victory": {"prompt": "A person raises one arm high in triumph.", "seconds": 4.0, "loop": True,
                    "root": "inplace"},
        "ultimate": {"prompt": "A person swings their arm in big circles, then slams it down.", "seconds": 3.0,
                     "root": "free"},
    },
    "loud_typer": {
        "idle": {"prompt": "A person bobs their head to music, tapping their fingers in the air.", "seconds": 4.0,
                 "loop": True, "root": "inplace"},
        "attack": {"prompt": "A person pounds the air in front of them with both fists, very fast.",
                   "seconds": 1.6, "root": "free"},
        "cast": {"prompt": "A person cups their hands around their mouth and yells.", "seconds": 2.0,
                 "root": "free"},
        "victory": {"prompt": "A person air-drums wildly.", "seconds": 4.0, "loop": True, "root": "inplace"},
        "ultimate": {"prompt": "A person hammers the air with both fists, faster and faster, then throws their "
                               "arms up.", "seconds": 3.0, "root": "free"},
    },
    "close_talker": {
        "idle": {"prompt": "A person leans forward, gesturing with one hand while talking.", "seconds": 4.0,
                 "loop": True, "root": "inplace"},
        "attack": {"prompt": "A person leans in close and points at someone's face.", "seconds": 1.6,
                   "root": "free"},
        "cast": {"prompt": "A person sips from a mug, then gestures while talking.", "seconds": 2.0,
                 "root": "free"},
        "victory": {"prompt": "A person laughs and pats someone on the shoulder.", "seconds": 4.0, "loop": True,
                    "root": "inplace"},
        "ultimate": {"prompt": "A person steps forward and talks with big, wild hand gestures.", "seconds": 3.0,
                     "root": "free"},
    },
}


def boss_of(model_id):
    """The boss a remix belongs to ("trucker_remix" -> "trucker"), or None."""
    b = model_id[:-len("_remix")] if model_id.endswith("_remix") else model_id
    return b if b in BOSSES else None


def boss_ids():
    return list(BOSSES) + [b + "_remix" for b in BOSSES]


def minion_ids():
    return list(MINIONS)


def folder_of(model_id):
    """Where a model's .glb goes under assets/models."""
    if boss_of(model_id):
        return "bosses"
    return "minions" if model_id in MINIONS else "heroes"


def spec(model_id):
    """The look spec for a hero, form, boss or minion id."""
    if model_id in HEROES or model_id in FORMS:
        return HEROES.get(model_id) or FORMS[model_id]
    if model_id in MINIONS:
        return MINIONS[model_id]
    return BOSSES[boss_of(model_id)]


def motion_owner(model_id):
    """Whose motions a model uses: forms share their hero's, remixes their boss's."""
    if model_id in FORMS:
        return FORMS[model_id]["base"]
    return boss_of(model_id) or model_id


def motions(hero_id):
    """Every animation for a hero, boss or minion: anim -> spec, with defaults filled in."""
    out = {}
    for anim in ANIMS:
        m = (HERO_MOTIONS.get(hero_id, {}).get(anim) or BOSS_MOTIONS.get(hero_id, {}).get(anim)
             or MINION_MOTIONS.get(hero_id, {}).get(anim) or SHARED_MOTIONS.get(anim))
        if m is None:
            continue
        m = dict(m)
        m.setdefault("loop", False)
        m.setdefault("cycle", False)
        m.setdefault("root", "inplace" if m["loop"] else "free")
        m.setdefault("seed", 100 + ANIMS.index(anim))
        out[anim] = m
    return out


def all_ids():
    return list(HEROES) + list(FORMS)


if __name__ == "__main__":  # heroes.ps1 prompts: every hero's concept prompts, ready to paste
    import sys
    ids = sys.argv[1].split(",") if len(sys.argv) > 1 else all_ids()
    for mid in ids:
        s = spec(mid)
        photo = FORMS[mid]["base"] if mid in FORMS else mid
        print("=" * 78)
        print("%s  (photo: %s.jpg)" % (s["name"], photo))
        print("-" * 78)
        print(concept_prompt(mid))
        for view, text in EXTRA_VIEWS.items():
            print("\n[then, for the %s view] %s" % (view, text))
        print()
