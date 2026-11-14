class_name Rng
extends RefCounted
## Small seeded PRNG (mulberry32) so fights and tests are reproducible.
## Ported from the original game's src/rng.ts.

const MASK := 0xFFFFFFFF

var state: int


func _init(seed: int = 0) -> void:
	state = seed & MASK


## 32-bit multiply that never overflows a 64-bit int.
static func _imul(a: int, b: int) -> int:
	a &= MASK
	b &= MASK
	var lo := (a & 0xFFFF) * b
	var hi := (((a >> 16) * b) & 0xFFFF) << 16
	return (lo + hi) & MASK


func next() -> float:
	state = (state + 0x6D2B79F5) & MASK
	var t := state
	t = _imul(t ^ (t >> 15), t | 1)
	t = (t ^ ((t + _imul(t ^ (t >> 7), t | 61)) & MASK)) & MASK
	return float((t ^ (t >> 14)) & MASK) / 4294967296.0


func int_range(lo: int, hi: int) -> int:
	return lo + int(floor(next() * (hi - lo + 1)))


func chance(p: float) -> bool:
	return next() < p


func pick(arr: Array) -> Variant:
	return arr[int(floor(next() * arr.size()))]


## Picks an item with probability proportional to weight.call(item).
func weighted(items: Array, weight: Callable) -> Variant:
	var total := 0.0
	for i in items:
		total += weight.call(i)
	var r := next() * total
	for i in items:
		r -= weight.call(i)
		if r <= 0.0:
			return i
	return items[-1]


## Shuffles in place and returns the array.
func shuffle(arr: Array) -> Array:
	for i in range(arr.size() - 1, 0, -1):
		var j := int(floor(next() * (i + 1)))
		var tmp = arr[i]
		arr[i] = arr[j]
		arr[j] = tmp
	return arr
