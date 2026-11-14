"""
How each detailed hero looks, as data: garments.py generates the outfit from it on the hero's
MakeHuman body (hero_mh.py has the body, face and hair). Skin tone and facial hair follow
each person's photo; outfits follow the original game. A new skin is a new look dict.
(Some keys, like "heads", "build" and hair "style", only matter to the older procedural
builder, hero_builder.py.)

Keys:
  sex          "m" or "f" (body shape)
  heads        how many head-heights tall (Pokemon trainers are about 6; fewer = cuter)
  build        overall bulk (1 = average); "muscle" adds shoulders and arms
  skin, eyes   colors
  hair         {"style": quiff | wavy | short | receding | full | capped | long | longwavy, "color"}
  face         {"brows", "mouth": smile | grin | smirk, "beard": none | stubble | short, "blush"}
  top          {"type": jersey | tee | buttonup | sweatshirt | sweater | tank | dress, "color",
                "sleeves": short | long | none, plus trim/pattern/print/number}
  bottom       {"type": pants | shorts | joggers | leggings | skirt, "color"}
  shoes        {"type": sneakers | flats | leather, "color", "sole"}
  acc          extras: watch, cap, sunglasses, glasses
Forms start from their hero ("base") and override keys.
"""

LOOKS = {
    "mason": {
        "sex": "m", "heads": 6.2, "build": 1.0,
        "skin": "#f2c6a4", "eyes": "#6b8299",
        "hair": {"style": "quiff", "color": "#8a5a33"},
        "face": {"brows": "#6b4426", "mouth": "grin", "beard": "none"},
        "top": {"type": "jersey", "color": "#f6f6f2", "sleeves": "short",
                "trim": ["#d7263d", "#159947"]},
        "bottom": {"type": "pants", "color": "#e8dcc2"},
        "shoes": {"type": "sneakers", "color": "#ffffff", "sole": "#d9d9d9"},
        "acc": ["watch"],
    },
    "james": {
        "sex": "m", "heads": 6.0, "build": 1.14,
        "skin": "#dfa983", "eyes": "#5a3d2b",
        "hair": {"style": "wavy", "color": "#141110"},
        "face": {"brows": "#1b1715", "mouth": "grin", "beard": "short", "beard_color": "#1d1917"},
        "top": {"type": "sweatshirt", "color": "#7a4a30", "sleeves": "long"},
        "bottom": {"type": "joggers", "color": "#6d412a"},
        "shoes": {"type": "sneakers", "color": "#ffffff", "sole": "#dcdcdc"},
        "acc": [],
    },
    "cole": {
        "sex": "m", "heads": 6.3, "build": 0.98,
        "skin": "#f0c3a0", "eyes": "#5d4a3a",
        "hair": {"style": "receding", "color": "#6e4a2c"},
        "face": {"brows": "#5a3a22", "mouth": "smile", "beard": "none"},
        "top": {"type": "buttonup", "color": "#1f2f5c", "sleeves": "short",
                "pattern": "dots", "pattern_color": "#e8ecf8"},
        "bottom": {"type": "shorts", "color": "#c4ab7c"},
        "shoes": {"type": "sneakers", "color": "#ece6da", "sole": "#cfc8b8"},
        "acc": [],
    },
    "cam": {
        "sex": "m", "heads": 6.0, "build": 1.03,
        "skin": "#f3c8a6", "eyes": "#5b4636",
        "hair": {"style": "capped", "color": "#3b2a1e"},
        "face": {"brows": "#3b2a1e", "mouth": "grin", "beard": "stubble", "beard_color": "#5a4232"},
        "top": {"type": "tee", "color": "#33363e", "sleeves": "short",
                "print": "cyber", "print_color": "#f2ff2e"},
        "bottom": {"type": "pants", "color": "#bfa676"},
        "shoes": {"type": "leather", "color": "#5a3b26", "sole": "#2e211a"},
        "acc": ["cap", "sunglasses"],
    },
    "sam": {
        "sex": "f", "heads": 5.4, "build": 0.9,
        "skin": "#ddab86", "eyes": "#4a3020",
        "hair": {"style": "long", "color": "#2a1a12"},
        "face": {"brows": "#2a1a12", "mouth": "smirk", "beard": "none", "blush": True},
        "top": {"type": "dress", "color": "#16141a", "sleeves": "short"},
        "bottom": {"type": "skirt", "color": "#16141a"},
        "shoes": {"type": "boots", "color": "#141216", "sole": "#0c0b0e"},
        "acc": [],
    },
    "sarah": {
        "sex": "f", "heads": 5.8, "build": 0.94,
        "skin": "#f2cfb4", "eyes": "#5a4636",
        "hair": {"style": "longwavy", "color": "#141110"},
        "face": {"brows": "#1b1715", "mouth": "smile", "beard": "none", "blush": True},
        "top": {"type": "sweater", "color": "#d77c9c", "sleeves": "long"},
        "bottom": {"type": "leggings", "color": "#1a1a1f"},
        "shoes": {"type": "sneakers", "color": "#2b2b33", "sole": "#e6e6e6"},
        "acc": ["glasses"],
    },
}

