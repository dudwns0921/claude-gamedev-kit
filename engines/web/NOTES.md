# Web

Whatever turns out different, add it to your rules (`/gamedev-kit:feedback` — "make this one of my rules").

- **No editor.** `init.py web --create` writes `index.html` (a canvas and one module script), `game/main.js` and `game/version.js` if they are not there.
- Value file: `game/balance.js` (`export const NAME = value; // GDD: <ID>`). Import it as `import * as Balance from "./balance.js"`.
- The game runs on the value file. The balance table (`data/balance.xlsx`) is a view of it: a number changed in the table reaches the game after `bake`, on the next page load.
- `.gitignore`: init appends the lines in `engines/web/gitignore` (`build/`, `node_modules/`).
- Write the headless browser's executable path in the game's CLAUDE.md under "Running".
- **A build to put online** (when the user asks — the kit has no step for it) is `index.html`, `game/` and `assets/` copied into `build/web`, plus any other folder the game loads from.
  The version is in `game/version.js`.
