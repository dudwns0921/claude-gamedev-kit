# CLAUDE.md — claude-gamedev-kit

Claude Code 플러그인 저장소다. 게임 코드는 여기 없다 — 게임 저장소에 설치돼 쓰인다.

## 규칙

- **엔진마다 다른 것은 `engines/<엔진>/` 에만 둔다.** 스킬과 스크립트에 엔진 이름으로 갈리는 분기를 넣지 않는다.
  스크립트는 `kit.config.json` 의 값(확장자 · 정규식 · 경로)만 본다. 새 엔진은 폴더 하나를 더하는 일이어야 한다.
- **스킬은 자기 폴더로 완결된다.** 다른 스킬의 스크립트를 import 하지 않는다. 설정은 `kit.config.json` 에 스킬 이름으로 된 절을 쓴다.
- **스크립트는 표준 라이브러리만 쓴다** (Python 3.9). 게임 루트는 지금 폴더에서 위로 올라가며 찾는다 — 스크립트 위치로 찾지 않는다.
- **게임 저장소의 파일을 덮어쓰지 않는다.** init 은 없는 파일만 만든다.
- 스킬 이름은 게임의 CLAUDE.md 와 GDD 에 박힌다 (`/gamedev-kit:gdd-sync`). 바꾸지 않는다.
- 고친 뒤에는 `.claude-plugin/plugin.json` 의 `version` 을 올린다 — 안 올리면 설치된 쪽이 새 판을 받지 않는다.

## 검증

```bash
python3 tests/test_tools.py        # 엔진 설정마다 임시 프로젝트를 만들어 gdd-sync · balance-table 을 끝까지 돌린다
claude plugin validate .           # 매니페스트
```

엔진 런타임 틀(`engines/*/files/`)은 이 테스트가 보지 않는다. 고쳤으면 그 엔진에서 직접 돌려 보고 README 의 "확인한 것" 열을 맞춘다.
