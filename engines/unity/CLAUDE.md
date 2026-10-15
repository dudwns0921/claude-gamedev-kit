
## Roles (Unity)

- **User**: makes assets and plays the game. Installs the editor and its build modules and signs in — nothing else in the editor.
- **Claude**: all code · scenes · settings · documents. Do not ask the user to click through the Unity editor — do editor work with editor scripts run by
  `-executeMethod`, and verify with batch-mode tests.

## Running

The Unity executable lives in a different place on each machine and per editor version. Write the per-machine path below — so it is not passed again to every agent.

```bash
<Unity executable> -batchmode -quit -projectPath . -logFile -          # import and compile; look for `error CS` in the output
<Unity executable> -batchmode -projectPath . -runTests -testPlatform EditMode -testResults build/tests.xml -logFile -   # no -quit with -runTests
```

- **Batch mode cannot open a project the editor has open.** Ask the user to close the editor, or the command fails at once.
- The first run after a clone imports everything into `Library/` and takes minutes. Later runs are fast.

## Verification

Everything that can be verified without a screen becomes an EditMode test. Run them before asking the user to "try it and tell me".

- **Rules without scenes.** Keep rulings (does it work · does it not · how many seconds) in plain C# classes that know neither `MonoBehaviour` nor input,
  and test only those classes in EditMode.
- **Flow by PlayMode test** (`-testPlatform PlayMode`): load the scene the game actually launches, feed input and look at state.
- A compile error anywhere stops every test from running — the result file is missing or empty. Look for `error CS` in the log first.

## Pitfalls (Unity)

1. **Every asset has a `.meta` file holding its GUID; scenes and prefabs refer to assets by that GUID.** Move, rename and delete a file together with its `.meta`,
   and commit the `.meta` Unity creates for a new file. A lost or regenerated `.meta` silently breaks every reference to that asset.
2. **Do not hand-write scene or prefab YAML.** The file IDs and GUIDs must agree across files. Build objects in code, or with an editor script run by `-executeMethod`.
3. **On Android, `StreamingAssets` is inside the app package** — `File.ReadAllText` cannot open it. Read it with `UnityWebRequest`, and write only under `Application.persistentDataPath`.
4. **IL2CPP strips code that is reached only by reflection** (JSON deserialization into a type, `Type.GetType` by name). It works in the editor and fails on the device —
   keep such types with `[Preserve]` or a `link.xml`.
5. **The editor is not the device.** Touch, screen sizes with notches, the back button and performance are checked only on a phone (the user: Build and Run with it plugged in). Say so when reporting a change as verified.
6. **In batch mode `AssetDatabase.ImportPackage` does nothing** — the import is queued and the process quits before it runs (TMP Essential Resources never arrive this way).
   A `.unitypackage` is a gzipped tar: one folder per asset, named by its GUID, holding `asset`, `asset.meta` and `pathname`. Unpack it and put each file at its path with its `.meta`.
