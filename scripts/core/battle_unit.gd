class_name BattleUnit
extends RefCounted
## One hero or enemy in a fight.

var uid := 0
var side := "hero" ## "hero" or "enemy"
var key := "" ## hero id or enemy id
var name := ""
var model := "" ## model/skin key for the renderer
var base_model := ""
var alt_model := "" ## transformed form (Cole's UW form, buff James)
var slot := 0
var row := "front"
var boss := false

var max_hp := 1
var hp := 1
var atk := 1.0
var def := 0.0
var crit := 0.05
var dodge := 0.0
var dmg_bonus := 0.0 ## all damage (New PC)
var ability_bonus := 0.0 ## ability damage only (Sam's weapons)
var parry := 0.0
var shield := 0
var alive := true

## Each status: {kind, dur, power, src}
var statuses: Array = []
var cd := {}
var ranks := {}
var weapon := ""

var dmg_taken := 0
var aura := 0.0 ## stacking damage bonus (Cam's Aura Farming, Sarah's Dance Rehearsal)
var prep := {} ## Cole's "next attack" effects
var passive_used := false
var revive_next := false
var stuns_taken := 0 ## boss stun diminishing returns

## Bosses
var remix := false ## the returning, remixed version of a boss
var inert := false ## takes no turns (the Boombox)
var owner_uid := -1 ## summons die with their owner
var stacks := 0 ## boss-specific counter (Aura, Boomboxes broken, ...)
var timer := 0 ## boss-specific countdown (music off, ...)

## Sam's mana and Sarah's energy (0 max = the hero doesn't use it).
var mp := 0.0
var max_mp := 0.0
var mp_regen := 0.0
var energy := 0.0
var max_energy := 0.0


func is_hero() -> bool:
	return side == "hero"