FORM_LOOKS = {
    "cole_uw": ("cole", {
        "hair": {"style": "full", "color": "#6e4a2c"},
        "face": {"brows": "#5a3a22", "mouth": "grin", "beard": "none"},
        "top": {"type": "jersey", "color": "#5b2a9e", "sleeves": "short",
                "trim": ["#e8c547", "#e8c547"]},
        "bottom": {"type": "pants", "color": "#4a2380"},
        "shoes": {"type": "sneakers", "color": "#ffffff", "sole": "#dcdcdc"},
    }),
    "james_buff": ("james", {
        "build": 1.25, "muscle": True,
        "top": {"type": "tank", "color": "#7a4a30", "sleeves": "none"},
    }),
}


def _suit(jacket, tie, pants=None, shirt="#f4f4f6", shoes="#141414", mat=None):
    top = {"type": "jacket", "color": jacket, "sleeves": "long", "buttons": True}
    bottom = {"type": "pants", "color": pants or jacket}
    if mat:
        top["material"] = bottom["material"] = mat
    return {"under": {"type": "buttonup", "color": shirt, "sleeves": "long", "tie": tie},
            "top": top, "bottom": bottom, "shoes": {"type": "leather", "color": shoes, "sole": "#0c0c0c"}}


def _keep_acc(lk, drop=(), add=()):
    return [a for a in lk.get("acc", []) if a not in drop] + list(add)


