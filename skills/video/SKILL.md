---
name: video
description: >-
  Makes motion-graphics videos from a script: cut table (on-screen text · seconds) → human approves → HTML composition (HyperFrames) →
  stills checked → render → placed where it is used. Two uses: `page` — outside the game (trailer, itch.io page, devlog clip) as mp4;
  `game` — a cutscene the game plays as a video file (intro, ending, title card), converted to the format the engine reads.
  One video style paragraph in docs/DESIGN.md is applied to every video, and each video's cut table and result are recorded.
  Use when the user says "영상 만들어줘", "트레일러 만들자", "컷씬 만들어줘", "인트로 영상", "엔딩 영상", "devlog 에 넣을 영상",
  asks to change the text, timing, colors or motion of an existing video, or approves a cut table; when the cycle's design section lists
  a cutscene or trailer that does not exist; when first setting the video style paragraph or installing HyperFrames.
---

# video

```
what it is + script ─▶ cut table ─▶ [human looks] ─▶ composition ─▶ stills ─▶ render ─▶ where it is used
new                    cuts          approve          compose        frames    render    docs/video · game folder
```

**The human looks at two places: the cut table and the finished video.** The table is cheap — rewrite it as often as needed. Writing the
composition and rendering take minutes and tokens, so only an approved table becomes a composition. You can check stills, but **you cannot
see motion** — after rendering, give the path and the user watches.

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/video.py" check
python3 "${CLAUDE_SKILL_DIR}/scripts/video.py" new <name> --for game|page [--size landscape|portrait|square] "<what video this is>"
python3 "${CLAUDE_SKILL_DIR}/scripts/video.py" cuts <name> [<file>|-]
python3 "${CLAUDE_SKILL_DIR}/scripts/video.py" approve <name>
python3 "${CLAUDE_SKILL_DIR}/scripts/video.py" compose <name>
python3 "${CLAUDE_SKILL_DIR}/scripts/video.py" lint <name>
python3 "${CLAUDE_SKILL_DIR}/scripts/video.py" frames <name>
python3 "${CLAUDE_SKILL_DIR}/scripts/video.py" render <name> [--draft]
python3 "${CLAUDE_SKILL_DIR}/scripts/video.py" status
```

## Which use

- **`page`** — a trailer, the video on the itch.io page, a clip for a devlog. Stays mp4, lands in `video.page.dir`.
  This skill makes the file. **It does not upload or post it anywhere** — the user does that.
- **`game`** — the game plays the file: an intro, an ending, a chapter card, a logo. Converted with `video.game.convert` into `video.game.dir`.
  This is text, shapes, images and sound moving on a flat screen. **A cutscene where the game's characters act in the game's world is not this** —
  that is made in the engine (development work, a cycle task). If the user asks for that, say so before starting.
  The code that plays the file and lets the player skip it is also development work.

## Procedure

1. **`check`.** If a tool is missing, see "First time only". If the video style paragraph is empty, fill it first ("Video style" below).
2. **Look at what exists.** `status`. To change an existing video, change its cut table or composition — do not start a new name.
3. **`new`.** One sentence on what the video is for and who watches it.
4. **Write the cut table** — one line per cut, `seconds | on-screen text | what moves`:

   ```
   2.5 | <게임>              | title drops in letter by letter, holds
   3   | 혼자서는 못 나간다   | line types on; background darkens
   4   |                     | three gameplay stills slide past (assets/shots/a.png …)
   ```

   - **On-screen text is not the script.** From a narration or story text, pull only the few words that must be read; the rest is said by motion or left out.
   - **Seconds come from reading, not from taste.** The script marks cuts too tight to read (`← 읽기 빠듯하다`) — shorten the text or lengthen the cut.
     If there is narration or music, the cuts add up to its length.
   - A cut may have no text. Then the third column says what is seen.
   - Name image, video and sound files that already exist in the game by path. Missing art and sound are made with the asset skill first.

   Save it with `cuts <name> -` (stdin) or a file. Changing the table clears the approval.
5. **Show the table as the script printed it and ask.** On a yes, `approve`. If the user said "make it" after seeing this exact table, that is the approval.
6. **`compose`.** The first time it scaffolds the composition folder (`hyperframes init`); every time it prints the style paragraph and each cut's start time.
   Write `comp/index.html` from that — one clip per cut, start and duration **exactly as printed**. Do not retime while animating; to retime, go back to `cuts`.
   The attribute and timeline rules belong to the installed HyperFrames version — read them from it, not from memory:
   `npx hyperframes docs data-attributes`, `npx hyperframes docs gsap`.
   Colors, fonts and sizes come from `docs/DESIGN.md` — the video is part of the same game.
7. **`lint`, then `frames`, and read the stills.** Check on each: is the text inside the frame, readable against the background, the right cut's text,
   nothing overlapping. Fix and repeat. Stills show layout, not motion.
8. **`render --draft`** and give the path. The user watches and says what to change. Text, color and size edits are composition edits — render again.
   When they say it is good, `render` without `--draft`. For a live look while editing, `npx hyperframes preview <work>/<name>/comp` opens a browser studio
   (it keeps running — stop it with `--stop` when done).
9. During a cycle, write the path in the "있는가" cell of the design section's "필요한 에셋" table.

## Video style

The paragraph between `<!-- video-style -->` and `<!-- /video-style -->` in `docs/DESIGN.md`, in English, things true of every video of this game:
background, type (family, weight, how big against the frame), how things enter and leave (snap, ease, typewriter), pace, how much is on screen at once,
what never appears. Derive it from the game's own colors and fonts already in that document.

If it is empty: ask the user for two or three screenshots of videos with the feel they want, describe what those have in common, write the paragraph, and
show it before making the first video. Changing it later makes new videos differ from old ones — say so.

## Config

```json
"video": {
  "work": "video",
  "size": "landscape",
  "quality": "standard",
  "page": { "dir": "docs/video" },
  "game": { "dir": "assets/video", "ext": "ogv", "convert": ["-c:v", "libtheora", "-q:v", "7", "-c:a", "libvorbis", "-q:a", "4"] }
}
```

- `game.ext` · `game.convert` — the format the engine plays and the ffmpeg arguments that produce it. They come with the engine's `kit.config.json`.
  If `game.dir` is empty, this game has no in-game video.
- `hyperframes` · `ffmpeg` — the commands to call, if not `npx hyperframes` and `ffmpeg`.
- `read_cps` — characters per second a viewer can read (default 8). Lower it for dense scripts or young players.
- Commit `<work>/<name>/video.json` and `comp/`. Add `<work>/*/renders/`, `<work>/*/comp/snapshots/` and `node_modules/` to `.gitignore`.

## First time only (done by the user)

- **Node.js 22+ and FFmpeg** on PATH. FFmpeg must include the encoder named in `game.convert`.
- **HyperFrames** is fetched by `npx hyperframes` on first run, and it downloads a browser for rendering. Tell the user this before the first run and let them start it.
  `npx hyperframes doctor` shows what is missing.

## Pitfalls

- **Long videos cost more than they look.** Each cut is HTML you write and frames the renderer captures. Past about a minute, split into several videos and join them.
- **Do not put the whole script on screen.** A frame full of text reads as a slide, not a video.
- **Rendering is deterministic but fonts are not.** A font that exists only on this machine renders differently elsewhere — use the game's font files by path.
- **Do not say "it came out well".** You saw stills. Say what you checked on them and give the path.

## Not covered

- Voice narration is not made here. If the user records one, name the file in the cut table and time the cuts to it.
- Recording gameplay footage. Use stills or clips the user captured.
- Uploading, posting, or embedding on a store page.
