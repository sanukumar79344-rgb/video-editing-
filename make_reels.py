#!/usr/bin/env python3
"""
make_reels.py — one long video -> 6..8 finished vertical Reels/Shorts (25-50 s each).

Reuses the proven single-clip engine in make_short.py (transcription, face-aware 9:16
framing, word-highlight captions, -14 LUFS audio, H.264 export) and adds:

  * candidate windows in the 26-48 s range, always sentence-aligned at both ends
  * multi-clip selection: greedy, non-overlapping, de-duplicated, quality-gated
  * per-clip punch-in, captions and loudness normalisation
  * Reel_01.mp4 .. Reel_08.mp4 + reels.json (timestamps, duration, score, transcript)

Usage
  python3 make_reels.py "<youtube url>" --cookies cookies.txt -o out
  python3 make_reels.py source.mp4 -o out --min-clips 6 --max-clips 8
"""
import argparse
import json
import re
import sys
from pathlib import Path

import make_short as ms

MIN_DUR, MAX_DUR = 26.0, 48.0
IDEAL_DUR = 36.0
MIN_SCORE = 0.0          # below this a window is not worth shipping as a Reel
HOP = 0.1


# --------------------------------------------------------------------------- selection
def candidate_windows(words, duration):
    """(i, j, t_in, t_out) windows of MIN_DUR..MAX_DUR that start at a sentence start
    and end at a sentence end / clear breath. Never cuts mid-word or mid-phrase."""
    n = len(words)
    for i in range(n):
        if i > 0 and not (ms.SENT_END.search(words[i - 1]["w"])
                          or words[i]["t0"] - words[i - 1]["t1"] >= 0.35):
            continue
        gap_before = words[i]["t0"] - (words[i - 1]["t1"] if i else 0.0)
        pre = min(0.12, max(0.0, gap_before - 0.08))
        for j in range(i, n):
            core = words[j]["t1"] - words[i]["t0"]
            if core > MAX_DUR:
                break
            if core < MIN_DUR - 0.3:
                continue
            gap_after = (words[j + 1]["t0"] if j + 1 < n else words[j]["t1"] + 1.5) - words[j]["t1"]
            if not (ms.SENT_END.search(words[j]["w"]) or gap_after >= 0.3):
                continue
            post = min(0.3, max(0.0, gap_after - 0.08))
            t_in, t_out = max(0.0, words[i]["t0"] - pre), words[j]["t1"] + post
            if t_out > duration or not (MIN_DUR <= t_out - t_in <= MAX_DUR):
                continue
            yield i, j, round(t_in, 3), round(t_out, 3)


def score_window(words, i, j, t_in, t_out, energy, heatmap):
    """Same signals as make_short, retuned for a 25-50 s Reel: the hook must land in the
    first 2 s, the tail must pay off, and the middle must stay dense and animated."""
    text = " ".join(w["w"] for w in words[i:j + 1])
    lower = text.lower()
    seg = energy[int(t_in / HOP):int(t_out / HOP)] or [-60]
    voiced = [e for e in seg if e > -45] or seg
    mean_db = sum(voiced) / len(voiced)
    dyn = max(seg) - mean_db
    g_voiced = [e for e in energy if e > -45] or energy
    loud = mean_db - (sum(g_voiced) / len(g_voiced))

    hook = sum(len(re.findall(p, lower)) for p in ms.HOOK_PATTERNS)
    first2 = " ".join(w["w"] for w in words[i:j + 1] if w["t0"] < t_in + 2.0).lower()
    early_hook = sum(len(re.findall(p, first2)) for p in ms.HOOK_PATTERNS)
    first = re.sub(r"[^a-z']", "", words[i]["w"].lower())
    weak_start = first in ms.WEAK_STARTS
    wps = (j - i + 1) / (t_out - t_in)
    conf = sum(w["p"] for w in words[i:j + 1]) / (j - i + 1)
    ends_clean = bool(ms.SENT_END.search(words[j]["w"]))
    tail = " ".join(w["w"] for w in words[i:j + 1] if w["t1"] > t_out - 4.0).lower()
    tail_weak = len(re.findall(ms.TAIL_WEAK, tail))
    # long dead air inside the clip is fatal for retention
    dead = sum(1 for k in range(i, j) if words[k + 1]["t0"] - words[k]["t1"] > 1.2)
    heat = ms.heat_at(heatmap, t_in, t_out)

    s = (3.0 * heat
         + 0.08 * dyn + 0.10 * loud
         + 0.30 * min(hook, 10) + 0.8 * min(early_hook, 3)
         + (-2.0 if early_hook == 0 else 0.0)
         + (-1.2 if weak_start else 0.0)
         + (0.6 if ends_clean else 0.0)
         - 0.6 * abs(wps - 2.7)
         + 1.0 * (conf - 0.8)
         - 1.5 * min(tail_weak, 2)
         - 0.5 * min(dead, 4)
         - 0.02 * abs((t_out - t_in) - IDEAL_DUR))
    return s, {"text": text, "heat": round(heat, 3), "dyn_db": round(dyn, 2),
               "loud_vs_avg_db": round(loud, 2), "hook_hits": hook, "early_hook_hits": early_hook,
               "weak_start": weak_start, "words_per_sec": round(wps, 2), "dead_air_gaps": dead,
               "weak_tail_hits": tail_weak, "asr_conf": round(conf, 3), "ends_on_sentence": ends_clean}


