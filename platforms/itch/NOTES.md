# itch.io

What the user does once. Claude does none of it for them.

- **Create the game's page** on itch.io (Dashboard → Create new project). Its address gives the target:
  for `https://user.itch.io/game`, write `"target": "user/game"` in `deploy` in `kit.config.json`.
- **Install butler** (https://itch.io/docs/butler/) and put it on PATH. If it is somewhere else, set the environment variable `BUTLER` to the executable.
- **Log in**: `butler login` in a terminal — it opens a browser. In CI, set `BUTLER_API_KEY` instead; do not write its value in the repository.
- **The channel's name is the name on itch.io.** A name containing `win`, `windows`, `linux`, `mac`, `osx` or `android` is tagged with that system.
  Upload a browser game as `html5`, and after the first upload turn on "This file will be played in the browser" for it in the page's settings (Edit game → Uploads).
- A channel that is new to the page appears as a new upload — set what it is (system · playable in browser) there once. Later uploads to the same channel replace it.
- The version shown on the page is the one `deploy.py version` prints.
