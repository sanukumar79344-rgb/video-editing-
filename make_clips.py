#!/usr/bin/env python3
"""
make_clips.py — turn a long video into several 25-50 s vertical Reels/Shorts.

Watches the whole video (word-level transcript + loudness curve + YouTube
"most replayed" heatmap when present), scores every sentence-aligned window in
the 25-50 s range for viral potential, then renders the best non-overlapping
ones as finished, publish-ready verticals.

Each clip gets: 1080x1920 9:16, face-tracked crop (or blurred fill), a slow
Ken-Burns drift with gentle punch-ins on the biggest emphasis beats, burned-in
word-highlight captions inside the Reels/Shorts safe zone, two-pass EBU R128
audio at -14 LUFS / -1 dBTP, fades, and H.264 High CRF 18 +faststart.

Usage
  python3 make_clips.py "https://youtu.be/VIDEOID" -n 3 -o out/
  python3 make_clips.py URL --cookies cookies.txt -n 5
  python3 make_clips.py source.mp4 --min 30 --max 45 --model medium
  python3 make_clips.py URL --dry-run          # pick + report timestamps, render nothing
"""
import argparse
import json
import math
import re
import subprocess
import sys
from pathlib import Path

import make_short as ms
from make_short import (SENT_END, HOOK_PATTERNS, WEAK_STARTS, TAIL_WEAK,
                        W, H, FADE, heat_at, fmt_ts, probe)

MIN_DUR, MAX_DUR, IDEAL = 25.0, 50.0, 34.0
MIN_GAP = 2.0          # seconds of source that must separate two chosen clips
HOP = 0.1


# --------------------------------------------------------------------- select
def windows(words, min_d, max_d, duration):
    """Sentence-aligned windows whose padded length lands in [min_d, max_d]."""
    n = len(words)
    for i in range(n):
        if i > 0 and not (SENT_END.search(words[i - 1]["w"])
                          or words[i]["t0"] - words[i - 1]["t1"] >= 0.35):
            continue
        gap_before = words[i]["t0"] - (words[i - 1]["t1"] if i else 0.0)
        pre = min(0.15, max(0.0, gap_before - 0.08))
        for j in range(i, n):
            core = words[j]["t1"] - words[i]["t0"]
            if core > max_d:
                break
            if core < min_d - 0.5:
                continue
            gap_after = (words[j + 1]["t0"] if j + 1 < n else words[j]["t1"] + 1.5) - words[j]["t1"]
            if not (SENT_END.search(words[j]["w"]) or gap_after >= 0.3):
                continue
            post = min(0.35, max(0.0, gap_after - 0.08))
            t_in, t_out = max(0.0, words[i]["t0"] - pre), words[j]["t1"] + post
            dur = t_out - t_in
            if not (min_d <= dur <= max_d) or t_out > duration:
                continue
            yield i, j, round(t_in, 3), round(t_out, 3)


def silence_ratio(energy, t_in, t_out):
    seg = energy[int(t_in / HOP):int(t_out / HOP)] or [-60]
    return sum(1 for e in seg if e < -45) / len(seg)


