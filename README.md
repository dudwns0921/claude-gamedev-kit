# claude-gamedev-kit

게임을 Claude Code 로 만들 때 쓰는 플러그인. 엔진은 게임 저장소의 `kit.config.json` 이 정한다 — 플러그인은 하나다.

| 스킬 | 하는 일 |
|---|---|
| `/gamedev-kit:init` | 게임 저장소에 설정 · GDD 틀 · CLAUDE.md 규칙 · 런타임 틀을 깐다 |
| `/gamedev-kit:gdd-sync` | GDD 부록 A 동기화 표와 코드의 `GDD: <ID>` 표식을 대조하고 한쪽으로 맞춘다 |
| `/gamedev-kit:balance-table` | 밸런스 값을 엑셀 표에서 고치고 코드와 맞춘다 (export · bake · check · serve) |
| `/gamedev-kit:playtest` | 플레이하며 적은 문제 목록 → 분석 문서(`docs/playtest/`) → 작업마다 에이전트 하나가 구현 |

| 에이전트 | 모델 | 하는 일 |
|---|---|---|
| `playtest-analyst` | Fable | 문제 목록의 원인을 찾아 작업 문서로 쓴다. 코드는 고치지 않는다 |
| `playtest-implementer` | Opus | 문서의 작업 하나를 적힌 대로 구현하고 확인한다. 다시 분석하지 않는다 |

모델은 에이전트에 정해져 있어서 세션이 어떤 모델이든 분석은 Fable, 구현은 Opus 가 한다. 세션은 지휘만 한다.
서로 다른 파일을 고치는 작업은 동시에 돈다.

## 엔진

| 엔진 | gdd-sync | 표 ↔ 코드 | 실행 중에 표 다시 읽기 | 확인한 것 |
|---|---|---|---|---|
| Godot | ○ | ○ | ○ 게임이 표 파일을 직접 읽는다 | 도구 테스트 · 헤드리스 실행 (4.7) |
| Roblox | ○ | ○ | ○ `serve` 가 내주는 JSON 을 Studio 가 가져온다 | 도구 테스트 · Lune 으로 런타임 실행 · Studio 플레이 테스트에서 실시간 반영 (0.741, 2026-10-06) |
| Unity | ○ | ○ | — | 도구 테스트만 |

## 설치

게임 저장소에서:

```bash
claude plugin marketplace add git@github.com-personal:dudwns0921/claude-gamedev-kit.git
```

```bash
claude plugin install gamedev-kit@claude-gamedev-kit --scope project
```

그다음 Claude 에게 `/gamedev-kit:init`.

올린 뒤 받기:

```bash
claude plugin marketplace update claude-gamedev-kit
```

```bash
claude plugin update gamedev-kit@claude-gamedev-kit
```

## 구조

```
.claude-plugin/     plugin.json · marketplace.json (이 저장소가 플러그인이자 마켓플레이스다)
skills/<이름>/      스킬 하나가 폴더 하나. 자기 스크립트는 scripts/ 에
agents/<이름>.md    에이전트. 모델을 정해 두어야 하는 일만 에이전트로 둔다
engines/<엔진>/     kit.config.json(엔진 설정) · NOTES.md · files/(게임 저장소에 그대로 복사될 런타임 틀)
templates/          GDD.md · CLAUDE.md — 게임 저장소에 깔리는 틀
tests/              python3 tests/test_tools.py — 엔진 없이 도구만 검사
```

도구는 플러그인 안에 있고 게임은 밖에 있다. 스크립트는 지금 폴더에서 위로 올라가며 `kit.config.json` 을 찾아 그곳을 게임 루트로 본다.