def _shingles(text):
    w = re.findall(r"[a-z0-9']+", text.lower())
    return {tuple(w[k:k + 4]) for k in range(max(0, len(w) - 3))}


def select_many(words, energy, heatmap, duration, want_max, min_gap=10.0, min_score=MIN_SCORE):
    """Score every candidate, then greedily take the best non-overlapping, non-duplicate ones."""
    scored = []
    for i, j, t_in, t_out in candidate_windows(words, duration):
        s, d = score_window(words, i, j, t_in, t_out, energy, heatmap)
        scored.append((s, i, j, t_in, t_out, d))
    scored.sort(key=lambda x: -x[0])
    picked, sh = [], []
    for s, i, j, t_in, t_out, d in scored:
        if len(picked) >= want_max or s < min_score:
            break                       # scores are sorted descending: nothing better remains
        if any(t_in < p[4] + min_gap and p[3] - min_gap < t_out for p in picked):
            continue
        g = _shingles(d["text"])
        if any(g and h and len(g & h) / len(g) > 0.3 for h in sh):   # same story told twice
            continue
        picked.append((s, i, j, t_in, t_out, d)); sh.append(g)
    picked.sort(key=lambda x: -x[0])
    return picked


# --------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", help="YouTube URL or local video file")
    ap.add_argument("-o", "--outdir", default="out")
    ap.add_argument("--work", default="work")
    ap.add_argument("--cookies", help="Netscape cookies.txt for yt-dlp")
    ap.add_argument("--model", default="small", help="faster-whisper size (small/medium/large-v3)")
    ap.add_argument("--min-clips", type=int, default=6)
    ap.add_argument("--max-clips", type=int, default=8)
    ap.add_argument("--min-score", type=float, default=MIN_SCORE)
    args = ap.parse_args()
    if not 1 <= args.min_clips <= args.max_clips <= 8:
        raise SystemExit("--min-clips/--max-clips must satisfy 1 <= min <= max <= 8")

    work = Path(args.work); work.mkdir(parents=True, exist_ok=True)
    outdir = Path(args.outdir); outdir.mkdir(parents=True, exist_ok=True)

    video, meta = ms.fetch(args.source, work, args.cookies)
    src = ms.probe(video)
    if not src["has_audio"]:
        raise SystemExit("Source has no audio track.")
    print(f"= source {src['w']}x{src['h']} @{src['fps']:.3f} fps, {src['duration']/60:.1f} min", file=sys.stderr)

    words = ms.transcribe(video, work, args.model)
    if not words:
        raise SystemExit("No speech detected; nothing to clip.")
    energy = ms.energy_curve(video, work)
    picked = select_many(words, energy, meta.get("heatmap"), src["duration"],
                         args.max_clips, min_score=args.min_score)
    print(f"= {len(picked)} clip(s) passed the quality gate", file=sys.stderr)
    if len(picked) < args.min_clips:
        print(f"! only {len(picked)} window(s) cleared the gate (wanted >= {args.min_clips}); "
              f"shipping those rather than padding with weak clips", file=sys.stderr)
    if not picked:
        raise SystemExit("No clip in this video clears the quality gate.")

    clips = []
    for n, (score, i, j, t_in, t_out, detail) in enumerate(picked, 1):
        out = outdir / f"Reel_{n:02d}.mp4"
        print(f"\n=== Reel_{n:02d}  {ms.fmt_ts(t_in)} -> {ms.fmt_ts(t_out)} "
              f"({t_out - t_in:.1f}s, score {score:.2f})", file=sys.stderr)
        peak = ms.hook_peak(words, i, j, energy, t_in, t_out)
        face_x = ms.face_crop_x(video, t_in, t_out, src["w"], src["h"])
        ass = work / f"captions_{n:02d}.ass"
        ms.build_ass(words, i, j, t_in, t_out, ass)
        ms.render(video, src, t_in, t_out, peak, ass, out, face_x)
        res, loud = ms.probe(out), ms.measure_output(out)
        clips.append({
            "clip": n, "file": out.name,
            "source_start": ms.fmt_ts(t_in), "source_end": ms.fmt_ts(t_out),
            "source_start_s": t_in, "source_end_s": t_out,
            "duration_s": round(t_out - t_in, 3),
            "viral_score_raw": round(score, 3),
            "punch_in_at_clip_s": round(peak, 2),
            "crop": "face-tracked 9:16" if face_x is not None else "centre/blur-fill",
            "transcript": detail["text"], "selection_metrics": detail,
            "output": {"width": res["w"], "height": res["h"], "fps": round(res["fps"], 3),
                       "duration_s": round(res["duration"], 3), **loud},
        })

    report = {"source": args.source, "title": meta.get("title"), "channel": meta.get("channel"),
              "source_duration_s": round(src["duration"], 3),
              "clips_requested": [args.min_clips, args.max_clips], "clips_delivered": len(clips),
              "ranked_best_first": True, "clips": clips}
    (outdir / "reels.json").write_text(json.dumps(report, indent=2))

    bad = [c for c in clips if not 25.0 <= c["output"]["duration_s"] <= 50.0
           or (c["output"]["width"], c["output"]["height"]) != (1080, 1920)]
    print(json.dumps(report, indent=2))
    print(f"\n= wrote {len(clips)} file(s) to {outdir}/" + ("" if not bad else
          f"\n! QC FAILED for: {[c['file'] for c in bad]}"), file=sys.stderr)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
