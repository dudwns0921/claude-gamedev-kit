# claude-gamedev-kit

게임을 Claude Code 로 만들 때 쓰는 플러그인. 엔진은 게임 저장소의 `kit.config.json` 이 정한다 — 플러그인은 하나다.

| 스킬 | 하는 일 |
|---|---|
| `/gamedev-kit:init` | 게임 저장소에 설정 · GDD 틀 · CLAUDE.md 규칙 · 런타임 틀을 깐다 |
| `/gamedev-kit:gdd-sync` | GDD 부록 A 동기화 표와 코드의 `GDD: <ID>` 표식을 대조하고 한쪽으로 맞춘다 |
| `/gamedev-kit:balance-table` | 밸런스 값을 엑셀 표에서 고치고 코드와 맞춘다 (export · bake · check · serve) |
| `/gamedev-kit:playtest` | 플레이하며 적은 문제 목록 → 분석 문서(`docs/playtest/`) → 작업마다 에이전트 하나가 구현 |
| `/gamedev-kit:cycle` | 한 사이클 — 목표 → 기획 → 디자인 → 계획 → 구현 → 플레이 → 배포 → 회고 — 를 문서 하나(`docs/cycle/`)로 끌고 간다 |
| `/gamedev-kit:handoff` | 세션을 바꿀 때 하던 일을 짧은 메모(`docs/handoff/`)로 남기고, 새 세션에서 그 메모로 잇는다 |
| `/gamedev-kit:asset` | 3D 에셋 — 설명 → 이미지(OpenAI) → 사람이 승인 → 메쉬(Meshy) → 크기 · 원점 맞추기(Blender) → 게임 폴더.<br>소리 — 설명 → 효과음 · 이어지는 소리 · 음악(ElevenLabs) → 게임 폴더 |
| `/gamedev-kit:deploy` | 빌드해서 butler 로 itch.io 에 올리고 (check · build · push · status), 그 빌드의 itch.io devlog 초안을 칸마다 채워 쓴다 (붙여 넣는 것은 사용자) |

| 에이전트 | 모델 | 하는 일 |
|---|---|---|
| `playtest-analyst` | Fable | 문제 목록의 원인을 찾아 작업 문서로 쓴다. 코드는 고치지 않는다 |
| `systems-designer` | Fable | 사이클의 목표를 규칙 · 밸런스 수치 · 공간의 치수로 쓴다. 값은 정하지 않고 계산을 붙인 범위로 내놓는다 |
| `designer` | Fable | 기획이 어떻게 보이고 들리는가(UI 의 생김새 · 연출 · 소리 · 에셋 목록)를 쓴다. 규칙 · 수치 · 치수는 정하지 않는다. 스크린샷을 `docs/DESIGN.md` 에 비추어 본다 |
| `developer` | Opus | 사이클의 작업을 나누고(plan), 사이클 · 플레이테스트 문서의 작업 하나를 적힌 대로 구현한다(build). 다시 분석하지 않는다 |
| `deployer` | Sonnet | 검사 · 빌드 · butler push. 빌드가 깨지면 첫 오류를 찾아 돌려준다 |
| `devlog-writer` | Opus | 실제로 만든 것만 읽고, 배포한 빌드의 itch.io devlog 초안(`docs/devlog/`)을 쓴다. 올리지 않는다 |

모델은 에이전트에 정해져 있어서 세션이 어떤 모델이든 분석은 Fable, 구현은 Opus 가 한다. 세션은 지휘만 한다.
서로 다른 파일을 고치는 작업은 동시에 돈다.

## 사이클

