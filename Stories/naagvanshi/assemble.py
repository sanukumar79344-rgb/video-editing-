#!/usr/bin/env python3
"""
assemble.py — Build the final horror story video from images + narration.

Maps each script beat to the right image, applies Ken Burns (slow zoom/pan),
crossfade transitions, and muxes the narration audio.

Output: 1920x1080, H.264 High, AAC 192k, +faststart.
"""
import json
import subprocess
import sys
import os

PROJ = os.path.dirname(os.path.abspath(__file__))
IMAGES = os.path.join(PROJ, "images")
AUDIO = os.path.join(PROJ, "audio", "narration.m4a")
TIMING = os.path.join(PROJ, "audio", "timing.json")
OUTPUT = os.path.join(PROJ, "naagvanshi_part1.mp4")
SHOTS_JSON = os.path.join(PROJ, "shots.json")

FPS = 24
W, H = 1920, 1080

# Map script segments to images based on the beat/visual flow.
# Each entry: (shot_image, start_time, end_time, ken_burns_type)
# Ken Burns types: "zoom_in", "zoom_out", "pan_left", "pan_right", "pan_up"

def build_scene_map(timing):
    """Map timing segments to images based on story beats."""
    segs = timing["segments"]
    total = timing["total_duration"]

    # Beat boundaries from the script — which image covers which time range
    # We assign images to time ranges based on the story flow
    scenes = []

    # BEAT 1 — COLD OPEN (0.0 - ~11.7s) → Shot 1 (foggy forest)
    scenes.append(("shot_01.jpg", 0.0, 11.7, "zoom_in"))

    # BEAT 2 — THE RULE (11.7 - ~38.3s) → Shot 2 (Dadi's room) + Shot 3 (death)
    scenes.append(("shot_02.jpg", 11.7, 34.7, "zoom_in"))
    scenes.append(("shot_03.jpg", 34.7, 43.3, "zoom_out"))  # Dadi dies, silent beat

    # BEAT 3 — THE VIOLATION (43.3 - ~98.6s)
    scenes.append(("shot_04.jpg", 43.3, 62.1, "pan_right"))  # Cremation
    scenes.append(("shot_05.jpg", 62.1, 82.0, "pan_left"))   # Village square, talking
    scenes.append(("shot_05.jpg", 82.0, 98.6, "zoom_in"))    # Arjun argues

    # BEAT 4 — FIRST CONTACT (98.6 - ~152.0s)
    scenes.append(("shot_06.jpg", 98.6, 109.6, "zoom_in"))   # House exterior night
    scenes.append(("shot_07.jpg", 109.6, 122.0, "pan_right")) # Arjun with trunk
    scenes.append(("shot_08.jpg", 122.0, 127.5, "zoom_in"))   # Old photograph
    scenes.append(("shot_09.jpg", 127.5, 143.9, "zoom_out"))  # Woman in white - long hold

    # BEAT 5 — ESCALATION (152.0 - ~262.9s)
    scenes.append(("shot_05.jpg", 143.9, 163.1, "pan_right")) # Village morning again
    scenes.append(("shot_07.jpg", 163.1, 185.5, "zoom_in"))   # Back at trunk/house
    scenes.append(("shot_16.jpg", 185.5, 194.2, "zoom_in"))   # Naagmani box found
    scenes.append(("shot_10.jpg", 194.2, 221.0, "pan_right")) # Marigold trail
    scenes.append(("shot_01.jpg", 221.0, 242.1, "zoom_in"))   # Forest walk
    scenes.append(("shot_11.jpg", 242.1, 262.9, "zoom_out"))  # Ruined temple

    # BEAT 6 — LORE DUMP (262.9 - ~327.6s)
    scenes.append(("shot_15.jpg", 262.9, 273.4, "zoom_in"))   # Tantrik Baba
    scenes.append(("shot_12.jpg", 273.4, 286.7, "pan_right")) # Flashback temple glory
    scenes.append(("shot_13.jpg", 286.7, 295.8, "pan_left"))  # Thakur's attack
    scenes.append(("shot_14.jpg", 295.8, 311.3, "zoom_in"))   # Priestess walled in
    scenes.append(("shot_15.jpg", 311.3, 327.6, "zoom_out"))  # Back to Tantrik

    # BEAT 7 — THE PLAN (327.6 - ~376.6s)
    scenes.append(("shot_15.jpg", 327.6, 343.4, "pan_right")) # Tantrik with scroll
    scenes.append(("shot_06.jpg", 343.4, 376.6, "zoom_out"))  # Arjun resolves, walks back

    # BEAT 8 — CONFRONTATION (376.6 - ~417.5s)
    scenes.append(("shot_16.jpg", 376.6, 385.7, "zoom_in"))   # Naagmani box open
    scenes.append(("shot_17.jpg", 385.7, 398.0, "zoom_out"))  # Naagkanya reveal!
    scenes.append(("thumbnail.jpg", 398.0, 405.7, "zoom_in")) # Arjun + Naagmani + Naagkanya at temple
    scenes.append(("shot_18.jpg", 405.7, 417.5, "zoom_in"))   # Snakes flooding

    # BEAT 9 — CLIFFHANGER (417.5 - end)
    scenes.append(("shot_19.jpg", 417.5, 431.6, "pan_right")) # Destroyed room
    scenes.append(("shot_20.jpg", 431.6, 445.3, "zoom_in"))   # Naagmani on altar
    scenes.append(("shot_21.jpg", 445.3, 460.9, "pan_left"))  # Village at night
    scenes.append(("shot_21.jpg", 460.9, total, "zoom_out"))   # Final + narrator outro

    return scenes


