---
name: deploy
description: >-
  Builds the game, uploads it to itch.io with butler, and drafts the itch.io devlog for that build — check, build, push,
  status (what is uploaded), devlog. The deploy section of kit.config.json sets the build command and the target. The deployer agent uploads;
  the devlog-writer agent drafts the devlog. There is no API for posting a devlog, so the user pastes it.
  Use when the user says "배포해줘", "itch 에 올려줘", "빌드 올려", "devlog 써줘", "올라갔어?", or mentions butler, a new version, release notes,
  or what is on itch now; when the cycle skill reaches the deploy step; when first filling in the deploy section.
---

# deploy

Uploading is hard to undo — an uploaded build stays with whoever downloaded it. So it is split in two: **prepare** (check, build, preview what will go up)
runs without asking; **push** runs only after the user has said to upload this build.

| Call | Meaning |
|---|---|
| `/gamedev-kit:deploy` | Prepare, show what goes where, and upload on approval |
| `/gamedev-kit:deploy prepare [channel]` | Prepare only |
| `/gamedev-kit:deploy push [channel]` | Upload an already prepared build (if the user said this, that is the approval) |
| `/gamedev-kit:deploy status` | Channels and builds itch.io has |
| `/gamedev-kit:deploy devlog` | Only draft the devlog for an already uploaded build |

## Procedure

1. **Check the config.** If `kit.config.json` has no `deploy` section or `itch` is empty, fill it with the user as in "Config" below. Do not invent values.
2. **What must hold before deploying.** If the game uses a balance table, the balance-table skill's `check` must pass — the deploy build uses only baked values.
   If they differ, ask the user whether to bake. If there are uncommitted changes, ask whether to commit (the script stops anyway).
3. **Call the `gamedev-kit:deployer` agent with `prepare`.** Pass: the script path `${CLAUDE_SKILL_DIR}/scripts/deploy.py`, the mode, the channel.
4. **Show what came back as is and ask** — target (`user/game:channel`), version, folder size. If blocked, relay the reason and stop.
   If the build is broken, ask whether to fix it. Do not add the check-skipping flag (`--dirty`) here — only when the user says to.
5. **On approval, call the agent with `push`.** When done, report the address (`https://<user>.itch.io/<game>`) and the version.
6. **Devlog draft.** Once the build is uploaded, call the `gamedev-kit:devlog-writer` agent. Pass: what to write about (the cycle document path,
   or if none, the commit range since the last deploy), the itch.io address, the version, the uploaded channel. Do not compose sentences yourself to pass along.
   Show the returned draft (`docs/devlog/<date>-<version>.md`) **as is, field by field** — Title, Post type, Attachments, Tags, Languages, Cover image, Content.
   The user copies it top to bottom into itch.io dashboard → game → Devlog → new post. **You cannot post this.**
   The content is written unformatted — bold and headings are done in the editor. The user takes the Cover image and screenshots.
   If asked for changes, edit the draft. If the user gives the address of the posted devlog, add one line `게시: <address>` at the end of the draft.
   If they decide not to post, keep the draft and note that — the deploy is complete without a devlog.
7. During a cycle, write the date, version, channel, commit, and devlog draft path (and posted address) in the "배포" section of the cycle document.

Run `status` directly, without an agent:

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/deploy.py" status
```

## Config

```json
"deploy": {
  "itch": "user/game",
  "version": { "file": "project.godot", "regex": "config/version=\"([^\"]+)\"" },
  "pre": ["command that must pass before uploading"],
  "channels": {
    "html5": { "build": "build command", "dir": "build/web", "must": "index.html" }
  }
}
```

- `itch` — the two parts of the itch.io address. For `https://user.itch.io/game` it is `user/game`. **The user creates the game page on itch.io first.**
- `channels` — the name becomes the itch.io channel. If the name contains `win`, `windows`, `linux`, `mac`, `osx` or `android`,
  itch.io tags it with that platform. Upload browser games as `html5`, and **the user turns on "play in browser" once in the page settings.**
  If `build` is empty, nothing is built and what is in `dir` is uploaded. `must` is a file that must exist in that folder.
- `version` — the file holding the version and the regex that captures it. If left empty, the commit hash is the version.
- `pre` — commands such as tests and lint whose failure must block the upload.

Engine-specific build commands are in the `kit.config.json` installed by init. If the engine needs more preparation, such as export presets,
it is in the guidance init printed at the end (the engine's NOTES).

## Login

`butler login` opens a browser and the user does it themselves. Claude does not do it for them. In CI, use the `BUTLER_API_KEY` environment variable —
do not write its value in the repository.