# Skins (scripts/data/outfits.gd): skin id -> (hero, changes to the hero's look). Only what
# changes is listed; a new skin is a new entry here, then
# heroes.ps1 assemble --makehuman --skins <id>.
SKINS = {
    "mason_home": ("mason", {"top": {"type": "jersey", "color": "#d7263d", "sleeves": "short",
                                     "trim": ["#ffffff", "#1a1a1a"]},
                             "bottom": {"type": "pants", "color": "#f4f4f4"}}),
    "james_gym": ("james", {"top": {"type": "tank", "color": "#2d2f36", "sleeves": "none"},
                            "bottom": {"type": "shorts", "color": "#1d1e22"}, "acc": ["belt"]}),
    "cole_polo": ("cole", {"top": {"type": "polo", "color": "#2e86c1", "sleeves": "short"}}),
    "cam_hoodie": ("cam", {"top": {"type": "hoodie", "color": "#2b2d42", "sleeves": "long", "print": "cyber",
                                   "print_color": "#39ff88"}}),
    "sam_witch": ("sam", {"acc": ["witch_hat"]}),
    "sarah_colorguard": ("sarah", {"top": {"type": "jersey", "color": "#5b2a86", "sleeves": "long",
                                           "trim": ["#e8c547", "#e8c547"], "pattern": "sash",
                                           "pattern_color": "#e8c547"},
                                   "bottom": {"type": "pants", "color": "#2b1640"}}),
    "mason_suit": ("mason", _suit("#1c2541", "#8b1a1a")),
    "james_suit": ("james", _suit("#34373f", "#c9a227")),
    "cole_suit": ("cole", _suit("#14213d", "#ce1126")),
    "cam_suit": ("cam", _suit("#111216", "#2ecc71")),
    "mason_united": ("mason", {"top": {"type": "jersey", "color": "#da291c", "sleeves": "short",
                                       "trim": ["#ffffff", "#ffffff"]},
                               "bottom": {"type": "shorts", "color": "#f6f6f6"}}),
    "cole_olemiss": ("cole", {"top": {"type": "jersey", "color": "#14213d", "sleeves": "short",
                                      "trim": ["#ce1126", "#ffffff"]},
                              "bottom": {"type": "pants", "color": "#d9d9d9"}}),
    "james_newjob": ("james", {"top": {"type": "buttonup", "color": "#cfe3f5", "sleeves": "long"},
                               "bottom": {"type": "pants", "color": "#3b3f4a"}, "acc": ["lanyard"]}),
    "cam_kith": ("cam", {"top": {"type": "hoodie", "color": "#e9e4da", "sleeves": "long", "text": "DRIP",
                                 "text_color": "#ffffff", "text_box": "#c8102e"}}),
    "cole_trucker": ("cole", {"acc": ["cap"], "cap": {"color": "#c0392b", "front": "#f4f4f4"}}),
    "cam_stirrer": ("cam", {"acc": ["cap", "sunglasses", "stirrer"]}),
    "mason_hoodie": ("mason", {"top": {"type": "hoodie", "color": "#151518", "sleeves": "long"},
                               "bottom": {"type": "joggers", "color": "#1d1d21"}, "acc": []}),
    "james_ghost": ("james", {"ghost": True}),
    "sam_throne": ("sam", {"acc": ["crown", "cape"]}),
    "sam_trucksmarter": ("sam", {"under": {"type": "tee", "color": "#4a4d55", "sleeves": "short"},
                                 "top": {"type": "vest", "color": "#d6ff1f", "pattern": "reflective"},
                                 "bottom": {"type": "pants", "color": "#34495e"}, "acc": ["lanyard"],
                                 "lanyard_color": "#e67e22"}),
    "sarah_subaru": ("sarah", {"top": {"type": "quarterzip", "color": "#1f3d99", "sleeves": "long",
                                       "pattern": "stripes", "stripes": ["#f1c40f"], "zip": "full"}}),
    "sarah_ohio": ("sarah", {"top": {"type": "hoodie", "color": "#bb0000", "sleeves": "long", "text": "OHIO",
                                     "text_color": "#ffffff"}}),
}

# Party-wide skins: one per hero, made from the hero's own look.
PARTY = {
    "headphones": lambda lk: {"acc": _keep_acc(lk, add=["headphones"])},
    "burger": lambda lk: {"top": {"type": "polo", "color": "#d62828", "sleeves": "short", "trim": ["#ffd23f"]},
                          "acc": _keep_acc(lk, drop=["cap"], add=["paper_hat"])},
    "golden": lambda lk: dict(_suit("#e6c04f", "#1a1a1a", shirt="#111111", mat="gold")),
    "casual": lambda lk: {"top": {"type": "quarterzip", "color": "#2c3e50", "sleeves": "long"},
                          "bottom": {"type": "skirt" if lk["bottom"]["type"] == "skirt" else "pants",
                                     "color": "#3b5998"}},
    "holiday": lambda lk: {"top": {"type": "sweater", "color": "#b8222e", "sleeves": "long", "pattern": "holiday"}},
}
for _h in list(LOOKS):
    for _s, _f in PARTY.items():
        SKINS["%s_%s" % (_h, _s)] = (_h, _f(LOOKS[_h]))


