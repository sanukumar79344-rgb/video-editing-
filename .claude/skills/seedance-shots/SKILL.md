---
name: seedance-shots
description: Break a finished video script into a professional shot list and write one ready-to-paste Seedance 2.0 prompt per shot, with a locked cast/location bible and full continuity tracking. Use when the user has a script (Hindi horror episodes, animated story videos) and wants shot prompts, a storyboard breakdown, Seedance/AI-video prompts, or says "shot list", "break this into shots", "seedance prompts".
---

# Seedance 2.0 shot breakdown

Turn a finished script into a numbered shot list where every shot is a
self-contained, copy-paste Seedance 2.0 prompt.

**The governing fact:** the user generates each clip manually, one at a time.
Seedance has NO MEMORY between generations — it will not remember the previous
shot, the character, or the room. Every prompt must therefore stand completely
alone. This single constraint drives every rule below.

## Workflow

### 1. Read the whole script first

Do not start at line one. Read it all and work out the story, every character,
the geography (which locations exist, how they connect), the emotional
temperature of each beat, where the scares land and where the breathing room is.
Only then start breaking it down.

### 2. Deliver the BIBLE — then stop

First reply contains **only**:

- A **CAST BLOCK** for every character — 25–35 words: age, build, skin tone,
  hair shape and colour, one distinguishing feature, exact garment colours,
  exact accessories.

  > MEGHNA — Indian woman, 22, slim, warm tan skin, centre-parted black hair
  > in a low bun with one loose strand at the left cheek, small red bindi,
  > deep blue saree with a thin silver border, plain silver stud earrings.

- A **LOCATION BLOCK** for every place, same length and specificity.
- The **REFERENCE IMAGE LIST** — one character sheet per speaking character,
  one plate per location, numbered in a fixed upload order.
- The **total shot count**, with a one-line justification.

Then stop and wait for "go". Do not write shots yet.

**Cast and location blocks are LOCKED.** Reproduce them word for word in every
prompt that character or place appears in. Never abbreviate, never reword, never
write "as described above" — byte-identical text is what produces identical
faces. The block in shot 200 must match shot 1 exactly.

### 3. Decide the shot count yourself

No formula. Decide what each moment needs, the way a director would.

| Shot type | Length |
|---|---|
| Reaction / cutaway | 2–3 s |
| Single line of dialogue | 3–5 s |
| Action or movement | 3–5 s |
| Establishing wide | 4–6 s |
| Atmosphere plate (no characters) | 4–8 s |
| Slow dread build / tension hold | 6–10 s |
| Fast scare | 2–3 s |

Pacing doctrine — cutting rate carries retention:

- **Fear beats** (first contact, confrontation): cut FAST, average 2.5–4 s.
  Short shots read as panic.
