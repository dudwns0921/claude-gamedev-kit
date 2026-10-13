# <game name> — Design rules

The rules for what the player sees and hears. The reasons behind the tone and the art direction are in the [GDD](GDD.md); this is how they are kept on screen.
The designer agent reads it and adds to it when a new rule is settled. A line the user edited always wins.

## Colors
Name · value · where it is used. A color that carries a meaning (danger · healing · reward) is written with its meaning.

## Fonts and text sizes

## Screen layout
Resolution · margins · where the HUD sits. What is on the HUD is set by GDD appendix A.5.

## Feedback to input
What comes back, and for how long, on a press · a hit · a pickup. Lengths are in seconds.

## Sound

### Sound style (generation prompt)
The paragraph the asset skill attaches as is behind the description of every sound effect and piece of music. In English, only words that fit any sound — texture (8-bit · acoustic · synth) · reverb · brightness.
Left empty, nothing is attached.

<!-- sound-style -->
<!-- /sound-style -->

## Assets
Where they go (folders) · how they are named · size · format.

### Art style (generation prompt)
The paragraph the asset skill attaches as is to the image prompt of every asset. In English, only words that fit any asset — how it is drawn · color · amount of detail · material · proportions.
Changing it sets new assets against the ones already made.

<!-- asset-style -->
<!-- /asset-style -->

### World (what exists)
What exists in this world — era and place, the materials things are made of, patterns and shapes that recur. One paragraph, in English. Attached after the art style, and read when writing a new asset's description. May stay empty.

<!-- asset-world -->
<!-- /asset-world -->

### Learned (said when turning assets down)
Rules that came from what the user said when turning assets down. One per line, in English, only words that fit any asset. The asset skill's `learn` adds them — up to twelve lines.

<!-- asset-learned -->
<!-- /asset-learned -->

## Video

### Footage style (attached to every clip)
The paragraph the video skill attaches behind the description every time it makes a shot with Higgsfield. In English, only words that fit any shot — what it looks made with (painted · photoreal · stop-motion …) ·
color · light · lens and grain · how the camera moves. It runs when left empty, but each clip then comes out with a different look.

<!-- footage-style -->
<!-- /footage-style -->

## What we do not do
