"""
Every character's look, as data for chibi.build(). Edit colors and accessories here,
then re-run make_models.py.

Spec keys (all optional):
  scale        overall size (heroes ~1.0, bosses 1.2-1.5)
  head, leg, arm, torso_h, width, depth   proportions (1.0 = default)
  belly        0-1, a round belly
  arm_thick    thicker arms (buff James)
  body         person | can | disc | tin | boombox
  skin, top, bottom, legs, shoes, sleeves, hands, dress, eyes, eye_glow
  shorts       khaki-shorts look (bare shins)
  long_sleeves False for short sleeves / bare arms
  hair         short | long | bob | buzz | slick | ponytail | receding | none
  hair_color, mustache, mustache_color, beard
  ghost        translucent glowing material
  acc          accessories: names, or (name, args...) tuples (see chibi.ACCESSORIES)

Colors for the original four come from the original game's sprite palettes.
"""

import copy

SKIN = "#f2c09a"

# Models you've made by hand in Blender: the generator skips these ids so it never
# overwrites your .glb. Example: HAND_MADE = {"cole", "cole_uw"}
HAND_MADE = set()

# --------------------------------------------------------------------- heroes
HEROES = {
    "mason": {  # Away kit, white pants, smartwatch
        "skin": SKIN, "hair": "short", "hair_color": "#8a5530",
        "top": "#f6f6f0", "bottom": "#efe4cc", "shoes": "#ffffff",
        "acc": ["watch", ("stripes", "#ff3b4a", "#14b05a")],
    },
    "james": {  # Brown matching set and the mustache
        "skin": SKIN, "hair": "short", "hair_color": "#141110", "mustache": True,
        "top": "#6a2e26", "bottom": "#552520", "shoes": "#ffffff", "width": 1.12,
        "acc": [("number", "#ffd23f")],
    },
    "cole": {  # Patterned button-up and khaki shorts (hair comes back in his UW form)
        "skin": "#e8b08a", "hair": "receding", "hair_color": "#5a3418",
        "top": "#1f3fa0", "bottom": "#c4ad80", "shoes": "#e8e4dc", "shorts": True,
        "acc": [("pattern", "#f0f4ff")],
    },
    "cam": {  # Mind Goblin cap, shades, Cyberpunk tee
        "skin": SKIN, "hair": "short", "hair_color": "#d8a85a",
        "top": "#363c4c", "bottom": "#bfa676", "shoes": "#4a3a30",
        "acc": [("cap", "#1c1c26", "#0c0c12", "#ffffff"), "shades", ("number", "#ffe600")],
    },
    "sam": {  # Extremely short, long dark hair, flowing black dress
        "skin": "#e8b48e", "hair": "long", "hair_color": "#24170f", "scale": 0.8, "head": 1.05,
        "top": "#141018", "bottom": "#141018", "dress": "#141018", "shoes": "#141018", "legs": "#e8b48e",
        "blush": True, "acc": [],
    },
    "sarah": {  # Black hair, glasses, sweater, black leggings
        "skin": "#f0c4a0", "hair": "bob", "hair_color": "#141110", "scale": 0.92,
        "top": "#c76b8f", "bottom": "#1a1a1f", "shoes": "#2b2b33",
        "blush": True, "acc": ["glasses"],
    },
}

# Transformed forms: Cole's Transfer to UW (hair's back), buff James (JimmyTrains).
FORMS = {
    "cole_uw": ("cole", {"hair": "short", "top": "#7a3ad8", "bottom": "#4b2a8a", "shorts": False,
                         "acc": [("number", "#ffd23f")]}),
    "james_buff": ("james", {"arm_thick": 1.6, "width": 1.35, "depth": 1.2, "long_sleeves": False}),
}

