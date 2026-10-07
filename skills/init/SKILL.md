---
name: init
description: >-
  게임 저장소에 gamedev-kit(gdd-sync · balance-table)이 쓰는 파일을 깐다 — 엔진 설정(kit.config.json), GDD 틀,
  CLAUDE.md 규칙, 밸런스 값 파일과 표를 실행 중에 다시 읽는 런타임 틀. Godot · Roblox · Unity 중 하나를 고른다.
  새 게임을 시작할 때, "gamedev-kit 깔아줘", "GDD 동기화 세팅", "밸런스 표 세팅" 이라고 할 때, 또는 gdd-sync 나
  balance-table 이 kit.config.json 을 찾지 못했다고 할 때 쓴다.
---

# init

게임 저장소 루트에서 돌린다. 이미 있는 파일은 건드리지 않으므로 다시 돌려도 안전하다.

## 절차

1. **엔진을 정한다.** 저장소를 보면 대개 알 수 있다 — `project.godot` 이면 godot, `default.project.json`(Rojo)이나
   `.luau` 파일이면 roblox, `Assets/` 와 `ProjectSettings/` 면 unity. 빈 저장소이거나 알 수 없으면 사용자에게 묻는다.

2. **깐다.**

   ```bash
   python3 "${CLAUDE_SKILL_DIR}/scripts/init.py" <godot|roblox|unity>
   ```

   깔리는 것: `kit.config.json` · `docs/GDD.md` · `docs/DESIGN.md` · `CLAUDE.md` · 엔진별 값 파일과 런타임 틀 · `.gitignore` 한 줄.
   끝에 그 엔진에서 손으로 이어 줄 일(오토로드 등록, Rojo 경로, HTTP 허용 등)이 적혀 나온다 — **그 일을 이어서 한다.**

3. **CLAUDE.md 가 이미 있었으면** 스크립트가 틀의 경로를 알려 준다. 틀의 절들과 엔진 규칙(실행 · 검증 · 함정)을
   기존 CLAUDE.md 에 옮겨 적는다. 새로 만들어졌으면 `<게임 이름>` 을 채운다 (`docs/GDD.md` 의 제목도).

4. **프로젝트 구조가 틀과 다르면 맞춘다.** 값 파일을 다른 자리에 두고 싶으면 파일을 옮기고 `kit.config.json` 의
   `balance-table.code` 를 고친다. 값 파일의 예시 값 세 줄은 게임의 값으로 바꾼다.

5. **표를 만들고 확인한다.** balance-table 스킬의 `export` 로 `data/balance.xlsx` 를 만들고, gdd-sync 스킬로
   보고서가 나오는지 본다. GDD 틀의 예시 행(BAL.PLAYER.HP)이 값 파일의 예시 값과 짝지어 `동기` 로 나오면 된 것이다.

6. **배포 · 에셋은 쓸 때 채운다.** `kit.config.json` 의 `deploy.itch`(itch.io 의 `사용자/게임`), 에셋 API 키,
   `docs/DESIGN.md` 의 화풍 문단은 비어 있는 채로 깔린다. 처음 쓸 때 deploy · asset 스킬이 채우는 법을 안내한다.

## 엔진을 더하려면 (플러그인 쪽 작업)

`engines/<이름>/` 에 `kit.config.json`(코드 확장자 · 값 줄 정규식 · 빌드 명령), `NOTES.md`(깐 뒤 이어서 할 일), `CLAUDE.md`(게임의 CLAUDE.md 에
붙을 엔진 규칙), `files/`(게임 저장소에 그대로 복사될 파일)를 둔다.
`tests/test_tools.py` 의 `CODE` 에 그 엔진 문법의 값 파일을 더해 도구가 읽고 고치는지 확인한다.
