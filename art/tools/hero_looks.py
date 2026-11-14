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
                "trim": ["#d7263d", "#159947"], "number": None},
        "bottom": {"type": "pants", "color": "#e8dcc2"},
        "shoes": {"type": "sneakers", "color": "#ffffff", "sole": "#d9d9d9"},
        "acc": ["watch"],
    },
    "james": {
        "sex": "m", "heads": 6.0, "build": 1.14,
        "skin": "#dfa983", "eyes": "#5a3d2b",
        "hair": {"style": "wavy", "color": "#5b3a22"},
        "face": {"brows": "#4a2e1a", "mouth": "grin", "beard": "short", "beard_color": "#4f321d"},
        "top": {"type": "sweatshirt", "color": "#7a4a30", "sleeves": "long",
                "number": "4", "number_color": "#ffd23f"},
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
        "hair": {"style": "longwavy", "color": "#3a261b"},
        "face": {"brows": "#3a261b", "mouth": "smile", "beard": "none", "blush": True},
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
                "trim": ["#e8c547", "#e8c547"], "number": "1", "number_color": "#e8c547"},
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
                                       "trim": ["#ffffff", "#ffffff"], "number": "7", "number_color": "#ffffff"},
                               "bottom": {"type": "shorts", "color": "#f6f6f6"}}),
    "cole_olemiss": ("cole", {"top": {"type": "jersey", "color": "#14213d", "sleeves": "short",
                                      "trim": ["#ce1126", "#ffffff"], "number": "1", "number_color": "#ffffff"},
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


def base_of(model_id):
    """The hero or form whose body (and motions) a model uses."""
    if model_id in SKINS:
        return SKINS[model_id][0]
    return model_id


def look(model_id):
    """The full look for a hero, form or skin id."""
    if model_id in LOOKS:
        return dict(LOOKS[model_id])
    if model_id in SKINS:
        base, over = SKINS[model_id]
    else:
        base, over = FORM_LOOKS[model_id]
    out = look(base) if base in FORM_LOOKS else dict(LOOKS[base])
    out.update(over)
    return out
