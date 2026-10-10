---
name: asset
description: >-
  Makes assets. 3D model: description → image (OpenAI) → human approves → mesh (Meshy) → size and origin fixed (Blender) → game folder.
  Sound: description → sound effect, looping sound, music (ElevenLabs) → game folder. One art style paragraph and one sound style
  paragraph in docs/DESIGN.md are attached to every asset, and each asset's prompt and result are recorded.
  Use when the user says "에셋 만들어줘", "모델 뽑아줘", "○○ 3D 로 만들어줘", "효과음 만들어줘", "소리 넣자", or asks for one more
  like an existing asset, background sound, BGM, or a sound redone; when the cycle's design section "필요한 에셋" lists a 3D model or
  sound that does not exist; when the user approves an image for meshing or says the size is wrong;
  when first setting the art style paragraph or the asset API keys.
---

# asset

3D models and sounds take different paths. Models follow the procedure below; sounds follow the "Sound" section at the bottom.

```
description ─▶ image (one per view) ─▶ [human looks] ─▶ mesh ─▶ finish ─▶ game folder
new            image                   approve          mesh    (mesh continues into it)
```

**The human looks at one place: the image.** Images are cheap and fast, so redraw as often as needed. Meshes are slow and cost credits —
so only approved images become meshes, and after approval it runs to the end without asking.

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/asset.py" new <name> --size <meters> [--poly <triangle count>] [--ref <photo> [--as-is]] "<what it is — in English>"
python3 "${CLAUDE_SKILL_DIR}/scripts/asset.py" image <name>... [--view back] [--ref <photo>]
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
   If the user asks you to screen them first, call `gamedev-kit:designer` with `review`, pass the paths, and get text back.
5. **Wait for the user's answer.** If they ask for changes — if the object is wrong, fix `subject` in `asset.json` and run `image`; if only one view is off, `image --view <view>`;
   if they now hand you a photo, `image <name> --ref <path>`. **Do not `approve` because it looks good to you.** `approve` only assets the user said are good.
   **When they turn one down, record what they said** — `reject <name> "<their words>"` — before redrawing. Then ask yourself whether it is about this one object or about every asset
   ("the metal is too shiny" is about every asset). If every: `learn "<the rule, one English line>"` and show them that line. See "What is attached to every asset".
6. **`mesh`.** Give all approved ones at once — they are made concurrently. It takes minutes, so run it in the background. If interrupted, rerunning the same command
   resumes waiting on the same job (it does not buy a new one). Once the mesh arrives it continues through finishing.
7. **Report the result.** File path, triangle count, size, credits spent. Opening it in the engine is the user's job.
   If only the size is wrong, `finish <name> --size <meters>` — do not call Meshy again.
8. During a cycle, write the path in the "있는가" cell of the design section's "필요한 에셋" table.

## What is attached to every asset

Three layers in `docs/DESIGN.md`, joined in this order behind every description (`look` prints them and their length):

| Layer | Between | What it is | Changes |
|---|---|---|---|
| **화풍** — how it is drawn | `<!-- asset-style -->` | rendering, palette, amount of detail, material feel, proportions | fixed. Changing it sets new assets against old ones |
| **세계** — what exists | `<!-- asset-world -->` | era and place, the materials things are made of, motifs and shapes that recur | grows slowly, with the user |
| **배운 것** — what turning assets down taught | `<!-- asset-learned -->` | one line per rule, from the user's own words | one line at a time, by `learn` |

- **세계** is optional. Write it with the user from the GDD's setting when the second or third asset shows the need — it is also what you read before writing a new asset's description.
- **배운 것 comes only from what the user said**, never from what you see in images they approved — your reading of their taste is not their taste. One line, in English, true of every asset
  ("Metal is matte, never glossy"). Show the line when you add it. The script stops at twelve lines: merge lines that overlap, or — with the user — move a rule that always holds up into 화풍.
- The three do not contradict: if a learned line fights the 화풍 paragraph, the paragraph is what needs the user's decision, not a thirteenth line.

