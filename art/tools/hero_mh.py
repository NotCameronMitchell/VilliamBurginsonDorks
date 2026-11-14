"""
Who each hero is, as MakeHuman settings (MPFB): body shape, face shape, skin, eyes, hair.
Tuned by eye against each person's photo (Pictures/Villiam Burginson Dorks/<id>.jpg).
What they wear lives in hero_looks.py (top, bottom, shoes, accessories) and is generated
by garments.py, so new skins are just new outfit entries.

phenotype: MakeHuman's macro sliders, 0..1 (gender 1 = male; age 0.5 = 25 years;
           height is a starting point, the build rescales to hero_specs heights).
targets:   MakeHuman's detail sliders by target name (see MPFB's data/targets folders),
           e.g. "head-oval", "chin-prominent-incr", "nose-scale-horiz-decr".
"""

MH = {
    "mason": {  # long face, strong chin, big grin, light eyes
        "phenotype": {"gender": 1.0, "age": 0.46, "muscle": 0.58, "weight": 0.45, "height": 0.62,
                      "proportions": 0.75},
        "targets": {"head-oval": 0.9, "head-scale-vert-incr": 0.25, "chin-height-incr": 0.5, "chin-prominent-incr": 0.35,
                    "chin-width-decr": 0.25, "nose-scale-vert-incr": 0.3, "nose-point-up": 0.2,
                    "mouth-scale-horiz-incr": 0.45, "mouth-angles-up": 0.9, "mouth-laugh-lines-in": 0.4,
                    "eyebrows-trans-up": 0.2, "l-cheek-bones-incr": 0.3, "r-cheek-bones-incr": 0.3},
        "skin": "young_caucasian_male", "eyes": "bluegreen", "eyebrows": "eyebrow001", "eyelashes": "eyelashes01",
        "hair": "short01", "hair_color": "#8a5a33",
    },
    "james": {  # broad square face, heavy build, beard (garments.py)
        "phenotype": {"gender": 1.0, "age": 0.56, "muscle": 0.65, "weight": 0.66, "height": 0.52,
                      "proportions": 0.55},
        "targets": {"head-square": 0.85, "head-fat-incr": 0.55, "head-scale-horiz-incr": 0.3, "chin-width-incr": 0.5,
                    "neck-scale-horiz-incr": 0.6, "nose-scale-horiz-incr": 0.35, "nose-volume-incr": 0.3,
                    "eyebrows-trans-down": 0.15, "mouth-angles-up": 0.45, "l-eye-scale-decr": 0.15,
                    "r-eye-scale-decr": 0.15},
        "skin": "young_caucasian_male", "eyes": "brown", "eyebrows": "eyebrow004", "eyelashes": "eyelashes01",
        "hair": "short02", "hair_color": "#4e3020",
    },
    "cole": {  # narrow face, high forehead, friendly smile
        "phenotype": {"gender": 1.0, "age": 0.5, "muscle": 0.5, "weight": 0.42, "height": 0.66,
                      "proportions": 0.65},
        "targets": {"head-oval": 0.65, "head-scale-horiz-decr": 0.25, "forehead-scale-vert-incr": 0.65,
                    "chin-prominent-incr": 0.3, "chin-width-decr": 0.2, "nose-scale-vert-incr": 0.15,
                    "mouth-scale-horiz-incr": 0.3, "mouth-angles-up": 0.75, "mouth-laugh-lines-in": 0.25,
                    "l-ear-scale-incr": 0.2, "r-ear-scale-incr": 0.2},
        "skin": "young_caucasian_male", "eyes": "brownlight", "eyebrows": "eyebrow002", "eyelashes": "eyelashes01",
        "hair": "short02", "hair_color": "#6e4a2c",
    },
    "cam": {  # round face, full cheeks, cap and shades
        "phenotype": {"gender": 1.0, "age": 0.48, "muscle": 0.45, "weight": 0.66, "height": 0.6,
                      "proportions": 0.5},
        "targets": {"head-round": 0.95, "head-fat-incr": 0.7, "l-cheek-volume-incr": 0.6, "r-cheek-volume-incr": 0.6,
                    "chin-height-decr": 0.25, "nose-volume-incr": 0.3, "nose-scale-horiz-incr": 0.2,
                    "mouth-angles-up": 0.7, "neck-double-incr": 0.3},
        "skin": "young_caucasian_male", "eyes": "brown", "eyebrows": "eyebrow003", "eyelashes": "eyelashes01",
        "hair": "short01", "hair_color": "#3b2a1e",
    },
    "sam": {
        "phenotype": {"gender": 0.0, "age": 0.48, "muscle": 0.45, "weight": 0.5, "height": 0.12,
                      "proportions": 0.6, "cupsize": 0.5, "firmness": 0.55},
        "targets": {"head-oval": 0.55, "l-eye-scale-incr": 0.35, "r-eye-scale-incr": 0.35, "eyebrows-trans-down": 0.05,
                    "nose-scale-vert-incr": 0.15, "nose-hump-incr": 0.15, "mouth-lowerlip-volume-incr": 0.3,
                    "mouth-angles-up": 0.45},
        "skin": "young_caucasian_female", "eyes": "brown", "eyebrows": "eyebrow009", "eyelashes": "eyelashes02",
        "hair": "long01", "hair_color": "#2a1a12",
    },
    "sarah": {
        "phenotype": {"gender": 0.0, "age": 0.5, "muscle": 0.45, "weight": 0.52, "height": 0.3,
                      "proportions": 0.6, "cupsize": 0.5, "firmness": 0.5},
        "targets": {"head-oval": 0.4, "head-round": 0.25, "chin-prominent-decr": 0.15, "nose-scale-horiz-decr": 0.1,
                    "mouth-scale-horiz-decr": 0.1, "mouth-angles-up": 0.2},
        "skin": "young_caucasian_female", "eyes": "brownlight", "eyebrows": "eyebrow010", "eyelashes": "eyelashes02",
        "hair": "long01", "hair_color": "#3a261b",
    },
}

