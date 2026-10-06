# Godot

- 값 파일: `game/config/balance.gd` (`class_name Balance`, `static var NAME := 값  # GDD: <ID>`).
- `game/debug/balance_watch.gd` 를 오토로드 `BalanceWatch` 로 건다. 배포 빌드에서는 스스로 사라진다.
- 새 `class_name` 은 에디터가 스캔해야 보인다 — 에디터가 꺼져 있으면 `godot --headless --path . --import` 한 번.
- 내보내기 프리셋의 `exclude_filter` 에 `data/*` 를 넣는다. 배포 빌드에 표가 들어가지 않게.
- 값 파일 자리를 바꾸면 `kit.config.json` 의 `balance-table.code` 와 balance.gd 안의 `res://` 경로 둘을 같이 고친다.
