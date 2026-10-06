extends Node
## 밸런스 표(data/balance.xlsx)를 지켜보다가 저장되면 다시 읽는다 — 게임을 끄지 않고 값을 바꿔 본다.
##
## 오토로드로 건다 (BalanceWatch). 배포 빌드에서는 뜨자마자 스스로 사라진다 — 표도 빌드에 넣지 않는다.
## 대부분의 코드는 `Balance.NAME` 을 쓸 때마다 읽으므로 그 자리에서 바뀐다. 다만 노드가 뜰 때
## `var x := Balance.NAME` 으로 받아 둔 값은 옛 값을 쥐고 있다 — 그런 변수를 스크립트에서 찾아 같이 고친다.
## 사람이 손댄 값(인스펙터 · 테스트가 바꾼 값)은 옛 기본값과 다르므로 건드리지 않는다.

const POLL_SEC := 0.5
const TOAST_SEC := 4.0
const TOAST_LINES := 6

## 지켜보는 표. 테스트는 진짜 표를 건드리지 않게 다른 파일로 바꾼다.
var path := Balance.TABLE_PATH

var _stamp := 0
var _wait := 0.0
var _label: Label
var _toast_left := 0.0
var _held := {}  # 스크립트 경로 → {변수 이름: Balance 이름}
var _held_re := RegEx.create_from_string("(?m)^(?:@export\\s+)?var\\s+(\\w+)\\s*(?::\\s*\\w+\\s*)?:?=\\s*Balance\\.([A-Z][A-Z0-9_]*)\\s*(?:#.*)?$")


func _ready() -> void:
	if not OS.is_debug_build():
		queue_free()
		return
	process_mode = Node.PROCESS_MODE_ALWAYS  # 일시정지 메뉴를 띄워 놓고 고쳐도 읽는다
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
	# 엑셀이 저장하는 도중이면 표가 비어 돌아온다 — 도장을 찍지 않고 다음 번에 다시 읽는다
	if Balance.Table.read(path).is_empty():
		return
	_stamp = stamp
	reload()


## 표를 다시 읽고 바뀐 값을 화면과 출력에 알린다. 치트 콘솔이 있으면 거기서도 이것을 부른다.
func reload() -> Dictionary:
	var changed: Dictionary = Balance.reload_table(path)
	if changed.is_empty():
		_show("밸런스 표: 바뀐 값 없음")
		return changed
	_refresh_held(get_tree().root, changed)
	var lines: Array[String] = []
	for name: String in changed:
		lines.append("%s  %s → %s" % [name, _text(changed[name][0]), _text(changed[name][1])])
	print("[balance] ", ", ".join(lines))
	if lines.size() > TOAST_LINES:
		var more := lines.size() - TOAST_LINES
		lines.resize(TOAST_LINES)
		lines.append("… 외 %d개" % more)
	_show("밸런스 표 반영\n" + "\n".join(lines))
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
