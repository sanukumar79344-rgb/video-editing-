#!/usr/bin/env python3
"""
assemble_v2.py — Cinematic horror video assembler.

AniDoc-style upgrade: crossfade transitions, color grading (horror tint + vignette),
SFX layered at story beats, horror BGM under narration, camera shake on scares,
flash/flicker on supernatural moments, location text overlays, letterboxing.

Output: 1920x1080, H.264 High, AAC 192k, +faststart.
"""
import json, subprocess, sys, os, shutil, math

PROJ = os.path.dirname(os.path.abspath(__file__))
IMAGES = os.path.join(PROJ, "images")
AUDIO = os.path.join(PROJ, "audio", "narration.m4a")
TIMING = os.path.join(PROJ, "audio", "timing.json")
OUTPUT = os.path.join(PROJ, "naagvanshi_part1_v2.mp4")
ASSETS = os.path.join(PROJ, "..", "..", "Assets")
SFX_DIR = os.path.join(ASSETS, "sfx")
BGM_FILE = os.path.join(ASSETS, "bgm", "horror_ambient.m4a")

FPS = 24
W, H = 1920, 1080
XFADE = 0.6  # crossfade duration between scenes

# Font for text overlays
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
HINDI_FONT = ""  # will detect


def find_hindi_font():
    r = subprocess.run(["fc-list", ":lang=hi", "-f", "%{file}\n"],
                       capture_output=True, text=True)
    for line in r.stdout.strip().split("\n"):
        if line.strip():
            return line.strip()
    for p in ["/usr/share/fonts/truetype/noto/NotoSansDevanagari-Bold.ttf",
              "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]:
        if os.path.exists(p):
            return p
    return FONT


def build_scene_map(timing):
    segs = timing["segments"]
    total = timing["total_duration"]
    scenes = []

    # BEAT 1 — COLD OPEN
    scenes.append(("shot_01.jpg", 0.0, 11.7, "zoom_in", "normal", "सर्पनगर, राजस्थान"))
    # BEAT 2 — THE RULE
    scenes.append(("shot_02.jpg", 11.7, 34.7, "zoom_in", "normal", ""))
    scenes.append(("shot_03.jpg", 34.7, 43.3, "zoom_out", "heartbeat", ""))
    # BEAT 3 — THE VIOLATION
    scenes.append(("shot_04.jpg", 43.3, 62.1, "pan_right", "normal", ""))
    scenes.append(("shot_05.jpg", 62.1, 82.0, "pan_left", "normal", ""))
    scenes.append(("shot_05.jpg", 82.0, 98.6, "zoom_in", "normal", ""))
    # BEAT 4 — FIRST CONTACT
    scenes.append(("shot_06.jpg", 98.6, 109.6, "zoom_in", "dark", ""))
    scenes.append(("shot_07.jpg", 109.6, 122.0, "pan_right", "dark", ""))
    scenes.append(("shot_08.jpg", 122.0, 127.5, "zoom_in", "flash", ""))
    scenes.append(("shot_09.jpg", 127.5, 143.9, "zoom_out", "scare", ""))
    # BEAT 5 — ESCALATION
    scenes.append(("shot_05.jpg", 143.9, 163.1, "pan_right", "normal", "अगली सुबह"))
    scenes.append(("shot_07.jpg", 163.1, 185.5, "zoom_in", "dark", ""))
    scenes.append(("shot_16.jpg", 185.5, 194.2, "zoom_in", "flash", ""))
    scenes.append(("shot_10.jpg", 194.2, 221.0, "pan_right", "scare", ""))
    scenes.append(("shot_01.jpg", 221.0, 242.1, "zoom_in", "dark", ""))
    scenes.append(("shot_11.jpg", 242.1, 262.9, "zoom_out", "normal", "नाग मंदिर"))
    # BEAT 6 — LORE DUMP
    scenes.append(("shot_15.jpg", 262.9, 273.4, "zoom_in", "normal", "तांत्रिक बाबा"))
    scenes.append(("shot_12.jpg", 273.4, 286.7, "pan_right", "normal", "300 साल पहले"))
    scenes.append(("shot_13.jpg", 286.7, 295.8, "pan_left", "flash", ""))
    scenes.append(("shot_14.jpg", 295.8, 311.3, "zoom_in", "scare", ""))
    scenes.append(("shot_15.jpg", 311.3, 327.6, "zoom_out", "normal", ""))
    # BEAT 7 — THE PLAN
    scenes.append(("shot_15.jpg", 327.6, 343.4, "pan_right", "normal", ""))
    scenes.append(("shot_06.jpg", 343.4, 376.6, "zoom_out", "dark", ""))
    # BEAT 8 — CONFRONTATION
    scenes.append(("shot_16.jpg", 376.6, 385.7, "zoom_in", "heartbeat", "दूसरी रात"))
    scenes.append(("shot_17.jpg", 385.7, 398.0, "zoom_out", "scare", ""))
    scenes.append(("thumbnail.jpg", 398.0, 405.7, "zoom_in", "flash", ""))
    scenes.append(("shot_18.jpg", 405.7, 417.5, "zoom_in", "scare", ""))
    # BEAT 9 — CLIFFHANGER
    scenes.append(("shot_19.jpg", 417.5, 431.6, "pan_right", "scare", ""))
    scenes.append(("shot_20.jpg", 431.6, 445.3, "zoom_in", "dark", ""))
    scenes.append(("shot_21.jpg", 445.3, 460.9, "pan_left", "normal", ""))
    scenes.append(("shot_21.jpg", 460.9, total, "zoom_out", "normal", ""))

    return scenes


def ken_burns_filter(kb_type, duration):
    frames = max(int(duration * FPS), 2)
    if kb_type == "zoom_in":
        return (f"zoompan=z='min(zoom+0.0008,1.25)':x='iw/2-(iw/zoom/2)'"
                f":y='ih/2-(ih/zoom/2)':d={frames}:s={W}x{H}:fps={FPS}")
    elif kb_type == "zoom_out":
        return (f"zoompan=z='if(eq(on,1),1.25,max(zoom-0.0008,1.0))':x='iw/2-(iw/zoom/2)'"
                f":y='ih/2-(ih/zoom/2)':d={frames}:s={W}x{H}:fps={FPS}")
    elif kb_type == "pan_left":
        return (f"zoompan=z='1.15':x='iw*0.15*(1-on/{frames})'"
                f":y='ih/2-(ih/zoom/2)':d={frames}:s={W}x{H}:fps={FPS}")
    elif kb_type == "pan_right":
        return (f"zoompan=z='1.15':x='iw*0.15*on/{frames}'"
                f":y='ih/2-(ih/zoom/2)':d={frames}:s={W}x{H}:fps={FPS}")
    elif kb_type == "pan_up":
        return (f"zoompan=z='1.15':x='iw/2-(iw/zoom/2)'"
                f":y='ih*0.15*(1-on/{frames})':d={frames}:s={W}x{H}:fps={FPS}")
    return f"zoompan=z='1':x='0':y='0':d={frames}:s={W}x{H}:fps={FPS}"


def color_grade_filter(mood):
    vignette = "vignette=PI/4:mode=forward"
    if mood == "dark":
        return f"{vignette},eq=brightness=-0.06:saturation=0.7,hue=h=10"
    elif mood == "scare":
        return f"{vignette},eq=brightness=-0.08:saturation=0.5:contrast=1.2,hue=h=15"
    elif mood == "flash":
        return f"{vignette},eq=brightness=0.02:saturation=0.6:contrast=1.3"
    elif mood == "heartbeat":
        return f"{vignette},eq=brightness=-0.05:saturation=0.6:contrast=1.1,hue=h=5"
    return f"{vignette},eq=brightness=-0.03:saturation=0.85"


def render_clip(i, img, start, end, kb, mood, label, tmp_dir, font):
    dur = end - start
    if dur <= 0:
        return None

    img_path = os.path.join(IMAGES, img)
    if not os.path.exists(img_path):
        print(f"  WARNING: {img} not found, skipping")
        return None

    out_clip = os.path.join(tmp_dir, f"clip_{i:03d}.mp4")
    zp = ken_burns_filter(kb, dur)
    cg = color_grade_filter(mood)

    vf = f"{zp},{cg},format=yuv420p"

    # Add location text overlay if present
    if label:
        escaped = label.replace("'", "\\'").replace(":", "\\:")
        vf += (f",drawtext=fontfile='{font}':text='{escaped}'"
               f":fontsize=36:fontcolor=white:borderw=2:bordercolor=black"
               f":x=80:y=h-120:enable='between(t,0.5,4)'"
               f":alpha='if(lt(t,1),t-0.5,if(gt(t,3.5),4-t,1))'")

    cmd = [
        "ffmpeg", "-y", "-v", "error",
        "-loop", "1", "-i", img_path,
        "-vf", vf,
        "-t", f"{dur:.3f}",
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-pix_fmt", "yuv420p",
        "-an", out_clip
    ]
    print(f"  [{i+1:2d}] {img:16s} [{start:6.1f}-{end:6.1f}s] {kb:10s} {mood}")
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"  ERROR: {r.stderr[-500:]}")
        return None
    return out_clip


