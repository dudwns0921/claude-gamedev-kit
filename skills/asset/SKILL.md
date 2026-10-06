---
name: asset
description: >-
  3D 에셋을 만든다 — 설명 → 이미지(OpenAI) → 사람이 보고 승인 → 메쉬(Meshy) → 크기 · 원점을 맞춰(Blender) 게임 폴더에.
  화풍은 docs/DESIGN.md 의 한 문단이 모든 에셋에 똑같이 붙고, 에셋마다 프롬프트 · 이미지 · 작업 번호가 기록으로 남는다.
  다음 상황이면 이 스킬을 쓴다: 사용자가 "에셋 만들어줘", "모델 뽑아줘", "○○ 3D 로 만들어줘", "이거랑 비슷한 걸로 하나 더" 라고 할 때;
  사이클의 디자인 절 "필요한 에셋" 에 없는 3D 모델이 있을 때; "이미지 괜찮아, 메쉬로 가자", "크기가 안 맞아" 라고 할 때;
  화풍 문단이나 에셋 API 키를 처음 잡을 때.
---

# asset

```
설명 ─▶ 이미지 (면마다 한 장) ─▶ [사람이 본다] ─▶ 메쉬 ─▶ 다듬기 ─▶ 게임 폴더
new      image                     approve          mesh     (mesh 가 이어서 한다)
```

