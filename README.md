<p align="center">
  <img src="assets/banner.svg" alt="claude-gamedev-kit — goal, spec, design, plan, build, play" width="860">
</p>

**A [Claude Code](https://code.claude.com) plugin for making games.**
Agents make your game one cycle at a time — spec, design, build. You decide, from a dashboard that shows where every game stands.

## Quick start

You need:

- [Claude Code](https://code.claude.com)
- [Python](https://www.python.org/downloads/) 3.9 or later
- [Node.js](https://nodejs.org) — for the dashboard
- The editor of the engine you make the game with (below) — a plain web game needs none
- Optional, to have assets made: an API key of a service below, as a line in `~/.config/gamedev-kit/asset.env` — without one a cycle runs on placeholders, and any file you put in its place counts

In your game's folder (an empty one is fine):

```bash
claude plugin marketplace add dudwns0921/claude-gamedev-kit
claude plugin install gamedev-kit@claude-gamedev-kit --scope project
```

Installed for the project, the kit stays with the game: anyone who opens the game's folder in Claude Code gets the same kit.
Then start Claude Code there and say what you want — there is nothing to learn:

```
I want to make a cozy farming game      → asks where it will be played, picks the engine, sets it up, then writes the GDD with you
this time, let's add a shop             → one cycle: spec, design, build; what is yours to decide waits on the dashboard
I played it — the prices are unreadable → finds the causes and fixes them
```

Every step also has a slash command — `/gamedev-kit:init`, `start`, `cycle`, `playtest`, `board`, … — if you would rather type one.

### Engines games have been made with

- [Godot](https://godotengine.org/download)
- [Unity](https://unity.com/download)
- Web — plain HTML and JavaScript, no editor

### Services assets have been made with

| Makes | Service | Line in `asset.env` |
|---|---|---|
| 3D models | [OpenAI](https://platform.openai.com/api-keys) (the picture) + [Meshy](https://www.meshy.ai) (the mesh) | `OPENAI_API_KEY=…` · `MESHY_API_KEY=…` |
| Sprites | [Ludo](https://ludo.ai) | `LUDO_API_KEY=…` |
| Sounds and music | [ElevenLabs](https://elevenlabs.io) | `ELEVENLABS_API_KEY=…` |
| Clips (trailers, cutscenes) | [Higgsfield](https://higgsfield.ai) | `HF_API_KEY_ID=…` · `HF_API_KEY_SECRET=…` |

## Why use it

Making a game with AI is easy. The trouble starts when making it takes weeks: you lose track of where it stands and what waits on you, the design and the code drift apart, and what you learned in the last game is gone by the next.

### See where every game stands — and decide there

<p align="center"><picture><source media="(prefers-color-scheme: dark)" srcset="assets/dashboard-dark.png"><img src="assets/dashboard-light.png" alt="The dashboard of a sample game: stage cards in play order with completion rings and meters for function, art, sound and verification; beside them the current cycle, the undecided questions and the cycles so far" width="860"></picture></p>

A dashboard on your machine shows each game as the player meets it, stage by stage — what is done, a placeholder, not made, or a problem. Every question the agents have for you is a decision there, with the pictures (or a clip of play) to judge it by. Pick an answer and the game's Claude session picks it up; the top bar always says whether that session is listening.

### The design and the code stay one thing

<p align="center"><img src="assets/sync.svg" alt="A GDD sync table beside code: one row synced, one mismatched — the GDD says 8 and the code says 10 — and one with no marker in code yet" width="860"></p>

Every number and rule in the GDD has an ID, and the code that implements it carries the same ID. The kit finds what disagrees and what is not built, and aligns the side you name. The balance numbers are one Excel sheet that follows the code.

### Every game you make leaves the next one better

<p align="center"><img src="assets/compounds.svg" alt="Three games in a row; the stack of your own rules under each one grows, with what came before carried over" width="860"></p>

What tripped you becomes one of your rules, loaded into every game you make next. Once you say so, rules go to this repository as issues, and the ones that hold for anyone become the kit's rules for everybody.

## License

MIT
