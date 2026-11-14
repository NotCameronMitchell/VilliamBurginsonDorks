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

**Route (one cycle):** like the original, a cycle is minion â†’ boss three times, then
the burger joint. Each cycle, **3 of the 5 office bosses are drawn at random**. Their
areas open on the office map, and the other two areas have an "Out of Office" sign on
the door. The bosses' areas are the Parking Lot, Desk Pods, Meeting Room, Middle of
the Office and James's Old Desk. After the third boss, the elevator goes down to
**Villiam Burginson's**.

**Returning bosses.** A boss you've beaten can come back in a later cycle, with a
slightly different look and one new trick (see "Remixes" under each boss). The first
time you meet a boss, it's always the original version. After that, each time it's
drawn there's a 50% chance it's the remix.

**Battle stage.** The camera swoops in. Heroes stand on round platforms in the
bottom left, enemies in the top right. Attack animations play on the 3D models,
the camera punches in on crits, and ultimates get a full-screen cut-in banner
(TRANSFER TO UW, NISSAN TITAN, ...).

**Battle HUD:**
- A name plate for each unit with an HP bar that drains smoothly (green â†’ yellow â†’ red),
  a level/rank pip, and status icons.
- A text box at the bottom: *"The Angry Trucker used SEND MY MONEY NOW!"*, typed out
  one letter at a time and skipped with a click or tap.
