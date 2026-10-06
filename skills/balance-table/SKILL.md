---
name: balance-table
description: >-
  밸런스 수치를 엑셀 표(data/balance.xlsx)에서 고치고 코드의 밸런스 값 파일과 맞춘다. 코드 → 표(export),
  표 → 코드(bake), 둘이 같은지(check), 실행 중인 게임에 표를 내주기(serve). 엔진을 가리지 않는다
  (값 줄의 모양은 kit.config.json 이 정한다). 다음 상황이면 이 스킬을 쓴다: 사용자가 "밸런스 표", "엑셀",
  "표 구워줘", "bake", "표랑 코드 맞춰", "값이 게임에 안 먹어" 라고 할 때; 밸런스 값 파일에 값을 새로 만들거나
  숫자를 손으로 고쳤을 때(export); 사용자가 표에서 값을 정했다고 할 때(bake → gdd-sync to-gdd);
  배포 빌드를 만들기 전(check); Roblox 처럼 디스크를 못 읽는 엔진에서 밸런싱을 시작할 때(serve).
---

# balance-table

밸런스 값은 두 곳에 있다. **표**(`data/balance.xlsx`)는 사람이 고치는 자리이고, **값 파일**(코드)은 게임이 쓰는 자리다.
개발 중에는 게임이 표를 읽어 값 파일의 값을 덮는다 — 게임을 끄지 않고 값을 바꿔 본다.
값이 정해지면 표를 코드에 굽는다. 배포 빌드는 표를 읽지 않고 구운 값만 쓴다.

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/balance_table.py" export   # 코드 → 표 (표를 다시 만든다)
python3 "${CLAUDE_SKILL_DIR}/scripts/balance_table.py" bake     # 표 → 코드
python3 "${CLAUDE_SKILL_DIR}/scripts/balance_table.py" check    # 다르면 다른 줄을 적고 1 로 끝난다
python3 "${CLAUDE_SKILL_DIR}/scripts/balance_table.py" serve    # 표를 http://127.0.0.1:8765/balance 로 내준다
```

## 언제 무엇을

| 일어난 일 | 할 일 |
|---|---|
| 값 파일에 새 값을 더했다 · 숫자를 손으로 고쳤다 | `export`. 안 하면 개발 빌드는 표의 옛 값을 쓴다 |
| 사용자가 표에서 값을 정했다 | `bake` → `/gamedev-kit:gdd-sync to-gdd` |
| 배포 빌드를 만든다 | `check` 가 통과해야 한다. 빌드 스크립트에 넣어 둔다 |
| GDD 를 고쳐 `/gdd-sync to-code` 로 값 파일이 바뀌었다 | `export` |

**export 는 표를 코드 값으로 다시 쓴다.** 표에서 고치던 값이 있으면 사라진다 — export 전에 `check` 로 다른 값이 있는지 보고,
있으면 먼저 bake 할지 사용자에게 묻는다.

## 값 파일의 규칙

- 값 하나가 한 줄, 숫자 하나. 줄 끝에 `GDD: <ID>` 표식. 줄 바로 위 설명 주석은 표의 설명 열이 된다.
- 이름은 대문자와 밑줄(`NOISE_RUN_PER_SEC`). 표의 A 열 이름과 같아야 한다.
- 실수는 소수점을 적는다(`4.0`). 소수점 없이 적힌 값은 정수로 보고, 표에 소수가 들어오면 bake 가 멈춘다.
- 숫자 하나로 정해지지 않는 줄(식 · 배열 · 문자열)은 표에 오르지 않는다. 파생 값은 코드에서 계산한다.
- 줄이 어떻게 생겼는지는 `kit.config.json` 의 `balance-table.line` 정규식이 정한다.

## 표의 규칙

- A 열 이름 · B 열 값만 읽는다. 나머지 열(코드값 · 분류 · GDD ID · 설명)은 사람이 보는 것이다.
- 표에만 있는 이름은 무시한다. 숫자가 아닌 칸도 넘긴다.
- 시작할 때만 쓰이는 값(시작 인원 등)은 저장해도 진행 중인 판은 그대로다 — 새 판부터.

## 실행 중에 다시 읽기 (엔진마다 다르다)

런타임 틀은 `/gamedev-kit:init` 이 게임 저장소에 깔아 준다 (플러그인의 `engines/<엔진>/files/`).

- **Godot** — 게임이 표 파일을 직접 읽는다 (`game/config/balance_table.gd` · `game/debug/balance_watch.gd`).
  저장하면 0.5초 안에 다시 읽고 화면에 바뀐 값을 알린다. 헤드리스 실행은 표를 읽지 않고 구운 값으로 돈다.
- **Roblox** — Roblox 는 디스크를 읽지 못한다. `serve` 를 켜 두면 Studio 플레이 테스트의 서버 스크립트
  (`src/server/BalanceWatch.server.luau`)가 0.5초마다 표를 가져와 덮고, 값은 속성(Attribute)으로 클라이언트에 복제된다.
  Studio 의 Allow HTTP Requests 를 켜야 한다. 올린 게임에서는 돌지 않는다.
  사용자가 밸런싱을 시작한다고 하면 `serve` 를 백그라운드로 켠다.
- **그 밖의 엔진** — 디스크를 읽을 수 있으면 Godot 방식(xlsx 는 XML 을 담은 zip), 못 읽으면 `serve` 의 JSON 을 가져온다:
  `{"stamp": "<저장 시각>", "values": {"이름": 숫자}}`. 저장 도중이면 503.

값을 쓰는 코드는 쓸 때마다 값 파일에서 읽는다. 뜰 때 변수에 받아 두면 옛 값을 쥐고 있게 된다.

## 배포 빌드 검사

플러그인은 Claude 가 관리하는 폴더에 설치되므로 게임의 빌드 스크립트가 이 스크립트를 경로로 부를 수 없다.
빌드 스크립트에서 `check` 를 돌려야 하면 `scripts/balance_table.py` 를 게임 저장소의 `tools/` 로 복사해 부른다
(파일 하나로 돌고 외부 패키지가 없다). 복사본은 플러그인을 올릴 때 다시 복사한다.