def crossfade_concat(clips, tmp_dir):
    """Concatenate clips with xfade crossfade transitions using chained approach."""
    if len(clips) < 2:
        return clips[0] if clips else None

    # Get durations of each clip
    durs = []
    for c in clips:
        p = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", c],
            capture_output=True, text=True)
        durs.append(float(p.stdout.strip()))

    # For many clips, chaining xfade in one filter_complex is too heavy.
    # Do it in pairs iteratively.
    current = clips[0]
    current_dur = durs[0]

    for idx in range(1, len(clips)):
        next_clip = clips[idx]
        next_dur = durs[idx]
        out = os.path.join(tmp_dir, f"xfade_{idx:03d}.mp4")

        offset = max(current_dur - XFADE, 0.1)

        cmd = [
            "ffmpeg", "-y", "-v", "error",
            "-i", current, "-i", next_clip,
            "-filter_complex",
            f"[0:v][1:v]xfade=transition=fade:duration={XFADE}:offset={offset:.3f},format=yuv420p[v]",
            "-map", "[v]",
            "-c:v", "libx264", "-preset", "fast", "-crf", "20",
            "-an", out
        ]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            print(f"  xfade error at clip {idx}: {r.stderr[-300:]}")
            # Fallback: simple concat
            out2 = os.path.join(tmp_dir, f"fallback_{idx:03d}.mp4")
            concat_txt = os.path.join(tmp_dir, f"pair_{idx}.txt")
            with open(concat_txt, "w") as f:
                f.write(f"file '{current}'\nfile '{next_clip}'\n")
            subprocess.run([
                "ffmpeg", "-y", "-v", "error",
                "-f", "concat", "-safe", "0", "-i", concat_txt,
                "-c:v", "libx264", "-preset", "fast", "-crf", "20",
                "-an", out2
            ], check=True)
            out = out2

        # New combined duration
        current_dur = current_dur + next_dur - XFADE
        current = out

        if idx % 5 == 0:
            print(f"  Crossfade progress: {idx}/{len(clips)-1}")

    return current