**사람이 보는 곳은 이미지 한 군데다.** 이미지는 싸고 빨라서 몇 번이고 다시 그린다. 메쉬는 느리고 크레딧이 든다 —
그래서 승인된 이미지만 메쉬가 되고, 승인 뒤로는 끝까지 묻지 않고 간다.

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/asset.py" new <이름> --size <미터> [--poly <삼각형 수>] "<무엇인지 — 영어로>"
python3 "${CLAUDE_SKILL_DIR}/scripts/asset.py" image <이름>... [--view back]
python3 "${CLAUDE_SKILL_DIR}/scripts/asset.py" approve <이름>...
python3 "${CLAUDE_SKILL_DIR}/scripts/asset.py" mesh <이름>...
python3 "${CLAUDE_SKILL_DIR}/scripts/asset.py" finish <이름>... [--size <미터>]
python3 "${CLAUDE_SKILL_DIR}/scripts/asset.py" status
```

## 절차

1. **화풍이 있는지 본다.** `docs/DESIGN.md` 의 `<!-- asset-style -->` … `<!-- /asset-style -->` 사이가 비어 있으면 먼저 채운다 (아래 "화풍").
   에셋을 만들면서 화풍을 그때그때 정하지 않는다 — 그러면 에셋마다 달라진다.
2. **있는 것을 먼저 본다.** `status` 와 에셋 폴더. 같은 것이 이미 있으면 만들지 않는다. 돌 · 상자 · 풀 같은 채움용은
   CC0 팩(Kenney · Quaternius)이 더 고르고 공짜다 — 사용자에게 그쪽을 먼저 권한다. 생성은 이 게임에만 있는 것에 쓴다.
3. **`new`.** 설명은 **무엇인지만** 영어로 적는다 — 모양 · 비율 · 재질 · 색, 눈에 띄는 부분 두셋. 화풍 · 배경 · 조명 · 구도는 적지 않는다
   (스크립트가 붙인다). `--size` 는 가장 긴 변의 길이(미터)다. 사용자가 말하지 않았으면 GDD 나 디자인 절에서 찾고, 없으면 묻는다.
   `--poly` 는 화면에 크게 나오거나 작게 나오는 것만 준다 (기본은 설정값).
4. **`image`.** 여럿이면 이름을 한 번에 준다. 끝나면 이미지 경로를 사용자에게 주고 직접 열어 보라고 한다.
   너도 이미지를 읽어 보고 눈에 띄는 문제(잘렸다 · 물체가 둘이다 · 배경이 남았다 · 앞뒤가 다른 물건이다)가 있으면 먼저 말한다.
5. **사용자의 답을 기다린다.** 고쳐 달라고 하면 — 물건이 틀렸으면 `asset.json` 의 `subject` 를 고치고 `image`, 한 면만 어긋났으면 `image --view <면>`.
   **네 눈에 좋아 보인다고 `approve` 하지 않는다.** 사용자가 좋다고 한 에셋만 `approve` 한다.
6. **`mesh`.** 승인된 것을 한 번에 준다 — 동시에 만들어진다. 몇 분 걸리므로 백그라운드로 돌린다. 끊겨도 같은 명령을 다시 돌리면
   같은 작업을 이어서 기다린다 (새로 사지 않는다). 메쉬를 받으면 다듬기까지 이어서 한다.
7. **결과를 전한다.** 파일 경로 · 삼각형 수 · 크기 · 든 크레딧. 엔진에서 열어 보는 것은 사용자가 한다.
   크기만 틀렸으면 `finish <이름> --size <미터>` — Meshy 를 다시 부르지 않는다.
8. 사이클 중이면 디자인 절 "필요한 에셋" 표의 "있는가" 칸에 경로를 적는다.

## 화풍

모든 프롬프트에 그대로 붙는 한 문단이다. 영어로, 이 게임의 어떤 에셋에나 맞는 말만 적는다:
그리는 방식(low-poly · hand-painted · flat-shaded …), 색(팔레트의 색 이름이나 값), 디테일의 양, 재질의 느낌, 비율(과장 · 사실).
물건 이름이나 배경 · 조명 · 구도는 넣지 않는다.

```markdown
<!-- asset-style -->
Stylized low-poly game asset, flat-shaded with hand-painted color blocks, chunky exaggerated proportions,
muted earthy palette with one saturated accent color, no fine surface detail, matte materials.
<!-- /asset-style -->
```

화풍 문단은 사용자와 정한다. `docs/DESIGN.md` 의 색 · 톤과 GDD 의 아트 방향에서 초안을 만들고, 시험 에셋 두셋을 `image` 로 뽑아 같이 보며 고친다.
마음에 드는 이미지가 나오면 `kit.config.json` 의 `asset.refs` 에 그 경로를 넣는다 — 그 뒤로 모든 첫 이미지가 그것을 보고 그려진다.
**화풍을 바꾸면 이미 만든 에셋과 어긋난다.** 바꾸기 전에 그렇게 말한다.

## 설정

```json
"asset": {
  "dir": "assets/models",
  "format": "glb",
  "views": ["front", "back"],
  "refs": [],
  "image": { "model": "gpt-image-2.5-flare", "size": "1024x1024", "quality": "medium" },
  "meshy": { "ai_model": "latest", "target_polycount": 5000, "topology": "triangle", "enable_pbr": false }
}
```

- `dir` · `format` — 끝난 모델이 놓이는 곳과 형식. 엔진이 정한다 (init 이 깐 값).
- `views` — 만들 면(`front` · `back` · `left` · `right`, 넷까지). 첫 면이 기준이고 나머지는 그것을 보고 그린다.
  면이 많을수록 뒷모습이 덜 지어내지지만, 면끼리 어긋나면 메쉬가 망가진다. 둘에서 시작한다.
- `image` · `meshy` — 각 API 에 그대로 넘어간다. 다른 값(`texture_resolution` 등)을 더 적어도 된다.
- 에셋마다 다른 것(설명 · 크기 · 삼각형 수)은 `assets/_gen/<이름>/asset.json` 에 있다. 손으로 고쳐도 된다.

`assets/_gen/` 은 저장소에 넣는다 — 기록(`asset.json`)과 이미지가 있어야 "이거랑 비슷하게 하나 더" 가 된다.
받은 그대로의 메쉬(`raw.glb`)는 커서 `.gitignore` 에 넣는다 (다시 `finish` 할 때만 쓴다).

## 처음 한 번 (사용자가 직접)

- **키**: OpenAI 와 Meshy 의 API 키를 저장소 **밖**의 파일에 적는다 (사용자가 터미널에서):

  ```bash
  mkdir -p ~/.config/gamedev-kit && chmod 700 ~/.config/gamedev-kit && ${EDITOR:-nano} ~/.config/gamedev-kit/asset.env
  ```

  파일에는 `OPENAI_API_KEY=...` 와 `MESHY_API_KEY=...` 두 줄. **키를 대화에 붙여 넣지 않게 하고, 받았더라도 저장소의 어떤 파일에도 적지 않는다.**
- **Blender**: `blender` 가 PATH 에 있어야 한다. 없으면 `asset.blender` 에 실행 파일 경로를 적는다.
- 두 서비스 모두 쓴 만큼 돈이 든다. Meshy 는 실패한 작업의 크레딧을 돌려준다. 여러 에셋을 한 번에 돌리기 전에 몇 개인지 말한다.

## 하지 않는 것

- 2D(UI 아이콘 · 텍스처)는 아직 없다. 리깅과 애니메이션도 없다 — 움직이지 않는 소품과 지형물까지다.
- 엔진에 넣은 뒤의 일(충돌체 · 머티리얼 손질 · 씬에 놓기)은 개발 작업이다. 사이클의 작업으로 쓴다.
