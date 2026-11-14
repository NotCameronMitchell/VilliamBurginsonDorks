"""
The trailer's timeline, shared by music.py (soundtrack) and trailer.py (Blender): shots,
narration lines, on-screen text and the music's big hits, all in seconds.

An epic-fantasy-cinematic homage, played for laughs: a frozen office at night, the Ghost of
James Civelli on a throne of office chairs, and the dorks clocking in to fight him.
All lines are original.
"""

FPS = 24
LENGTH = 64.0

# (name, start, end): trailer.py builds a camera move for each.
SHOTS = [
    ("office", 0.0, 7.0),        # dolly down the frozen aisle, snow drifting in
    ("throne", 7.0, 11.8),       # slow push toward the throne of office chairs
    ("ghost_face", 11.8, 17.3),  # close on the ghost; his eyes flare
    ("ghost_rise", 17.3, 21.0),  # low angle: he stands and raises the sword
    ("elevator", 21.0, 24.4),    # elevator doors open on six silhouettes
    ("mason", 24.4, 26.4),
    ("james", 26.4, 28.4),
    ("cole", 28.4, 30.4),
    ("cam", 30.4, 32.4),
    ("sam", 32.4, 34.4),
    ("sarah", 34.4, 36.4),
    ("march", 36.4, 41.0),       # all six walk out of the fog toward the camera
    ("ghost_attack", 41.0, 44.0),  # ice blast
    ("montage", 44.0, 50.0),     # quick cuts (MONTAGE)
    ("clash", 50.0, 53.0),       # everyone charges; white flash
    ("title", 53.0, 60.0),
    ("end", 60.0, LENGTH),
]

# Quick cuts inside the montage: (who, animation, camera side, seconds of the move to skip
# so its big moment lands inside the 0.75 s cut). Each is a move that reads in a glance.
MONTAGE = [
    ("mason", "attack", 1, 0.35),    # the kick
    ("ghost", "hit", -1, 0.1),
    ("james", "ultimate", 1, 0.2),   # chest pound
    ("cam", "attack", -1, 0.3),      # magic blast
    ("ghost", "attack", 1, 0.25),    # the lunge
    ("cole", "cast", -1, 0.3),       # arguing, pointing
    ("sam", "attack", 1, 0.45),      # the overhead slam
    ("sarah", "attack", -1, 0.3),    # spin and strike
]

# Real gameplay, recorded from the game itself with Godot's Movie Maker (make_trailer.ps1
# -Step gameplay). Each entry covers one montage cut (0.75 s) with the recording from that
# frame on: (montage cut index, first frame of the recording). Every other cut is gameplay,
# so the trailer shows the actual game between the cinematic shots.
GAMEPLAY_CUTS = [(1, 10), (3, 96), (5, 240), (7, 192)]  # boss banner, Transfer to UW, Nissan Titan, hits

HEROES = ["mason", "james", "cole", "cam", "sam", "sarah"]
# Each hero's solo shot: the move that sells their tagline (Mason shows off his ring).
HERO_SHOT_ANIM = {"mason": "ultimate", "james": "ultimate", "cole": "ultimate", "cam": "attack",
                  "sam": "cast", "sarah": "attack"}
HERO_TAGLINE = {  # roles from scripts/data/hero_data.gd
    "mason": "Beastmaster. Wife, btw.",
    "james": "Berserker. Peptides.",
    "cole": "Melee DPS. From Texas.",
    "cam": "Caster. Mind Goblin.",
    "sam": "Wizard. Tiny glass cannon.",
    "sarah": "Rogue. Pure damage.",
}

# Narration: (file id, start, text). Spoken by Kokoro (voice.py; phrasing and pauses there),
# or Windows' built-in voice as a fallback (make_trailer.ps1), deepened a little by music.py.
NARRATION = [
    ("n1", 1.0, "Every office has its ghosts."),
    ("n2", 7.4, "Some of them never clock out."),
    ("n3", 11.9, "He gave this company everything. Even his lunch break."),
    ("n4", 17.6, "Now he wants yours."),
    ("n5", 21.5, "Clock in, dorks."),
    ("n6", 36.8, "Your shift starts now."),
]

# On-screen text: (start, end, text, style). Styles: "sub" (subtitle), "name", "tag",
# "title", "small".
TEXT = [
    (18.4, 21.0, "THE GHOST OF JAMES CIVELLI", "title2"),
    (53.6, 60.0, "VILLIAM BURGINSON DORKS", "title"),
    (56.4, 60.0, "Clock in. Fight back.", "tag"),
    (60.6, 63.6, "Coming to phone and PC", "small"),
]

# Music: where the big hits land.
HITS_BIG = [17.3, 24.4, 36.4, 41.0, 52.4, 53.0]
HITS = [7.0, 11.8, 18.4, 26.4, 28.4, 30.4, 32.4, 34.4, 42.4] + [44.0 + 0.75 * i for i in range(8)] + [56.4, 60.0]
SILENCE = [(21.0, 21.5), (52.6, 53.0)]  # drops before a big moment
ACTION = (24.4, 52.6)  # driving drums and strings
BPM = 120


def shot_at(t):
    for name, a, b in SHOTS:
        if a <= t < b:
            return name, a, b
    return SHOTS[-1]
