#!/usr/bin/env python3
"""
make_story.py — one command from a written script to a finished YouTube story video.

It drives the cinematic-film skill end to end with a real voice (Piper, local):

    new project -> fonts -> voiceover -> per-line timings -> board textures
    -> stills you check -> draft -> sound effects -> mix -> full render -> captions

Usage
  python3 make_story.py new  Stories/ice-core --title "What Was Under The Ice"
      Writes a project folder with script.json ready to fill in.

  python3 make_story.py voice Stories/ice-core --voice ryan
      Records the script with Piper and works out every line's timing.
      Re-run it whenever the script changes; nothing else needs touching.

  python3 make_story.py look  Stories/ice-core --at 2,8,15
      Stills at those seconds, so the layout can be judged before any render.

  python3 make_story.py draft Stories/ice-core --seconds 30
      First 30 s at 720p.

  python3 make_story.py final Stories/ice-core [--vertical] [--size 1920x1080]
      Sound effects, mix, full render, burned-in captions and an SRT.
      --vertical renders 1080x1920 for Shorts/Reels instead.

Voices (tools/voices, Piper, MIT, no account, no limit, nothing leaves the machine):
  ryan      en_US male, deep, documentary narrator
  amy       en_US female, warm (hfc_female)
  pratham   hi_IN male
  priyamvada hi_IN female
"""
import argparse
import json
import os
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent
SK = ROOT / ".claude" / "skills" / "cinematic-film" / "scripts"
VOICES = ROOT / "tools" / "voices"
NAMES = {"ryan": "en_US-ryan-high", "amy": "en_US-hfc_female-medium",
         "pratham": "hi_IN-pratham-medium", "priyamvada": "hi_IN-priyamvada-medium"}


def sk(script, *args, **kw):
    cmd = [sys.executable, str(SK / script), *map(str, args)]
    print("+", " ".join(cmd[1:]), file=sys.stderr)
    subprocess.run(cmd, check=True, **kw)


def voice_model(name):
    m = VOICES / f"{NAMES.get(name, name)}.onnx"
    if not m.exists():
        sys.exit(f"no voice {name}: have {', '.join(sorted(NAMES))}\n"
                 f"(models live in {VOICES}; setup.sh downloads them)")
    return m


def cmd_new(a):
    sk("new_project.py", a.project, "--title", a.title)
    sk("get_fonts.py", "--project", a.project)
    print(f"\nNow write {a.project}/script.json, then:  python3 make_story.py voice {a.project}")


def cmd_voice(a):
    model = voice_model(a.voice)
    # length_scale <1 speeds the read up; 0.95 keeps a documentary pace without sounding rushed.
    tts = (f"{sys.executable} {ROOT / 'tools' / 'piper_take.py'} --model {model} "
           f"--pace {a.pace} --gap {a.gap} --txt {{txt}} --out {{out}}")
    sk("tts_say.py", "--project", a.project, "--cmd", tts)
    sk("split_takes.py", "--project", a.project)
    sk("build_narration.py", "--project", a.project)
    sk("prep_assets.py", "--project", a.project)
    t = json.loads((pathlib.Path(a.project) / "audio" / "timing.json").read_text())
    dur = t.get("total_duration", 0.0)
    print(f"\nvoice done — {dur:.1f}s. Next: write the scene, then "
          f"python3 make_story.py look {a.project}")


def cmd_look(a):
    sk("render.py", "--project", a.project, "--probe", a.at, "--size", "1280x720")
    print(f"\nstills in {a.project}/out/probe — look at every one before rendering")


def cmd_draft(a):
    sk("render.py", "--project", a.project, "--t0", "0", "--t1", str(a.seconds),
       "--size", "1280x720", "--out", "out/draft.mp4", "--audio", "audio/narration.m4a")


def cmd_final(a):
    p = pathlib.Path(a.project)
    size = "1080x1920" if a.vertical else a.size
    sk("render.py", "--project", a.project, "--cues")
    sk("build_sfx.py", "--project", a.project)
    music = ["--music", str(a.music)] if a.music else []
    sk("mix_soundtrack.py", "--project", a.project, *music)
    mix = p / "audio" / "mix.m4a"
    audio = "audio/mix.m4a" if mix.exists() else "audio/narration.m4a"
    sk("render.py", "--project", a.project, "--size", size, "--out", "out/film.mp4", "--audio", audio)
    sk("burn_captions.py", "--project", a.project, "--video", "out/film.mp4",
       "--audio", audio, "--style", a.captions, "--out", "out/final.mp4")
    sk("burn_captions.py", "--project", a.project, "--srt-only", "--out", "out/captions.srt")
    out = p / "out" / "final.mp4"
    print(f"\ndone -> {out if out.exists() else p / 'out' / 'film.mp4'}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    s = ap.add_subparsers(dest="cmd", required=True)
    n = s.add_parser("new"); n.add_argument("project"); n.add_argument("--title", default="Untitled")
    n.set_defaults(fn=cmd_new)
    v = s.add_parser("voice"); v.add_argument("project"); v.add_argument("--voice", default="ryan")
    v.add_argument("--pace", type=float, default=0.95)
    v.add_argument("--gap", type=float, default=0.9, help="silence after each sentence (split_takes needs it)")
    v.set_defaults(fn=cmd_voice)
    l = s.add_parser("look"); l.add_argument("project"); l.add_argument("--at", default="1,5,10")
    l.set_defaults(fn=cmd_look)
    d = s.add_parser("draft"); d.add_argument("project"); d.add_argument("--seconds", type=int, default=30)
    d.set_defaults(fn=cmd_draft)
    f = s.add_parser("final"); f.add_argument("project"); f.add_argument("--size", default="1920x1080")
    f.add_argument("--vertical", action="store_true"); f.add_argument("--music", default=None)
    f.add_argument("--captions", default="highlighter", choices=["highlighter","clean","paper","redbar"]); f.set_defaults(fn=cmd_final)
    a = ap.parse_args()
    if not SK.exists():
        sys.exit(f"cinematic-film skill missing at {SK} — run ./setup.sh")
    a.fn(a)


if __name__ == "__main__":
    main()
