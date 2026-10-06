# Unity

도구(gdd-sync · 표 export/bake/check)만 지원한다. 실행 중에 표를 다시 읽는 런타임 틀은 아직 없다.

- 값 파일: `Assets/Scripts/Config/Balance.cs` (`public static float NAME = 4.0f; // GDD: <ID>`).
- 실수는 `4.0f` 처럼 소수점을 적는다.
- 런타임이 필요하면 에디터에서 `data/balance.xlsx` 를 직접 읽거나(zip + XML) balance-table 의 `serve` JSON 을 가져온다.
