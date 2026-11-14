# Villiam Burginson Dorks: Game Design

The 3D sequel to [The Quest for Villiam Burginson](https://github.com/NotCameronMitchell/FirstProj).
Same crew, same mission (get the Village Sauce), same turn-based party combat.
New bosses, 3D models made in Blender, a Pokemon-style look, polished UI,
achievements and skins from day one, and rebalanced abilities.

Engine: **Godot 4**. Art: **Blender**, exported as glTF (`.glb`).

---

## 1. What carries over from the original

- **The party:** Mason (Beastmaster), James (Berserker), Cole (Melee DPS) and Cam
  (Caster / Support). Same abilities, ultimates, passives and weapons, with the
  balance changes in section 5.
- **Combat:** fully manual and turn-based. Every hero acts once per round, in any
  order, then the enemies act. Abilities have cooldowns, ultimates are ready on turn 4,
  and quick buffs don't use up the turn.
- **Run loop:** upgrade picks after every win, the Break Room Shop (PTO Hours), random
  events between fights, and Village Sauce for permanent upgrades.

## 2. What's new

| Area | Original | Sequel |
|---|---|---|
| Visuals | 8-bit sprites drawn in code | Low-poly 3D models from Blender, Pokemon-style camera and battle stage |
| World | Fight after fight on menus | A walkable 3D office overworld that leads to each boss arena |
| Bosses | Middle Manager, Mascot, Legacy Code, HR Rep, Logistics Director | Six new bosses (section 4) |
| UI | DOM screens | Pokemon-style battle HUD, text boxes, move menu, party screen |
| Skins | 4 classics, 8 unlockable | 2 free skins per hero from the start, plus unlockables |
| Balance | Long boss fights, outlier abilities | Tuned against the simulator (section 5) |

## 3. Look and feel ("like a Pokemon game")

**Overworld.** A third-person, slightly top-down camera follows the party leader
around the office (the other three follow in a line, Pokemon follower style).
Coworkers stand at their desks; walk into their line of sight and you get a **"!"**
and a minion fight. Each boss stands at the end of their area, and you have to talk
to them to start the fight.

**Route (one cycle):**
Parking Lot → Desk Pods → Meeting Room → Middle of the Office → James's Old Desk →
elevator down to **Villiam Burginson's**.

**Battle stage.** The camera swoops in. Heroes stand on round platforms in the
bottom left, enemies in the top right. Attack animations play on the 3D models,
the camera punches in on crits, and ultimates get a full-screen cut-in banner
(TRANSFER TO UW, NISSAN TITAN, ...).

**Battle HUD:**
- A name plate for each unit with an HP bar that drains smoothly (green → yellow → red),
  a level/rank pip, and status icons.
- A text box at the bottom: *"The Angry Trucker used SEND MY MONEY NOW!"*, typed out
  one letter at a time and skipped with a click or tap.
- A 2×2 move menu (the hero's four abilities) plus Attack, Ultimate and Bag (items).
  Each move shows its cooldown and a color-coded type tag (Damage / Buff / Debuff / Heal).
- Hold or right-click a move for its full tooltip.

**Menus.** A party screen (each hero's stats, weapon and skin), a Bag, the
Achievements list and Settings. Rounded panels, chunky outlines and bright colors:
a modern take on the Pokemon menu style.

## 4. The bosses

Stats are on the original's scale: original bosses had 240-310 HP and 11-13 ATK,
and normal bosses still scale up each cycle. Each boss lists:

- its **gimmick** (the joke, turned into a mechanic)
- its **counterplay** (so the gimmick is beatable and not just annoying)
- its **lines** (shown before and after the fight, and as combat quips)

### 4.1 The Angry Trucker (Parking Lot)

*A semi idling across four parking spaces. He's here about an invoice.*

- **HP** 280 · **ATK** 13 · **DEF** 10%
- **Grudge (passive):** he has it out for Cole. Half of his single-target attacks go
  at Cole, and each hit on Cole has a 35% chance to stun him for a turn.
- **SEND MY MONEY NOW (ultimate, every 5 turns):** honks the air horn at Cole:
  160% ATK and a 2-turn stun. If Cole isn't in the party, it targets the hardest hitter.
- **Air Horn:** 70% ATK to the whole party.
- **Jake Brake:** 120% ATK to one hero and pushes their ultimate back a turn.
- **Counterplay, Road Rage:** Cole can't be stunned two turns in a row, and every time
  he shakes off a stun he gets +10% damage for the rest of the fight (stacks). The more
  the Trucker picks on him, the harder Cole hits back.
- **Lines:** "SEND MY MONEY NOW." His other speech bubbles are bleeped rants
  ("#@$%&!!"). Defeated: "...I'll have my dispatcher call your dispatcher."
- **Arena:** the parking lot, with the truck parked behind him.

### 4.2 The Mystery Sales Guy (Desk Pods)

*Nobody knows his name, what he sells, or why there's a coffee stirrer over his ear.*

- **HP** 260 · **ATK** 12 · **Dodge** 20%
- **Aura (passive):** he gains 1 Aura stack every turn (max 5). Each stack gives the
  whole party *Mogged*: -6% damage per stack. He never speaks: every speech bubble is
  just "*aura*" with a sparkle.
- **Jawline Reveal (ultimate, every 5 turns):** he slowly turns to the side. Each hero
  has a 35% chance to lose their turn staring, and the rest are Weakened 20% for 2 turns.
- **Silent Stare:** 120% ATK to one hero. Gains +1 Aura if it crits.
- **Stirrer Flick:** 60% ATK to two random heroes.
- **Counterplay:**
  - Every crit a hero lands knocks off 1 Aura stack.
  - Cam's Aura Farming makes him **immune to Mogged**, and every turn Cam takes
    he steals 1 Aura stack ("Cam out-aura'd him"). This is a fight where Cam shines.
- **Defeated:** "*aura*" (it's fading).

### 4.3 The Copilot Grim Reaper (Meeting Room)

*A hooded figure with a glowing laptop and a scythe. He just wants to save you some time.*

- **HP** 270 · **ATK** 12
- **Cowork Skills Pop-Up (gimmick, every 3 turns):** the game stops and a pop-up
  appears: *"Have you downloaded my Cowork skills yet?"* with a countdown bar
  (2.5 seconds at first, shrinking to 1.5 seconds) and two buttons:
  - **"Not now"**: you dodged it. No damage.
  - **"Yes, install"**: no damage, but the party gets *Productivity Suite*: -15% damage
    for 2 turns, because you're now in 4 onboarding videos.
  - **Too slow:** he takes it personally. 150% ATK to the whole party, and one random
    hero is Silenced for a turn ("Auto-installed.").
  - The buttons swap sides at random, so you have to actually read them.
- **Mandatory Rollout (ultimate, every 6 turns):** two pop-ups back to back.
- **Scythe of Suggestions:** 60% ATK to the whole party.
- **Lines:** "This is for your own good." / "We can save so much time if you just do
  this." Defeated: "Fine. I'll just add it to your startup apps."
- **Accessibility:** a Settings option makes the timer longer or turns it off, so the
  fight still works on a phone or for slower players.

### 4.4 The Guardian of Tunes (Middle of the Office)

*She controls the office speaker. She has one playlist. It is on repeat.*

- **HP** 290 · **ATK** 12
- **On Repeat (passive):** every turn she plays a song, and the party gets 1
  *Earworm* stack: -8% damage reduction per stack (so they take more damage), max 5.
- **The Boombox:** a separate enemy on her platform (60 HP). Breaking it stops the
  music for 2 turns and clears every Earworm stack. Then she plugs in a new one, which
  has 20% more HP each time.
- **Maroon 5 Deep Cut:** 60% ATK to the whole party, +1 Earworm.
- **Baby (10th Play Today) (ultimate, every 5 turns):** +2 Earworm on everyone and
  Confuses two heroes.
- **Lines:** "Maroon 5 makes really good songs." / "Don't you just love Justin Bieber
  for the 10th time today?" Defeated: "...okay, you can pick the next song."

### 4.5 The Ghost of James Civelli (James's Old Desk)

*The desk was never cleaned out. Something's still logged in.*

- **HP** 230 · **ATK** 12
- **Possession (gimmick, fight start):** the ghost instantly KOs the James in your
  party for the whole fight. Nothing can revive him until the fight ends; afterwards
  he comes back at 50% HP. This doesn't count as a death for achievements or run stats.
  To make up for fighting three against one, the ghost has the lowest HP of any boss.
- **If there's no James in the party:** the ghost is bored. +20% HP and ATK, and each
  turn he haunts the hardest hitter (Weaken 15%).
- **My New Irons Are So Sick:** a full golf swing, 170% ATK to one hero, and it can't
  be dodged.
- **Back From Emails Going Through Lunch (ultimate, every 5 turns):** he goes Away
  for a turn (can't be targeted), then comes back healed 15%.
- **Ghostly Reply-All:** 50% ATK to the whole party, and Poisons.
- **Defeated:** "Tell everyone I said what's up. I'm going to go hit balls."

### 4.6 The Villiam Burginson Crew (Final boss at Villiam Burginson's)

*They will do anything to protect the sauce.*

A three-person boss fight, and the finale of every cycle. It replaces the original's
crew / cook / coworker fight.

| Member | HP | ATK | Role |
|---|---|---|---|
| The Cashier | 160 | 11 | **"That's not on the menu":** Silences the last hero who used an ability, for 2 turns. |
| The Grill Master | 180 | 13 | **Flat-Top Flare:** single-target Burn, and an AoE grease splash every 3 turns. |
| The Sauce Keeper | 200 | 10 | Holds the sauce. Heals and shields the other two. |

- **"Yeah I'll bring you the sauce..." (Sauce Keeper ultimate):** the party gets
  *Waiting on Sauce*. If the Sauce Keeper doesn't take damage within 2 turns, it turns
  into *Sauce Never Came* (-25% damage for 3 turns). If you hit him first, the party
  gets +15% damage instead.
- **Protect the Sauce (passive):** when one member falls, the others get +25% ATK. The
  last one standing gets a 20% max HP shield.
- **Defeated:** "...fine. One sauce. ONE."

> **Naming note:** this design calls them "The Villiam Burginson Crew", so the
> jokes come from the burger job and the sauce gatekeeping. Tell me if you want a
> different name.

## 5. Balance changes

**Where these come from:**
- Running the original's balance simulator (`tests/balance.test.ts`, 4 sauce levels).
- Reading the ability code.

The simulator says:

- **Boss fights drag:** 13.5 rounds on average, against 4.9 for minions.
- **The third boss of each cycle is a wall.** At 0 sauce upgrades, 14 out of ~60
  simulated deaths came at the cycle 1 third boss (1-6B), and 19 at the cycle 2 third
  boss (2-6B). Stage-to-stage scaling spikes there.
- **Sauce upgrades snowball:** at max meta, burger 1 is a 100% win and burger 2 is 97%.
  At 0 meta, burger 2 is 18%.

**Proposed changes:**

| # | Change | Why |
|---|---|---|
| 1 | Boss HP -15%, or hero damage +10% in cycle 1. Target about 9 rounds per boss. | Boss fights are too long. |
| 2 | Smooth `scaling()` so the third boss isn't a spike. | The 6B death clusters. |
| 3 | **Transfer to UW:** triple damage becomes double, and the full max HP shield becomes 50%. Still heals to full. | Heal + 100% shield + 3× damage is the strongest button in the game. |
| 4 | **Daily Dollar:** scales off ATK instead of James's max HP, and goes to cooldown 3. | 20% of 150 HP is about 2.5× his ATK as unavoidable flat damage on a 2-turn cooldown. |
| 5 | **Stuns on bosses:** each stun after the first in a fight lasts 1 turn less (minimum 1), and Resolve lasts 2 turns. | Iceland Story + Nissan Titan + Mind Goblin can stun-lock a boss. |
| 6 | **We Go Next:** trigger threshold rises from 15% to 25% HP. | It almost never fires, so Mason's passive does nothing. |
| 7 | **Secret Sauce / Seasoned Veterans:** +5%/+6% per level becomes +3%/+4%, max level stays 10. | Max meta trivializes the game. |
| 8 | **New early-game catch-up:** if the party wipes before burger 1, they get +5 Village Sauce. | Soften the 0-meta start. |

Every change gets re-checked with the simulator once combat is ported.

**Win-rate targets (0 meta / max meta):**
- Reach burger 1: 60% / 100%
- Beat burger 2: 15% / 70%

## 6. Achievements

Achievements unlock skins (section 7). The originals carry over, and new ones are
added for the new bosses.

| Achievement | How | Unlocks |
|---|---|---|
| First Day on the Job | Win your first fight. | - |
| Promoted | Beat a boss. | Suit & Tie (Mason) |
| Performance Review | Beat 5 bosses (all-time). | Suit & Tie (James) |
| Lunch Break | Reach Villiam Burginson's. | Suit & Tie (Cole) |
| Secret Sauce | Beat the Villiam Burginson Crew. | Suit & Tie (Cam) |
| Glory Glory | Win a fight where We Go Next goes off. | Manchester United Mason |
| Hotty Toddy | Win after 9 Iron on Ciabatta revives Cole. | Ole Miss Cole |
| New Job, Who Dis? | Hit blackjack on Daily Dollar and win. | New Job James |
| Drip Check | Hit 3+ enemies with one Nissan Titan. | Kith Cam |
| **Paid in Full** | Beat the Angry Trucker without Cole getting stunned. | Trucker Hat Cole |
| **Out-Aura'd** | Beat the Mystery Sales Guy while Cam holds all 5 Aura stacks. | Coffee Stirrer Cam |
| **Not Now** | Dismiss every Cowork pop-up in a Grim Reaper fight. | Hoodie Mason |
| **Skip Track** | Break 3 Boomboxes in one fight. | Headphones (all) |
| **Who You Gonna Call** | Beat the Ghost of James Civelli. | Ghost James |
| **Extra Sauce** | Beat the Crew without anyone being Silenced. | Burger Uniform (all) |
| Ten Toes Down | Win 25 fights (all-time). | - |
| Overtime | Reach cycle 3 in one run. | Golden Suit (all) |

## 7. Skins

**Free from the start (2 per hero):**

- **Mason:** Classic (away kit), Home Kit (red)
- **James:** Classic (brown matching set), Gym Fit (tank top, lifting belt)
- **Cole:** Classic (patterned button-up), Golf Polo
- **Cam:** Classic (Mind Goblin cap), Gamer Hoodie

**Unlockable:** see section 6. A few extras are sold for Village Sauce on the Suit Up
screen.

**In 3D:** each skin is a separate material set (texture swap), or a separate mesh
for big changes like a suit, built on the same rig, so every skin works with every
animation. See [ART_PIPELINE.md](ART_PIPELINE.md).

## 8. Open questions

- Should the bosses come in a **fixed order** (like gym leaders, following the route
  in section 3), or be **drawn at random** each cycle like the original?
- Are the old bosses (Middle Manager, HR Rep, ...) gone for good, or do they come back
  as harder minibosses in cycle 2+?
- Is the Ghost of James Civelli the same James who's in the party (the ghost of his
  old job), or a different James?
- Platforms: PC only, or PC + phone? The original was a phone-friendly web game. Godot
  can export to the web and Android, but 3D on phones needs a lower-poly budget.
