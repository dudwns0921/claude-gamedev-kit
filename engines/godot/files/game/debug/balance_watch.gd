extends Node
## Watches the balance table (data/balance.xlsx) and re-reads it when it is saved — values are tried without quitting the game.
##
## Registered as an autoload (BalanceWatch). In a release build it removes itself at once — the table is not put in the build either.
## Most code reads `Balance.NAME` each time it is used, so it changes on the spot. But a value taken when a node starts,
## as `var x := Balance.NAME`, holds on to the old value — such variables are found in the script and updated too.
## A value a person touched (in the inspector · changed by a test) differs from the old default, so it is left alone.

const POLL_SEC := 0.5
const TOAST_SEC := 4.0
const TOAST_LINES := 6

## The table being watched. Tests point it at another file so the real table is not touched.
var path := Balance.TABLE_PATH

var _stamp := 0
var _wait := 0.0
var _label: Label
var _toast_left := 0.0
var _held := {}  # script path → {variable name: Balance name}
var _held_re := RegEx.create_from_string("(?m)^(?:@export\\s+)?var\\s+(\\w+)\\s*(?::\\s*\\w+\\s*)?:?=\\s*Balance\\.([A-Z][A-Z0-9_]*)\\s*(?:#.*)?$")


func _ready() -> void:
	if not OS.is_debug_build():
		queue_free()
		return
	process_mode = Node.PROCESS_MODE_ALWAYS  # still reads while the pause menu is up
	_stamp = _modified()
	var layer := CanvasLayer.new()
	layer.layer = 120
	add_child(layer)
	_label = Label.new()
	_label.position = Vector2(24, 24)
	_label.add_theme_font_size_override("font_size", 20)
	_label.add_theme_color_override("font_color", Color(1.0, 0.85, 0.45))
	_label.add_theme_color_override("font_outline_color", Color(0, 0, 0))
	_label.add_theme_constant_override("outline_size", 6)
	_label.visible = false
	layer.add_child(_label)


func _process(delta: float) -> void:
	if _toast_left > 0.0:
		_toast_left -= delta
		if _toast_left <= 0.0:
			_label.visible = false
	_wait -= delta
	if _wait > 0.0:
		return
	_wait = POLL_SEC
	var stamp := _modified()
	if stamp == 0 or stamp == _stamp:
		return
	# While Excel is mid-save the table comes back empty — the stamp is not taken, and it is read again next time
	if Balance.Table.read(path).is_empty():
		return
	_stamp = stamp
	reload()


## Re-reads the table and reports the changed values on screen and in the output. A cheat console, if there is one, calls this too.
func reload() -> Dictionary:
	var changed: Dictionary = Balance.reload_table(path)
	if changed.is_empty():
		_show("Balance table: no values changed")
		return changed
	_refresh_held(get_tree().root, changed)
	var lines: Array[String] = []
	for name: String in changed:
		lines.append("%s  %s → %s" % [name, _text(changed[name][0]), _text(changed[name][1])])
	print("[balance] ", ", ".join(lines))
	if lines.size() > TOAST_LINES:
		var more := lines.size() - TOAST_LINES
		lines.resize(TOAST_LINES)
		lines.append("… and %d more" % more)
	_show("Balance table applied\n" + "\n".join(lines))
	return changed


func _modified() -> int:
	var file := ProjectSettings.globalize_path(path)
	return FileAccess.get_modified_time(file) if FileAccess.file_exists(file) else 0


func _show(text: String) -> void:
	_label.text = text
	_label.visible = true
	_toast_left = TOAST_SEC


func _text(v: Variant) -> String:
	return str(v) if v is int else String.num(v, 3)


func _refresh_held(node: Node, changed: Dictionary) -> void:
	var script: Script = node.get_script()
	if script != null and script.resource_path != "":
		var held: Dictionary = _held_in(script)
		for prop: String in held:
			var name: String = held[prop]
			if changed.has(name) and node.get(prop) == changed[name][0]:
				node.set(prop, changed[name][1])
	for child in node.get_children():
		_refresh_held(child, changed)


func _held_in(script: Script) -> Dictionary:
	var path := script.resource_path
	if not _held.has(path):
		var found := {}
		if script is GDScript and script.has_source_code():
			for m in _held_re.search_all(script.source_code):
				found[m.get_string(1)] = m.get_string(2)
		_held[path] = found
	return _held[path]