FORM_MH = {
    "cole_uw": ("cole", {"hair": "short02"}),
    "james_buff": ("james", {"phenotype": {"gender": 1.0, "age": 0.56, "muscle": 1.0, "weight": 0.72,
                                           "height": 0.58, "proportions": 0.75},
                             "targets": {"head-square": 0.85, "head-fat-incr": 0.4, "neck-scale-horiz-incr": 0.9,
                                         "torso-vshape-incr": 0.9, "torso-muscle-pectoral-incr": 0.8,
                                         "measure-shoulder-dist-incr": 0.7, "mouth-angles-up": 0.3}}),
}


# Bosses: made-up people, except the ghost, who is James's old-job self (James's face, a
# heavier build). Remixes ("<boss>_remix") use their boss's body.
BOSS_MH = {
    "trucker": {  # big, bearded, scowling
        "phenotype": {"gender": 1.0, "age": 0.68, "muscle": 0.62, "weight": 0.9, "height": 0.85,
                      "proportions": 0.45},
        "targets": {"head-square": 0.7, "head-fat-incr": 0.6, "neck-scale-horiz-incr": 0.8,
                    "chin-width-incr": 0.5, "nose-volume-incr": 0.45, "nose-scale-horiz-incr": 0.3,
                    "eyebrows-trans-down": 0.5, "mouth-angles-down": 0.6, "l-eye-scale-decr": 0.2,
                    "r-eye-scale-decr": 0.2},
        "skin": "middleage_caucasian_male", "eyes": "brown", "eyebrows": "eyebrow004", "eyelashes": "eyelashes01",
        "hair": "short01", "hair_color": "#4a3020",  # short, so none of it pokes out under the cap
    },
    "sales_guy": {  # tall, slick, a salesman's grin
        "phenotype": {"gender": 1.0, "age": 0.55, "muscle": 0.5, "weight": 0.45, "height": 0.9,
                      "proportions": 0.75},
        "targets": {"head-oval": 0.5, "head-square": 0.2, "chin-prominent-incr": 0.3,
                    "mouth-scale-horiz-incr": 0.35, "mouth-angles-up": 0.9, "eyebrows-trans-up": 0.25,
                    "l-cheek-bones-incr": 0.3, "r-cheek-bones-incr": 0.3},
        "skin": "young_caucasian_male", "eyes": "blue", "eyebrows": "eyebrow002", "eyelashes": "eyelashes01",
        "hair": "short04", "hair_color": "#151515",
    },
    "guardian": {  # bright and cheerful, always has music on
        "phenotype": {"gender": 0.0, "age": 0.5, "muscle": 0.5, "weight": 0.5, "height": 0.6,
                      "proportions": 0.7, "cupsize": 0.5, "firmness": 0.55},
        "targets": {"head-oval": 0.5, "l-eye-scale-incr": 0.3, "r-eye-scale-incr": 0.3,
                    "mouth-angles-up": 0.8, "mouth-lowerlip-volume-incr": 0.3, "nose-scale-horiz-decr": 0.15},
        "skin": "young_caucasian_female", "eyes": "green", "eyebrows": "eyebrow010", "eyelashes": "eyelashes02",
        "hair": "ponytail01", "hair_color": "#7b4a2a",
    },
}
BOSS_FORM_MH = {
    "ghost": ("james", {"phenotype": {"gender": 1.0, "age": 0.62, "muscle": 0.55, "weight": 0.75,
                                      "height": 0.62, "proportions": 0.55}}),
}


def get(model_id):
    if model_id.endswith("_remix"):
        model_id = model_id[:-len("_remix")]
    if model_id in MH:
        return dict(MH[model_id])
    if model_id in BOSS_MH:
        return dict(BOSS_MH[model_id])
    if model_id in BOSS_FORM_MH:
        base, over = BOSS_FORM_MH[model_id]
        out = dict(MH[base])
        out.update(over)
        return out
    base, over = FORM_MH[model_id]
    out = dict(MH[base])
    out.update(over)
    return out
