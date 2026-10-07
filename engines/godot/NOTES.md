# Godot

- 값 파일: `game/config/balance.gd` (`class_name Balance`, `static var NAME := 값  # GDD: <ID>`).
- `game/debug/balance_watch.gd` 를 오토로드 `BalanceWatch` 로 건다. 배포 빌드에서는 스스로 사라진다.
- 새 `class_name` 은 에디터가 스캔해야 보인다 — 에디터가 꺼져 있으면 `godot --headless --path . --import` 한 번.
- 내보내기 프리셋의 `exclude_filter` 에 `data/*` 를 넣는다. 배포 빌드에 표가 들어가지 않게.
- 값 파일 자리를 바꾸면 `kit.config.json` 의 `balance-table.code` 와 balance.gd 안의 `res://` 경로 둘을 같이 고친다.
- **배포(itch.io)**: `kit.config.json` 의 `deploy.itch` 에 `사용자/게임` 을 적는다. 에디터의 프로젝트 → 내보내기에서 **`Web`** 이라는 이름의
  프리셋을 만들고 내보내기 템플릿을 받는다 (에디터에서 사용자가 한 번). 프리셋 이름을 달리하면 `deploy.channels.html5.build` 를 고친다.
  버전은 `project.godot` 의 `config/version` 에서 읽는다 — 프로젝트 설정 → 애플리케이션 → 구성 → 버전에 적는다. `build/` 는 `.gitignore` 에 넣는다.
  데스크톱 빌드를 더하려면 채널을 더한다: `"windows": { "build": "godot --headless --path . --export-release Windows build/windows/game.exe", "dir": "build/windows" }`.
- **에셋(asset 스킬)**: 끝난 모델은 `assets/models/<이름>.glb` 에 놓인다. Godot 는 glb 를 그대로 읽는다 — 에디터가 켜져 있으면 창에 돌아올 때,
  꺼져 있으면 `godot --headless --path . --import` 로 가져온다. 1 단위가 1 m 라서 `--size` 가 그대로 게임 안 크기다. 원점은 바닥 가운데.
  `.gitignore` 에 `assets/_gen/*/raw.glb` 를 넣는다. `docs/DESIGN.md` 의 화풍 문단과 API 키는 asset 스킬이 처음 쓸 때 안내한다.
- **소리(asset 스킬)**: `assets/sounds/<이름>.mp3` 에 놓인다. Godot 는 mp3 를 `AudioStreamMP3` 로 읽는다. 이어지는 소리와 음악은
  가져오기 설정에서 **Loop** 를 켠다 (파일을 고르고 가져오기 독 → Loop → 다시 가져오기) — `--loop` 로 만들어도 이 설정이 꺼져 있으면 한 번만 난다.
