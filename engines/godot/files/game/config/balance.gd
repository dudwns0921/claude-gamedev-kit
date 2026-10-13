class_name Balance
extends RefCounted
## The one place for balance numbers. It pairs one to one with the GDD's Appendix A.1 — the `# GDD:` marker on each line is the pairing.
##
## Values are edited in the balance table (data/balance.xlsx). A development build reads the table at startup over the values below,
## and re-reads it every time the table is saved (balance_watch.gd). Hence static var, not const — callers still write `Balance.NAME`.
## The numbers below are the baked values: a release build does not read the table and uses only these. `balance_table.py bake` writes them.

const Table := preload("res://game/config/balance_table.gd")
const TABLE_PATH := "res://data/balance.xlsx"

## Example values — change them to fit the game. One number per line, the marker at the end of the line.
static var PLAYER_HP := 100  # GDD: BAL.PLAYER.HP
## Walking speed (m/s)
static var PLAYER_WALK_SPEED := 4.0  # GDD: BAL.PLAYER.WALK_SPEED
static var COIN_VALUE := 5  # GDD: BAL.COIN.VALUE


# ── Balance table ────────────────────────────────────────────────────────────
static func _static_init() -> void:
	# Headless runs (smoke tests · build checks) use the baked values — a value being tried in the table must not shake the tests
	if DisplayServer.get_name() != "headless":
		reload_table()


## Reads the table over the values. Returns what changed as {name: [before, after]}. Empty in a release build, with no table, or with a half-written file.
static func reload_table(path := TABLE_PATH) -> Dictionary:
	var changed := {}
	if not OS.is_debug_build():
		return changed
	var rows: Dictionary = Table.read(path)
	if rows.is_empty():
		return changed
	var script: GDScript = load("res://game/config/balance.gd")
	for name: String in rows:
		var was: Variant = script.get(name)
		if was == null:
			continue
		var now: Variant = rows[name]
		if typeof(was) == TYPE_INT:
			now = roundi(now)
		elif typeof(was) != TYPE_FLOAT:
			continue
		if now != was:
			script.set(name, now)
			changed[name] = [was, now]
	return changed
