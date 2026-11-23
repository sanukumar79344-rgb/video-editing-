#!/usr/bin/env python3
"""Speak one take with Piper, one line at a time, with a real pause between lines.

The film is cut into lines by finding the silences, and `piper` run over a whole take
joins its lines with almost no gap, so the cutter sees one long line. This speaks each
line on its own and joins them with a fixed silence, which is also a steadier read.

  piper_take.py --model VOICE.onnx --txt take.txt --out take.wav [--gap 0.75] [--pace 0.95]
"""
import argparse
import pathlib
import subprocess
import sys
import tempfile
import wave


def say(model, text, out, pace):
    p = subprocess.run(["piper", "-m", str(model), "--length-scale", str(pace), "-f", str(out)],
                       input=text, capture_output=True, text=True)
    if p.returncode != 0 or not pathlib.Path(out).exists():
        sys.exit(f"piper failed on: {text[:60]}\n{p.stderr[-600:]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--txt", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--gap", type=float, default=0.75)
    ap.add_argument("--pace", type=float, default=0.95)
    a = ap.parse_args()

    lines = [l.strip() for l in pathlib.Path(a.txt).read_text().splitlines() if l.strip()]
    if not lines:
        sys.exit("empty take")
    with tempfile.TemporaryDirectory() as td:
        td = pathlib.Path(td)
        parts = []
        for i, line in enumerate(lines):
            w = td / f"{i:03d}.wav"
            say(a.model, line, w, a.pace)
            parts.append(w)
        with wave.open(str(parts[0])) as w0:
            params = w0.getparams()
        silence = b"\0" * int(params.framerate * a.gap) * params.sampwidth * params.nchannels
        with wave.open(a.out, "wb") as out:
            out.setparams(params)
            for i, p in enumerate(parts):
                if i:
                    out.writeframes(silence)
                with wave.open(str(p)) as w:
                    out.writeframes(w.readframes(w.getnframes()))
    print(f"{len(lines)} lines -> {a.out}")


if __name__ == "__main__":
    main()
