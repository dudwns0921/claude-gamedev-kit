---
name: promo
description: >-
  개발 일지를 Threads 에 올린다. 홍보 에이전트(promoter)가 이번에 실제로 만든 것을 읽고 docs/promo/ 에 초안을 쓰고,
  스크립트가 Threads API 로 올린다 (글이 여럿이면 답글로 잇는다). itch.io devlog 는 여기가 아니라 deploy 스킬이 배포할 때 쓴다. 다음 상황이면 이 스킬을 쓴다: 사용자가 "홍보",
  "스레드에 올려줘", "개발 일지 써줘", "이번 업데이트 알리자" 라고 할 때; cycle 스킬이 홍보 단계에 왔을 때;
  Threads 토큰을 처음 연결하거나 "토큰 만료" 오류가 났을 때.
---

# promo

쓰는 일과 올리는 일을 가른다. 쓰는 것은 에이전트가 하고 초안으로 남는다. 올리는 것은 스크립트가 초안의 글을 **글자 그대로** 올린다.
올린 글은 사용자의 이름으로 남는다.

| 호출 | 뜻 |
|---|---|
| `/gamedev-kit:promo [무엇에 대해]` | 초안을 쓰고 올린다. 생략하면 가장 새 사이클 문서 |
| `/gamedev-kit:promo draft [무엇에 대해]` | 초안만 |
| `/gamedev-kit:promo post [초안]` | 있는 초안을 올린다. 생략하면 `docs/promo/` 에서 `게시:` 줄이 없는 가장 새 초안 |
| `/gamedev-kit:promo setup` | 토큰 연결을 확인한다 |

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/threads.py" check <초안.md>   # 올릴 글과 길이. 올리지 않는다
python3 "${CLAUDE_SKILL_DIR}/scripts/threads.py" post <초안.md>    # 올리고 초안에 주소를 적는다
python3 "${CLAUDE_SKILL_DIR}/scripts/threads.py" whoami            # 토큰이 어느 계정인지
python3 "${CLAUDE_SKILL_DIR}/scripts/threads.py" refresh           # 토큰을 새로 받는다
```

## 절차

1. **`gamedev-kit:promoter` 에이전트를 `threads` 로 부른다.** 넘길 것: 모드, 무엇에 대해 쓸지(사이클 문서 경로 또는 사용자의 말 그대로), 배포된 주소(있으면).
   네가 문장을 지어 넘기지 않는다. 돌아오면 초안 경로와 "뺀 것" 을 전한다. `draft` 면 여기서 멈춘다.
2. **`check` 를 돌린다.** 한 글은 500자까지다 (이모지는 하나가 서너 자로 세진다). 넘는 글이 있으면 에이전트에게 그 글을 줄이라고 다시 부른다 — 네가 자르지 않는다.
3. **올린다.** `kit.config.json` 의 `promo.confirm` 이
   - `true`(기본)면 `check` 가 보여 준 글을 그대로 보여 주고 올릴지 묻는다. 사용자가 고쳐 달라고 하면 초안을 고치고 다시 `check`.
   - `false` 면 묻지 않고 `post` 한다. 사용자가 그렇게 해 두었다는 뜻이다 — 대신 올린 뒤 글 전문과 주소를 반드시 전한다.
4. `post` 가 끝나면 초안에 `게시: <주소>` 줄이 붙는다. 그 줄이 있는 초안은 스크립트가 다시 올리지 않는다.
   중간에 멈췄으면(넷 중 둘만 올라감) 그 사실이 초안에 적힌다 — 남은 글을 이어 올릴지는 사용자에게 묻는다.
5. 사이클 중이면 사이클 문서의 "홍보" 절에 초안 경로와 주소를 적는다.

## 올리면 안 되는 것

에이전트가 걸렀어야 하지만 올리기 전에 한 번 더 본다: 구현되지 않은 기능, 정해지지 않은 날짜, 토큰 · 내부 경로 · 다른 사람의 실명.
보이면 올리지 않고 초안을 고친다. `confirm` 이 `false` 여도 마찬가지다.

## 처음 한 번 (사용자가 직접)

Threads API 는 Meta 개발자 앱과 그 계정의 토큰이 있어야 한다. 계정을 만들고 권한을 허락하고 토큰을 받는 일은 사용자가 한다.

1. <https://developers.facebook.com> 에서 앱을 만들고 **Threads API** 를 더한다. 권한: `threads_basic` · `threads_content_publish`.
   이어지는 글(자기 글에 다는 답글)이 권한 오류로 막히면 `threads_manage_replies` 를 더한다.
2. 올릴 Threads 계정을 앱의 테스터로 넣고, 그 계정으로 토큰을 받아 **오래가는 토큰**(60일)으로 바꾼다.
3. 토큰을 저장소 **밖**의 파일에 적는다 (사용자가 터미널에서):

   ```bash
   mkdir -p ~/.config/gamedev-kit && chmod 700 ~/.config/gamedev-kit && ${EDITOR:-nano} ~/.config/gamedev-kit/threads.env
   ```

   파일에는 `THREADS_ACCESS_TOKEN=<토큰>` 한 줄. 게임마다 계정이 다르면 `kit.config.json` 의 `promo.env_file` 로 다른 파일을 가리킨다.
4. `whoami` 로 계정 이름이 맞게 나오는지 본다.

토큰은 60일 뒤 끊긴다. `refresh` 가 새 토큰을 받아 같은 파일에 적는다 (받은 지 하루가 지났고 아직 끊기지 않았을 때만 된다). 끊겼으면 2번부터 다시 한다.
**토큰을 대화에 붙여 넣지 않게 하고, 받았더라도 저장소의 어떤 파일에도 적지 않는다.**

## 설정

```json
"promo": { "confirm": true, "env_file": "~/.config/gamedev-kit/threads.env" }
```

말투 · 쓰는 말 · 해시태그는 `docs/promo/VOICE.md` 에 적어 두면 에이전트가 따른다. 없어도 된다.
Threads 에는 지금 글만 올린다. 그림과 영상은 Threads 가 공개 주소를 요구해서 아직 없다 — 초안의 "같이 올리면 좋을 것" 은 사용자가 손으로 붙인다.
