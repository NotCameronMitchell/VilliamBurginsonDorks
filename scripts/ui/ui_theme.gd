class_name UITheme
extends RefCounted
## The game's look: rounded panels, chunky dark outlines, bright colors. A modern
## take on Pokemon menus. Everything is built in code so it's easy to tweak here.

const INK := Color("#1a1a2e")
const PANEL := Color("#fdfbf3")
const PANEL_ALT := Color("#e9f3ff")
const DARK := Color("#2b2d42")
const ACCENT := Color("#ffd23f")
const HP_GREEN := Color("#3ddc84")
const HP_YELLOW := Color("#ffc93c")
const HP_RED := Color("#ff4d4d")
const SHIELD := Color("#bfe6ff")
const MP := Color("#6c8cff")
const ENERGY := Color("#ffb627")
const DAMAGE := Color("#ff7a59")
const SUPPORT := Color("#4fc3a1")
const ULT := Color("#ffd23f")
const MUTED := Color("#8a8fa8")

const FONT_SIZE := 20


static func box(bg: Color, border := INK, radius := 14, border_w := 4, pad := 10) -> StyleBoxFlat:
	var s := StyleBoxFlat.new()
	s.bg_color = bg
	s.border_color = border
	s.set_border_width_all(border_w)
	s.set_corner_radius_all(radius)
	s.set_content_margin_all(pad)
	s.shadow_color = Color(0, 0, 0, 0.25)
	s.shadow_size = 4
	s.shadow_offset = Vector2(0, 3)
	return s


static func make() -> Theme:
	var t := Theme.new()
	t.default_font_size = FONT_SIZE
	t.set_color("font_color", "Label", INK)
	t.set_stylebox("panel", "PanelContainer", box(PANEL))
	t.set_stylebox("panel", "Panel", box(PANEL))
	# Buttons: big, rounded, readable with a thumb.
	t.set_stylebox("normal", "Button", box(Color.WHITE, INK, 12, 3, 8))
	t.set_stylebox("hover", "Button", box(Color("#fff6d6"), INK, 12, 3, 8))
	t.set_stylebox("pressed", "Button", box(ACCENT, INK, 12, 3, 8))
	t.set_stylebox("focus", "Button", box(Color(0, 0, 0, 0), ACCENT, 12, 3, 8))
	t.set_stylebox("disabled", "Button", box(Color("#e4e4ea"), MUTED, 12, 3, 8))
	t.set_color("font_color", "Button", INK)
	t.set_color("font_hover_color", "Button", INK)
	t.set_color("font_pressed_color", "Button", INK)
	t.set_color("font_focus_color", "Button", INK)
	t.set_color("font_disabled_color", "Button", MUTED)
	t.set_font_size("font_size", "Button", 19)
	t.set_constant("h_separation", "Button", 6)
	t.set_color("default_color", "RichTextLabel", INK)
	t.set_font_size("normal_font_size", "RichTextLabel", 22)
	t.set_font_size("bold_font_size", "RichTextLabel", 22)
	return t


## A button tinted with a color (move type), keeping the outline.
static func tint_button(b: Button, c: Color, pad := 6) -> void:
	b.add_theme_stylebox_override("normal", box(c.lerp(Color.WHITE, 0.55), INK, 12, 3, pad))
	b.add_theme_stylebox_override("hover", box(c.lerp(Color.WHITE, 0.35), INK, 12, 3, pad))
	b.add_theme_stylebox_override("pressed", box(c, INK, 12, 3, pad))
	b.add_theme_stylebox_override("disabled", box(Color("#e4e4ea"), MUTED, 12, 3, pad))


static func label(text: String, size := FONT_SIZE, color := INK, outline := 0) -> Label:
	var l := Label.new()
	l.text = text
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", color)
	if outline > 0:
		l.add_theme_color_override("font_outline_color", INK)
		l.add_theme_constant_override("outline_size", outline)
	return l


static func hp_color(frac: float) -> Color:
	if frac > 0.5:
		return HP_GREEN
	if frac > 0.2:
		return HP_YELLOW
	return HP_RED
