// The one place for balance numbers. It pairs one to one with the GDD's Appendix A.1 — the `// GDD:` marker on each line is the pairing.
//
// Values are edited in the balance table (data/balance.xlsx); `balance_table.py bake` writes them here. The game runs on these baked values.
// One number per line, the marker at the end of the line. Callers: `import * as Balance from "./balance.js"` → `Balance.NAME`.

// Example values — change them to fit the game.
export const PLAYER_HP = 100; // GDD: BAL.PLAYER.HP
/// Walking speed (px/s)
export const PLAYER_WALK_SPEED = 4.0; // GDD: BAL.PLAYER.WALK_SPEED
export const COIN_VALUE = 5; // GDD: BAL.COIN.VALUE