def ken_burns_filter(kb_type, duration, idx):
    """Generate zoompan filter for a Ken Burns effect on a 1920x1080 image."""
    frames = int(duration * FPS)
    if frames < 2:
        frames = 2

    # We scale image up to allow room for pan/zoom (2x)
    # zoompan works on the input image dimensions
    if kb_type == "zoom_in":
        zp = (f"zoompan=z='min(zoom+0.0008,1.25)':x='iw/2-(iw/zoom/2)'"
              f":y='ih/2-(ih/zoom/2)':d={frames}:s={W}x{H}:fps={FPS}")
    elif kb_type == "zoom_out":
        zp = (f"zoompan=z='if(eq(on,1),1.25,max(zoom-0.0008,1.0))':x='iw/2-(iw/zoom/2)'"
              f":y='ih/2-(ih/zoom/2)':d={frames}:s={W}x{H}:fps={FPS}")
    elif kb_type == "pan_left":
        zp = (f"zoompan=z='1.15':x='iw*0.15*(1-on/{frames})'"
              f":y='ih/2-(ih/zoom/2)':d={frames}:s={W}x{H}:fps={FPS}")
    elif kb_type == "pan_right":
        zp = (f"zoompan=z='1.15':x='iw*0.15*on/{frames}'"
              f":y='ih/2-(ih/zoom/2)':d={frames}:s={W}x{H}:fps={FPS}")
    elif kb_type == "pan_up":
        zp = (f"zoompan=z='1.15':x='iw/2-(iw/zoom/2)'"
              f":y='ih*0.15*(1-on/{frames})':d={frames}:s={W}x{H}:fps={FPS}")
    else:
        zp = f"zoompan=z='1':x='0':y='0':d={frames}:s={W}x{H}:fps={FPS}"

    return zp


def build_video(scenes):
    """Build the final video using ffmpeg concat with Ken Burns on each segment."""
    timing = json.load(open(TIMING))
    total_dur = timing["total_duration"]

    # Strategy: render each scene segment as a short clip, then concat them all
    # with crossfade transitions, and mux the narration audio.

    tmp_dir = os.path.join(PROJ, "tmp_render")
    os.makedirs(tmp_dir, exist_ok=True)

    clip_files = []

    for i, (img, start, end, kb) in enumerate(scenes):
        dur = end - start
        if dur <= 0:
            continue

        img_path = os.path.join(IMAGES, img)
        if not os.path.exists(img_path):
            print(f"WARNING: {img} not found, skipping")
            continue

        out_clip = os.path.join(tmp_dir, f"clip_{i:03d}.ts")
        zp = ken_burns_filter(kb, dur, i)

        cmd = [
            "ffmpeg", "-y", "-v", "error",
            "-loop", "1", "-i", img_path,
            "-vf", f"{zp},format=yuv420p",
            "-t", f"{dur:.3f}",
            "-c:v", "libx264", "-preset", "fast", "-crf", "20",
            "-an",
            "-f", "mpegts", out_clip
        ]
        print(f"  Rendering clip {i+1}/{len(scenes)}: {img} [{start:.1f}-{end:.1f}s] {kb}")
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            print(f"  ERROR: {r.stderr[-300:]}")
            sys.exit(1)
        clip_files.append(out_clip)

    # Concat all clips
    concat_file = os.path.join(tmp_dir, "concat.txt")
    with open(concat_file, "w") as f:
        for c in clip_files:
            f.write(f"file '{c}'\n")

    # First concat video only
    video_only = os.path.join(tmp_dir, "video_only.mp4")
    print(f"\nConcatenating {len(clip_files)} clips...")
    cmd = [
        "ffmpeg", "-y", "-v", "error",
        "-f", "concat", "-safe", "0", "-i", concat_file,
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-profile:v", "high", "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        "-an", video_only
    ]
    subprocess.run(cmd, check=True)

    # Now mux with audio
    print("Muxing with narration audio...")
    cmd = [
        "ffmpeg", "-y", "-v", "error",
        "-i", video_only,
        "-i", AUDIO,
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k",
        "-map", "0:v:0", "-map", "1:a:0",
        "-shortest",
        "-movflags", "+faststart",
        OUTPUT
    ]
    subprocess.run(cmd, check=True)

    # Verify
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "format=duration,size:stream=width,height,codec_name,r_frame_rate",
         "-of", "json", OUTPUT],
        capture_output=True, text=True
    )
    info = json.loads(probe.stdout)
    print(f"\nFinal video: {OUTPUT}")
    print(f"  Duration: {float(info['format']['duration']):.1f}s")
    print(f"  Size: {int(info['format']['size'])/1024/1024:.1f} MB")
    for s in info.get("streams", []):
        if "width" in s:
            print(f"  Video: {s['width']}x{s['height']} {s['codec_name']} {s.get('r_frame_rate','')}")
        else:
            print(f"  Audio: {s['codec_name']}")

    # Cleanup temp files
    import shutil
    shutil.rmtree(tmp_dir, ignore_errors=True)
    print("Done!")


def main():
    timing = json.load(open(TIMING))
    scenes = build_scene_map(timing)
    print(f"Scene map: {len(scenes)} segments, {timing['total_duration']:.1f}s total")
    build_video(scenes)


if __name__ == "__main__":
    main()