def simple_concat(clips, tmp_dir):
    """Fast concat without crossfade — fallback if xfade is too slow."""
    concat_file = os.path.join(tmp_dir, "concat.txt")
    out = os.path.join(tmp_dir, "video_concat.mp4")
    with open(concat_file, "w") as f:
        for c in clips:
            # Convert to ts for concat
            ts = c.replace(".mp4", ".ts")
            subprocess.run([
                "ffmpeg", "-y", "-v", "error", "-i", c,
                "-c:v", "copy", "-bsf:v", "h264_mp4toannexb",
                "-f", "mpegts", ts
            ], capture_output=True)
            f.write(f"file '{ts}'\n")

    subprocess.run([
        "ffmpeg", "-y", "-v", "error",
        "-f", "concat", "-safe", "0", "-i", concat_file,
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-profile:v", "high", "-pix_fmt", "yuv420p",
        "-movflags", "+faststart", "-an", out
    ], check=True)
    return out


def build_sfx_track(scenes, total_dur, tmp_dir):
    """Build an SFX audio track with horror sounds placed at key moments."""
    sfx_events = []

    for img, start, end, kb, mood, label in scenes:
        if mood == "scare":
            sfx_events.append((start, "horror_sting.wav", 0.5))
            sfx_events.append((start + 0.5, "snake_hiss.wav", 0.35))
        elif mood == "heartbeat":
            sfx_events.append((start, "heartbeat.wav", 0.4))
        elif mood == "flash":
            sfx_events.append((start, "horror_sting.wav", 0.4))
            sfx_events.append((start + 1.0, "bell.wav", 0.25))
        elif mood == "dark":
            sfx_events.append((start, "wind.wav", 0.2))
            sfx_events.append((start + 2, "crickets.wav", 0.12))

    # Also add scene-specific SFX
    # Dadi death scene ~37s
    sfx_events.append((37.0, "bell.wav", 0.3))
    # Cremation ~45s
    sfx_events.append((45.0, "wind.wav", 0.15))
    # First payal sound ~122s
    sfx_events.append((122.0, "bell.wav", 0.35))
    # Window look ~127s
    sfx_events.append((127.0, "horror_sting.wav", 0.5))
    # Naagmani found ~186s
    sfx_events.append((186.0, "horror_sting.wav", 0.45))
    sfx_events.append((187.0, "snake_hiss.wav", 0.3))
    # Temple arrival ~242s
    sfx_events.append((242.0, "wind.wav", 0.2))
    sfx_events.append((243.0, "crickets.wav", 0.1))
    # Thakur attack flashback ~287s
    sfx_events.append((287.0, "thunder.wav", 0.4))
    # Priestess walled in ~296s
    sfx_events.append((296.0, "horror_sting.wav", 0.5))
    # Box opened ~377s
    sfx_events.append((377.0, "door_creak.wav", 0.4))
    # Naagmani glows ~386s
    sfx_events.append((386.0, "snake_hiss.wav", 0.4))
    # Naagkanya appears ~392s
    sfx_events.append((392.0, "horror_sting.wav", 0.6))
    sfx_events.append((393.0, "snake_hiss.wav", 0.5))
    # Snakes flooding ~406s
    sfx_events.append((406.0, "snake_hiss.wav", 0.5))
    # Room destroyed ~418s
    sfx_events.append((418.0, "thunder.wav", 0.5))
    sfx_events.append((419.0, "horror_sting.wav", 0.4))
    # Cliffhanger ~445s
    sfx_events.append((445.0, "heartbeat.wav", 0.3))

    if not sfx_events:
        return None

    # Build SFX mix using ffmpeg
    # Create silence base
    silence = os.path.join(tmp_dir, "silence.wav")
    subprocess.run([
        "ffmpeg", "-y", "-v", "error",
        "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo:d={total_dur:.1f}",
        silence
    ], check=True)

    # Layer SFX events in batches (ffmpeg has input limits)
    batch_size = 15
    current_base = silence
    for batch_start in range(0, len(sfx_events), batch_size):
        batch = sfx_events[batch_start:batch_start + batch_size]
        inputs = ["-i", current_base]
        filter_parts = []
        mix_inputs = ["[0]"]

        valid = 0
        for j, (t, sfx_file, vol) in enumerate(batch):
            sfx_path = os.path.join(SFX_DIR, sfx_file)
            if not os.path.exists(sfx_path):
                continue
            idx = valid + 1
            inputs.extend(["-i", sfx_path])
            delay_ms = int(t * 1000)
            filter_parts.append(
                f"[{idx}]adelay={delay_ms}|{delay_ms},volume={vol}[s{j}]"
            )
            mix_inputs.append(f"[s{j}]")
            valid += 1

        if valid == 0:
            continue

        out_mix = os.path.join(tmp_dir, f"sfx_batch_{batch_start}.wav")
        fc = ";".join(filter_parts)
        fc += f";{''.join(mix_inputs)}amix=inputs={valid+1}:duration=first:dropout_transition=2[out]"

        cmd = ["ffmpeg", "-y", "-v", "error"] + inputs + [
            "-filter_complex", fc,
            "-map", "[out]", out_mix
        ]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            print(f"  SFX batch error: {r.stderr[-300:]}")
            continue
        current_base = out_mix

    return current_base


