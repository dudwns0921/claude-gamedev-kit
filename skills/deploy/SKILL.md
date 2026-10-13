---
name: deploy
description: >-
  Builds the game and gets the build to the platform it is for — check, build, show what goes where, upload on approval, status (what is uploaded).
  The deploy section of kit.config.json names the platform, the target and the build command; what differs per platform is read from the kit's
  platforms/ folder. Where the platform has an upload command the deployer agent uploads; where it has none, the user is told which file to upload and where.
  Use when the user says "배포해줘" ("deploy it"), "빌드 올려" ("upload the build"), "스토어에 올려줘" ("put it on the store"),
  "올라갔어?" ("is it up?"), "release it", "ship it", or mentions a new version or what is uploaded now; when first filling in the deploy section.
  Not part of a cycle — a build goes out when the user asks, usually after several cycles.
---

# deploy

Uploading is hard to undo — an uploaded build stays with whoever downloaded it. So it is split in two: **prepare** (check, build, preview what will go up)
runs without asking; **push** runs only after the user has said to upload this build.

The order is the same on every platform: **check → build → show what goes where → the user approves → upload.**
What differs per platform — the tool, the login, the form of the target, the upload command or its absence — is in the kit's `platforms/<platform>/`,
and `deploy.py` reads it. Do not write a platform's commands yourself; `deploy.py notes` prints what the user does once on the configured platform,
and a failing `check` prints the same under the reasons.

| Call | Meaning |
|---|---|
| `/gamedev-kit:deploy` | Prepare, show what goes where, and upload on approval |
| `/gamedev-kit:deploy prepare [channel]` | Prepare only |
| `/gamedev-kit:deploy push [channel]` | Upload an already prepared build (if the user said this, that is the approval) |
| `/gamedev-kit:deploy status` | What the platform holds now |

## Procedure

1. **Check the config.** If `kit.config.json` has no `deploy` section, or `platform` or `target` is empty, fill it with the user as in "Config" below —
   run `deploy.py notes` and relay what the user does first (create the page or the app, log in). Do not invent values.
2. **What must hold before deploying.** If the game uses a balance table, the balance-table skill's `check` must pass — a number changed in the table and not baked is not in the build.
   If they differ, ask the user whether to bake. If there are uncommitted changes, ask whether to commit (the script stops anyway).
3. **Call the `gamedev-kit:deployer` agent with `prepare`.** Pass: the script path `${CLAUDE_SKILL_DIR}/scripts/deploy.py`, the mode, the channel.
4. **Show what came back as is and ask** — platform, target, channel, version, folder size. If blocked, relay the reason and stop.
   If the build is broken, ask whether to fix it. Do not add the check-skipping flag (`--dirty`) here — only when the user says to.
5. **On approval, call the agent with `push`.** When done, report the version and what the script said to look at.
   **When the platform has no upload command** (the prepare result says `uploaded by the user`), nothing leaves this machine and there is nothing to approve:
   the last step is relaying, as is, the instruction the script printed — which file the user uploads and where.

Run `status` and `notes` directly, without an agent:

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/deploy.py" status
python3 "${CLAUDE_SKILL_DIR}/scripts/deploy.py" notes
```

## Config

```json
"deploy": {
  "platform": "<a folder of the kit's platforms/>",
  "target": "<the game on that platform>",
  "version": { "file": "<file holding the version>", "regex": "<group 1 is the version>" },
  "pre": ["command that must pass before uploading"],
  "channels": {
    "<channel>": { "build": "build command", "dir": "build/out", "must": "a file that must be in dir" }
  }
}
```

- `platform` — where the build goes. init writes the one the engine's build is for; `deploy.py check` lists the ones there are when it is empty or unknown.
- `target` — the game on that platform. Its form is the platform's (`deploy.py notes` shows it), and **the user creates it there first.**
- `channels` — one build each. If `build` is empty, nothing is built and what is in `dir` goes up. `must` is a file that must exist in that folder.
  What the channel's name means on the platform is in its notes.
- `version` — the file holding the version and the regex that captures it. If left empty, the commit hash is the version.
- `pre` — commands such as tests and lint whose failure must block the upload.
- A config from an older kit that names its target under the platform's own key, with no `platform`, is still read. Leave it as it is unless the user asks.

The build command is the engine's business: it is in the `kit.config.json` installed by init, and what the engine needs first (export presets, signing)
is in the guidance init printed at the end (the engine's NOTES).

## Login

The user logs in to the platform themselves, and creates the page or the app there. Claude does not do it for them, and no key or password is written in the repository.
How is in the platform's notes (`deploy.py notes`).