# Bosses (hero_specs.BOSSES): outfits follow their original chibi models (characters.py).
BOSS_LOOKS = {
    "trucker": {
        "sex": "m", "skin": "#e0a37e", "eyes": "#4a3020",
        "hair": {"style": "short", "color": "#4a3020"},
        "face": {"brows": "#3a2616", "beard": "short", "beard_color": "#4a3020"},
        "top": {"type": "buttonup", "color": "#b03a2e", "sleeves": "long", "pattern": "plaid",
                "pattern_color": "#4a120c"},
        "bottom": {"type": "pants", "color": "#34495e"},
        "shoes": {"type": "boots", "color": "#3e2723", "sole": "#1e1410"},
        "acc": ["cap"], "cap": {"color": "#2c3e50", "front": "#ecf0f1"},
    },
    "sales_guy": dict(_suit("#2c3e50", "#8e44ad"), **{
        "sex": "m", "skin": "#f0c09a", "eyes": "#3a5a7a",
        "hair": {"style": "short", "color": "#151515"},
        "face": {"brows": "#151515", "beard": "none"},
        "acc": ["stirrer"],
    }),
    "guardian": {
        "sex": "f", "skin": "#f2c09a", "eyes": "#4a6a3a",
        "hair": {"style": "long", "color": "#7b4a2a"},
        "face": {"brows": "#5a3420", "beard": "none", "blush": True},
        "top": {"type": "tee", "color": "#e056a0", "sleeves": "short"},
        "bottom": {"type": "pants", "color": "#3b5998"},
        "shoes": {"type": "sneakers", "color": "#ffffff", "sole": "#e0e0e0"},
        "acc": ["headphones"],
    },
    # James's old-job self, back to haunt the office: James in his old work clothes, as a ghost.
    "ghost": dict(LOOKS["james"], **{
        "ghost": True,
        "top": {"type": "buttonup", "color": "#cfe3f5", "sleeves": "long", "tie": "#5a6a8a"},
        "bottom": {"type": "pants", "color": "#3b3f4a"},
        "shoes": {"type": "leather", "color": "#2a2a2a", "sole": "#111111"},
        "acc": ["lanyard"],
    }),
    # The AI assistant as a grim reaper: a hooded robe, a face lost in shadow, glowing eyes,
    # a scythe and a laptop.
    "copilot": {
        "sex": "m", "skin": "#15151f", "skin_tint": 0.92, "eye_glow": "#7fd4ff",
        "hair": {"style": "none", "color": "#111111"},
        "face": {"brows": "#111111", "beard": "none"},
        "top": {"type": "robe", "color": "#1b1b2f", "sleeves": "long"},
        "bottom": {"type": "robe", "color": "#1b1b2f"},
        "shoes": {"type": "leather", "color": "#111122", "sole": "#08080c"},
        "acc": ["hood", "scythe", "laptop", "cord"], "hood_color": "#141428", "cord_color": "#4a4a6a",
    },
    # The burger crew (Villiam Burginson's, the final fight).
    "cashier": {
        "sex": "f", "skin": "#c68c66", "skin_tint": 0.35,
        "hair": {"style": "long", "color": "#2b1d14"},
        "face": {"brows": "#2b1d14", "beard": "none", "blush": True},
        "top": {"type": "polo", "color": "#e74c3c", "sleeves": "short", "badge": True},
        "bottom": {"type": "pants", "color": "#2c3e50"},
        "shoes": {"type": "sneakers", "color": "#111111", "sole": "#3a3a3a"},
        "acc": ["visor"], "visor_color": "#ffcc33",
    },
    "grill_master": {
        "sex": "m", "skin": "#b07850", "skin_tint": 0.4,
        "hair": {"style": "short", "color": "#1a1a1a"},
        "face": {"brows": "#1a1a1a", "beard": "mustache", "beard_color": "#1a1a1a"},
        "top": {"type": "buttonup", "color": "#f4f4f2", "sleeves": "long"},
        "bottom": {"type": "pants", "color": "#2c3e50"},
        "shoes": {"type": "leather", "color": "#111111", "sole": "#0a0a0a"},
        "acc": ["chef_hat", "apron", "spatula"], "apron_color": "#dfe6e9",
    },
    "sauce_keeper": {
        "sex": "m", "skin": "#d39a72",
        "hair": {"style": "short", "color": "#2b1d14"},
        "face": {"brows": "#2b1d14", "beard": "stubble", "beard_color": "#2b1d14"},
        "top": {"type": "tee", "color": "#e67e22", "sleeves": "short"},
        "bottom": {"type": "pants", "color": "#2c3e50"},
        "shoes": {"type": "sneakers", "color": "#111111", "sole": "#3a3a3a"},
        "acc": ["apron", "bottle"], "apron_color": "#ffffff",
    },
}