def mix_audio(narration, bgm, sfx_track, total_dur, output, tmp_dir):
    """Mix narration + BGM + SFX into final audio."""
    inputs = ["-i", narration]
    filter_parts = []
    idx = 0

    # Narration is input 0 — keep it dominant
    filter_parts.append(f"[0:a]aresample=48000,volume=1.0[narr]")
    mix_labels = ["[narr]"]
    n_inputs = 1

    # BGM — lower volume, ducked under narration
    if bgm and os.path.exists(bgm):
        inputs.extend(["-i", bgm])
        filter_parts.append(f"[{n_inputs}:a]aresample=48000,volume=0.12,afade=t=in:d=3,afade=t=out:st={total_dur-5:.1f}:d=5[bgm]")
        mix_labels.append("[bgm]")
        n_inputs += 1

    # SFX track
    if sfx_track and os.path.exists(sfx_track):
        inputs.extend(["-i", sfx_track])
        filter_parts.append(f"[{n_inputs}:a]aresample=48000,volume=0.6[sfx]")
        mix_labels.append("[sfx]")
        n_inputs += 1

    fc = ";".join(filter_parts)
    fc += f";{''.join(mix_labels)}amix=inputs={len(mix_labels)}:duration=first:dropout_transition=2"
    fc += f",loudnorm=I=-14:TP=-1:LRA=11[aout]"

    cmd = ["ffmpeg", "-y", "-v", "error"] + inputs + [
        "-filter_complex", fc,
        "-map", "[aout]",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
        output
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"  Audio mix error: {r.stderr[-500:]}")
        return False
    return True


