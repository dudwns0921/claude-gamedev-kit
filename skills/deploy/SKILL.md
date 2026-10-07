---
name: deploy
description: >-
  게임을 빌드해 butler 로 itch.io 에 올리고, 그 빌드에 붙일 itch.io devlog 초안을 쓴다 — 검사(check) · 빌드(build) · 올리기(push) ·
  올라간 것 보기(status) · devlog. 빌드 명령과 올릴 곳은 kit.config.json 의 deploy 절이 정한다. 올리는 일은 배포 에이전트(deployer)가,
  devlog 초안은 promoter 에이전트가 한다. devlog 를 올리는 API 는 없어서 붙여 넣는 것은 사용자다.
  다음 상황이면 이 스킬을 쓴다: 사용자가 "배포해줘", "itch 에 올려줘", "빌드 올려", "butler", "새 버전 내자", "devlog 써줘", "itch 데브로그", "릴리스 노트" 라고 할 때;
  "올라갔어?", "itch 에 지금 뭐가 있어" 라고 할 때; cycle 스킬이 배포 단계에 왔을 때; deploy 절을 처음 채울 때.
---

# deploy

올리는 것은 되돌리기 어렵다 — 올라간 빌드는 받은 사람에게 남는다. 그래서 둘로 가른다: **준비**(검사 · 빌드 · 올라갈 것 미리 보기)는
묻지 않고 하고, **올리기**는 사용자가 이번 빌드를 두고 올리라고 한 뒤에만 한다.

| 호출 | 뜻 |
|---|---|
| `/gamedev-kit:deploy` | 준비하고, 무엇이 어디로 올라가는지 보여 주고, 승낙을 받으면 올린다 |
| `/gamedev-kit:deploy prepare [채널]` | 준비만 |
| `/gamedev-kit:deploy push [채널]` | 이미 준비된 빌드를 올린다 (사용자가 이 말을 했으면 그것이 승낙이다) |
| `/gamedev-kit:deploy status` | itch.io 가 가진 채널과 빌드 |
| `/gamedev-kit:deploy devlog` | 이미 올린 빌드의 devlog 초안만 쓴다 |

## 절차

1. **설정을 본다.** `kit.config.json` 에 `deploy` 절이 없거나 `itch` 가 비어 있으면 아래 "설정" 대로 사용자와 채운다. 지어내지 않는다.
2. **배포 전에 맞아야 하는 것.** 밸런스 표를 쓰는 게임이면 balance-table 스킬의 `check` 가 통과해야 한다 — 배포 빌드는 구운 값만 쓴다.
   다르면 bake 할지 사용자에게 묻는다. 커밋 안 된 변경이 있으면 커밋할지 묻는다 (스크립트가 어차피 멈춘다).
3. **`gamedev-kit:deployer` 에이전트를 `prepare` 로 부른다.** 넘길 것: 스크립트 경로 `${CLAUDE_SKILL_DIR}/scripts/deploy.py`, 모드, 채널.
4. **돌아온 것을 그대로 보여 주고 묻는다** — 대상(`사용자/게임:채널`), 버전, 폴더 크기. 막혔으면 이유를 전하고 멈춘다.
   빌드가 깨진 것이면 고칠지 묻는다. 여기서 검사를 건너뛰는 플래그(`--dirty`)를 붙이지 않는다 — 사용자가 그러라고 할 때만.
5. **승낙을 받으면 에이전트를 `push` 로 부른다.** 끝나면 주소(`https://<사용자>.itch.io/<게임>`)와 버전을 전한다.
6. **devlog 초안.** 빌드가 올라갔으면 `gamedev-kit:promoter` 에이전트를 `devlog` 로 부른다. 넘길 것: 모드, 무엇에 대해 쓸지(사이클 문서 경로,
   없으면 지난 배포 뒤의 커밋 범위), itch.io 주소, 버전, 올린 채널. 네가 문장을 지어 넘기지 않는다.
   돌아온 초안(`docs/devlog/<날짜>-<버전>.md`)을 **칸째로 그대로** 보여 준다 — Title · Post type · Attachments · Tags · Languages · Cover image · 본문.
   사용자가 itch.io 대시보드 → 게임 → Devlog → 새 글에서 위에서 아래로 옮겨 적는다. **이것은 네가 올릴 수 없다.**
   본문은 꾸밈 없이 쓰여 있다 — 굵게 · 제목은 편집기에서 한다. Cover image 와 스크린샷은 사용자가 찍는다.
   고쳐 달라고 하면 초안을 고친다. 사용자가 올린 글의 주소를 주면 초안 끝에 `게시: <주소>` 한 줄을 적는다.
   올리지 않기로 하면 초안은 남기고 그렇게 적는다 — 배포는 devlog 없이도 끝난 것이다.
7. 사이클 중이면 사이클 문서의 "배포" 절에 날짜 · 버전 · 채널 · 커밋 · devlog 초안 경로(와 올린 주소)를 적는다.

`status` 는 에이전트 없이 바로 돌린다:

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/deploy.py" status
```

## 설정

```json
"deploy": {
  "itch": "사용자/게임",
  "version": { "file": "project.godot", "regex": "config/version=\"([^\"]+)\"" },
  "pre": ["올리기 전에 통과해야 하는 명령"],
  "channels": {
    "html5": { "build": "빌드 명령", "dir": "build/web", "must": "index.html" }
  }
}
```

- `itch` — itch.io 주소의 두 부분. `https://사용자.itch.io/게임` 이면 `사용자/게임`. **게임 페이지는 사용자가 itch.io 에서 먼저 만든다.**
- `channels` — 이름이 itch.io 의 채널이 된다. 이름에 `win` · `windows` · `linux` · `mac` · `osx` · `android` 가 들어 있으면
  itch.io 가 그 플랫폼으로 표시한다. 브라우저 게임은 `html5` 로 올리고 **페이지 설정에서 "브라우저에서 플레이" 를 사용자가 한 번 켠다.**
  `build` 가 비어 있으면 빌드하지 않고 `dir` 에 있는 것을 올린다. `must` 는 그 폴더에 꼭 있어야 하는 파일.
- `version` — 버전이 적힌 파일과 그것을 집는 정규식. 비워 두면 커밋 해시가 버전이 된다.
- `pre` — 테스트 · 린트처럼 실패하면 올리면 안 되는 명령.

엔진마다 다른 빌드 명령은 init 이 깐 `kit.config.json` 에 들어 있다. 엔진에 내보내기 프리셋 같은 준비가 더 필요하면
init 이 끝에 적어 준 안내(엔진의 NOTES)에 있다.

## 로그인

`butler login` 은 브라우저를 열어 사용자가 직접 한다. Claude 가 대신 하지 않는다. CI 에서는 `BUTLER_API_KEY` 환경 변수를 쓴다 —
그 값은 저장소에 적지 않는다.