# Hero skins (outfit ids from scripts/data/outfits.gd). Each entry changes the base
# hero's spec: plain keys replace, "acc" replaces the accessory list, "acc+" adds to it.
SKINS = {
    "mason_home": ("mason", {"top": "#d01c2c", "bottom": "#ffffff", "acc+": []}),
    "james_gym": ("james", {"top": "#555555", "long_sleeves": False, "acc": ["belt"]}),
    "cole_polo": ("cole", {"top": "#2e86c1", "acc": []}),
    "cam_hoodie": ("cam", {"top": "#34495e", "acc": [("cap", "#1c1c26", "#0c0c12", "#ffffff"), "shades", "hood"]}),
    "sam_witch": ("sam", {"acc+": ["witch_hat"]}),
    "sarah_colorguard": ("sarah", {"top": "#8e44ad", "bottom": "#8e44ad", "acc+": [("jacket_stripes", "#f1c40f"), "shako"]}),
    "mason_suit": ("mason", {"top": "#3a3a48", "bottom": "#3a3a48", "shoes": "#141010", "acc": ["watch", ("tie", "#ff3b4a")]}),
    "james_suit": ("james", {"top": "#1e1e26", "bottom": "#1e1e26", "shoes": "#141010", "acc": [("tie", "#ffd23f")]}),
    "cole_suit": ("cole", {"top": "#24305a", "bottom": "#24305a", "shoes": "#141010", "shorts": False, "acc": [("tie", "#ff9a1f")]}),
    "cam_suit": ("cam", {"top": "#4a4a58", "bottom": "#4a4a58", "shoes": "#141010",
                         "acc": [("cap", "#1c1c26", "#0c0c12", "#ffffff"), "shades", ("tie", "#4fc3ff")]}),
    "mason_united": ("mason", {"top": "#da291c", "bottom": "#ffffff", "acc": ["watch", ("stripes", "#ffe500", "#ffe500")]}),
    "cole_olemiss": ("cole", {"top": "#14213d", "bottom": "#1c2c52", "shorts": False, "acc": [("number", "#ce1126")]}),
    "james_newjob": ("james", {"top": "#9ad0ff", "bottom": "#d6bf8e", "shoes": "#4a3020", "acc": [("tie", "#ff3b4a", "#ffffff"), "lanyard"]}),
    "cam_kith": ("cam", {"top": "#e8e0cc", "bottom": "#2a2a2e", "shoes": "#ffffff",
                         "acc": [("cap", "#1c1c26", "#0c0c12", "#ffffff"), "shades", ("number", "#1f5a3a")]}),
    "cole_trucker": ("cole", {"acc+": [("trucker_hat", "#a04000", "#ffffff")]}),
    "cam_stirrer": ("cam", {"acc+": [("stirrer", 1)]}),
    "mason_hoodie": ("mason", {"top": "#1b1b2f", "acc": ["watch", ("hood", "#1b1b2f")]}),
    "james_ghost": ("james", {"ghost": True, "top": "#a0c8ff", "bottom": "#7fa8e0", "skin": "#cfe3ff", "hair_color": "#7fa8e0", "shoes": "#cfe3ff"}),
    "sam_throne": ("sam", {"acc+": ["throne"]}),
    "sam_trucksmarter": ("sam", {"acc+": ["hivis", ("badge", "#95a5a6")]}),
    "sarah_subaru": ("sarah", {"top": "#2e5cb8", "acc+": [("jacket_stripes", "#ffd23f")]}),
    "sarah_ohio": ("sarah", {"top": "#bb0000", "acc+": [("number", "#ffffff")]}),
}

# Party-wide skins: generated for every hero as "<hero>_<suffix>".
PARTY_SKINS = {
    "headphones": {"acc+": ["headphones"]},
    "burger": {"top": "#e74c3c", "bottom": "#2c3e50", "acc+": [("paper_hat", "#ffffff", "#e74c3c"), "apron"]},
    "golden": {"top": "#d4af37", "bottom": "#d4af37", "shoes": "#b8860b", "dress_gold": True},
    "casual": {"top": "#2e7d6b", "bottom": "#3b5998"},
    "holiday": {"top": "#1e8449", "acc+": ["lights"]},
}

# --------------------------------------------------------------------- bosses
BOSSES = {
    "trucker": {"scale": 1.45, "skin": "#e0a37e", "belly": 0.9, "width": 1.25, "hair": "short", "hair_color": "#4a3020",
                "beard": "#4a3020", "top": "#b03a2e", "bottom": "#34495e", "shoes": "#3e2723",
                "acc": [("trucker_hat", "#2c3e50", "#ecf0f1"), ("pattern", "#7b241c")]},
    "sales_guy": {"scale": 1.35, "skin": "#f0c09a", "hair": "slick", "hair_color": "#1a1a1a", "leg": 1.15, "width": 0.95,
                  "top": "#2c3e50", "bottom": "#2c3e50", "shoes": "#111111",
                  "acc": [("tie", "#8e44ad"), ("stirrer", 1)]},
    "copilot": {"scale": 1.45, "skin": "#1c1c2c", "hair": "none", "eyes": "#7fd4ff", "eye_glow": 4.0, "mouth": False,
                "top": "#1b1b2f", "bottom": "#1b1b2f", "dress": "#1b1b2f", "shoes": "#111122", "hands": "#d5d8dc",
                "acc": [("hood", "#141428"), "scythe", ("laptop", 1)]},
    "guardian": {"scale": 1.3, "skin": "#f2c09a", "hair": "long", "hair_color": "#7b4a2a", "blush": True,
                 "top": "#e056a0", "bottom": "#3b5998", "shoes": "#ffffff",
                 "acc": [("headphones", "#2d2d2d", "#ffd23f")]},
    "ghost": {"scale": 1.3, "ghost": True, "skin": "#cfe3ff", "hair": "short", "hair_color": "#7fa8e0", "mustache": True,
              "top": "#a0c8ff", "bottom": "#7fa8e0", "shoes": "#cfe3ff", "width": 1.12},
    "cashier": {"scale": 1.15, "skin": "#c68c66", "hair": "ponytail", "hair_color": "#2b1d14",
                "top": "#e74c3c", "bottom": "#2c3e50", "shoes": "#111111",
                "acc": [("visor", "#ffcc33"), ("badge", "#ffffff")]},
    "grill_master": {"scale": 1.2, "skin": "#b07850", "hair": "buzz", "hair_color": "#1a1a1a", "belly": 0.5, "mustache": True,
                     "top": "#ecf0f1", "bottom": "#2c3e50", "shoes": "#111111",
                     "acc": [("chef_hat",), ("apron", "#dfe6e9"), "spatula"]},
    "sauce_keeper": {"scale": 1.2, "skin": "#d39a72", "hair": "short", "hair_color": "#2b1d14",
                     "top": "#e67e22", "bottom": "#2c3e50", "shoes": "#111111",
                     "acc": [("apron", "#ffffff"), "bottle"]},
    "boombox": {"body": "boombox", "scale": 1.0},
}

