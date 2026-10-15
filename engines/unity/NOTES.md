# Unity

Whatever turns out different, add it to your rules (`/gamedev-kit:feedback` — "make this one of my rules").

- Value file: `Assets/Scripts/Config/Balance.cs` (`public static float NAME = 4.0f; // GDD: <ID>`). Write floats with a decimal point and `f`.
  The game runs on this file — after `bake`, Unity recompiles and the game runs on the new values.
- `.gitignore`: init appends the lines in `engines/unity/gitignore` (`Library/`, `Temp/`, `Logs/`, `obj/`, `UserSettings/`, `build/`, `*.csproj`, `*.sln`, `*.slnx`, `*.keystore`, `*.jks`, `assets/_gen/*/raw.glb`).
- **Unity's own plugin for Claude Code, if used**: install it for this project, not for the user (`claude plugin install unity@claude-plugins-official --scope project`, run in the game root) —
  it is then written in `.claude/settings.json`, which is committed, so every machine that builds this game has the skills the plan names on a task's "Skills" line.
- **A store build** (when the user asks — the kit has no step for it): the package name (Player Settings → Identification, `com.<name>.<game>`) cannot change after the first upload,
  and the upload keystore (Player Settings → Publishing Settings → Keystore Manager) stays **outside the repo, with a backup** — without it no update can be uploaded.
- **Assets (asset skill)**: finished models land in `Assets/Models/<name>.fbx` — Unity does not read glb without an extra package. 1 unit is 1 m.
  Check the first model's scale and rotation in a scene (FBX from Blender often arrives rotated or scaled by 100). (`art/_gen/*/raw.glb` is in the `.gitignore` lines init appends.)
  The asset skill's work folder is `art/_gen/` here, not `assets/_gen/` — on a disk that ignores case (macOS · Windows) `assets/` is `Assets/`, and Unity would import the source pictures and gifs.
- **Sprites (asset skill)**: stills land in `Assets/Sprites/<name>.png`, animated sheets in `Assets/Sprites/<name>_<motion>.png`. Set Texture Type `Sprite (2D and UI)`;
  for a sheet, Sprite Mode `Multiple` sliced by the cell size `sprite.py status` prints, and Pixels Per Unit to the game's pixels per metre. The last row may be partly empty: use only the frame count given.
  A sheet with a side over 4096 px is scaled down on import even at Max Size 4096, and the recorded cell size no longer fits — slice from the texture's real size in code, or make the sheet smaller (fewer frames).
- **Sound (asset skill)**: lands in `Assets/Audio/<name>.mp3`. Looping is set on the `AudioSource` (`loop = true`), not on the file.
- **Video (video skill)**: in-game videos land in `Assets/Video/<name>.mp4` (H.264 + AAC), played with `VideoPlayer`.
  The clip is downloaded as mp4 (Higgsfield) and re-encoded on `place`. Its keys go in `~/.config/gamedev-kit/asset.env`. Playing and skipping the video is game code.
