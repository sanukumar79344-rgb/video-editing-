#!/usr/bin/env bash
# Install the video toolchain this repo expects.
#
# Run it by hand after cloning, or paste it into a cloud environment's setup
# script so every new session starts ready. Safe to re-run.
#
# Already present in the standard image, so not installed here: ffmpeg (with
# libass and libx264), node, python3, cmake/g++, and a Chromium at
# /opt/pw-browsers/chromium that Remotion and HyperFrames are pointed at.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOOLS="$ROOT/tools"
mkdir -p "$TOOLS"

echo "==> Python: yt-dlp, faster-whisper, JS challenge solver"
pip install -q --upgrade yt-dlp yt-dlp-ejs faster-whisper "opencv-python-headless<5" numpy

echo "==> cinematic-film skill deps (skia needs EGL; espeak-ng is the scratch voice)"
if ! python3 -c "import skia" 2>/dev/null; then
  (apt-get install -y -q libegl1 libgl1 espeak-ng >/dev/null 2>&1 \
    || (apt-get update -q >/dev/null && apt-get install -y -q libegl1 libgl1 espeak-ng >/dev/null))
  pip install -q "skia-python>=87.6" pillow scipy
fi

echo "==> Captions font (Montserrat ExtraBold)"
if ! fc-list | grep -qi montserrat; then
  mkdir -p /usr/local/share/fonts/reels
  curl -sL -o /usr/local/share/fonts/reels/Montserrat-ExtraBold.ttf \
    "https://fonts.gstatic.com/s/montserrat/v31/JTUHjIg1_i6t8kCHKm4532VJOt5-QNFgpCvr70w-.ttf"
  fc-cache -f >/dev/null
fi

echo "==> whisper.cpp"
if [ ! -x "$TOOLS/whisper.cpp/build/bin/whisper-cli" ]; then
  git clone -q --depth 1 https://github.com/ggml-org/whisper.cpp.git "$TOOLS/whisper.cpp" 2>/dev/null || true
  cmake -S "$TOOLS/whisper.cpp" -B "$TOOLS/whisper.cpp/build" -DCMAKE_BUILD_TYPE=Release \
        -DWHISPER_BUILD_TESTS=OFF >/dev/null
  cmake --build "$TOOLS/whisper.cpp/build" -j"$(nproc)" --config Release >/dev/null
fi
if [ ! -s "$TOOLS/whisper.cpp/models/ggml-base.bin" ]; then
  curl -sL -o "$TOOLS/whisper.cpp/models/ggml-base.bin" \
    https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin
fi

echo "==> Remotion"
if [ -f "$TOOLS/remotion/package.json" ]; then
  (cd "$TOOLS/remotion" && npm install --silent --no-audit --no-fund)
fi

echo "==> HyperFrames"
if [ -f "$TOOLS/hyperframes/package.json" ]; then
  (cd "$TOOLS/hyperframes" && npm install --silent --no-audit --no-fund)
else
  mkdir -p "$TOOLS/hyperframes"
  (cd "$TOOLS/hyperframes" && npm install --silent --no-audit --no-fund hyperframes)
fi
(cd "$TOOLS/hyperframes" && npx --no-install hyperframes telemetry disable >/dev/null 2>&1 || true)

echo
echo "Ready. Versions:"
ffmpeg -version | head -1
echo "yt-dlp        $(yt-dlp --version)"
echo "faster-whisper $(pip show faster-whisper 2>/dev/null | awk '/^Version/{print $2}')"
echo "whisper.cpp   $([ -x "$TOOLS/whisper.cpp/build/bin/whisper-cli" ] && echo built || echo MISSING)"
echo "remotion      $(cd "$TOOLS/remotion" 2>/dev/null && node -p "require('./package.json').dependencies.remotion" 2>/dev/null || echo MISSING)"
echo "hyperframes   $(cd "$TOOLS/hyperframes" 2>/dev/null && npx --no-install hyperframes --version 2>/dev/null | head -1 || echo MISSING)"
