
## Roles (web)

- **User**: makes assets and plays the game in a browser. Does not touch code or settings.
- **Claude**: all code · pages · settings · documents. The game is plain HTML and JavaScript modules — no framework and no build step unless a cycle decides on one.

## Running

Modules do not load from `file://`, so the game is served, from the game root:

```bash
python3 -m http.server <port>      # then http://localhost:<port>
```

Take a port nothing else is using. Another project — or another agent working on this one — may already be serving on the usual one,
and a check that reads that page instead passes or fails for the wrong reason: confirm the page is this game's before trusting what it shows.

A headless browser is used to verify. Its executable lives in a different place on each machine — write the path below, so it is not passed again to every agent.

## Verification

Everything that can be verified without a screen becomes a test. Run them, and look at the play route's pictures yourself — the build verifies what it built; the user is not asked to "try it and tell me" (only the one thing a person alone can judge goes to them).

- **Rules without the page.** Keep rulings (does it hit · how many points · when it ends) in modules that touch neither `document` nor `window`,
  and test those with `node --test "tests/*.test.js"` — it finishes within a second. (Give it the files, not the folder: `node --test tests/` takes the folder for a module and fails.)
- **Flow by smoke run.** Give the game a `?smoke` mode: it steps a fixed number of frames with scripted input, without waiting for real time, and writes the resulting
  state as JSON into `<pre id="smoke">`. Read it with `<browser> --headless --virtual-time-budget=5000 --dump-dom "http://localhost:<port>/?smoke"`.
- **Screen (color · layout · HUD) by capture.** `<browser> --headless --screenshot=<file> --window-size=<w>,<h> --virtual-time-budget=3000 "<url>"`. Claude reads the captured image.
- **Play route** (the board skill's): the game sets a stop's state from the address (`?stop=<id>`), and a small script shoots each stop that way into `<folder>/<id>.jpg`; its command is `board.play.run`.
- Stop the server you started when the check is done.

## Pitfalls (web)

1. **A build to put online** (when the user asks) is `index.html`, `game/` and `assets/` copied into one folder, plus any other folder the game loads from — a module loaded from a folder left out fails only online.
