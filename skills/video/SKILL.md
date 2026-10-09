---
name: video
description: >-
  Makes footage — a shot that looks filmed — with Higgsfield: description (· reference images) → human approves → generated →
  human watches → placed where it is used. Two uses: `page` — outside the game (trailer, itch.io page, devlog clip) as mp4;
  `game` — a cutscene the game plays as a video file (intro, ending), converted to the format the engine reads. One footage style
  paragraph in docs/DESIGN.md is attached to every description, and each clip's description and result are recorded.
  Use when the user says "영상 만들어줘", "트레일러 만들자", "컷씬 만들어줘", "인트로 영상", "엔딩 영상", "devlog 에 넣을 영상",
  "힉스필드로 만들어줘", "이 그림을 움직이게", "한 번 더 뽑아줘"; approves a shot description or says a clip is good; when the cycle's
  design section lists a cutscene or trailer that does not exist; when first setting the footage style, the Higgsfield keys or the model.
---

# video

```
what happens (+ reference images) ─▶ [human looks] ─▶ generate ─▶ [human watches] ─▶ where it is used
new                                   approve          make        place
```

**The human looks twice: at what will be sent, and at what came back.** Generating costs credits and takes minutes, so only an approved description is sent,
and the result is placed only after the user has watched it — **you cannot see motion.**

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/clip.py" check
python3 "${CLAUDE_SKILL_DIR}/scripts/clip.py" new <name> --for game|page [--seconds <n>] [--size landscape|portrait|square] [--image <path>]... "<what happens — in English>"
python3 "${CLAUDE_SKILL_DIR}/scripts/clip.py" approve <name>...
python3 "${CLAUDE_SKILL_DIR}/scripts/clip.py" make <name>... [--again]
python3 "${CLAUDE_SKILL_DIR}/scripts/clip.py" place <name>...
python3 "${CLAUDE_SKILL_DIR}/scripts/clip.py" status
```

1. **`check`** first. It says what is missing — the keys, the model, where game videos go, the footage style paragraph.
2. **`new`.** Write in English **what happens in the shot** — who or what, doing what, where, how the camera moves — one shot, one action. Do not write the look:
   the footage style paragraph is appended to every description. Give reference images with `--image` (paths from the game root) when the shot must match
   something that exists — a character, a place, a frame to start from. The game's own art (asset images, screenshots) makes the footage look like the game.
3. **Show the user** the line `new` prints ("보낼 설명") and the reference images, with the seconds and the model. When they agree, `approve`. Changing the description, the images,
   the length or the model undoes the approval.
4. **`make`.** Tell the user it costs credits before the first one of a session. It uploads the images, sends the request, waits and downloads `<work>/<name>/clip.mp4`.
   If the wait is cut off, `make` again continues waiting — it does not send a second request. Run several names in one call only when each was approved.
5. **Give the path and wait.** The user watches. Not right → change the description (`new` again, then approve · make), or `make --again` for another take of the same description.
   Each take costs credits — say so, and do not retake unasked.
6. **`place`** when the user says it is good: `page` stays mp4 in `video.page.dir`; `game` is converted with `video.game.convert` into `video.game.dir`.

**Footage style** — one English paragraph between `<!-- footage-style -->` and `<!-- /footage-style -->` in `docs/DESIGN.md`: medium and rendering (painted, photoreal, stop-motion …),
palette, light, lens and grain, how the camera behaves. It is optional but without it every clip comes out in a different look — write it with the user before the second clip.

**The model is a setting.** `video.clip.model` is the Higgsfield endpoint ID; the user picks the model in the Higgsfield console and its page gives the ID and its inputs.
Models name their inputs differently — set them in `video.clip.fields`, and what is always sent in `video.clip.params`:

```json
"clip": { "model": "higgsfield/cinema-studio/4.0", "seconds": 5, "params": { "resolution": "720p" },
          "fields": { "prompt": "prompt", "seconds": "duration", "aspect": "aspect_ratio", "images": "image_urls", "image": "" } }
```

`images` is for a model that takes a list of reference images, `image` for one that takes a single start image (then set `images` to `""`). An empty name is not sent.
When changing the model, read that model's page for its allowed lengths and sizes — do not guess them. A model that returns an image or audio, not a video, does not work here.

- **Keys** (the user's, kept outside the repository): `HF_API_KEY_ID` and `HF_API_KEY_SECRET` in `~/.config/gamedev-kit/asset.env`, from the Higgsfield console. The user writes them in — do not ask for them in chat.
- Results stay on Higgsfield's servers for about a week; the downloaded `clip.mp4` is the copy that lasts. Commit `clip.json`; add `<work>/*/clip.mp4` to `.gitignore` if the files are large.
- Rejected by content moderation → the description or an image has to change; sending the same thing again does not help.
- Text inside generated footage comes out garbled. Put words on screen in the engine or an editor, not in the description.

## Which use

- **`page`** — a trailer, the video on the itch.io page, a clip for a devlog. Stays mp4, lands in `video.page.dir`.
  This skill makes the file. **It does not upload or post it anywhere** — the user does that.
- **`game`** — the game plays the file: an intro, an ending, a shot between chapters. Converted with `video.game.convert` into `video.game.dir`
  (the engine's config sets the format). If `game.dir` is empty, this game has no in-game video. The code that plays the file and lets the player skip it is development work.

One clip is one shot. A trailer or a cutscene of several shots is several clips, joined by the user or with ffmpeg — and anything where the game's characters
must act exactly as they do in play is made in the engine, not here. Say so before starting.

## Not covered

- Moving text — title cards, captions, credits. The kit used to render these from HTML (HyperFrames); that was taken out in 0.18.0 and is in the git history.
- Voice narration, and recording gameplay footage. Use what the user recorded.
- Uploading, posting, or embedding on a store page.
