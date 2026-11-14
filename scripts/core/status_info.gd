class_name StatusInfo
extends RefCounted
## Every status effect: its label, HUD tag, color, and whether it's a buff.

const DOTS := ["poison", "bleed", "burn"]
## Statuses whose power adds up when reapplied (others keep the max).
const STACKING := ["poison", "bleed", "burn", "regen", "empower", "weaken", "guard", "dodge", "crit", "earworm"]

const INFO := {
	"poison": {"label": "Poison", "short": "PSN", "color": "#7cff4f", "good": false, "desc": "Takes damage at the start of each turn. Stacks."},
	"bleed": {"label": "Bleed", "short": "BLD", "color": "#ff4f6d", "good": false, "desc": "Takes damage at the start of each turn. Stacks. Can be detonated."},
	"burn": {"label": "Burn", "short": "BRN", "color": "#ff9a1f", "good": false, "desc": "Takes damage at the start of each turn. Stacks."},
	"regen": {"label": "Regen", "short": "RGN", "color": "#5effc8", "good": true, "desc": "Heals at the start of each turn."},
	"empower": {"label": "Damage Up", "short": "DMG+", "color": "#ffd23f", "good": true, "desc": "Deals more damage."},
	"weaken": {"label": "Damage Down", "short": "DMG-", "color": "#c08aff", "good": false, "desc": "Deals less damage."},
	"guard": {"label": "Guard", "short": "GRD", "color": "#6fd3ff", "good": true, "desc": "Takes less damage."},
	"dodge": {"label": "Dodge Up", "short": "DDG", "color": "#a0f0ff", "good": true, "desc": "More likely to dodge attacks."},
	"crit": {"label": "Crit Up", "short": "CRT", "color": "#ffe37a", "good": true, "desc": "More likely to land critical hits."},
	"protect": {"label": "Immune", "short": "IMM", "color": "#ffffff", "good": true, "desc": "Takes no damage."},
	"reflect": {"label": "Reflect", "short": "RFL", "color": "#ff7ae0", "good": true, "desc": "Sends part of the damage it takes (or blocks) back at the attacker."},
	"stun": {"label": "Stunned", "short": "STUN", "color": "#fff04f", "good": false, "desc": "Skips its turn."},
	"confuse": {"label": "Confused", "short": "CONF", "color": "#ff7ae0", "good": false, "desc": "May attack itself or its allies instead."},
	"silence": {"label": "Silenced", "short": "SIL", "color": "#9aa0b8", "good": false, "desc": "Can only use basic attacks."},
	"taunt": {"label": "Taunted", "short": "TNT", "color": "#ff5a3a", "good": false, "desc": "Must attack the hero who taunted it."},
	"away": {"label": "Away", "short": "AWAY", "color": "#9aa0b8", "good": false, "desc": "Pulled out of the fight. Can't act or be targeted."},
	"exposed": {"label": "Exposed", "short": "EXP", "color": "#ffb347", "good": false, "desc": "Can't dodge. May take extra damage."},
	"earworm": {"label": "Earworm", "short": "EAR", "color": "#ff7ae0", "good": false, "desc": "The song is stuck in their head: takes more damage. Stacks."},
	"blind": {"label": "Blinded", "short": "BLND", "color": "#fff7a0", "good": false, "desc": "High beams: attacks may miss."},
	"waiting_sauce": {"label": "Waiting on Sauce", "short": "WAIT", "color": "#ffd23f", "good": false, "desc": "Hit the Sauce Keeper before it runs out, or the sauce never comes."},
	"possessed": {"label": "Possessed", "short": "GHST", "color": "#a0c8ff", "good": false, "desc": "Out for the rest of this fight. Back afterwards at 50% HP."},
	"resolve": {"label": "Resolve", "short": "RES", "color": "#ffffff", "good": true, "hidden": true, "desc": "Just shook off a stun; can't be stunned right now."},
}
