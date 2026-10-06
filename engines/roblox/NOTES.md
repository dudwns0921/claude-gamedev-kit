# Roblox — 이어서 할 일

Rojo 프로젝트를 전제로 한다. 아래에서 아직 안 된 것을 순서대로 한다.

## 1. 준비물

- **사용자가 직접**: Roblox 계정 · Roblox Studio 설치와 로그인 · Studio 의 Toolbox(Creator Store)에서 **Rojo 플러그인** 설치.
  계정을 만들거나 로그인하는 일은 Claude 가 대신 하지 않는다.
- **Claude 가** (사용자에게 설치해도 되는지 묻고): `brew install rojo lune stylua selene`

## 2. Rojo 프로젝트

`default.project.json` 이 없으면 `rojo init --kind place .` 로 만든다. 그다음:

- `rojo init` 이 넣은 예시 스크립트(`src/server/init.server.luau` · `src/shared/Hello.luau` · `src/client/init.client.luau`)를 지운다.
  `init.server.luau` 가 있으면 `Server` 가 폴더가 아니라 스크립트가 된다.
- `default.project.json` 의 `tree` 에 HTTP 허용을 넣는다 — 표 서버에 닿으려면 필요하고, 여기 넣어 두면 Studio 에서 손으로 켜지 않아도 된다:

  ```json
  "HttpService": { "$properties": { "HttpEnabled": true } },
  ```

- 경로는 틀과 같아야 한다: `src/shared` → `ReplicatedStorage.Shared`, `src/server` → `ServerScriptService.Server` (rojo init 의 기본값이다).
  다르게 두려면 `BalanceWatch.server.luau` 의 `WaitForChild("Shared")` 줄을 고친다.
- 기본 브랜치가 `master` 로 만들어졌으면 `main` 으로 바꾼다.

## 3. Studio 에 연결 (사용자와 같이)

1. `rojo build -o <게임>.rbxlx` 로 플레이스 파일을 만든다 (.gitignore 에 이미 들어 있다). Studio 는 폴더를 열지 못한다 — 이 파일을 연다.
2. `rojo serve` 를 켠다 (백그라운드).
3. 사용자: 플레이스 파일을 열고 → Plugins 탭 → Rojo → **Connect** → Accept.
   스크립트 주입 권한을 물으면 **허용**. 거부되면 새 스크립트가 들어가지 않는다.
4. 탐색기에 `ReplicatedStorage > Shared > Balance` 가 보이면 됐다.

## 4. 밸런스 표가 닿는지 확인

1. balance-table 스킬의 `export` 로 표를 만들고 `serve` 를 켠다 (백그라운드).
2. 사용자: 플레이를 누른 채 `data/balance.xlsx` 의 값 하나를 바꿔 저장한다.
3. Studio 로그에서 `[balance] 이름  전 → 후` 를 찾는다 (로그 읽는 법은 CLAUDE.md). 사용자에게 출력 창을 붙여 달라고 하지 않는다.
4. 끝나면 사용자에게 엑셀을 저장하지 않고 닫아 달라고 하고, `export` 로 표를 코드 값으로 되돌린다.

## 알아둘 것

- 값 파일: `src/shared/Balance.luau` (`Balance.NAME = 값 -- GDD: <ID>`). 값은 서버에서 덮고 모듈의 속성(Attribute)으로
  클라이언트에 복제된다 — 클라이언트도 `Balance.NAME` 으로 읽으면 된다.
- Luau 는 정수와 실수를 가리지 않지만, 실수로 쓸 값은 `4.0` 처럼 소수점을 적는다 — 도구가 그것으로 정수/실수를 가린다.
- `tests/balance_runtime.luau` 는 Studio 없이 Lune 으로 런타임을 돌린다 (Roblox 쪽은 흉내). Studio 에서는 0.741 에서 확인했다 (2026-10-06).
- 맵을 Studio 에서 손으로 만들면 플레이스 파일에만 남는다. 그렇게 가기로 하면 플레이스 파일을 .gitignore 에서 빼고 커밋한다.
