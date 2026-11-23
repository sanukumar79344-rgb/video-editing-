---
name: hindi-horror-script-writer
description: Writes a complete, production-ready 23-minute Hindi animated horror script (screenplay format with dialogue, narration, shot directions, silent visual beats and sound cues) from just a topic or folklore idea, then delivers it as a clean PDF. Use this skill whenever someone gives a horror story topic, folk entity, chudail/bhoot/taboot/kuan/dayan idea, or asks for a Hindi horror script, bhootiya kahani script, horror animation script, YouTube horror story script, or a script for a horror animation channel — even if they only say "write a script about X" and don't mention Hindi, length or PDF. Also use it when someone wants a multi-part horror series outline or asks to continue an existing horror series.
---

# Hindi Animated Horror Script Writer

Writes full-length Hindi animated horror scripts built on a beat architecture reverse-engineered from the highest-performing channels in the category (a corpus of 32 scripts, 83,521 words, 692 minutes of runtime).

The output is not narration with pictures over it. It is a **screenplay** — dialogue, narration, shot directions, wordless visual sequences and sound cues — because that is what the top performers in this category actually are.

## Workflow

1. Take the topic. If the user gave only a folk entity or a one-line idea, that is enough — do not interrogate them. Infer the rest.
2. Read `references/beat-architecture.md` and follow the nine-beat structure exactly.
3. Read `references/hooks-and-cliffhangers.md` to select the opening and closing machine.
4. Read `references/language-craft.md` for Hindi register, stock phrases, sound cue inventory and silent-beat rules.
5. Write the full script to a `.txt` file using the element format below.
6. Run `scripts/build_pdf.py` to render it as a PDF.
7. Present the PDF with `present_files`.

Ask a clarifying question **only** if the user has not indicated whether this is a standalone or part of a series, and the topic doesn't imply it. Default to **Part 1 of a series with a cliffhanger ending** — series episodes outperform standalones by 4× on both views and comment rate.

## The numbers this script must hit

These are not stylistic preferences. They are the measured specification of what works in this category.

| Target | Value | Why |
|---|---|---|
| Total spoken words | 2,800–2,900 | Produces 23 minutes at the correct delivery speed |
| Delivery speed | 130 WPM | The breakout series ran 127–140; slower content underperformed |
| Runtime | 23:00 | 18–26 min is the proven band; over 30 min collapses |
| Wordless screen time | ~14% (≈3 min 15 s) | Travel, arrival, atmosphere. The animation carries these. |
| Silent beats | 12–16 | Distributed, not clustered |
| Sound cues | 20–24 | Roughly one designed audio event every 65 seconds |
| Question marks | ~35 | Tension markers, ~1.5 per minute |
| Calls to action | **Zero** | Never write "subscribe", "like", "share", "comment", or the channel name into the voice track |
| First supernatural signal | Under 60 s (Part 1) / under 25 s (Part 2+) | The single clearest difference between breakout and non-breakout content |

Count the words when finished. If under 2,700 or over 3,000, revise rather than shipping it.

## Element format

Write the script in plain text using exactly these element types. The PDF builder parses them.

```
# TITLE OF STORY — Part 1

[VISUAL] Wide. A village lane at night, one lantern burning. Camera slowly pushes in.
[SFX] संगीत — low drone, rising
[SILENT 12s] Madan walks left-to-right down the lane. Cut to the forest edge — he is still moving left-to-right. Crickets fade.

NARRATOR: बेरमपुर, मध्य प्रदेश की वादियों में बसा एक खूबसूरत गांव।

पिताजी: अरे मदन, कहां जा रहा है इस समय?

मदन: पिताजी, मेरे मित्रों से इतने दिनों बाद मिलना हो रहा है।

[BEAT 2 — THE RULE | 0:40–1:50 | 140 words]
```

**Element rules:**

- `[VISUAL]` — a shot direction. Name the shot scale (Wide / Medium / Close / Atmosphere plate) and the camera move if any. One or two lines.
- `[SFX]` — a sound cue. Use the Hindi cue names from `references/language-craft.md`.
- `[SILENT Ns]` — a wordless sequence with its duration in seconds. Describe what the animation shows. These are load-bearing; see the silent-beat section below.
- `[BEAT n — NAME | clock | word budget]` — a beat header. Insert one before each of the nine beats.
- `NARRATOR:` — narration line.
- `NAME:` — dialogue. Use the character's Hindi name.

## Silent beats — the part most scripts get wrong

Roughly one seventh of the runtime has nobody speaking. In the source corpus the longest of these runs 31 seconds. They are not padding — they are how a low-budget animation feels like a film.

