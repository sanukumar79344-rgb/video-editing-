#!/usr/bin/env bash
# Download only the needed section of the source video (with padding so
# make_short.py can snap the cut to word gaps), at the highest resolution
# available. The 9:16 crop of a 4K frame is 1215x2160, so the 1080x1920 output
# is a true downscale instead of an upscale.
#
#   ./fetch_source.sh            -> source_section.mkv covering 2592-2627 s
#   ./fetch_source.sh A B        -> custom window in seconds
set -euo pipefail
URL="https://www.youtube.com/watch?v=CswOUBuokjo"
A="${1:-2592}"
B="${2:-2627}"

yt-dlp \
  -f "313+140/401+140/271+140/bestvideo[height>=1080]+bestaudio" \
  --download-sections "*${A}-${B}" --force-keyframes-at-cuts \
  --merge-output-format mkv -o "source_section.%(ext)s" "$URL"

echo "source_section.mkv starts at ${A}s in the original video (use --source-offset ${A})"