# Remixes (cycle 2+): changes on top of the boss.
REMIXES = {
    "trucker": {"acc+": ["hivis", "shades"]},
    "sales_guy": {"top": "#7f8c8d", "acc": [("stirrer", 1), ("stirrer", -1), ("tie", "#2c3e50")]},
    "copilot": {"top": "#d4af37", "dress": "#d4af37", "acc": [("hood", "#b8860b"), "scythe", ("laptop", 1), ("laptop", -1)]},
    "guardian": {"top": "#1e8449", "acc+": ["santa_hat", "lights"]},
    "ghost": {"bottom": "#8e9fd6", "acc+": [("visor", "#cfe3ff"), "golf_bag"], "bag": "#a0c8ff"},
    "cashier": {"acc": [("paper_hat", "#ffffff", "#e74c3c"), ("badge", "#ffffff")]},
    "grill_master": {"acc": [("paper_hat", "#ffffff", "#e74c3c"), ("apron", "#dfe6e9"), "spatula"]},
    "sauce_keeper": {"acc+": [("paper_hat", "#ffffff", "#e74c3c")]},
}

# --------------------------------------------------------------------- minions
MINIONS = {
    "energy_drink": {"body": "can", "top": "#3ad1ff", "label": "#ffffff", "scale": 0.85},
    "tallboy": {"body": "can", "top": "#c03ad1", "label": "#ffd23f", "tall": 1.45, "scale": 0.9},
    "nic_pouch": {"body": "disc", "top": "#eef0f6", "scale": 0.9},
    "pouch_tin": {"body": "tin", "top": "#6fb3e0", "lid": "#d0e6f5", "scale": 1.0},
    "reply_all": {"skin": "#f2c09a", "hair": "short", "hair_color": "#6b4f2a", "top": "#9aa4c8", "bottom": "#4a4a58",
                  "shoes": "#222222", "acc": ["glasses", ("laptop", 1, "#555555", "#ffffff")]},
    "fish_guy": {"skin": "#e0a37e", "hair": "buzz", "hair_color": "#3c2418", "top": "#8fd18f", "bottom": "#5d6d7e",
                 "shoes": "#222222", "belly": 0.4, "acc": ["fish"]},
    "loud_typer": {"skin": "#f2c09a", "hair": "short", "hair_color": "#c0392b", "top": "#c8a46e", "bottom": "#34495e",
                   "shoes": "#222222", "acc": [("headphones", "#222222", "#555555"), "keyboard"]},
    "close_talker": {"skin": "#d39a72", "hair": "slick", "hair_color": "#2b1d14", "top": "#7f8fa6", "bottom": "#4a4a58",
                     "shoes": "#222222", "acc": ["mug", ("tie", "#c0392b")]},
}


# --------------------------------------------------------------------- helpers
def apply(base, mods):
    """A copy of base with mods applied ("acc+" appends accessories)."""
    s = copy.deepcopy(base)
    for k, v in mods.items():
        if k == "acc+":
            s["acc"] = list(s.get("acc", [])) + list(v)
        elif k == "dress_gold":
            if "dress" in s:
                s["dress"] = "#d4af37"
        else:
            s[k] = copy.deepcopy(v)
    return s


def all_models():
    """[(folder, model id, spec, in_lineup)] for everything the game can load."""
    out = []
    for hid, spec in HEROES.items():
        out.append(("heroes", hid, spec, True))
    for mid, (hid, mods) in FORMS.items():
        out.append(("heroes", mid, apply(HEROES[hid], mods), False))
    for sid, (hid, mods) in SKINS.items():
        out.append(("heroes", sid, apply(HEROES[hid], mods), False))
    for suffix, mods in PARTY_SKINS.items():
        for hid, spec in HEROES.items():
            out.append(("heroes", "%s_%s" % (hid, suffix), apply(spec, mods), False))
    for bid, spec in BOSSES.items():
        out.append(("bosses", bid, spec, True))
    for bid, mods in REMIXES.items():
        out.append(("bosses", bid + "_remix", apply(BOSSES[bid], mods), False))
    for mid, spec in MINIONS.items():
        out.append(("minions", mid, spec, True))
    return [m for m in out if m[1] not in HAND_MADE]
