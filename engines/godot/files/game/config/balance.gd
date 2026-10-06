class_name Balance
extends RefCounted
## 밸런스 수치의 유일한 자리. GDD 부록 A.1 과 1:1 로 대응한다 — 각 줄의 `# GDD:` 표식이 그 짝이다.
##
## 값은 밸런스 표(data/balance.xlsx)에서 고친다. 개발 빌드는 뜰 때 표를 읽어 아래 값을 덮고, 표가 저장될 때마다
## 다시 읽는다 (balance_watch.gd). 그래서 const 가 아니라 static var 다 — 쓰는 쪽은 `Balance.NAME` 그대로.
## 아래 적힌 숫자는 구운 값이다: 배포 빌드는 표를 읽지 않고 이 값만 쓴다. `balance_table.py bake` 가 적는다.

const Table := preload("res://game/config/balance_table.gd")
const TABLE_PATH := "res://data/balance.xlsx"

## 예시 값이다 — 게임에 맞게 바꾼다. 한 줄에 숫자 하나, 줄 끝에 표식.
static var PLAYER_HP := 100  # GDD: BAL.PLAYER.HP
## 걷는 속도 (m/s)
static var PLAYER_WALK_SPEED := 4.0  # GDD: BAL.PLAYER.WALK_SPEED
static var COIN_VALUE := 5  # GDD: BAL.COIN.VALUE


# ── 밸런스 표 ────────────────────────────────────────────────────────────────
static func _static_init() -> void:
	# 헤드리스(스모크 테스트 · 빌드 검사)는 구운 값으로 돈다 — 표에서 시험하던 값에 테스트가 흔들리면 안 된다
	if DisplayServer.get_name() != "headless":
		reload_table()


## 표를 읽어 값을 덮는다. 바뀐 것을 {이름: [전, 후]} 로 돌려준다. 배포 빌드 · 표가 없을 때 · 읽다 만 파일이면 빈 값.
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
