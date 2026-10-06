# Unity

도구(gdd-sync · 표 export/bake/check)만 지원한다. 실행 중에 표를 다시 읽는 런타임 틀은 아직 없다.

- 값 파일: `Assets/Scripts/Config/Balance.cs` (`public static float NAME = 4.0f; // GDD: <ID>`).
- 실수는 `4.0f` 처럼 소수점을 적는다.
- 런타임이 필요하면 에디터에서 `data/balance.xlsx` 를 직접 읽거나(zip + XML) balance-table 의 `serve` JSON 을 가져온다.
- **배포(itch.io)**: 빌드 명령은 비워 두었다 — 에디터에서 WebGL 로 `build/web` 에 빌드하면 deploy 스킬이 그 폴더를 올린다.
  명령으로 빌드하려면 `-executeMethod` 로 부를 에디터 스크립트를 만들고 `kit.config.json` 의 `deploy.channels.html5.build` 에 적는다.
  버전은 `ProjectSettings.asset` 의 `bundleVersion` 에서 읽는다.
