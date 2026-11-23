#!/usr/bin/env python3
"""
screenplay.py — turn a Hindi horror screenplay into a film project, and voice it.

The hindi-horror-script-writer skill writes a screenplay in plain text:

    # TITLE — Part 1
    [BEAT 1 — THE HOOK | 0:00-0:40 | 90 words]
    [VISUAL] Wide. A village lane at night, one lantern burning.
    [SFX] low drone, rising
    [SILENT 12s] Madan walks down the lane.
    NARRATOR: बेरमपुर, एक छोटा सा गाँव।
    मदन: पिताजी, मैं अभी आता हूँ।

This reads that and writes a project:

    script.json   every spoken line, in order, with who says it and which voice
    shots.json    the visual, silent and sound directions, tied to the line they follow
    audio/narration.m4a + audio/timing.json   voiced with Piper, line by line

Timings are exact: each line is rendered on its own and laid end to end with a
known gap, so nothing has to be recovered by looking for silences.

    python3 screenplay.py script.txt Stories/my-film            # parse + voice
    python3 screenplay.py script.txt Stories/my-film --parse-only
"""
import argparse
import json
import pathlib
import re
import subprocess
import sys
import tempfile
import wave

ROOT = pathlib.Path(__file__).resolve().parent
VOICES = ROOT / "tools" / "voices"

RE_TITLE = re.compile(r"^#\s+(.*)")
RE_BEAT = re.compile(r"^\[BEAT\s*(.*?)\]\s*$", re.I)
RE_VISUAL = re.compile(r"^\[VISUAL\]\s*(.*)", re.I)
RE_SFX = re.compile(r"^\[SFX\]\s*(.*)", re.I)
RE_SILENT = re.compile(r"^\[SILENT\s*([\d.]+)\s*s?\]\s*(.*)", re.I)
RE_SPEAK = re.compile(r"^([^:\[\]]{1,40}):\s*(.+)$")

# Piper has one male and one female Hindi voice; the narrator reads a touch slower
# than the characters so the two are easy to tell apart.
NARRATOR_VOICE = ("hi_IN-pratham-medium", 1.06)
MALE_VOICE = ("hi_IN-pratham-medium", 0.98)
FEMALE_VOICE = ("hi_IN-priyamvada-medium", 1.0)
FEMALE_HINT = re.compile(r"(माँ|मां|माता|अम्मा|बहन|दीदी|चाची|काकी|दादी|नानी|बुआ|मामी|"
                         r"पत्नी|बेटी|लड़की|औरत|महिला|चुड़ैल|डायन|देवी|रानी|मीरा|सीता|गीता|"
                         r"राधा|लक्ष्मी|पार्वती|कमला|शांति|सुनीता|रेखा|पूजा|आरती)")


def parse(path):
    title, beats = "Untitled", []
    cur = {"beat": "OPEN", "lines": [], "shots": []}
    lines_out, shots, idx = [], [], 0
    for raw in pathlib.Path(path).read_text(encoding="utf-8").splitlines():
        s = raw.strip()
        if not s:
            continue
        m = RE_TITLE.match(s)
        if m:
            title = m.group(1).strip()
            continue
        m = RE_BEAT.match(s)
        if m:
            if cur["lines"] or cur["shots"]:
                beats.append(cur)
            cur = {"beat": m.group(1).strip(), "lines": [], "shots": []}
            continue
        m = RE_VISUAL.match(s)
        if m:
            shot = {"kind": "visual", "after": idx, "beat": cur["beat"], "text": m.group(1).strip()}
            shots.append(shot); cur["shots"].append(shot); continue
        m = RE_SFX.match(s)
        if m:
            shot = {"kind": "sfx", "after": idx, "beat": cur["beat"], "text": m.group(1).strip()}
            shots.append(shot); cur["shots"].append(shot); continue
        m = RE_SILENT.match(s)
        if m:
            shot = {"kind": "silent", "after": idx, "beat": cur["beat"],
                    "seconds": float(m.group(1)), "text": m.group(2).strip()}
            shots.append(shot); cur["shots"].append(shot); continue
        m = RE_SPEAK.match(s)
        if m:
            who, text = m.group(1).strip(), m.group(2).strip()
        else:
            who, text = "NARRATOR", s
        idx += 1
        voice, pace = (NARRATOR_VOICE if who.upper() in ("NARRATOR", "नैरेटर", "सूत्रधार")
                       else FEMALE_VOICE if FEMALE_HINT.search(who) else MALE_VOICE)
        line = {"id": idx, "who": who, "text": text, "spoken": text,
                "voice": voice, "pace": pace, "beat": cur["beat"]}
        lines_out.append(line); cur["lines"].append(line)
    if cur["lines"] or cur["shots"]:
        beats.append(cur)
    takes = [{"take": f"B{i:02d}_" + re.sub(r"[^A-Za-z0-9]+", "_", b["beat"])[:24].strip("_"),
              "lines": b["lines"]} for i, b in enumerate(beats, 1) if b["lines"]]
    return {"title": title, "takes": takes}, shots