- A 2Ã—2 move menu (the hero's four abilities) plus Attack, Ultimate and Bag (items).
  Each move shows its cooldown and a color-coded type tag (Damage / Buff / Debuff / Heal).
- Hold or right-click a move for its full tooltip.

**Menus.** A party screen (each hero's stats, weapon and skin), a Bag, the
Achievements list and Settings. Rounded panels, chunky outlines and bright colors:
a modern take on the Pokemon menu style.

## 3b. New heroes

The roster is now 6 heroes, and you pick 4 per run. All 6 are playable from the start.
Stats are on the same scale as the originals:

| Hero | HP | ATK | DEF | Crit | Dodge |
|---|---|---|---|---|---|
| James | 150 | 12 | 12% | 5% | 0% |
| Cole | 110 | 14 | 3% | 12% | 10% |
| Mason | 95 | 11 | 0% | 8% | 5% |
| Cam | 90 | 11 | 0% | 6% | 5% |

**Both new heroes use a resource instead of (most) cooldowns.** It shows as a second
bar under their HP: blue for Sam's MP, yellow for Sarah's Energy. In the tables below,
"r" is the ability's rank (1-5).

### Sam (Wizard, back row)

*Extremely short Italian woman with long dark hair and a flowing black dress.*
*"4'8 is not that short." / "I hate Mason."*

| HP | ATK | DEF | Crit | Dodge |
|---|---|---|---|---|
| 75 | 13 | 0% | 8% | 5% |

She's the glass cannon: the lowest HP in the game, tied with Sarah and Cole for the most damage.

**Mana instead of cooldowns.** Sam has 100 max MP. She starts each fight with 40 and
regenerates MP every turn (how much depends on her weapon). Her abilities have **no
cooldowns**, so she can cast the same one every turn as long as she has the MP.
Ranking an ability up raises its power and lowers its cost by 2 per rank.

| Ability | MP | Effect |
|---|---|---|
| **Ignore Emails** | 35 | A shield worth 25% of her max HP (it lasts until it breaks), and she reflects 20% of the damage aimed at her for 2 turns. *+5% shield and +5% reflect per rank.* |
| **Rage Bait** | 30 | A fireball at one enemy: 220% ATK, and the target is Weakened 20% for a turn. **If Mason is in the party: +25% crit chance**, and sometimes she says "I hate Mason." *+15% damage per rank.* |
| **Energy Drinks Are Bad For You** | 25 | Scolds every enemy: 45% ATK to all, and they're **Exposed** (can't dodge) for 2 turns. Deals +50% damage to Energy Drink and Tallboy minions. *+10% damage per rank. At r3+, Exposed enemies also take 10% more damage.* |
| **Refrigerated Burger Bomb** | 45 | Takes a bite of a cold burger (poisons herself for 4% max HP a turn, 2 turns), then throws it: 80% ATK to all enemies, plus Poison at 30% ATK a turn for 3 turns. *+15% damage per rank. At r5 the burger's fine, so no self-poison.* |
| **Passive, Desk Treadmill** | - | Heals 5% max HP every turn. Healing past full HP turns into a shield, up to 10% max HP. *+1% healing per rank.* |
| **Ultimate, Unexpected Out of Pocket Message** | - | Says something so heinous it deals 240% ATK to every enemy and stuns them for 2 turns. Uses the normal ultimate timer (ready on turn 4, then every 5). *+20% damage per rank.* Boss stun diminishing returns still apply. |

**Weapons:**

| Weapon | Cost | Basic attack | Bonus |
|---|---|---|---|
| **Booster Seat** (default) | - | 120% ATK, one enemy | +15 MP per turn. She needs it because she's short. |
| **TruckSmarter LOR** | 20 PTO | 100% ATK | +20 MP per turn, abilities deal +15%. She escaped TruckSmarter, but kept the power. |
| **Lampedusa Flag** | 28 PTO | 90% ATK | +22 MP per turn, abilities deal +30%, and every ability has a 30% chance to Burn (30% ATK a turn). The flag of home. |

**Why it balances:**
- About 15 MP a turn means a big spell roughly every other turn. Basic attacks with
  the Booster Seat fill the gaps.
- Spamming Rage Bait (about 29 damage) is strong but drains her MP in 2-3 turns.

**Simulator check (all 15 possible parties, 60 fights each):** in late minion fights Sam
does about 30% of her party's damage and Sarah about 31%. In boss-length fights Sarah
does about 39% (the boss killer), Cole 32%, Sam 25%. The original four stayed where
they were. The numbers above are the tuned ones, and `tests/run_tests.gd` re-runs this
report.
- Her shield, the treadmill and reflect keep her alive despite 75 HP. If she's focused
  while out of MP, she goes down fast.

### Sarah (Rogue, front row)

*Short (not as short as Sam), dark hair, glasses, sweater and black leggings.*
*"Clock it." / "Stop stealing my leads."*

| HP | ATK | DEF | Crit | Dodge |
|---|---|---|---|---|
| 100 | 12 | 0% | 15% | 12% |

Pure damage: no defense, no crowd control. She stacks Bleeds, then detonates them.

**Energy.** Sarah has 100 max Energy and starts each fight at 0. Builders make Energy
and have short cooldowns. Dab spends it, and her ultimate scales with it.
**Detonating** a Bleed deals all of its remaining damage instantly (times a multiplier)
and removes it.

| Ability | CD | Energy | Effect |
|---|---|---|---|
| **The Worm** | 2 | +8 per hit | Flops on the ground throwing 4 knives at random enemies: 30% ATK each, and each hit Bleeds (20% ATK a turn, 3 turns). *+1 knife at r3 and r5.* |
| **Scuba** | 2 | +10 per hit | Slashes one enemy 3 times for 40% ATK each. Every hit adds a Bleed stack (15% ATK a turn). *+1 slash at r3 and r5.* |
| **Dab** | - | costs 50 | Hits a mean dab: **detonates every Bleed on every enemy** at 125%. *+25% per rank. At r4 it costs 40.* |
| **Catching the Fish** | 3 | +20 | Reels in the **highest-HP enemy** automatically, then stabs it: 150% ATK and Bleed (30% ATK a turn). *+15% damage per rank.* |
| **Passive, Dance Rehearsal** | - | - | Rehearses during enemy turns: +3% damage every round, up to +30%. *+1% per round per rank.* |
| **Ultimate, Subaru Drive-by** | - | spends all | Drives by every enemy: 100% ATK and a Bleed, then detonates every Bleed at 50% **+0.5% for each point of Energy spent** (so at 100 Energy, 100%). *+20% detonate per rank.* |

**Weapons:**

| Weapon | Cost | Basic attack | Bonus |
|---|---|---|---|
| **Colorguard Gun** (default) | - | 130% ATK blunt, one enemy | 25% chance to detonate the target's Bleeds at 75%. It's a prop, not a real gun. |
| **Tambourine** | 20 PTO | No damage | The whole party deals +15% damage for a turn, and Sarah gets +15 Energy. |
| **The Great State of Ohio** | 24 PTO | 40% ATK to all enemies | 60% chance each for Bleed and Poison (25% ATK a turn) on every enemy. |

**Why it balances:**
- She does nothing but damage, so she's the best boss killer, but she has no way to
  protect herself. She needs James's taunts or Cam's stuns to stay alive.
- Her damage builds up: weak on turns 1-2, a monster by turn 6 (Rehearsal + Dab +
  a full-Energy Subaru). Short minion fights favor the other heroes, and long boss fights
  favor her.
- To keep Dab from one-shotting a boss, detonation damage is capped at 35% of a boss's
  max HP per detonation.

### New skins and achievements

| Hero | Free skins | Unlock skin | Achievement |
|---|---|---|---|
| Sam | Classic (black dress), Witch Hat | Booster Seat Throne | **I Hate Mason:** crit Rage Bait on 3 enemies in one fight with Mason in the party. |
| Sam | | TruckSmarter Escapee (hi-vis, broken badge) | **4'8 Is Not That Short:** win a boss fight without Sam taking damage. |
| Sarah | Classic (sweater, glasses), Colorguard Uniform | Subaru Racing Jacket | **Clock It:** detonate 150+ damage with one Dab. |
| Sarah | | Ohio Hoodie | **Stop Stealing My Leads:** land the killing blow on 3 bosses (all-time). |

New combat features the engine port needs to support:
- MP and Energy resources
- the Exposed status (can't dodge)
- Bleed detonation
- "highest-HP enemy" auto-targeting
- weapons that change MP regen or ability damage

## 4. The bosses

Stats are on the original's scale: original bosses had 240-310 HP and 11-13 ATK,
and normal bosses still scale up each cycle. Each boss lists:

- its **gimmick** (the joke, turned into a mechanic)
- its **counterplay** (so the gimmick is beatable and not just annoying)
- its **lines** (shown before and after the fight, and as combat quips)

### 4.1 The Angry Trucker (Parking Lot)

*A semi idling across four parking spaces. He's here about an invoice.*

- **HP** 280 Â· **ATK** 13 Â· **DEF** 10%
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
- **Remix, Night Shift Trucker:** hi-vis vest, sunglasses at night, the truck's
  headlights on. **High Beams:** his ultimate also blinds a second hero (-30% accuracy
  for 2 turns).

### 4.2 The Mystery Sales Guy (Desk Pods)

*Nobody knows his name, what he sells, or why there's a coffee stirrer over his ear.*

- **HP** 260 Â· **ATK** 12 Â· **Dodge** 20%
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
- **Remix, Q4 Sales Guy:** a stirrer over **both** ears, plus a quarter-zip. He starts
  the fight with 2 Aura stacks.

### 4.3 The Copilot Grim Reaper (Meeting Room)

*A hooded figure with a glowing laptop and a scythe. He just wants to save you some time.*

- **HP** 270 Â· **ATK** 12
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
- **Remix, Copilot Pro Reaper:** a gold robe and a second laptop. Sometimes the pop-up
  gets a third button, **"Upgrade to Pro"**, which acts like "Yes, install" but lasts
  4 turns.

### 4.4 The Guardian of Tunes (Middle of the Office)

*She controls the office speaker. She has one playlist. It is on repeat.*

- **HP** 290 Â· **ATK** 12
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
- **Remix, Holiday Playlist Guardian:** a Santa hat and a light-up sweater, and the
  Boombox is a jingling speaker. Earworm maxes out at 7 instead of 5.

### 4.5 The Ghost of James Civelli (James's Old Desk)

*James left for a new job, but his old desk was never cleaned out. The James who
used to work here is still logged in.*

- **HP** 230 Â· **ATK** 12
- **Lore:** this is party James's own old-job self, wearing the brown matching set and
  the mustache in see-through ghost blue. The intro plays it straight:
  - **Ghost:** "Back from emails going through lunch."
  - **James:** "...is that me?"
- **Possession (gimmick, fight start):** the ghost reaches into James and takes back
  "his" spot. Party James is instantly KO'd for the whole fight. Nothing can revive him until the fight ends; afterwards
  he comes back at 50% HP. This doesn't count as a death for achievements or run stats.
  To make up for fighting three against one, the ghost has the lowest HP of any boss.
- **Mirror moves:** he fights with ghost versions of James's own kit. Daily Dollar
  becomes Haunted Blackjack (he gambles with *your* HP), and Peptide Rage becomes
  Spectral Rage.
- **If there's no James in the party** (once the roster grows past 4): the ghost is bored. +20% HP and ATK, and each
  turn he haunts the hardest hitter (Weaken 15%).
- **My New Irons Are So Sick:** a full golf swing, 170% ATK to one hero, and it can't
  be dodged.
- **Back From Emails Going Through Lunch (ultimate, every 5 turns):** he goes Away
  for a turn (can't be targeted), then comes back healed 15%.
- **Ghostly Reply-All:** 50% ATK to the whole party, and Poisons.
- **Defeated:** "Tell everyone I said what's up. I'm going to go hit balls." James
  wakes up: "Bih Ahh Boi."
- **Remix, Golf Trip Ghost:** a visor, plaid pants and a ghostly golf bag. My New
  Irons hits twice.

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
- **Remix, Late Night Crew (cycle 2+):** paper hats, the lights dimmed, and a "closing
  soon" sign up. The Cashier's Silence also hits the hero next to the target.

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
| 3 | **Transfer to UW:** triple damage becomes double, and the full max HP shield becomes 50%. Still heals to full. | Heal + 100% shield + 3Ã— damage is the strongest button in the game. |
| 4 | **Daily Dollar:** scales off ATK instead of James's max HP, and goes to cooldown 3. | 20% of 150 HP is about 2.5Ã— his ATK as unavoidable flat damage on a 2-turn cooldown. |
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
- **Sam:** Classic (black dress), Witch Hat
- **Sarah:** Classic (sweater, glasses), Colorguard Uniform

**Unlockable:** see section 6. A few extras are sold for Village Sauce on the Suit Up
screen.

**In 3D:** each skin is a separate material set (texture swap), or a separate mesh
for big changes like a suit, built on the same rig, so every skin works with every
animation. See [ART_PIPELINE.md](ART_PIPELINE.md).

## 8. Platforms: phone and PC

- **Builds:** Windows (desktop) and Android, plus a web build so it can still be
  played from a link like the original. iOS later: that needs a Mac to build.
- **Renderer:** Godot's **Mobile** renderer on every platform, so phone and PC look
  the same and there are no PC-only effects to cut later.
- **Layout:** landscape only. Every menu works with touch, mouse, keyboard and
  controller:
  - Buttons are at least 48 px tall.
  - The move menu sits in the bottom-right, within thumb reach.
  - Tooltips open on a long-press on phones, and on hover or right-click on PC.
- **Overworld controls:** a virtual joystick on phones, WASD or arrow keys on PC, and
  tap-to-move on both.
- **Performance budget:** 60 fps on a mid-range phone. That means the poly budgets in
  [ART_PIPELINE.md](ART_PIPELINE.md), one shared palette material, baked lighting in
  arenas, and only the sun casting real-time shadows.
- **Saves:** a local save file on each device (no cross-device sync for now).

## 9. Decisions log

- **Bosses:** drawn at random each cycle (3 of the 5 office bosses), with the burger
  crew always last. Bosses you've beaten come back in later cycles as remixes with a
  new look and one new trick.
- **The Ghost of James Civelli** is party James's own old-job self.
- **Platforms:** phone and PC.
- **The original's bosses** (Middle Manager, Corporate Mascot, Legacy Code, HR Rep,
  Logistics Director) do **not** return. The combat engine and the four heroes carry
  over, and **two new heroes** join the roster, so you pick 4 of 6.