The grammar is consistent and you should reproduce it:

**Write a departure, then cut to an arrival, and hand the middle to the animator.**

```
NARRATOR: उसने गांव के एक आदमी विपुल को साथ लिया और जंगल की तरफ बढ़ गया।

[SILENT 31s] They walk into the treeline. Cut: feet on dry leaves. Cut: lantern
swinging, shadows swelling on trunks. Cut: wide, two small figures swallowed by
the forest. Both figures move left-to-right in every shot.
[SFX] पायल / footsteps on leaves, crickets, one distant dog

NARRATOR: काफी देर बाद एक बरगद के पेड़ के पास जाकर उनके कदम रुके।
```

Note the phrase that reopens the dialogue: **काफी देर बाद** ("after a long while"), **वहां पहुंचते हुए** ("on reaching there"), **उसी समय** ("at that moment"). These arrival phrases are the signature of a silent sequence having just ended. Use them.

Place silent beats at:
- Any journey between two locations
- The moment immediately after a scare, before anyone reacts
- Establishing a new location for the first time
- The final 20–30 seconds under the closing music

## Screen direction

Keep motion consistent across cuts. If a character moves left-to-right in one shot and the scene jump-cuts elsewhere, they still move left-to-right. If two characters face each other, keep them on the same sides of frame throughout the conversation.

This is the 180-degree rule and it is why the good channels in this category don't feel cheap. Every time the viewer has to re-establish who is where, comprehension drops slightly — and across 23 minutes of half-attention phone viewing before bed, that compounds into drop-off.

State the direction explicitly inside `[VISUAL]` and `[SILENT]` blocks so the animator can follow it.

## Shot vocabulary

Rotate through these. A script that is all medium shots reads as a slideshow.

| Shot | Use |
|---|---|
| **Atmosphere plate** | No characters at all — moon, dead trees, crows, fog, a dog silhouette. Pure mood. Cheap to animate, buys 10–20 seconds. Use 2–4 per script. |
| **Wide establishing** | First appearance of any location. Deep perspective. |
| **Medium** | Default for dialogue. Subject off-centre. |
| **Close reaction** | Fear, realisation, the moment of violation. Add radial speed lines and squiggle marks for shock beats — anime grammar, instantly readable, reusable asset. |
| **Symmetrical portrait** | Kings, tantriks, the entity revealed. Frontal, centred, static. Signals power. |

Vary the register across the script too — if the story has a flashback, put it in a different visual world (period palace, daylight city, rural night). This is what stops 23 minutes looking like six backgrounds.

## Hard rules

- **No calls to action in the voice track.** Not once. The cliffhanger does that job.
- **Never invent a monster.** The entity must be a real folk belief with a region attached. If the user's topic is invented, ground it in the nearest genuine folklore and say so briefly when presenting.
- **The rationalist is always wrong.** A modern sceptical character dismisses the tradition and is punished. This appears in 27 of 32 source scripts. It exists so the audience's inherited belief is validated.
- **No gore, no explicit violence, no sexual content, no real named people, no communal framing.** The category's advantage is that it is safe enough for a 12-year-old and broad enough for a Hindu and Muslim audience simultaneously.
- **Resolution mechanics stay generic** — tantrik, ritual, mantra, fire, ash — rather than explicitly sectarian. Roughly a quarter of this audience is Pakistani.

## Building the PDF

Once the `.txt` is written:

```bash
python3 scripts/build_pdf.py <input.txt> <output.pdf>
```

The script handles the Devanagari font automatically (downloads and caches it if not present) and installs `weasyprint` if missing. It also prints a validation report — word count, estimated runtime, silent-beat total, sound cue count and CTA check. **Read that report.** If it flags a problem, fix the script and rebuild rather than delivering it.

Save the PDF to `/mnt/user-data/outputs/` and present it.

## When presenting

Give the user, briefly:
- The word count and estimated runtime
- Which hook type you used and why
- The Rule (the taboo line) — this is the story's engine and they should know it
- If Part 1 of a series, one line on where Part 2 goes

Don't recap the plot. They can read it.

## Reference files

- `references/beat-architecture.md` — the nine beats, clock timings, word budgets, and what each beat must contain. Read this every time.
- `references/hooks-and-cliffhangers.md` — nine opening machines with real examples, the four-part cliffhanger, and a selection matrix. Read this every time.
- `references/language-craft.md` — Hindi register and honorifics, dialogue conventions, stock atmospheric phrases, the sound cue inventory, character archetypes. Read this every time.
