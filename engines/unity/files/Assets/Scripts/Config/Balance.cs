/// The one place for balance numbers. It pairs one to one with the GDD's Appendix A.1 — the marker at the end of each line is the pairing.
///
/// Values are edited in the balance table (data/balance.xlsx) and `balance_table.py bake` writes the numbers below.
/// Nothing re-reads the table while the game runs — it runs on the values compiled after a bake.
/// static, not const: a const is copied into the assembly that uses it, so the old value stays until that assembly is recompiled.
public static class Balance
{
    /// Example values — change them to fit the game. One number per line, the marker at the end of the line. Write a float with its decimal point, as in `4.0f`.
    public static int PLAYER_HP = 100; // GDD: BAL.PLAYER.HP
    /// Walking speed (m/s)
    public static float PLAYER_WALK_SPEED = 4.0f; // GDD: BAL.PLAYER.WALK_SPEED
    public static int COIN_VALUE = 5; // GDD: BAL.COIN.VALUE
}