# Minions (hero_specs.MINIONS): the office coworkers, from their chibi designs.
MINION_LOOKS = {
    "reply_all": {
        "sex": "m", "skin": "#f2c09a",
        "hair": {"style": "short", "color": "#6b4f2a"},
        "face": {"brows": "#5a3e22", "beard": "none"},
        "top": {"type": "buttonup", "color": "#9aa4c8", "sleeves": "short"},
        "bottom": {"type": "pants", "color": "#4a4a58"},
        "shoes": {"type": "leather", "color": "#222222", "sole": "#111111"},
        "acc": ["glasses", "laptop"], "glasses_color": "#2d2d2d",
    },
    "fish_guy": {
        "sex": "m", "skin": "#e0a37e",
        "hair": {"style": "short", "color": "#3c2418"},
        "face": {"brows": "#3c2418", "beard": "stubble", "beard_color": "#3c2418"},
        "top": {"type": "tee", "color": "#8fd18f", "sleeves": "short"},
        "bottom": {"type": "pants", "color": "#5d6d7e"},
        "shoes": {"type": "sneakers", "color": "#222222", "sole": "#dcdcdc"},
        "acc": ["fish"],
    },
    "loud_typer": {
        "sex": "m", "skin": "#f2c09a",
        "hair": {"style": "short", "color": "#c0392b"},
        "face": {"brows": "#a93226", "beard": "none"},
        "top": {"type": "tee", "color": "#c8a46e", "sleeves": "short"},
        "bottom": {"type": "pants", "color": "#34495e"},
        "shoes": {"type": "sneakers", "color": "#2b2b33", "sole": "#e6e6e6"},
        "acc": ["headphones", "keyboard"], "phones_color": "#555555",
    },
    "close_talker": {
        "sex": "m", "skin": "#d39a72",
        "hair": {"style": "short", "color": "#2b1d14"},
        "face": {"brows": "#2b1d14", "beard": "none"},
        "top": {"type": "buttonup", "color": "#7f8fa6", "sleeves": "long", "tie": "#c0392b"},
        "bottom": {"type": "pants", "color": "#4a4a58"},
        "shoes": {"type": "leather", "color": "#222222", "sole": "#111111"},
        "acc": ["mug"],
    },
}

# Remixes (cycle 2+): changes on top of the boss's look.
REMIX_LOOKS = {
    "trucker": {"under": BOSS_LOOKS["trucker"]["top"],
                "top": {"type": "vest", "color": "#d6ff1f", "pattern": "reflective"},
                "acc": ["cap", "sunglasses"]},
    "sales_guy": dict(_suit("#7f8c8d", "#2c3e50"), acc=["stirrer"]),
    "guardian": {"top": {"type": "sweater", "color": "#1e8449", "sleeves": "long", "pattern": "holiday"}},
    "ghost": {"acc": ["lanyard", "cap"], "cap": {"color": "#cfe3ff", "front": "#cfe3ff"}},
    "copilot": {"top": {"type": "robe", "color": "#c9a227", "sleeves": "long"},  # the premium tier, in gold
                "bottom": {"type": "robe", "color": "#c9a227"}, "hood_color": "#a8841c", "cord_color": "#5a4510",
                "acc": ["hood", "scythe", "laptop", "floating_laptop", "cord"]},  # and a second laptop
    "cashier": {"acc": ["paper_hat"]},
    "grill_master": {"acc": ["paper_hat", "apron", "spatula"]},
    "sauce_keeper": {"acc": ["paper_hat", "apron", "bottle"]},
}


def base_of(model_id):
    """The hero, form or boss whose body (and motions) a model uses."""
    if model_id in SKINS:
        return SKINS[model_id][0]
    if model_id.endswith("_remix"):
        return model_id[:-len("_remix")]
    return model_id


def look(model_id):
    """The full look for a hero, form, skin, boss or remix id."""
    if model_id in LOOKS:
        return dict(LOOKS[model_id])
    if model_id in BOSS_LOOKS:
        return dict(BOSS_LOOKS[model_id])
    if model_id in MINION_LOOKS:
        return dict(MINION_LOOKS[model_id])
    if model_id.endswith("_remix"):
        boss = model_id[:-len("_remix")]
        out = dict(BOSS_LOOKS[boss])
        out.update(REMIX_LOOKS[boss])
        return out
    if model_id in SKINS:
        base, over = SKINS[model_id]
    else:
        base, over = FORM_LOOKS[model_id]
    out = look(base) if base in FORM_LOOKS else dict(LOOKS[base])
    out.update(over)
    return out
