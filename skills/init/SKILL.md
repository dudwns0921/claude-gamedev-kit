---
name: init
description: >-
  게임 저장소에 gamedev-kit(gdd-sync · balance-table)이 쓰는 파일을 깐다 — 엔진 설정(kit.config.json), GDD 틀,
  CLAUDE.md 규칙, 밸런스 값 파일과 표를 실행 중에 다시 읽는 런타임 틀. Godot · Roblox · Unity 중 하나를 고른다.
  키트가 판을 올린 뒤 CLAUDE.md 의 키트 규칙을 맞춘다 (rules). 새 게임을 시작할 때, "gamedev-kit 깔아줘", "키트 규칙 맞춰줘", "init rules", "GDD 동기화 세팅", "밸런스 표 세팅" 이라고 할 때, 또는 gdd-sync 나
  balance-table 이 kit.config.json 을 찾지 못했다고 할 때 쓴다.
---

# init

게임 저장소 루트에서 돌린다. 이미 있는 파일은 건드리지 않으므로 다시 돌려도 안전하다.

**이미 깐 프로젝트에서 다시 돌리면** 덮어쓰는 것은 없고, 하는 일은 셋이다: 그 뒤로 키트에 생긴 문서 틀(예: `docs/DESIGN.md`)을 없으면 만들고,
`kit.config.json` 에 없는 설정 절을 알려 주고(옮겨 적는 것은 네가 한다 — 파일을 고치지 않는다), 엔진 틀(값 파일 · 런타임)은 건너뛴다.
엔진 틀을 건너뛰는 까닭: 값 파일을 옮겼거나 틀을 일부러 지운 프로젝트에 같은 파일을 또 만들면 중복이 된다. 정말 다시 깔려면 `--files`.
CLAUDE.md 는 손대지 않고, 키트 규칙이 옛 판이면 그렇다고 알려 준다 — 맞추는 것은 아래 "키트 규칙 맞추기" 다.

## 절차

1. **엔진을 정한다.** 저장소를 보면 대개 알 수 있다 — `project.godot` 이면 godot, `default.project.json`(Rojo)이나
   `.luau` 파일이면 roblox, `Assets/` 와 `ProjectSettings/` 면 unity. 빈 저장소이거나 알 수 없으면 사용자에게 묻는다.

2. **깐다.**

   ```bash
   python3 "${CLAUDE_SKILL_DIR}/scripts/init.py" <godot|roblox|unity>
   ```

   깔리는 것: `kit.config.json` · `docs/GDD.md` · `docs/DESIGN.md` · `CLAUDE.md` · 엔진별 값 파일과 런타임 틀 · `.gitignore` 한 줄.
   끝에 그 엔진에서 손으로 이어 줄 일(오토로드 등록, Rojo 경로, HTTP 허용 등)이 적혀 나온다 — **그 일을 이어서 한다.**

3. **CLAUDE.md 가 새로 만들어졌으면** `<게임 이름>` 을 채운다 (`docs/GDD.md` 의 제목도). 이미 있었으면 손대지 않는다 —
   키트 규칙 블록이 없다고 나오면 아래 "키트 규칙 맞추기" 를 할지 사용자에게 묻는다.

4. **프로젝트 구조가 틀과 다르면 맞춘다.** 값 파일을 다른 자리에 두고 싶으면 파일을 옮기고 `kit.config.json` 의
   `balance-table.code` 를 고친다. 값 파일의 예시 값 세 줄은 게임의 값으로 바꾼다.

5. **표를 만들고 확인한다.** balance-table 스킬의 `export` 로 `data/balance.xlsx` 를 만들고, gdd-sync 스킬로
   보고서가 나오는지 본다. GDD 틀의 예시 행(BAL.PLAYER.HP)이 값 파일의 예시 값과 짝지어 `동기` 로 나오면 된 것이다.

6. **배포 · 에셋은 쓸 때 채운다.** `kit.config.json` 의 `deploy.itch`(itch.io 의 `사용자/게임`), 에셋 API 키,
   `docs/DESIGN.md` 의 화풍 문단은 비어 있는 채로 깔린다. 처음 쓸 때 deploy · asset 스킬이 채우는 법을 안내한다.

## 키트 규칙 맞추기 (`/gamedev-kit:init rules`)

게임의 CLAUDE.md 에서 키트의 것은 `<!-- gamedev-kit 시작 … -->` 과 `<!-- gamedev-kit 끝 -->` 사이 하나다 — 공통 규칙(GDD 동기화 · 밸런스 표 · 사이클 …)과
그 엔진의 규칙(실행 · 검증 · 함정)이 들어 있다. 키트가 판을 올리면 그 사이만 통째로 바꾼다. **블록 밖은 게임의 것이고 건드리지 않는다.**
세션이 시작될 때 훅이 블록을 보고, 없거나 옛 판이면 한 줄로 알린다.

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/init.py" <엔진> --rules
```

- **블록이 옛 판이면** 블록만 바뀐다. 끝이다. 무엇이 달라졌는지 `git diff CLAUDE.md` 로 보고 한두 줄로 전한다.
- **블록이 없으면**(이 방식 전에 깐 프로젝트) 끝에 붙는다. 있던 글은 그대로라서 옛 판을 옮겨 적은 절이 블록 밖에 남아 **같은 말이 두 번** 있게 된다.
  스크립트가 겹치는 제목을 적어 준다. 그 절들을 하나씩 블록과 견준다: 블록과 같은 말은 밖에서 지우고, 이 게임에서 고쳐 쓰거나 더한 말만
  밖에 남긴다 ("이 게임의 규칙" 아래로 모은다). **지우기 전에 무엇을 지우고 무엇을 남기는지 사용자에게 보이고 답을 받는다** — 사용자가 쓴 글이다.
  엔진 규칙의 함정과 게임의 "함정" 이 겹치는 것도 같은 식으로 본다.
- **블록 안이 손으로 고쳐졌으면** 스크립트가 멈춘다. 고친 말을 블록 밖으로 옮기고 다시 돌린다 — 밖의 말이 블록보다 앞선다. `--force` 는 사용자가 버려도 된다고 할 때만.
- 블록을 두고 싶지 않다고 하면 `kit.config.json` 에 `"init": { "rules": false }` — 훅이 알리지 않는다.

## 엔진을 더하려면 (플러그인 쪽 작업)

`engines/<이름>/` 에 `kit.config.json`(코드 확장자 · 값 줄 정규식 · 빌드 명령), `NOTES.md`(깐 뒤 이어서 할 일), `CLAUDE.md`(게임의 CLAUDE.md 에
붙을 엔진 규칙), `files/`(게임 저장소에 그대로 복사될 파일)를 둔다.
`tests/test_tools.py` 의 `CODE` 에 그 엔진 문법의 값 파일을 더해 도구가 읽고 고치는지 확인한다.