def score(words, i, j, t_in, t_out, energy, heatmap):
    """Viral-potential score for a 25-50 s window. Higher is better."""
    text = " ".join(w["w"] for w in words[i:j + 1])
    lower = text.lower()
    dur = t_out - t_in
    seg = energy[int(t_in / HOP):int(t_out / HOP)] or [-60]
    voiced = [e for e in seg if e > -45] or seg
    mean_db = sum(voiced) / len(voiced)
    dyn = max(seg) - mean_db
    g_voiced = [e for e in energy if e > -45] or energy
    loud = mean_db - (sum(g_voiced) / len(g_voiced))

    hook = sum(len(re.findall(p, lower)) for p in HOOK_PATTERNS)
    first3 = " ".join(w["w"] for w in words[i:j + 1] if w["t0"] < t_in + 3.0).lower()
    early_hook = sum(len(re.findall(p, first3)) for p in HOOK_PATTERNS)
    first = re.sub(r"[^a-z']", "", words[i]["w"].lower())
    weak_start = first in WEAK_STARTS
    wps = (j - i + 1) / dur
    conf = sum(w["p"] for w in words[i:j + 1]) / (j - i + 1)
    ends_clean = bool(SENT_END.search(words[j]["w"]))
    tail = " ".join(w["w"] for w in words[i:j + 1] if w["t1"] > t_out - 4.0).lower()
    tail_weak = len(re.findall(TAIL_WEAK, tail))
    heat = heat_at(heatmap, t_in, t_out)
    dead = silence_ratio(energy, t_in, t_out)        # long clips die on dead air
    # A question early + its answer later reads as a complete, satisfying arc.
    arc = 1.0 if ("?" in text[:len(text) // 2] and ends_clean) else 0.0

    s = (3.0 * heat
         + 0.08 * dyn + 0.10 * loud
         + 0.30 * min(hook, 10) + 0.6 * min(early_hook, 3)
         + (-1.5 if early_hook == 0 else 0.0)
         + (-1.2 if weak_start else 0.0)
         + (0.5 if ends_clean else 0.0)
         + 0.8 * arc
         - 0.6 * abs(wps - 2.7)
         + 1.0 * (conf - 0.8)
         - 1.5 * min(tail_weak, 2)
         - 3.0 * max(0.0, dead - 0.25)
         - 0.02 * abs(dur - IDEAL))
    return s, {"text": text, "heat": round(heat, 3), "dyn_db": round(dyn, 2),
               "loud_vs_avg_db": round(loud, 2), "hook_hits": hook,
               "early_hook_hits": early_hook, "weak_start": weak_start,
               "words_per_sec": round(wps, 2), "weak_tail_hits": tail_weak,
               "asr_conf": round(conf, 3), "ends_on_sentence": ends_clean,
               "silence_ratio": round(dead, 3), "question_arc": bool(arc)}


def pick(words, energy, heatmap, duration, count, min_d, max_d):
    """Greedy: best-scoring window first, then the best that doesn't overlap it."""
    scored = []
    for i, j, t_in, t_out in windows(words, min_d, max_d, duration):
        s, d = score(words, i, j, t_in, t_out, energy, heatmap)
        scored.append((s, i, j, t_in, t_out, d))
    if not scored:
        raise SystemExit(f"No sentence-aligned window between {min_d:g}s and {max_d:g}s was found.")
    scored.sort(key=lambda x: -x[0])
    chosen = []
    for cand in scored:
        if len(chosen) >= count:
            break
        _, _, _, t_in, t_out, _ = cand
        if all(t_in >= c[4] + MIN_GAP or t_out <= c[3] - MIN_GAP for c in chosen):
            chosen.append(cand)
    chosen.sort(key=lambda x: x[3])      # chronological output order
    return chosen, len(scored)


def punch_times(words, i, j, energy, t_in, t_out, want=3):
    """Times (relative to clip) of the most emphasised words, >=5 s apart."""
    cands = []
    for w in words[i:j + 1]:
        if w["t0"] < t_in + 1.0 or w["t0"] > t_out - 2.0:
            continue
        e = max(energy[int(w["t0"] / HOP):int(w["t1"] / HOP) + 1] or [-90])
        bonus = 3.0 if re.search(HOOK_PATTERNS[0], w["w"].lower()) else 0.0
        cands.append((e + bonus, w["t0"] - t_in))
    cands.sort(key=lambda x: -x[0])
    picked = []
    for _, t in cands:
        if len(picked) >= want:
            break
        if all(abs(t - p) >= 5.0 for p in picked):
            picked.append(t)
    return sorted(picked)


# --------------------------------------------------------------------- render
def zoom_expr(dur, peaks):
    """Slow 1.00->1.05 drift plus smooth +0.055 bumps on each emphasis beat."""
    terms = [f"1.0+0.05*t/{dur:.3f}"]
    for t in peaks:
        terms.append(f"0.055*exp(-0.5*pow((t-{t:.3f})/0.9\\,2))")
    return "+".join(terms)


def render_clip(video, src, t_in, t_out, peaks, ass_path, out, face_x):
    dur = t_out - t_in
    out_fps = 60 if src["fps"] > 45 else 30
    sw, sh = src["w"], src["h"]
    if face_x is not None or sw / sh <= 9 / 16 + 0.01:
        cw = min(sw, round(sh * 9 / 16 / 2) * 2)
        cx = 0.5 if face_x is None else face_x
        x = int(min(max(cx * sw - cw / 2, 0), sw - cw))
        base = f"[0:v]crop={cw}:{sh}:{x}:0,scale={W}:{H}:flags=lanczos,setsar=1[base]"
    else:
        base = (f"[0:v]split[a][b];"
                f"[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
                f"boxblur=30:3,eq=brightness=-0.08[bg];"
                f"[b]scale={W}:-2:flags=lanczos[fg];"
                f"[bg][fg]overlay=(W-w)/2:(H-h)/2-120,setsar=1[base]")
    z = zoom_expr(dur, peaks)
    zoom = (f"[base]scale=w='trunc({W}*({z})/2)*2':h='trunc({H}*({z})/2)*2':"
            f"eval=frame:flags=bicubic,crop={W}:{H}:(iw-{W})/2:(ih-{H})/2*0.85")
    ass_esc = str(ass_path).replace("\\", "/").replace(":", r"\:").replace("'", r"\'")
    vf = (f"{base};{zoom},fps={out_fps},ass='{ass_esc}',"
          f"fade=t=in:st=0:d={FADE},fade=t=out:st={dur - FADE:.3f}:d={FADE},format=yuv420p[v]")
    wav = ms.normalize_audio(video, t_in, dur, Path(out).with_suffix(".norm.wav"))
    ms.run(["ffmpeg", "-y", "-hide_banner", "-v", "warning",
            "-ss", f"{t_in:.3f}", "-t", f"{dur:.3f}", "-i", str(video),
            "-i", str(wav), "-filter_complex", vf, "-map", "[v]", "-map", "1:a",
            "-c:v", "libx264", "-profile:v", "high", "-level", "4.2", "-preset", "slow",
            "-crf", "18", "-g", str(out_fps * 2), "-pix_fmt", "yuv420p",
            "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
            "-movflags", "+faststart", "-t", f"{dur:.3f}", str(out)])
    enforce_true_peak(out, wav)
    wav.unlink(missing_ok=True)
    return out_fps


def enforce_true_peak(out, wav, tries=3):
    """AAC can overshoot the limiter's ceiling. Measure the delivered file and, if it
    sits above TP, re-encode just the audio (video copied) until it doesn't."""
    trim = 0.0
    for _ in range(tries):
        tp = ms.measure_output(out)["true_peak_dbfs"]
        if tp is None or tp <= ms.TP + 0.05:
            return
        trim += (ms.TP - 0.2) - tp
        tmp = Path(out).with_suffix(".fix.mp4")
        ms.run(["ffmpeg", "-y", "-hide_banner", "-v", "error", "-i", str(out), "-i", str(wav),
                "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                "-af", f"volume={trim:.2f}dB", "-c:a", "aac", "-b:a", "192k",
                "-ar", "48000", "-ac", "2", "-movflags", "+faststart", str(tmp)])
        tmp.replace(out)


def title_from(text, limit=70):
    s = re.split(r"(?<=[.?!])\s", text.strip())[0]
    s = re.sub(r"\s+", " ", s).strip(" ,;:-")
    return (s[:limit].rsplit(" ", 1)[0] + "...") if len(s) > limit else s


# ----------------------------------------------------------------------- main
def fetch_or_die(source, work, cookies):
    try:
        return ms.fetch(source, work, cookies)
    except subprocess.CalledProcessError:
        raise SystemExit(
            "\nyt-dlp could not download that video.\n"
            "  * 'Sign in to confirm you're not a bot' -> export cookies.txt from a\n"
            "    logged-in browser and re-run with --cookies cookies.txt\n"
            "  * 'no rule or network setting allows this host' -> this sandbox only\n"
            "    allows a fixed host list; download the file locally and pass its path.\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", help="YouTube URL or local video file")
    ap.add_argument("-o", "--outdir", default="out", help="directory for the clips")
    ap.add_argument("-n", "--count", type=int, default=3, help="how many clips to make")
    ap.add_argument("--min", type=float, default=MIN_DUR, dest="min_d")
    ap.add_argument("--max", type=float, default=MAX_DUR, dest="max_d")
    ap.add_argument("--work", default="work")
    ap.add_argument("--cookies", help="Netscape cookies.txt for yt-dlp")
    ap.add_argument("--model", default="small",
                    help="faster-whisper model (tiny/base/small/medium/large-v3)")
    ap.add_argument("--dry-run", action="store_true",
                    help="choose clips and print timestamps without rendering")
    args = ap.parse_args()

    if args.min_d < 5 or args.max_d <= args.min_d:
        raise SystemExit("--min must be >=5 and below --max.")

    work = Path(args.work); work.mkdir(parents=True, exist_ok=True)
    outdir = Path(args.outdir); outdir.mkdir(parents=True, exist_ok=True)

    video, meta = fetch_or_die(args.source, work, args.cookies)
    src = probe(video)
    if not src["has_audio"]:
        raise SystemExit("Source has no audio track.")
    print(f"= source: {src['w']}x{src['h']} @ {src['fps']:.3f} fps, "
          f"{src['duration']:.1f}s", file=sys.stderr)

    words = ms.transcribe(video, work, args.model)
    if not words:
        raise SystemExit("No speech detected; nothing to caption.")
    energy = ms.energy_curve(video, work)
    heatmap = meta.get("heatmap")
    print(f"= transcript: {len(words)} words"
          f"{'; most-replayed heatmap available' if heatmap else ''}", file=sys.stderr)

    chosen, n_cand = pick(words, energy, heatmap, src["duration"],
                          args.count, args.min_d, args.max_d)
    print(f"= scored {n_cand} candidate windows, picked {len(chosen)}", file=sys.stderr)

    clips = []
    for idx, (s, i, j, t_in, t_out, detail) in enumerate(chosen, 1):
        stem = f"clip{idx:02d}"
        rec = {"clip": idx, "file": None, "score": round(s, 3),
               "source_start": fmt_ts(t_in), "source_end": fmt_ts(t_out),
               "source_start_s": t_in, "source_end_s": t_out,
               "duration_s": round(t_out - t_in, 3),
               "suggested_title": title_from(detail["text"]),
               "transcript": detail["text"], "selection_metrics": detail}
        if args.dry_run:
            clips.append(rec)
            print(f"  {stem}: {fmt_ts(t_in)} -> {fmt_ts(t_out)} "
                  f"({rec['duration_s']:.1f}s, score {s:.2f})", file=sys.stderr)
            continue

        out = outdir / f"{stem}.mp4"
        peaks = punch_times(words, i, j, energy, t_in, t_out)
        face_x = ms.face_crop_x(video, t_in, t_out, src["w"], src["h"])
        ass = work / f"{stem}.ass"
        ms.build_ass(words, i, j, t_in, t_out, ass)
        render_clip(video, src, t_in, t_out, peaks, ass, out, face_x)
        res = probe(out)
        rec.update({
            "file": str(out),
            "crop": "face-tracked 9:16" if face_x is not None else "centre/blur-fill",
            "punch_ins_at_clip_s": [round(p, 2) for p in peaks],
            "output": {"width": res["w"], "height": res["h"], "fps": round(res["fps"], 3),
                       "duration_s": round(res["duration"], 3),
                       **ms.measure_output(out)}})
        clips.append(rec)
        print(f"  wrote {out}", file=sys.stderr)

    report = {"source": args.source, "title": meta.get("title"),
              "source_duration_s": round(src["duration"], 3),
              "clip_length_range_s": [args.min_d, args.max_d],
              "candidates_scored": n_cand, "clips": clips}
    (outdir / "clips.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