**Seeing them together.** Consistency shows only side by side. The board's asset sheet (`docs/board/assets.html`, drawn by the board skill's script, no model) lays every asset out in one grid
under these three layers, and marks the ones drawn under an older 화풍 paragraph, the ones turned down and why, and the style references. After making a batch, give the user that page rather than a list of paths.
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
- `sound` — `{ "dir": "assets/sounds", "format": "mp3_44100_128", "influence": 0.3, "music_model": "music_v1" }`.
  `format` is ElevenLabs' output_format. If it starts with `pcm_`, like `pcm_44100`, the file is saved as wav (may be blocked depending on the plan).
- Per-asset values (description, size, triangle count) are in `assets/_gen/<name>/asset.json`. Editing by hand is fine.

Commit `assets/_gen/` to the repository — the record (`asset.json`) and images are what make "one more like this" possible.
The mesh as received (`raw.glb`) is large, so put it in `.gitignore` (it is only used when running `finish` again).

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
   If that paragraph is empty, decide it with the user while making the first few sounds and write it down. Same as the art style paragraph: changing it clashes with sounds already made.
3. **Length.** If the design section "연출과 소리" gives seconds, pass them with `--seconds`. Sound effects are 0.5–30 s (omit to let it decide), music 3–600 s.
   Use `--loop` for sounds that run endlessly, like wind, engines and ambience. Keep sounds that answer an input short — long ones overlap.
4. **Make it, give the path, tell the user to listen.** For several, say how many first. Do not say "it came out well" without hearing it.
5. **Revise.** If they only want a different result, `again <name>` (same description, different sound). If the sound is wrong, fix the description and run `sfx` again under the same name.
   To follow the description more literally use about `--influence 0.6`; for more freedom, `0.1`. The same name overwrites the file —
   the user may prefer the earlier one, so ask before remaking a sound they said was good.
6. During a cycle, write the path in the "있는가" cell of the design section's "필요한 에셋" table. The code that plays the sound in the game is development work.

Pitfalls:

- **A sound effect description, including the sound style paragraph, must fit in 450 characters.** Over that the script stops — shorten the description, not the sound style paragraph.
- **When the sound style paragraph conflicts with the description, the sound style paragraph wins.** If the style says "no voices" and you need a shout, state clearly in the description that it is a voice.
- **Looping sounds and music sometimes arrive with silence at the end.** Looped as is, the beat breaks — trim the silence (`ffmpeg -af silenceremove`).
  Loudness also differs per sound: for background layers, measure with `ffmpeg -af volumedetect` and match.
- **Two sounds that must stay in time must be made exactly the same length.** If generating them whole and matching is hard, generate pieces (one drum hit, one shout) separately and sequence them.

## First time only (done by the user)

- **Keys**: write the OpenAI and Meshy API keys in a file **outside** the repository (the user, in a terminal):

  ```bash
  mkdir -p ~/.config/gamedev-kit && chmod 700 ~/.config/gamedev-kit && ${EDITOR:-nano} ~/.config/gamedev-kit/asset.env
  ```

  The file has two lines, `OPENAI_API_KEY=...` and `MESHY_API_KEY=...`. To make sounds, add one more line, `ELEVENLABS_API_KEY=...`
  (the ElevenLabs key must have Sound Effects and Music permissions enabled). **Keep the user from pasting keys into the conversation, and even if you receive one, do not write it to any file in the repository.**
- **Blender**: `blender` must be on PATH. If not, write the executable path in `asset.blender`.
- All three services charge by use. Meshy refunds credits for failed jobs. Before running several assets at once, say how many.

## Not covered

- 2D (UI icons, textures) is not available yet. Neither are rigging and animation — only static props and terrain pieces.
  If the game rigged with Meshy separately, know this: in a rigged glb the mesh sits under an `Armature` with scale 0.01 and the skinned mesh follows the bones —
  measure position and size by the bones, not the mesh's transform. Auto weights are bound in the arms-down pose, so arm flesh may follow the thigh bone —
  capture an arm-raising clip up close, and for vertices whose weights you fixed, check that they sum to 1.
- No voice (reading lines). Music is made without lyrics.
- Work after import into the engine (colliders, material touch-up, placing in scenes) is development work. Write it as a cycle task.
