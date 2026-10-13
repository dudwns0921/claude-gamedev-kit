
## Roles (Godot)

- **User**: makes assets and plays the game. Does not touch code · scenes · settings.
- **Claude**: all code · scenes · settings · documents. Do not ask the user to operate the Godot editor — write settings as files, and verify with headless tests and captures.

## Running

The Godot executable lives in a different place on each machine (`godot` is often not on PATH). Write the per-machine paths below — so they are not passed again to every agent.

```bash
<Godot executable> --path .                     # the game
<Godot executable> --headless --path . --import   # a freshly cloned repo, or after model · sound · material files changed — once before tests
```

- `--import` **rewrites `project.godot`** (line order changes, and autoload lines added by editor plugins can be erased).
  After running it look at `git diff project.godot`, and revert if it changed unintentionally. Do not run it while the editor is open.
  Check whether the editor has the project open as a step of its own, before the import (`pgrep -fl -i godot`) — chained into one command with the import, you find out after it has run.
- Put an empty `.gdignore` file in folders Godot must not import, like `docs/` · `assets/_gen/`.

## Verification

Everything that can be verified without a screen becomes a headless test. Run them before asking the user to "try it and tell me".

- **Rules without scenes.** Keep rulings (does it work · does it not · how many seconds) in a script that knows neither nodes nor input, and write a test that loads and runs only that script — it finishes within 1 second.
- **Flow by smoke test.** Attach the scene the game actually launches as a child, feed input and look at state: `<godot> --headless --path . res://tests/smoke_<name>.tscn`.
- **Screen (color · layout · HUD) by capture.** Keep a scene that briefly opens a window and shoots set scenes (`res://tests/capture_<name>.tscn -- <folder>`). Claude reads the captured images.
  **If the screen is locked or the window is covered, nothing is captured** (it does not draw). If the window grabs the mouse, mouse movement during the shot changes the framing.
- **Motion by frames.** `<godot> --path . --write-movie <folder>/<scene>.png --fixed-fps 10 --resolution 800x450 res://tests/capture_play.tscn -- <scene>`.
- `Parameter "material" is null` in headless output is noise from having no renderer. Look only at `SCRIPT ERROR`.
- **Run every headless test under a time limit.** A script with a parse error does not fail the run — it hangs. When a run hangs, look for a parse error first.
  macOS has no `timeout` command (a loop that calls it gets rc 127 every time and checks nothing): `perl -e 'alarm shift; exec @ARGV' <seconds> <command>`.
- **In a windowed run, wait two `process_frame`s before reading a value that moves per frame** (a Tween, the field of view). A test that only counts physics ticks
  can read it before `_process` has run once — it looks unmoved, and the same test passes headless.
- **Put the process id in the save path a test uses** (`OS.get_process_id()`). Two runs of the same smoke test at once otherwise write the same save file.
- **Frame time swings by about a fifth between runs.** To measure what an effect costs, switch it on and off in turns inside one process — do not compare two runs.
- **Headless does not compile shaders.** If you changed a shader, run the capture scene once in a window and look for `SHADER ERROR` in the output.

## Pitfalls (Godot)

1. **Do not use `class_name` — bind with `const X := preload("res://…")`.** A new `class_name` is a nonexistent class until the editor scans it,
   so headless tests in a freshly cloned repo do not start. (The `Balance` the kit installs is scanned by one `--import`.)
2. **Input actions get two events per key** — one with only `physical_keycode` and one with only `keycode`. If both are filled in one event Godot matches by keycode only,
   and under Korean input mode W arrives as a different keycode, so WASD does not respond.
3. **In tests, inject a key pressed once with `Input.parse_input_event(InputEventAction)`.** `Input.action_press` is "just pressed" only in the frame it is called,
   so if called after a timer the game's `_process` has already passed that frame. A held key works with `action_press`.
4. **Do not write comments in `project.godot`.** When the editor or import rewrites the file, a `#` line becomes a broken key and the setting line right below it disappears. Write the reason in CLAUDE.md.
5. **If you got an autoload with `get_node("/root/Name")`, do not use `:=` on its return value.** The type is `Node`, so you get a "Cannot infer the type" parse error,
   and every scene using that script fails to start — the symptom shows up somewhere unrelated. Write the type explicitly (`var x: Array[int] = …`).
6. **In a project with physics interpolation on, turn interpolation off for nodes moved directly in `_process`.** Interpolated, they jitter one tick late.
   Something that follows an interpolated object follows that object's interpolated position.
7. **Do not use `speed_scale = 0` to hold a clip on its first frame.** The blend stops too and it freezes in the previous clip's pose — `play(clip, blend, 0.0)` then `seek(0.0, true)`.
8. **If a method name in your own script collides with a GDScript built-in function, call it with `self.`.** Called by bare name like `wrap(...)`, it is read as the built-in and gives a parse error.
9. **When a test attaches a game that uses pause as a child,** if the test's `process_mode` is ALWAYS the game inherits it and pause does not take effect — set PAUSABLE on the game node.
   While a menu pauses the tree, a test waiting on a timer is paused too.
10. **Web builds render at 1x** — `window/dpi/allow_hidpi.web=false` in `project.godot`. Rendering at 2x pixels on Retina gives 4~5 fps.
11. **The Compatibility renderer — what a web build uses — is not Forward+ with less.** With the same `light_energy`, sky ambient and sky reflection, lit surfaces come out about twice as bright,
    and `GeometryInstance3D.transparency` is ignored. Branch the values on the renderer (`RenderingServer.get_current_rendering_method() == "gl_compatibility" or OS.has_feature("web")`)
    and shoot the capture once more on desktop with `--rendering-method gl_compatibility`. Lower sky ambient with `ambient_light_sky_contribution`, not `ambient_light_energy`.
    To fade an object, dither it in screen space in the opaque pass (`discard`) — not alpha blending, which also loses depth sorting.
12. **A `DirectionalLight3D` shines along its −z.** The direction towards the sun, which a sky shader wants, is `+basis.z`.
13. **With IK as a `SkeletonModifier3D`, `get_bone_global_pose` read from a test gives the pose before IK.** Read bone positions inside the `skeleton_updated` signal.
14. **A skinned mesh in the Compatibility renderer (web too) gets the same tangent at every vertex, so a normal map breaks** (bright triangular patches).
    Compute the normal-map frame in the shader from screen derivatives, and keep a capture scene that shoots the skinned mesh beside the same mesh with its bones removed — the difference is the check.
15. **Soften the edge of a thresholded noise with `fwidth`, not a fixed-width `smoothstep`** — a fixed width smears where the noise is gentle.
16. **`cast_motion` misses a small ball grazing a wide thin box, and once it misses it never sees a body the shape leaves while overlapping** (projectiles pass through floors and walls).
    Split the step into pieces shorter than the thinnest collider, check the overlap at each piece's end with `get_rest_info`, and narrow down the first overlapping position. Keep a test that fires hundreds of shots into the real room and counts the ones that get through.
