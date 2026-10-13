class_name Balance
extends RefCounted
## The one place for balance numbers. It pairs one to one with the GDD's Appendix A.1 — the `# GDD:` marker on each line is the pairing.
##
## The game runs on the values below. The balance table (data/balance.xlsx) is a view of them, kept in step with this file:
## it is rewritten when a value here changes, and `balance_table.py bake` writes a number changed in the table back here.
## Callers write `Balance.NAME`.

## Example values — change them to fit the game. One number per line, the marker at the end of the line.
static var PLAYER_HP := 100  # GDD: BAL.PLAYER.HP
## Walking speed (m/s)
static var PLAYER_WALK_SPEED := 4.0  # GDD: BAL.PLAYER.WALK_SPEED
static var COIN_VALUE := 5  # GDD: BAL.COIN.VALUE
