# Unity

Not yet checked in a real game with this kit — the build script and the asset · video settings below follow Unity's documentation.
Whatever turns out different, write it in `docs/kit-feedback.md`.

- Value file: `Assets/Scripts/Config/Balance.cs` (`public static float NAME = 4.0f; // GDD: <ID>`). Write floats with a decimal point and `f`.
  There is no runtime template that re-reads the table while running — after `bake`, Unity recompiles and the game runs on the baked values.
- **Editor and modules (`init.py unity --editor`)**: macOS — the editor is `/Applications/Unity/Hub/Editor/<version>/Unity.app/Contents/MacOS/Unity` (the newest version is picked when several are installed;
  `UNITY` overrides). The Android module is there when `/Applications/Unity/Hub/Editor/<version>/PlaybackEngines/AndroidPlayer` exists and holds `SDK`, `NDK` and `OpenJDK`.
  The Windows and Linux paths in `project.json` follow Unity's documented install layout and were not run.
- **Adding the Android module**: close the editor, then Unity Hub → Installs → the gear on that version → Add modules → **Android Build Support with OpenJDK and Android SDK & NDK Tools**. From a shell:
  `"/Applications/Unity Hub.app/Contents/MacOS/Unity Hub" -- --headless install-modules --version <version> -m android android-sdk-ndk-tools android-open-jdk`.
  It downloads several GB — the user decides when; do not run it unasked.
- **Creating the project (`init.py unity --create`)**: `<Unity> -batchmode -quit -createProject <game root> -logFile <file>` — works in a folder that already has `.git`, `docs/` and the like.
  After installing, `init.py unity --import` runs `<Unity> -batchmode -quit -projectPath <game root> -logFile -` once: it compiles and creates the `.meta` files for what init installed, and stops on `error CS` lines.
  Commit the `.meta` files. Both need the editor closed on this project. (Run on macOS; not on Windows or Linux.)
- `.gitignore`: init appends the lines in `engines/unity/gitignore` (`Library/`, `Temp/`, `Logs/`, `obj/`, `UserSettings/`, `build/`, `*.csproj`, `*.sln`, `*.slnx`, `*.keystore`, `*.jks`, `assets/_gen/*/raw.glb`).
- Write the Unity executable path of this machine and the installed modules in the game's CLAUDE.md **under the existing `## This game's rules` heading** (`--editor` prints the line; do not add a second heading),
  and export the path as `UNITY` for the build command.
- **What the user does once (Claude cannot):** install Unity Hub and the editor, and sign in to activate the license; set the package name (Player Settings → Android → Identification, `com.<name>.<game>`) — it cannot change after the first upload;
  create the upload keystore (Player Settings → Publishing Settings → Keystore Manager) and **keep it and its passwords outside the repo, with a backup**.
- **Build (Google Play)**: `deploy.py build android` runs `Assets/Editor/KitBuild.cs` in batch mode and leaves `build/android/game.aab` (IL2CPP · ARM64 · app bundle).
  Close the editor first — batch mode cannot open a project the editor has open. Signing comes from the environment:
  `KIT_KEYSTORE` (path) · `KIT_KEYSTORE_PASS` · `KIT_KEY_ALIAS` · `KIT_KEY_PASS`, and `KIT_VERSION_CODE` (an integer that must grow with every upload).
  Without `KIT_KEYSTORE` the bundle is debug-signed and Play rejects it. The build writes its settings into `ProjectSettings/ProjectSettings.asset` — look at `git diff` afterwards.
  The version is read from `bundleVersion` in that file (Player Settings → Version).
- **Upload (Google Play)**: this kit has no upload path for Play — `deploy.py push` is itch.io only, so `deploy.itch` stays empty. The user uploads
  `build/android/game.aab` in Play Console (the first upload of an app must be done there by hand in any case).
  To also put a build on itch.io, fill `deploy.itch` and add a channel whose `dir` holds an `.apk`.
- **Assets (asset skill)**: finished models land in `Assets/Models/<name>.fbx` — Unity does not read glb without an extra package. 1 unit is 1 m.
  Check the first model's scale and rotation in a scene (FBX from Blender often arrives rotated or scaled by 100). (`assets/_gen/*/raw.glb` is in the `.gitignore` lines init appends.)
- **Sprites (asset skill)**: stills land in `Assets/Sprites/<name>.png`, animated sheets in `Assets/Sprites/<name>_<motion>.png`. Set Texture Type `Sprite (2D and UI)`;
  for a sheet, Sprite Mode `Multiple` sliced by the cell size `sprite.py status` prints, and Pixels Per Unit to the game's pixels per metre. The last row may be partly empty: use only the frame count given.
- **Sound (asset skill)**: lands in `Assets/Audio/<name>.mp3`. Looping is set on the `AudioSource` (`loop = true`), not on the file.
- **Video (video skill)**: in-game videos land in `Assets/Video/<name>.mp4` (H.264 + AAC), played with `VideoPlayer`.
  The clip is downloaded as mp4 (Higgsfield) and re-encoded on `place`. Its keys go in `~/.config/gamedev-kit/asset.env`. Playing and skipping the video is game code.