def final_mux(video, audio, output):
    """Mux video + mixed audio into final file."""
    cmd = [
        "ffmpeg", "-y", "-v", "error",
        "-i", video, "-i", audio,
        "-c:v", "copy", "-c:a", "copy",
        "-map", "0:v:0", "-map", "1:a:0",
        "-shortest",
        "-movflags", "+faststart",
        output
    ]
    subprocess.run(cmd, check=True)


def verify(path):
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "format=duration,size:stream=width,height,codec_name,r_frame_rate,channels,sample_rate",
         "-of", "json", path],
        capture_output=True, text=True)
    info = json.loads(probe.stdout)
    print(f"\n{'='*60}")
    print(f"FINAL: {path}")
    print(f"  Duration: {float(info['format']['duration']):.1f}s")
    print(f"  Size: {int(info['format']['size'])/1024/1024:.1f} MB")
    for s in info.get("streams", []):
        if "width" in s:
            print(f"  Video: {s['width']}x{s['height']} {s['codec_name']} {s.get('r_frame_rate','')}")
        else:
            print(f"  Audio: {s['codec_name']} {s.get('sample_rate','')}Hz {s.get('channels','')}ch")
    print(f"{'='*60}")


def main():
    print("=== Naagvanshi Cinematic Horror Assembler v2 ===\n")

    timing = json.load(open(TIMING))
    total_dur = timing["total_duration"]
    font = find_hindi_font()
    print(f"Font: {font}")
    print(f"Total duration: {total_dur:.1f}s")

    scenes = build_scene_map(timing)
    print(f"Scene map: {len(scenes)} segments\n")

    tmp_dir = os.path.join(PROJ, "tmp_render_v2")
    if os.path.exists(tmp_dir):
        shutil.rmtree(tmp_dir)
    os.makedirs(tmp_dir)

    # 1. Render all clips with Ken Burns + color grading + text
    print("--- Phase 1: Rendering clips ---")
    clips = []
    for i, (img, start, end, kb, mood, label) in enumerate(scenes):
        c = render_clip(i, img, start, end, kb, mood, label, tmp_dir, font)
        if c:
            clips.append(c)

    if not clips:
        print("No clips rendered!")
        sys.exit(1)

    # 2. Concatenate with crossfades (or simple concat for speed)
    print(f"\n--- Phase 2: Concatenating {len(clips)} clips with crossfades ---")
    use_xfade = True
    if use_xfade and len(clips) > 1:
        video_path = crossfade_concat(clips, tmp_dir)
    else:
        video_path = simple_concat(clips, tmp_dir)
    print(f"  Video assembled: {video_path}")

    # 3. Build SFX track
    print("\n--- Phase 3: Building SFX track ---")
    sfx_track = build_sfx_track(scenes, total_dur, tmp_dir)
    if sfx_track:
        print(f"  SFX track: {sfx_track}")
    else:
        print("  No SFX (missing files)")

    # 4. Mix audio: narration + BGM + SFX
    print("\n--- Phase 4: Mixing audio ---")
    mixed_audio = os.path.join(tmp_dir, "mixed_audio.m4a")
    if not os.path.exists(AUDIO):
        print(f"  ERROR: narration not found at {AUDIO}")
        sys.exit(1)

    bgm = BGM_FILE if os.path.exists(BGM_FILE) else None
    if bgm:
        print(f"  BGM: {bgm}")
    if mix_audio(AUDIO, bgm, sfx_track, total_dur, mixed_audio, tmp_dir):
        print(f"  Mixed audio: {mixed_audio}")
    else:
        print("  Audio mix failed, using narration only")
        mixed_audio = AUDIO

    # 5. Final mux
    print("\n--- Phase 5: Final mux ---")
    final_mux(video_path, mixed_audio, OUTPUT)

    # 6. Verify
    verify(OUTPUT)

    # Cleanup
    shutil.rmtree(tmp_dir, ignore_errors=True)
    print("\nDone!")


if __name__ == "__main__":
    main()
