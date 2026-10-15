<p align="center">
  <img src="assets/banner.svg" alt="claude-gamedev-kit — goal, spec, design, plan, build, play" width="860">
</p>

**A [Claude Code](https://code.claude.com) plugin for making games.**
Agents make your game one cycle at a time — spec, design, build. You decide, from a dashboard that shows where every game stands.

[Landing page](https://gamedev-kit-site.vercel.app)

## Quick start

In Claude Code, in your game's folder (an empty one is fine):

```
/plugin marketplace add dudwns0921/claude-gamedev-kit
/plugin install gamedev-kit@claude-gamedev-kit
```

Restart Claude Code, and that's it — there is nothing to learn. Say what you want, and the kit's skills step in:

```
I want to make a cozy farming game      → asks where it will be played, picks the engine, sets it up, then writes the GDD with you
this time, let's add a shop             → one cycle: spec, design, build; what is yours to decide waits on the dashboard
I played it — the prices are unreadable → finds the causes and fixes them
```

You need Claude Code and Python 3.9 or later; the dashboard needs Node.js; Godot and Unity need their editor.

### Engines

**Godot**, **Unity** and plain **web** (HTML and JavaScript, no editor). The kit asks where your game will be played — a phone, a computer, the browser — and picks the engine with you.
The engine decides how the kit reads your code, where assets go, and which traps it warns the agents about; the cycle and the dashboard are the same for all three.

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

Every step also has a slash command — `/gamedev-kit:init`, `start`, `cycle`, `playtest`, `board`, `gdd-sync`, `asset`, … — if you would rather type one.

Models, sprites, sounds and clips can be made through outside services with your own API keys — or not at all: a cycle runs on placeholders, and any file you make and put in its place counts.
The kit covers making the game; when it is ready to ship, ask Claude Code to build and upload it.

## Updating

```bash
claude plugin marketplace update claude-gamedev-kit
claude plugin update gamedev-kit@claude-gamedev-kit
```

Run both in the game's folder, then restart the game's Claude session.

## License

MIT