[gstack](https://github.com/garrytan/gstack) 의 틀 — 역할마다 에이전트, 단계마다 문서, 뒤 단계가 앞 단계의 문서를 읽는다 — 을 게임 한 판에 맞춘 것이다.

```
목표 ─▶ 기획 ─────────▶ 디자인 ─▶ 계획 ─▶ 구현 ─▶ 플레이 ─▶ 배포 ───────────────────▶ 회고
사용자   systems-designer  designer  developer developer  사용자    deployer · devlog-writer
                                       ▲                    ▲          ▲
                                    결정을 묻는다       내보낼지 묻는다  올리기 전에 묻는다
```

**대신 정해 주는 CEO 에이전트는 없다.** 에이전트는 "결정할 것" 을 선택지와 권하는 것 하나로 돌려주고, 사용자의 답이 사이클 문서의 "결정" 절에
그대로 적힌다. 답이 없는 결정에 걸린 일은 하지 않는다.

밖으로 나가는 것은 배포 하나다: 올리기 전에 대상 · 버전 · 크기를 보여 주고 묻는다. butler 로그인은 사용자가 한 번 하고 저장소 밖에 둔다.
**알리는 일(SNS)은 이 키트에 없다** — 사용자가 직접 한다. itch.io devlog 는 초안까지만 쓰고, 붙여 넣는 것도 사용자다.

## 토큰과 시간

실제 세션 기록으로 재 보면 토큰의 대부분은 **메인 세션이 턴마다 다시 읽는 양**에서 나간다 (한 세션을 며칠 이어 간 Keros 에서 67%).
그래서: 사이클 · 플레이테스트 문서의 장부는 스크립트가 맡고(`cycle.py` · `playtest.py` — 문서를 통째로 읽지 않는다),
컨텍스트가 20만 토큰을 넘으면 훅이 새 세션을 권하게 하고, 넘어갈 때는 사이클 문서나 `/gamedev-kit:handoff` 메모가 맥락을 들고 간다.
고치기 전과 뒤는 `python3 tools/session_usage.py <게임 저장소>` 로 견준다.

## 엔진

| 엔진 | gdd-sync | 표 ↔ 코드 | 실행 중에 표 다시 읽기 | itch.io 배포 | 3D 에셋 · 소리 | 확인한 것 |
|---|---|---|---|---|---|---|
| Godot | ○ | ○ | ○ 게임이 표 파일을 직접 읽는다 | △ `Web` 프리셋을 빌드해 올린다 — 실제 빌드는 확인 안 함 | ○ glb · mp3 | 도구 테스트 · 헤드리스 실행 (4.7) |
| Roblox | ○ | ○ | ○ `serve` 가 내주는 JSON 을 Studio 가 가져온다 | — Studio 에서 올린다 | — | 도구 테스트 · Lune 으로 런타임 실행 · Studio 플레이 테스트에서 실시간 반영 (0.741, 2026-10-06) |
| Unity | ○ | ○ | — | △ 에디터에서 빌드한 폴더를 올린다 | — | 도구 테스트만 |

배포 · 에셋 도구는 가짜 butler · 가짜 OpenAI/Meshy/ElevenLabs 서버로만 돌려 보았다 (`tests/test_tools.py`). 진짜 itch.io 에 올린 적,
진짜 API 로 에셋을 뽑은 적은 아직 없다. 에셋의 다듬기(Blender 5.2)는 진짜로 돌렸고, 나온 glb 를 Godot 4.7 이 헤드리스로 가져와 크기와 원점이 맞는 것까지 확인했다.

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
engines/<엔진>/     kit.config.json(엔진 설정) · NOTES.md(깐 뒤 할 일) · CLAUDE.md(엔진 규칙) · files/(게임에 복사될 틀)
templates/          GDD.md · DESIGN.md · CLAUDE.md — 게임 저장소에 깔리는 틀
hooks/              세션의 컨텍스트가 커지면 새 세션을 권하게 하는 훅 하나
tools/              session_usage.py — 게임 저장소의 세션 기록에서 토큰이 어디로 갔는지 센다
tests/              python3 tests/test_tools.py — 엔진 없이 도구만 검사
```

도구는 플러그인 안에 있고 게임은 밖에 있다. 스크립트는 지금 폴더에서 위로 올라가며 `kit.config.json` 을 찾아 그곳을 게임 루트로 본다.
