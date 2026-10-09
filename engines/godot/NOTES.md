# Godot

- Value file: `game/config/balance.gd` (`class_name Balance`, `static var NAME := value  # GDD: <ID>`).
- Register `game/debug/balance_watch.gd` as the autoload `BalanceWatch`. In release builds it removes itself.
- A new `class_name` is visible only after the editor scans it — if the editor is closed, run `godot --headless --path . --import` once.
- Add `data/*` to the export preset's `exclude_filter`. So the table does not go into release builds.
- If you move the value file, change both `balance-table.code` in `kit.config.json` and the `res://` path inside balance.gd.
- **Deploy (itch.io)**: write `user/game` in `deploy.itch` in `kit.config.json`. In the editor's Project → Export create a preset named **`Web`**
  and download the export templates (once, by the user in the editor). If you name the preset differently, change `deploy.channels.html5.build`.
  The version is read from `config/version` in `project.godot` — set it in Project Settings → Application → Config → Version. Add `build/` to `.gitignore`.
  To add a desktop build, add a channel: `"windows": { "build": "godot --headless --path . --export-release Windows build/windows/game.exe", "dir": "build/windows" }`.
- **Assets (asset skill)**: finished models land in `assets/models/<name>.glb`. Godot reads glb as is — if the editor is open it imports when you return to the window,
  if closed import with `godot --headless --path . --import`. 1 unit is 1 m, so `--size` is the in-game size as is. The origin is the center of the bottom.
  Add `assets/_gen/*/raw.glb` to `.gitignore`. The art style paragraph in `docs/DESIGN.md` and the API key are walked through by the asset skill on first use.
- **Sound (asset skill)**: lands in `assets/sounds/<name>.mp3`. Godot reads mp3 as `AudioStreamMP3`. For looping sounds and music
  turn on **Loop** in the import settings (select the file, Import dock → Loop → Reimport) — even if made with `--loop`, with this setting off it plays only once.
- **Video (video skill)**: in-game videos land in `assets/video/<name>.ogv`. Godot plays only Ogg Theora built in (`VideoStreamPlayer` + `VideoStreamTheora`),
  so the skill converts with ffmpeg — the ffmpeg on PATH must have `libtheora` and `libvorbis` (`ffmpeg -encoders | grep theora`).
  The clip is downloaded as mp4 (Higgsfield) and converted to `.ogv` on `place`. Its keys go in `~/.config/gamedev-kit/asset.env`. Playing and skipping the video is game code.
  Not yet checked in a real game with this kit — if playback stutters or seeking is off, write it in `docs/kit-feedback.md`.
