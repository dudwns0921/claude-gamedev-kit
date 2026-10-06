# CLAUDE.md — claude-gamedev-kit

Claude Code 플러그인 저장소다. 게임 코드는 여기 없다 — 게임 저장소에 설치돼 쓰인다.

## 규칙

- **엔진마다 다른 것은 `engines/<엔진>/` 에만 둔다.** 스킬과 스크립트에 엔진 이름으로 갈리는 분기를 넣지 않는다.
  스크립트는 `kit.config.json` 의 값(확장자 · 정규식 · 경로)만 본다. 새 엔진은 폴더 하나를 더하는 일이어야 한다.
- **스킬은 자기 폴더로 완결된다.** 다른 스킬의 스크립트를 import 하지 않는다. 설정은 `kit.config.json` 에 스킬 이름으로 된 절을 쓴다.
- **스크립트는 표준 라이브러리만 쓴다** (Python 3.9). Blender 가 돌리는 스크립트(`blender_finish.py`)만 `bpy` 를 쓴다. 게임 루트는 지금 폴더에서 위로 올라가며 찾는다 — 스크립트 위치로 찾지 않는다.
- **게임 저장소의 파일을 덮어쓰지 않는다.** init 은 없는 파일만 만든다.
- 스킬 이름은 게임의 CLAUDE.md 와 GDD 에 박힌다 (`/gamedev-kit:gdd-sync`). 바꾸지 않는다.
- **밖으로 나가는 일(배포 · 게시)은 스크립트가 검사하고, 묻는 일은 스킬이 한다.** 에이전트는 승낙을 받지도 건너뛰지도 않는다.
  로그인과 토큰은 사용자가 하고 저장소 밖에 둔다.
- 고친 뒤에는 `.claude-plugin/plugin.json` 의 `version` 을 올린다 — 안 올리면 설치된 쪽이 새 판을 받지 않는다.

## 검증

```bash
python3 tests/test_tools.py        # 엔진 설정마다 임시 프로젝트를 만들어 gdd-sync · balance-table 을 끝까지 돌린다. deploy 는 가짜 butler, promo · asset 은 가짜 API 서버로 (asset 의 다듬기는 Blender 가 있으면 진짜로)
claude plugin validate .           # 매니페스트
```

Godot 런타임 틀은 이 테스트가 보지 않는다 (Roblox 는 lune 이 있으면 흉내로 돌린다). 고쳤으면 그 엔진에서 직접 돌려 보고 README 의 "확인한 것" 열을 맞춘다.

## 게임에서 배운 것은 여기로 돌아온다

게임 저장소에서 엔진 설정을 손으로 한 것, 걸려 넘어진 함정, 확인하는 방법은 `engines/<엔진>/NOTES.md`(깐 뒤 할 일)와
`engines/<엔진>/CLAUDE.md`(게임의 규칙이 될 것)에 옮겨 적는다. 다음 게임이 같은 일을 다시 겪지 않게.
