# Concept stage — agreeing on the look

The outcome is not pictures. It is three written things: the GDD's `Art direction`, the `Screen layout` section of `docs/DESIGN.md`, and the reference images in `docs/concept/` they name.
(Documents made before the titles were English have `아트 방향`, `화면 구성` and `색` — write into the sections the document has.)
Pictures are how the user finds out what they want.

## 1. Three questions before any picture

Ask these first, one per turn with options and one `recommended` (the GDD's loop and inputs usually decide them — say which line you read it from):

1. **Screen orientation** — portrait or landscape.
2. **Viewpoint** — top-down, side, isometric, first-person, behind the character…
3. **2D or 3D.** The viewpoint mostly decides it — read the answer to 2 before recommending:
   - **A camera that never turns** (straight-down, side view, one fixed screen) gets nothing from what 3D buys — any angle from one model — and still pays for meshes, rigs and lighting. Recommended: 2D.
     Seen from straight above, one drawing turned to the heading covers every direction.
   - **3D earns its cost** when the camera moves or turns; when one thing is seen from many directions (a slanted top-down or isometric view with 8-way movement —
     in 2D every motion is drawn once per direction); when many characters share motions (a rig is reused, a 2D motion is made per character); when light and shadow must react.
   - Mixing (3D characters over 2D ground) works but adds the work of joining them — say so when offering it.

These change how everything is built (and what the engine project is set to), and a picture drawn before them answers a question nobody asked.

## 2. References first

**Ask whether the user has reference images** — screenshots, photos, drawings they like. They go in `docs/concept/` (the user puts them there; any image format).
For each, ask what in it they like (one thing) — a reference without that sentence gets copied whole.

If the user would rather have pictures generated, the kit draws none itself: follow the user's ways of working (`ways.md`) if they say how pictures are made,
otherwise ask which tool or service they want and keep the answer as a way (the feedback skill's `way`). Say how many will be made and that each one may cost money, and wait for a yes.
Start with two or three that differ in one clear way, not eight, in the orientation decided above, saved in `docs/concept/` under new names — never over an existing one.

## 3. You do not look

**Do not Read a generated image.** An image stays in context for the rest of the session and is re-sent every turn — and your opinion of it is not the point.
Give the paths, say plainly **"I have not looked at this picture"**, and ask what the user sees: what is right, what is wrong, one thing to change.
(The same goes for references the user added — ask them to describe what they like in it rather than opening it.)

## Prompt rules (when pictures are generated)

- **No studio, brand, film or game names, and no real person's likeness.** When the user says "like X", turn it into described traits — shape language (round · angular · chunky), palette, light, line, level of detail — and **tell the user you did** and show the traits, so they can correct the translation.
- **One change per redraw.** Two changes at once and nobody knows which one fixed it or broke it.
- **When the user likes an image, redraw from it as the reference**, asking only for the change — starting over from text loses what they liked.
- A prompt describes what is on screen: the viewpoint and orientation decided above, what the player sees in a typical moment of the innermost loop, palette, light, how things are drawn.

## What a picture can and cannot fix

- **A generated picture fixes the look, not the layout.** Where rooms, paths and objects sit is laid out in the game, where it can be exact and tested. When the user judges a picture by its layout ("문이 왼쪽이어야 하는데" — "the door should be on the left"), say so, and ask whether the *look* is right.
- **Different looks for different kinds of things are allowed** — e.g. characters drawn one way, the environment another. Record each and **why** (what the difference does for the player); a difference with no reason is drift.

## Writing it down

When the user agrees:

- **GDD `Art direction`**: orientation · viewpoint · 2D/3D, the look in a few lines (per kind of thing, if they differ, with the reason), and the reference images by path (`docs/concept/<name>.png` — which one stands for what).
- **`docs/DESIGN.md` → `Screen layout`**: orientation and reference resolution, viewpoint, where the play area and the HUD sit. Name the same reference images.
  Add the agreed palette to `Colors` if it was settled.
- **`docs/DESIGN.md` → `Art style`**: how things are drawn, palette, level of detail — a few lines anyone making an asset can follow, whatever they make it with.

## End of the stage

`start.py status` shows concept as done. One line: this is a good place to `/clear` — then `/gamedev-kit:start` continues (next: first goal).
