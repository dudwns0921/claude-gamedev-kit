# Unity

Not yet checked in a real game with this kit — the build script and the asset · video settings below follow Unity's documentation.
Whatever turns out different, write it in `docs/kit-feedback.md`.

- Value file: `Assets/Scripts/Config/Balance.cs` (`public static float NAME = 4.0f; // GDD: <ID>`). Write floats with a decimal point and `f`.
  There is no runtime template that re-reads the table while running — after `bake`, Unity recompiles and the game runs on the baked values.
- Unity creates a `.meta` file for every file init installed the next time the project is opened. Commit them.
- `.gitignore`: add `Library/`, `Temp/`, `Logs/`, `obj/`, `UserSettings/`, `build/`, `*.keystore`, `*.jks`.
- Write the Unity executable path of this machine in the game's CLAUDE.md, and export it as `UNITY` for the build command
  (macOS: `/Applications/Unity/Hub/Editor/<version>/Unity.app/Contents/MacOS/Unity`).
- **What the user does once (Claude cannot):** install the editor with the **Android Build Support** module (with OpenJDK and Android SDK & NDK Tools) in Unity Hub
  and sign in to activate the license; set the package name (Player Settings → Android → Identification, `com.<name>.<game>`) — it cannot change after the first upload;
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
  Check the first model's scale and rotation in a scene (FBX from Blender often arrives rotated or scaled by 100). Add `assets/_gen/*/raw.glb` to `.gitignore`.
- **Sound (asset skill)**: lands in `Assets/Audio/<name>.mp3`. Looping is set on the `AudioSource` (`loop = true`), not on the file.
- **Video (video skill)**: in-game videos land in `Assets/Video/<name>.mp4` (H.264 + AAC), played with `VideoPlayer`.
  The clip is downloaded as mp4 (Higgsfield) and re-encoded on `place`. Its keys go in `~/.config/gamedev-kit/asset.env`. Playing and skipping the video is game code.
