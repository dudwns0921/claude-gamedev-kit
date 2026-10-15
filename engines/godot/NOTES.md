# Godot

- **Editor (`init.py godot --editor`)**: `GODOT` if set, else `godot` · `godot4` on PATH, else (macOS) `/Applications/Godot*.app/Contents/MacOS/Godot`. The kit's commands call `godot` —
  if it was found only as an app, put it on PATH under that name or write the path in the game's CLAUDE.md under the existing `## This game's rules` heading. Godot has no build modules to check here (export templates are below, under Deploy).
- **Creating the project (`init.py godot --create`)**: Godot has no create command — a folder with a `project.godot` is a project, so init writes a minimal one (`config_version=5`, an empty `config/name`, `config/version="0.1.0"`).
  Set the name in Project Settings (or in the file) and open the project once in the editor so it fills in the rest (`config/features`, the renderer, an icon). `init.py godot --import` runs `godot --headless --path <game root> --import`.
- `.gitignore`: init appends the lines in `engines/godot/gitignore` (`.godot/`, `/android/`, `build/`, `assets/_gen/*/raw.glb`).
- Value file: `game/config/balance.gd` (`class_name Balance`, `static var NAME := value  # GDD: <ID>`).
- A new `class_name` is visible only after the editor scans it — if the editor is closed, run `godot --headless --path . --import` once.
- If you move the value file, change `balance-table.code` in `kit.config.json`.
- **A game installed by an older kit** has code that reads the balance table while the game runs. The kit no longer installs it. To remove it: delete
  `game/config/balance_table.gd` and `game/debug/balance_watch.gd`, remove the `BalanceWatch` line under `[autoload]` in `project.godot`, and in `game/config/balance.gd` delete
  the `Table` and `TABLE_PATH` constants, `_static_init()` and `reload_table()` — the value lines stay as they are. Nothing breaks if it is left in.
- **Deploy**: the Web build goes to the platform in `deploy.platform` in `kit.config.json`; write the game there in `deploy.target` (`deploy.py notes` says what it looks like and what the user does once). In the editor's Project → Export create a preset named **`Web`**
  and download the export templates (once, by the user in the editor). If you name the preset differently, change `deploy.channels.html5.build`.
  The version is read from `config/version` in `project.godot` — set it in Project Settings → Application → Config → Version.
  The export does not create its target folder — the build command makes it first (`mkdir -p build/web && …`).
  Add `build/*` to the preset's exclude filter: a build folder inside the project is packed into the next `.pck`, pictures and all.
  Plain text (a licence `.txt`) is not packed by default — add `*.txt` to the preset's include filter, or put the credits in the game.
  To add a desktop build, add a channel: `"windows": { "build": "godot --headless --path . --export-release Windows build/windows/game.exe", "dir": "build/windows" }`.
- **Assets (asset skill)**: finished models land in `assets/models/<name>.glb`. Godot reads glb as is — if the editor is open it imports when you return to the window,
  if closed import with `godot --headless --path . --import`. 1 unit is 1 m, so `--size` is the in-game size as is. The origin is the center of the bottom.
  The art style paragraph in `docs/DESIGN.md` and the API key are walked through by the asset skill on first use.
- **Sprites (asset skill)**: stills land in `assets/sprites/<name>.png`, animated sheets in `assets/sprites/<name>_<motion>.png`. Cut a sheet with the grid `sprite.py status` prints —
  `Sprite2D` `hframes` · `vframes`, or `SpriteFrames` built from `AtlasTexture` regions for `AnimatedSprite2D`. The last row may be partly empty: play only the frame count given.
- **Sound (asset skill)**: lands in `assets/sounds/<name>.mp3`. Godot reads mp3 as `AudioStreamMP3`. For looping sounds and music
  turn on **Loop** in the import settings (select the file, Import dock → Loop → Reimport) — even if made with `--loop`, with this setting off it plays only once.
- **Video (video skill)**: in-game videos land in `assets/video/<name>.ogv`. Godot plays only Ogg Theora built in (`VideoStreamPlayer` + `VideoStreamTheora`),
  so the skill converts with ffmpeg — the ffmpeg on PATH must have `libtheora` and `libvorbis` (`ffmpeg -encoders | grep theora`).
  The clip is downloaded as mp4 (Higgsfield) and converted to `.ogv` on `place`. Its keys go in `~/.config/gamedev-kit/asset.env`. Playing and skipping the video is game code.
  Not yet checked in a real game with this kit — if playback stutters or seeking is off, add it to your rules (`/gamedev-kit:feedback`).
