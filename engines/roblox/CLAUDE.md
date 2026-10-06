
## 역할 분담 (Roblox)

- **사용자**: 에셋을 만들고, Studio 에서 플레이 버튼을 누르고 화면을 본다. 코드는 손대지 않는다.
- **Claude**: 코드 · 설정 · 문서 전부. 파일로 쓰면 Rojo 가 Studio 로 옮긴다.

Claude 는 Studio 를 직접 다루지 못한다. 화면으로만 확인되는 것은 사용자에게 무엇을 볼지 구체적으로 부탁한다.
Studio 없이 확인할 수 있는 것은 Lune 테스트로 만든다.

**Studio 출력 창은 사용자에게 묻지 말고 로그 파일에서 읽는다.** `~/Library/Logs/Roblox/` 의 가장 새 `*_Studio_*_last.log`:

```bash
f="$(ls -t ~/Library/Logs/Roblox/*_Studio_*_last.log | head -1)"; grep -a "CreatorOutput\|CreatorError" "$f" | tail -40
```

스크립트의 `print` 는 `[FLog::CreatorOutput]`, 오류는 `[FLog::CreatorError]` 줄이다 (Rojo 플러그인의 오류도 여기 나온다). 시각은 UTC 다.

## 실행

```bash
rojo build -o <게임>.rbxlx      # 플레이스 파일. Studio 는 폴더가 아니라 이 파일을 연다 (처음 한 번, 프로젝트 파일을 바꿨을 때)
rojo serve                      # Studio 의 Rojo 플러그인에서 Connect — 파일이 Studio 로 실시간 반영된다
```

밸런싱할 때는 balance-table 스킬의 `serve` 도 켠다 (표 → 플레이 테스트 중인 게임).
숫자는 플레이 중에 바뀌고, 코드는 플레이를 껐다 켜야 바뀐다.

## 검증

```bash
selene src                              # 린트 (오류 0 이어야 한다)
stylua --check src tests                # 포맷
rojo build -o /tmp/place.rbxlx          # 프로젝트 파일 · 경로가 맞는지
lune run tests/balance_runtime.luau http://127.0.0.1:8765/balance   # 밸런스 런타임 — serve 를 켜고, 표에 PLAYER_HP 130 · PLAYER_WALK_SPEED 12.5 를 넣고
```

## 구조

```
default.project.json   Rojo — 파일과 Studio 트리의 대응
src/shared/            → ReplicatedStorage.Shared   서버 · 클라이언트가 같이 쓴다 (Balance 등)
src/server/            → ServerScriptService.Server 서버 스크립트 (*.server.luau)
src/client/            → StarterPlayerScripts.Client 클라이언트 스크립트 (*.client.luau)
data/                  balance.xlsx — 밸런스 표. 게임에는 들어가지 않는다
docs/                  GDD.md · playtest/
tests/                 Lune 으로 도는 테스트
kit.config.json        gamedev-kit 설정 (엔진: roblox)
```

## 함정

1. **Roblox 는 서버와 클라이언트가 따로 돈다.** 게임 규칙과 값 판정은 서버에서 한다. 클라이언트가 보낸 값은 믿지 않는다.
2. **`local x = Balance.NAME` 으로 받아 두지 않는다.** 표가 바뀌어도 옛 값을 쥐고 있다. 쓸 때마다 `Balance.NAME`.
   엔진에 한 번 넣어 두는 값(`Humanoid.WalkSpeed` 등)은 `Balance.Changed` 를 듣고 다시 넣는다:

   ```lua
   Balance.Changed:Connect(function(name)
   	if name == "PLAYER_WALK_SPEED" then
   		humanoid.WalkSpeed = Balance.PLAYER_WALK_SPEED
   	end
   end)
   ```
3. **Studio 에서 고친 스크립트는 Rojo 가 덮어쓴다.** 코드는 파일에서만 고친다.
4. **새 스크립트가 Studio 에 안 보이면 Rojo 의 스크립트 주입 권한을 본다.** 로그에 `Plugin "Rojo" was denied script injection permission`
   이 있으면 그 뒤로 동기화가 멈춘 것이다. 사용자가 권한을 허용하고 Rojo 를 다시 Connect 해야 한다.
5. **테스트가 표를 고쳤으면 되돌린다.** 시험용 값이 든 표를 커밋하지 않는다 — 커밋 전에 balance-table 의 `check`.
