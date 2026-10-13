/// The one place for balance numbers. It pairs one to one with the GDD's Appendix A.1 — the marker at the end of each line is the pairing.
///
/// The game runs on the values below. The balance table (data/balance.xlsx) is a view of them, kept in step with this file:
/// it is rewritten when a value here changes, and `balance_table.py bake` writes a number changed in the table back here.
/// static, not const: a const is copied into the assembly that uses it, so the old value stays until that assembly is recompiled.
public static class Balance
{
    /// Example values — change them to fit the game. One number per line, the marker at the end of the line. Write a float with its decimal point, as in `4.0f`.
    public static int PLAYER_HP = 100; // GDD: BAL.PLAYER.HP
    /// Walking speed (m/s)
    public static float PLAYER_WALK_SPEED = 4.0f; // GDD: BAL.PLAYER.WALK_SPEED
    public static int COIN_VALUE = 5; // GDD: BAL.COIN.VALUE
}
