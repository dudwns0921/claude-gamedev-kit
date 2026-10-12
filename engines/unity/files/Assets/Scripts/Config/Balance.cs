/// 밸런스 수치의 유일한 자리. GDD 부록 A.1 과 1:1 로 대응한다 — 각 줄 끝의 표식이 그 짝이다.
///
/// 값은 밸런스 표(data/balance.xlsx)에서 고치고 `balance_table.py bake` 가 아래 숫자를 적는다.
/// 실행 중에 표를 다시 읽는 틀은 아직 없다 — 구운 뒤 다시 컴파일된 값으로 돈다.
/// const 가 아니라 static 이다: const 는 쓰는 쪽 어셈블리에 값이 박혀서, 그쪽이 다시 컴파일되지 않으면 옛 값이 남는다.
public static class Balance
{
    /// 예시 값이다 — 게임에 맞게 바꾼다. 한 줄에 숫자 하나, 줄 끝에 표식. 실수는 `4.0f` 처럼 소수점을 적는다.
    public static int PLAYER_HP = 100; // GDD: BAL.PLAYER.HP
    /// 걷는 속도 (m/s)
    public static float PLAYER_WALK_SPEED = 4.0f; // GDD: BAL.PLAYER.WALK_SPEED
    public static int COIN_VALUE = 5; // GDD: BAL.COIN.VALUE
}
