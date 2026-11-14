# Style guide

The look, feel and sound every new piece should match. When adding a skin, boss, arena,
effect or sound, check it against this page (and a screenshot of the game) first.

## Characters

- **Who:** realistic people, in the spirit of Pokemon Scarlet/Violet: real proportions,
  clean readable shapes, soft materials. No outlines and no chibi heads.
- **Faces and bodies:** MakeHuman, tuned to each person (heroes) or made up (bosses).
- **Clothes:** generated from the body, in solid, saturated colors. One bold idea per
  outfit (a print, a pattern, a trim), not three. No real brand logos or numbers.
- **Silhouette first:** every character should be recognizable as a small shadow, so give
  each one a signature shape, such as a cap, headphones, a suit or a ghostly glow.

## Motion

- Motion-captured feel (Kimodo), never stiff. Each hero's idle, attack and ultimate says
  who they are; shared moves (walk, hit, faint) are the same for everyone.
- Prompts are plain physical descriptions ("A man swings a golf club hard with both hands").
  A one-shot move should end facing forward, so it blends back into the idle.

## Arenas and lighting

- **Light:** a warm or cool sun with soft shadows, plus a cool rim light from behind the
  stage, so characters stand out from the background.
- **Sky:** a gradient sky (horizon and overhead colors), seen through windows indoors.
- **Grade:** a touch more contrast (1.06) and color (1.12) than neutral, with filmic tone
  mapping and gentle glow on bright things.
- **Palette:** one dominant color per arena (blue office, orange parking lot, purple
  middle of the office, red and yellow burger joint), with the battle platforms in it.
- **Fill the space:** no empty floors or bare walls behind the fight.

## Combat feel

- Every hit lands: a white flash, sparks, a short hit-stop and a sound with low end.
  Crits are bigger and gold, with a camera shake.
- Enemies glint (a star and a "ting") just before they strike, so the player can read them.
- Damage numbers pop in, rise and fade; they never cover a speech bubble.

## UI

- Rounded panels with thick dark outlines (`scripts/ui/ui_theme.gd`): cream panels, dark
  ink text, gold accents, green and red for health.
- Big, tappable buttons; everything works with a mouse, a finger or a gamepad.

## Sound

- Original chiptune music (`art/audio/make_audio.py`), one track per place, looping
  seamlessly. Comedy first: the game-over jingle is a sad trombone.
- Sound effects are short and punchy, and quieter than the hits for UI clicks and blips.

## Trailer

- An epic-fantasy homage played for laughs: cinematic shots of the game's own models, cut
  with real gameplay recorded from the game.
- Every hero gets a solo shot that sells their tagline, and walks and runs match how far
  the characters actually travel (no sliding feet).
