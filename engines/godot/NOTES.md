# Godot

Whatever turns out different, add it to your rules (`/gamedev-kit:feedback` — "make this one of my rules").

- `.gitignore`: init appends the lines in `engines/godot/gitignore` (`.godot/`, `/android/`, `build/`, `assets/_gen/*/raw.glb`).
- Value file: `game/config/balance.gd` (`class_name Balance`, `static var NAME := value  # GDD: <ID>`). If you move it, change `balance-table.code` in `kit.config.json`.
- **Exporting** (when the user asks for a build — the kit has no step for it): in the editor's Project → Export the user creates a preset (e.g. **`Web`**)
  and downloads the export templates once; then `godot --headless --path . --export-release <preset> <path>`.
  The version is `config/version` in `project.godot` (Project Settings → Application → Config → Version).
  The export does not create its target folder — make it first (`mkdir -p build/web && …`).
  Add `build/*` to the preset's exclude filter: a build folder inside the project is packed into the next `.pck`, pictures and all.
  Plain text (a licence `.txt`) is not packed by default — add `*.txt` to the preset's include filter, or put the credits in the game.
- **Assets (asset skill)**: finished models land in `assets/models/<name>.glb`. Godot reads glb as is (imported as the engine rules' "Running" says). 1 unit is 1 m, so `--size` is the in-game size as is. The origin is the center of the bottom.
  The art style paragraph in `docs/DESIGN.md` and the API key are walked through by the asset skill on first use.
- **Sprites (asset skill)**: stills land in `assets/sprites/<name>.png`, animated sheets in `assets/sprites/<name>_<motion>.png`. Cut a sheet with the grid `sprite.py status` prints —
  `Sprite2D` `hframes` · `vframes`, or `SpriteFrames` built from `AtlasTexture` regions for `AnimatedSprite2D`. The last row may be partly empty: play only the frame count given.
- **Sound (asset skill)**: lands in `assets/sounds/<name>.mp3`. Godot reads mp3 as `AudioStreamMP3`. For looping sounds and music
  turn on **Loop** in the import settings (select the file, Import dock → Loop → Reimport) — even if made with `--loop`, with this setting off it plays only once.
- **Video (video skill)**: in-game videos land in `assets/video/<name>.ogv`. Godot plays only Ogg Theora built in (`VideoStreamPlayer` + `VideoStreamTheora`),
  so the skill converts with ffmpeg — the ffmpeg on PATH must have `libtheora` and `libvorbis` (`ffmpeg -encoders | grep theora`).
  The clip is downloaded as mp4 (Higgsfield) and converted to `.ogv` on `place`. Its keys go in `~/.config/gamedev-kit/asset.env`. Playing and skipping the video is game code.
