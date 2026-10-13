---
name: asset
description: >-
  Makes assets. 3D model: description → image (OpenAI) → human approves → mesh (Meshy) → size and origin fixed (Blender) → game folder.
  2D sprite: description → still picture (Ludo) → human approves → animated sprite sheet (Ludo) → game folder — characters, props, tiles, icons.
  Sound: description → sound effect, looping sound, music (ElevenLabs) → game folder. One art style paragraph and one sound style
  paragraph in docs/DESIGN.md are attached to every asset, and each asset's prompt and result are recorded.
  Use when the user says "에셋 만들어줘" (make an asset), "모델 뽑아줘" (make a model), "○○ 3D 로 만들어줘" (make ○○ in 3D),
  "스프라이트 만들어줘" (make a sprite), "2D 로 그려줘" (draw it in 2D), "걷는 모션 뽑아줘" (make a walk animation),
  "아이콘 그려줘" (draw an icon), "Ludo 로 만들어줘" (make it with Ludo), "효과음 만들어줘" (make a sound effect), "소리 넣자" (let's add sound),
  or asks for one more like an existing asset, background sound, BGM,
  or a sound redone; when the cycle's design section "Assets needed" lists a 3D model, sprite or sound that does not exist; when the user
  approves an image for meshing or animating, or says the size is wrong; when first setting the art style paragraph or the asset API keys.
---

# asset

**Making assets here is optional.** The cycle owns the asset's *slot* — its name, the path it sits at, its size or length — and a file in that slot
counts whoever made it. This skill is one way to fill slots, with services the user has to set up. The other way needs nothing:

## Bring your own — no service needed

Use this when the user made the asset themselves or elsewhere, or when a key is missing and they would rather not set the service up.
Do not push the services: say both ways once and take the one they pick.

1. Read the row in the cycle document's "Assets needed" table: the kind, the size or length, and the path the placeholder holds (the "Have" cell, `placeholder <path>`).
   No path yet → ask the developer agent's task or the code where the placeholder is loaded from; do not invent one.
2. Tell the user exactly what to deliver: the path, the format the game already uses (the `asset` section of `kit.config.json`: `format` for models, `sound.format` for sounds; png for sprites) and the folder (`asset.dir`, `asset.sound.dir`, `asset.sprite.dir`),
   and the size — longest side in metres for a model, shown pixels for a sprite, seconds for a sound. One line per asset.
3. When the file is there, write the path in the "Have" cell (`` `path` ``, without `placeholder`), run the engine's import and the project's verification,
   and say what to look at. A file that does not drop in as it is (a different size, a pivot, a rig) is a build task — write it into the cycle document.

An asset brought this way has no record, so the board's asset sheet marks it "no record" and no art style paragraph was attached to it —
when it sits beside generated ones, tell the user to compare them on the asset sheet.

## With a tool that is already connected (MCP)

If this session has a generation tool connected — a service's own MCP server, a Blender connection — it can fill a slot, and keeping up with that service is then
the tool's maker's job, not the kit's. Prefer it over the scripts below when it covers what the asset needs. The workflow does not change:

1. Take the three paragraphs from `asset.py look` (art style · world · learned) and put them in the tool's prompt, as the scripts would have.
2. **The human still looks at the picture first.** Make the cheap thing (an image), show it, and only run the expensive step (a mesh, an animation) on what was approved.
3. Get the result as a file in the slot. A tool that returns a link or leaves the file elsewhere → download or move it to the slot's path, in the game's format and size.
4. Then as in "Bring your own" step 3: write the path in the "Have" cell, import, verify.

An asset made this way has no record either — the asset sheet shows it as "no record". Do not connect, install or log in to a tool for the user; if none is connected, say which ways are open.

## Make it with the kit's scripts

Three kinds of asset, three paths. Pick by what the game does with the thing, not by what it depicts:

| The game… | Path | Made with |
|---|---|---|
| shows it as a mesh — a static prop, a terrain piece | 3D model — the procedure below | OpenAI image → Meshy → Blender |
| draws it as a flat picture — a character, prop, tile, icon, UI piece — or plays it frame by frame | "2D sprite" section | Ludo |
| plays it as sound | "Sound" section | ElevenLabs |

Not here: a whole-screen picture for agreeing on the look (→ start skill's concept stage), a filmed-looking shot (→ video skill),
and anything code draws as well — flat panels, lines, plain shapes, tints. Do not generate those.

**Why Ludo for 2D:** a sprite's frames must be one character, the same size, in the same place in every cell. A general image model asked for a sheet
draws each cell anew — the figure drifts between frames and the stride comes out wrong. Ludo animates one approved picture, removes the background
and returns the grid. Ludo also sells sound, 3D and video; the kit uses it for 2D only — one service per kind keeps each kind's style in one place.

```
description ─▶ image (one per view) ─▶ [human looks] ─▶ mesh ─▶ finish ─▶ game folder
new            image                   approve          mesh    (mesh continues into it)
```

**The human looks at one place: the image.** Images are cheap and fast, so redraw as often as needed. Meshes are slow and cost credits —
so only approved images become meshes, and after approval it runs to the end without asking.

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/asset.py" new <name> --size <meters> [--poly <triangle count>] [--ref <photo> [--as-is]] "<what it is — in English>"
python3 "${CLAUDE_SKILL_DIR}/scripts/asset.py" image <name>... [--view back [--note "<words for that view only>"]] [--ref <photo>]
python3 "${CLAUDE_SKILL_DIR}/scripts/asset.py" approve <name>...
python3 "${CLAUDE_SKILL_DIR}/scripts/asset.py" reject <name> "<the user's words>"
python3 "${CLAUDE_SKILL_DIR}/scripts/asset.py" learn "<one line — in English>"
python3 "${CLAUDE_SKILL_DIR}/scripts/asset.py" look
python3 "${CLAUDE_SKILL_DIR}/scripts/asset.py" mesh <name>...
python3 "${CLAUDE_SKILL_DIR}/scripts/asset.py" finish <name>... [--size <meters>]
python3 "${CLAUDE_SKILL_DIR}/scripts/asset.py" status
```

## Procedure

1. **Check that the art style exists.** If the space between `<!-- asset-style -->` … `<!-- /asset-style -->` in `docs/DESIGN.md` is empty, fill it first ("Art style" below).
   Do not decide the art style ad hoc while making assets — each asset would come out different.
2. **Look at what exists first.** `status` and the asset folder. If the same thing already exists, do not make it. For filler like rocks, crates and grass,
   CC0 packs (Kenney, Quaternius) are more consistent and free — recommend those to the user first. Generate only what is unique to this game.
3. **`new`.** Write the description in English, **only what the thing is** — shape, proportions, material, color, two or three standout parts. Do not write art style, background, lighting or composition
   (the script attaches them). `--size` is the length of the longest side in meters. If the user did not say, look in the GDD or the design section; if absent, ask.
   Give `--poly` only for things that appear large or small on screen (default is the configured value).
   **If the user gave a reference photo for this thing, pass it with `--ref <path>`** (from the game root) — the image model is shown the photo itself and told to redraw that
   exact object in the game's style. Do not turn the photo into words and drop it: a description cannot carry a silhouette. Still write the description — it names the thing and what must stay.
   `--as-is` uses the photo as the first view without redrawing (png, a clean straight-on shot of one object) — closest to the photo, but the look is the photo's, not the game's. Ask which they want when it is not obvious.
4. **`image`.** For several, give the names at once. When done, give the user the image paths and tell them to open the images themselves.
   **Do not Read the images yourself** — a picture stays in this session to the end and is re-read every turn. The one who looks is the user.
   If the user asks you to screen them first, call `gamedev-kit:designer` with `review` and `model: opus`, pass the paths, and get text back.
5. **Wait for the user's answer.** If they ask for changes — if the object is wrong, fix `subject` in `asset.json` and run `image`; if only one view is off, `image --view <view>` — and when it is off because it copies the first view (a palm drawn as the back of the hand, the wrong one of a left · right pair),
   say what that side shows with `--note` ("the palm faces the viewer, thumb on the viewer's left"); the note stays with that view;
   a left · right pair (two arms, two legs) is made one side at a time — asked for in one picture, only one comes out or the two come out fused;
   if they now hand you a photo, `image <name> --ref <path>`. **Do not `approve` because it looks good to you.** `approve` only assets the user said are good.
   **When they turn one down, record what they said** — `reject <name> "<their words>"` — before redrawing. Then ask yourself whether it is about this one object or about every asset
   ("the metal is too shiny" is about every asset). If every: `learn "<the rule, one English line>"` and show them that line. See "What is attached to every asset".
6. **`mesh`.** Give all approved ones at once — they are made concurrently. It takes minutes, so run it in the background. If interrupted, rerunning the same command
   resumes waiting on the same job (it does not buy a new one). Once the mesh arrives it continues through finishing.
7. **Report the result.** File path, triangle count, size, credits spent. Opening it in the engine is the user's job.
   If only the size is wrong, `finish <name> --size <meters>` — do not call Meshy again.
8. During a cycle, write the path in the "Have" cell of the design section's "Assets needed" table (older cycle documents name them "있는가" and "필요한 에셋").

## What is attached to every asset

Three layers in `docs/DESIGN.md`, joined in this order behind every description (`look` prints them and their length):

| Layer | Between | What it is | Changes |
|---|---|---|---|
| **Art style** — how it is drawn | `<!-- asset-style -->` | rendering, palette, amount of detail, material feel, proportions | fixed. Changing it sets new assets against old ones |
| **World** — what exists | `<!-- asset-world -->` | era and place, the materials things are made of, motifs and shapes that recur | grows slowly, with the user |
| **Learned** — what turning assets down taught | `<!-- asset-learned -->` | one line per rule, from the user's own words | one line at a time, by `learn` |

- **World** is optional. Write it with the user from the GDD's setting when the second or third asset shows the need — it is also what you read before writing a new asset's description.
- **Learned comes only from what the user said**, never from what you see in images they approved — your reading of their taste is not their taste. One line, in English, true of every asset
  ("Metal is matte, never glossy"). Show the line when you add it. The script stops at twelve lines: merge lines that overlap, or — with the user — move a rule that always holds up into Art style.
- The three do not contradict: if a learned line fights the Art style paragraph, the paragraph is what needs the user's decision, not a thirteenth line.

**Seeing them together.** Consistency shows only side by side. The board's asset sheet (`docs/board/assets.html`, drawn by the board skill's script, no model) lays every asset out in one grid
under these three layers, and marks the ones drawn under an older Art style paragraph, the ones turned down and why, and the style references. After making a batch, give the user that page rather than a list of paths.
What they point at there is `reject` · `learn` material.

## Art style

One paragraph attached verbatim to every prompt. In English, containing only what fits any asset of this game:
rendering method (low-poly, hand-painted, flat-shaded …), color (palette color names or values), amount of detail, material feel, proportions (exaggerated or realistic).
No object names, background, lighting or composition.

```markdown
<!-- asset-style -->
Stylized low-poly game asset, flat-shaded with hand-painted color blocks, chunky exaggerated proportions,
muted earthy palette with one saturated accent color, no fine surface detail, matte materials.
<!-- /asset-style -->
```

Decide the art style paragraph with the user. Draft it from the colors and tone in `docs/DESIGN.md` and the art direction in the GDD, then generate two or three test assets with `image` and revise while looking at them together.
When an image they like comes out, put its path in `asset.refs` in `kit.config.json` — from then on every first image is drawn with it as reference.
**Changing the art style makes it clash with assets already made.** Say so before changing it.

## Config

```json
"asset": {
  "dir": "assets/models",
  "format": "glb",
  "views": ["front", "back"],
  "refs": [],
  "image": { "model": "gpt-image-2.5-flare", "size": "1024x1024", "quality": "medium" },
  "meshy": { "ai_model": "latest", "target_polycount": 5000, "topology": "triangle", "enable_pbr": false }
}
```

- `dir`, `format` — where finished models go and in what format. The engine decides (values installed by init).
- `views` — views to make (`front`, `back`, `left`, `right`, up to four). The first is the reference; the rest are drawn from it.
  More views mean less of the back is invented, but if views disagree the mesh breaks. Start with two.
- `image`, `meshy` — passed straight to each API. Other values (`texture_resolution` etc.) may be added.
- `sprite` — `{ "dir": "assets/sprites", "style_ref": "", "view": "", "image": { "image_type": "sprite" }, "animate": { "model": "hydra", "duration": 3 } }`.
  `style_ref` is one picture whose style every new picture is matched to (set it once the user likes one); `view` is the viewpoint in words.
  `image` and `animate` are passed straight to Ludo — `art_style` · `perspective` · `aspect_ratio` may be added to `image`, `frames` · `frame_size` · `loop` to `animate`.
  Per-sprite records are in `assets/_gen/<name>/sprite.json`.
- `sound` — `{ "dir": "assets/sounds", "format": "mp3_44100_128", "influence": 0.3, "music_model": "music_v1" }`.
  `format` is ElevenLabs' output_format. If it starts with `pcm_`, like `pcm_44100`, the file is saved as wav (may be blocked depending on the plan).
- Per-asset values (description, size, triangle count) are in `assets/_gen/<name>/asset.json`. Editing by hand is fine.

Commit `assets/_gen/` to the repository — the record (`asset.json`) and images are what make "one more like this" possible.
The mesh as received (`raw.glb`) is large, so put it in `.gitignore` (it is only used when running `finish` again).

## 2D sprite

```
description ─▶ still picture ─▶ [human looks] ─▶ game folder ─▶ animate ─▶ [human watches] ─▶ game folder
new            image             approve                         animate
```

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/sprite.py" new <name> [--type <kind>] [--ref <picture> [--as-is]] "<what it is — in English>"
python3 "${CLAUDE_SKILL_DIR}/scripts/sprite.py" image <name>... [--ref <picture>]
python3 "${CLAUDE_SKILL_DIR}/scripts/sprite.py" approve <name>...
python3 "${CLAUDE_SKILL_DIR}/scripts/sprite.py" reject <name> "<the user's words>"
python3 "${CLAUDE_SKILL_DIR}/scripts/sprite.py" animate <name> <motion> [--seconds <seconds>] [--frames <count>] "<the motion — in English>"
python3 "${CLAUDE_SKILL_DIR}/scripts/sprite.py" status
python3 "${CLAUDE_SKILL_DIR}/scripts/sprite.py" credits
```

The gate is the same as for models: **the still picture is cheap, the animation is not** (an animation costs about as much as twenty stills).
Only an approved picture is animated. The Art style · World · Learned layers are the same ones — `asset.py look` · `asset.py learn`.

1. **Art style and what exists first** — steps 1 and 2 of the model procedure. Also ask whether code can draw it (a flat panel, a bar, a tint): if so it is not an asset.
2. **`new`.** The description says only what the thing is. `--type` is Ludo's kind of image — `sprite` (default; characters and props), `icon`, `item-icon`,
   `ui_asset`, `tile`, `texture`, `portrait`, `sprite-vfx` — it changes how the picture is framed and cut out, so set it rather than describing it.
   A character that already exists as concept art: pass it with `--ref` (redrawn as a sprite in the game's style and view), or `--as-is` to animate that very picture (png).
3. **`image`**, give the path, the user looks — you do not Read it. Changes: fix `subject` in `sprite.json` and run `image` again; turned down → `reject`, and `asset.py learn` if it holds for every asset.
4. **`approve`** only what the user said is good. The still lands in the game folder as `<name>.png`.
5. **`animate`** — say the cost first (below) and run it in the background; it takes minutes, and rerunning the same command resumes the same job.
   The motion is one phrase for an action the model knows ("walking", "idle breathing", "chopping with a knife") — the character, style and view come from the picture, so do not describe them again.
   `--seconds` 3 is the default; allow about a second per 16 frames. The sheet lands as `<name>_<motion>.png`; a preview gif stays in the work folder.
6. **The user watches the gif.** You cannot judge motion. Ask what they see: does the figure stay the same, do the feet alternate, does the loop close.
   A redo is the same command again (it overwrites the sheet — ask before redoing one they said was good).
7. **Report the grid**: `status` prints frames · columns × rows · cell size for each sheet. The sheet may hold fewer frames than asked — read the numbers, never assume them.
   Slicing the sheet and playing it in the engine is development work; give the developer those numbers and the path.

Pitfalls:

- **Say the view in words.** "Top-down" in sprite tools usually means seen from a slant. If the game looks straight down, write it in `sprite.view`
  ("seen from directly above, the top of the head visible, facing the top of the image") — it is attached to every description.
  Seen from straight above, one direction is enough: the game turns the picture to the heading. A slanted view needs each motion once per direction.
- **The still is the first frame.** Draw it in the pose the motion starts from, limbs close to the body, nothing touching the edge — what is cut off in the still is cut off in every frame.
- **Generated size is not shown size.** Decide how many pixels one metre is (in `docs/DESIGN.md`) and let the engine scale; write generated size → shown size in the "Assets needed" table.
  Collision and layout come from the spec's dimensions — stretch the picture to the box, never the box to the picture.
- **One character, one still.** Every motion of a character is animated from the same approved still, or the character changes between motions.
- **Cost.** Stills: 0.5 credit. Animation: by the second — `hydra` 3 credits/s (3 s at least), `forge` · `forge-pixel` 1.5 credits/s (simpler motion, pixel art). `credits` shows what is left. Failed jobs are refunded.
  Ludo's links expire, so the script downloads at once; what is in the work folder is the only copy.

## Sound

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/sound.py" sfx <name> [--seconds <seconds>] [--loop] [--influence <0~1>] "<what sound — in English>"
python3 "${CLAUDE_SKILL_DIR}/scripts/sound.py" music <name> --seconds <seconds> "<what music — in English>"
python3 "${CLAUDE_SKILL_DIR}/scripts/sound.py" again <name>...
python3 "${CLAUDE_SKILL_DIR}/scripts/sound.py" status
```

A sound comes out in one step — there is no intermediate gate like the image. But **you cannot hear it.** Only the user knows whether it is good.

1. **Look at what exists first.** `status` and the sound folder. If the same sound exists, do not make it.
2. **Write the description.** In English, what is heard, in order: what hits what, material, intensity, tail (cuts short / rings).
   Not "coin pickup" but "a small metal coin dropped on a stone floor, one bright ping, short tail". Do not write the game's sound style (8-bit, dry, no reverb) —
   if the `<!-- sound-style -->` … `<!-- /sound-style -->` paragraph in `docs/DESIGN.md` exists, the script attaches it.
   Music does not get that paragraph (words for effects, like "no music" or "short tail", wreck a music description) — it gets `<!-- music-style -->` … `<!-- /music-style -->` if that exists.
   If that paragraph is empty, decide it with the user while making the first few sounds and write it down. Same as the art style paragraph: changing it clashes with sounds already made.
3. **Length.** If the design section "Effects and sound" (older documents: "연출과 소리") gives seconds, pass them with `--seconds`. Sound effects are 0.5–30 s (omit to let it decide), music 3–600 s.
   Use `--loop` for sounds that run endlessly, like wind, engines and ambience. Keep sounds that answer an input short — long ones overlap.
4. **Make it, give the path, tell the user to listen.** For several, say how many first. Do not say "it came out well" without hearing it.
5. **Revise.** If they only want a different result, `again <name>` (same description, different sound). If the sound is wrong, fix the description and run `sfx` again under the same name.
   To follow the description more literally use about `--influence 0.6`; for more freedom, `0.1`. The same name overwrites the file —
   the user may prefer the earlier one, so ask before remaking a sound they said was good.
6. During a cycle, write the path in the "Have" cell of the design section's "Assets needed" table. The code that plays the sound in the game is development work.

Pitfalls:

- **A sound effect description, including the sound style paragraph, must fit in 450 characters.** Over that the script stops — shorten the description, not the sound style paragraph.
- **When the sound style paragraph conflicts with the description, the sound style paragraph wins.** If the style says "no voices" and you need a shout, state clearly in the description that it is a voice.
- **Looping sounds and music sometimes arrive with silence at the end.** Looped as is, the beat breaks — trim the silence (`ffmpeg -af silenceremove`).
  Loudness also differs per sound: for background layers, measure with `ffmpeg -af volumedetect` and match.
- **Two sounds that must stay in time must be made exactly the same length.** If generating them whole and matching is hard, generate pieces (one drum hit, one shout) separately and sequence them.

## First time only (done by the user)

None of this is needed to bring your own. A script that needs a key that is not there stops and says so — offer "Bring your own" beside setting the key up.

- **Keys**: write the API keys (OpenAI and Meshy for models) in a file **outside** the repository (the user, in a terminal):

  ```bash
  mkdir -p ~/.config/gamedev-kit && chmod 700 ~/.config/gamedev-kit && ${EDITOR:-nano} ~/.config/gamedev-kit/asset.env
  ```

  The file has two lines, `OPENAI_API_KEY=...` and `MESHY_API_KEY=...`. To make sounds, add one more line, `ELEVENLABS_API_KEY=...`
  (the ElevenLabs key must have Sound Effects and Music permissions enabled). To make sprites, add `LUDO_API_KEY=...`
  (ludo.ai → account → API; the API needs a plan that includes it, and sheets from the free plan carry a watermark). **Keep the user from pasting keys into the conversation, and even if you receive one, do not write it to any file in the repository.**
- **Blender**: `blender` must be on PATH. If not, write the executable path in `asset.blender`.
  If the game runs Blender scripts of its own: **Blender exits 0 even when a `--python` script dies with an exception** — have the script print a last line when it has finished
  and judge by that line, not the exit code (this is what `asset.py` does). And before decimating a mesh, merge vertices that share a position (`remove_doubles`):
  vertices split along UV seams otherwise tear the mesh into pieces — if a size guard then stops it, look at the decimated result, do not loosen the guard.
- All of these services charge by use. Meshy refunds credits for failed jobs. Before running several assets at once, say how many.

## Not covered

- 3D rigging and animation — models are static props and terrain pieces only. (2D animation is the sprite path.)
  If the game rigged with Meshy separately, know this: in a rigged glb the mesh sits under an `Armature` with scale 0.01 and the skinned mesh follows the bones —
  measure position and size by the bones, not the mesh's transform. Auto weights are bound in the arms-down pose, so arm flesh may follow the thigh bone —
  capture an arm-raising clip up close, and for vertices whose weights you fixed, check that they sum to 1.
  A hand that is always in view (first-person arms) starts from a base model that already has finger bones: an auto-rigged generated body cut down to the arm has no finger bones and the hand shape baked into the mesh — check the rig level at design time.
- No voice (reading lines). Music is made without lyrics.
- Work after import into the engine (colliders, material touch-up, placing in scenes) is development work. Write it as a cycle task.
