# Roblox

파일로 코드를 관리하는 Rojo 프로젝트를 전제로 한다.

- 값 파일: `src/shared/Balance.luau` → ReplicatedStorage.Shared.Balance (`Balance.NAME = 값 -- GDD: <ID>`).
- `src/server/BalanceWatch.server.luau` → ServerScriptService. Studio 에서만 돈다.
- `default.project.json` 에서 `src/shared` 를 ReplicatedStorage 의 `Shared` 로, `src/server` 를 ServerScriptService 아래로 잇는다.
  이름이 다르면 BalanceWatch 의 `WaitForChild("Shared")` 줄을 고친다.
- 밸런싱할 때: 터미널에서 balance-table 스킬의 `serve` 를 켜 두고, Studio 의 Game Settings → Security →
  Allow HTTP Requests 를 켠다. 표를 저장하면 플레이 테스트 중인 게임의 값이 바뀐다.
- 값은 서버에서 덮고 모듈의 속성(Attribute)으로 클라이언트에 복제된다. 클라이언트도 `Balance.NAME` 으로 읽으면 된다.
- Luau 는 정수와 실수를 가리지 않지만, 실수로 쓸 값은 `4.0` 처럼 소수점을 적는다 — 도구가 그것으로 정수/실수를 가린다.
- **이 런타임 틀은 Lune 으로만 돌려 봤다 (Roblox 쪽은 흉내). Studio 에서는 아직이다.** 처음 붙일 때 출력 창의 `[balance]` 줄을 확인한다.
