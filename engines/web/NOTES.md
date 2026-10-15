# Web

Whatever turns out different, add it to your rules (`/gamedev-kit:feedback` — "make this one of my rules").

- **No editor.** `init.py web --create` writes `index.html` (a canvas and one module script), `game/main.js` and `game/version.js` if they are not there.
- Value file: `game/balance.js` (`export const NAME = value; // GDD: <ID>`). Import it as `import * as Balance from "./balance.js"`.
- The game runs on the value file. The balance table (`data/balance.xlsx`) is a view of it: a number changed in the table reaches the game after `bake`, on the next page load.
- `.gitignore`: init appends the lines in `engines/web/gitignore` (`build/`, `node_modules/`).
- Write the headless browser's executable path in the game's CLAUDE.md under "Running".
- **Deploy**: the build goes to the platform in `deploy.platform` in `kit.config.json`; write the game there in `deploy.target` (`deploy.py notes` says what it looks like and what the user does once). The `html5` channel copies `index.html`, `game/` and `assets/` into `build/web` —
  if the game loads anything from another folder, add it to that channel's `build` command. The version is read from `game/version.js`.