def say(model, text, out, pace):
    p = subprocess.run(["piper", "-m", str(VOICES / f"{model}.onnx"), "--length-scale", str(pace),
                        "-f", str(out)], input=text, capture_output=True, text=True)
    if p.returncode != 0 or not pathlib.Path(out).exists():
        sys.exit(f"piper failed: {text[:60]}\n{p.stderr[-500:]}")


def voice(script, shots, proj, gap=0.55, lead=0.6):
    """Render every line, lay them end to end, and write exact timings."""
    proj = pathlib.Path(proj)
    (proj / "audio").mkdir(parents=True, exist_ok=True)
    lines = [l for t in script["takes"] for l in t["lines"]]
    silent_after = {}
    for sh in shots:
        if sh["kind"] == "silent":
            silent_after[sh["after"]] = silent_after.get(sh["after"], 0.0) + sh["seconds"]
    with tempfile.TemporaryDirectory() as td:
        td = pathlib.Path(td)
        parts, segs, t = [], [], lead
        for i, l in enumerate(lines):
            w = td / f"{i:04d}.wav"
            say(l["voice"], l["spoken"], w, l["pace"])
            with wave.open(str(w)) as f:
                dur = f.getnframes() / f.getframerate()
                params = f.getparams()
            segs.append({"id": l["id"], "who": l["who"], "beat": l["beat"], "text": l["text"],
                         "start": round(t, 3), "end": round(t + dur, 3), "duration": round(dur, 3)})
            parts.append((w, t))
            t += dur + gap + silent_after.get(l["id"], 0.0)       # room for the wordless beats
        total = t + 1.2
        out_wav = proj / "audio" / "narration.wav"
        with wave.open(str(out_wav), "wb") as out:
            out.setparams(params)
            sr, sw, ch = params.framerate, params.sampwidth, params.nchannels
            written = 0
            for w, start in parts:
                pad = int(start * sr) - written
                if pad > 0:
                    out.writeframes(b"\0" * pad * sw * ch); written += pad
                with wave.open(str(w)) as f:
                    n = f.getnframes(); out.writeframes(f.readframes(n)); written += n
            tail = int(total * sr) - written
            if tail > 0:
                out.writeframes(b"\0" * tail * sw * ch)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(out_wav), "-af",
                    "highpass=f=70,acompressor=threshold=-20dB:ratio=2.2:makeup=2,"
                    "loudnorm=I=-16:TP=-1.5:LRA=11", "-c:a", "aac", "-b:a", "192k",
                    str(proj / "audio" / "narration.m4a")], check=True)
    out_wav.unlink(missing_ok=True)
    timing = {"total_duration": round(total, 3), "lead_in": lead, "gap": gap, "segments": segs}
    (proj / "audio" / "timing.json").write_text(json.dumps(timing, ensure_ascii=False, indent=1))
    return timing


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("screenplay")
    ap.add_argument("project")
    ap.add_argument("--parse-only", action="store_true")
    ap.add_argument("--gap", type=float, default=0.55)
    a = ap.parse_args()
    proj = pathlib.Path(a.project); proj.mkdir(parents=True, exist_ok=True)
    script, shots = parse(a.screenplay)
    (proj / "script.json").write_text(json.dumps(script, ensure_ascii=False, indent=1))
    (proj / "shots.json").write_text(json.dumps(shots, ensure_ascii=False, indent=1))
    n = sum(len(t["lines"]) for t in script["takes"])
    words = sum(len(l["spoken"].split()) for t in script["takes"] for l in t["lines"])
    print(f"{script['title']}: {len(script['takes'])} beats, {n} lines, {words} spoken words, "
          f"{len(shots)} directions "
          f"({sum(1 for s in shots if s['kind'] == 'silent')} silent, "
          f"{sum(1 for s in shots if s['kind'] == 'sfx')} sfx)")
    if a.parse_only:
        return
    t = voice(script, shots, proj, gap=a.gap)
    print(f"voiced: {t['total_duration'] / 60:.1f} min -> {proj}/audio/narration.m4a")


if __name__ == "__main__":
    main()
