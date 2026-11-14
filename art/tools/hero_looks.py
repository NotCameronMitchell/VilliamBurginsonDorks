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


def look(model_id):
    """The full look for a hero or form id."""
    if model_id in LOOKS:
        return dict(LOOKS[model_id])
    base, over = FORM_LOOKS[model_id]
    out = dict(LOOKS[base])
    out.update(over)
    return out