- **Exposition beats** (the elder's warning, the lore): cut SLOW, average 6–9 s.
  Long shots read as gravity.
- Never hold a static shot past 10 s — something must move: camera, subject,
  fog, firelight, a curtain.
- Change shot scale on every cut. Never medium to medium. Wide → medium → close.
- Cutting to the same subject: change angle by at least 30°, or it reads as a
  broken jump cut.
- Open every new location on a wide, then move in. Never open on a close-up in
  a place the audience has not seen.

A 23-minute episode typically lands between 230 and 320 shots.

### 4. Assign every line

Every narration and dialogue line in the script goes to a specific numbered
shot. Nothing is dropped. Split long narration paragraphs across several shots
rather than parking them on one static image. Wordless passages get shots too —
those are the travel and atmosphere sequences, and they need the most visual
invention.

### 5. Write each prompt

Seedance 2.0's official structure: **SUBJECT + MOTION** (both required), then
ENVIRONMENT, AESTHETICS, CAMERA, AUDIO. Natural flowing English prose, not
comma-separated keywords. **Under 200 words** — Seedance degrades past that.

Open any prompt using reference images with the official syntax:

> Reference the woman's appearance from Image 1 and the location from Image 2,
> maintaining consistent features.

Then, in order: shot scale and framing → the character using the locked cast
block verbatim → one clear action with unambiguous direction → the location
using the locked location block verbatim → lighting and time of day → camera
move (or "camera is locked off and static") → the style line → ambient sound only.

The exact style line, negative line, anti-drift line and output template are in
`reference/prompt-blocks.md`. Read that file before writing the first shot and
paste those lines unchanged.

### 6. Deliver in batches

1. Bible only → **stop**, wait for "go".
2. Then 15 shots per reply, in order. End each reply with the shot numbers
   covered and what comes next.
3. On "next", continue from where you stopped. Never restart, never re-number,
   never summarise what you already gave.

## The continuity engine

This is the part that matters most. Track it deliberately per shot.

**Screen direction** — a character faces one way and can only move that way.
Facing screen-left in shot 12 means walking screen-left in shot 13. Establish
direction the first time a character moves in a scene and hold it for the whole
scene. A turn must be written into a shot, never happen silently between cuts.

**The 180° line** — once two characters face each other they keep their sides
for the entire conversation. Meghna frame-left looking right, Dadi frame-right
looking left — that never swaps. Crossing it makes the room feel flipped.

**Pose handoff** — the last frame of a shot is the first frame of the next.
Open every continuing prompt with the exact starting pose: weight, which foot,
which hand holds what, where the head is turned. Not "he walks" but "beginning
mid-stride with weight already forward on the left foot, right hand gripping a
brass lantern at hip height".

**Entry and exit** — exits frame-right means enters the next shot from
frame-left. Always state which edge of frame they enter and leave by.

**Eyelines** — if A looks screen-right at B, B's shot shows B looking
screen-left. State the direction explicitly in both prompts.

**State persistence** — wet stays wet, mud stays, a torn sleeve stays torn, the
lantern stays in the same hand. Carry every state forward until the script
changes it. This is the most commonly dropped thing.

**Time of day cannot jump** — if the scene is night, every shot in it is night,
same moon position, same key light direction.

## Unambiguous motion

Never describe direction only in relation to the camera — the model reads it
either way and will get it backwards. Anchor direction to a physical detail
that **changes as the movement happens**.

| Weak | Strong |
|---|---|
| an old man walks into the pond | an old man wades from the dry bank into the water, the water line climbing from his ankles to his knees to his waist as he advances, his back to camera, ripples spreading outward away from him |
| she enters the house | she steps over the threshold from the lit courtyard into the dark interior, the doorway frame passing behind her shoulders, the light on her face falling away as she moves deeper in |
| he stands up | he pushes down on the armrests, his hips lifting clear of the seat, the chair rocking back slightly behind him as his full height comes into frame |

Every prompt involving movement needs at least one changing physical detail
that makes the direction impossible to reverse.

## When to use EXTEND instead of a fresh generation

Seedance 2.0 can extend an existing clip forward, picking up its exact ending
pose. Use it — not a fresh generation — whenever a shot continues the same
unbroken physical action as the shot before: rising and walking, turning and
reaching, running through a doorway. Fresh generation always breaks these.

For those shots give:

```
MODE: EXTEND — upload the previous clip as Video 1
PROMPT: "Generate the content after Video 1. [what happens next]"
```

Mark them clearly.

## Audio

The user lays their own Hindi voiceover in the edit — the narrator is their
channel's brand. **Never request narration or generated dialogue.** Request
ambient sound only: wind, crickets, water, footsteps, distant dogs.

When a character speaks on camera the mouth must still move, so add:

> the character's lips move naturally as if speaking, no audible dialogue

Then list the Hindi line separately in the AUDIO block below the prompt.

## Reference images

Remind the user, before shots start, to generate reference images: one clean
sheet per character (front / three-quarter / profile, neutral expression, plain
grey background) and one plate per location. Seedance's image reference system
does most of the consistency work — text descriptions alone are a fallback.

Limits: up to 9 images, 3 videos, 3 audio files per generation, but ByteDance
explicitly recommends far fewer than the maximum. **Two or three references
beats nine** — the character sheet and the location plate, nothing else unless
the shot genuinely needs it.

## Re-rolls

If a shot comes back wrong, rewrite only that one prompt, keeping the cast and
location blocks byte-identical. Never regenerate the batch.
