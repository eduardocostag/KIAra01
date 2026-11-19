#!/bin/sh
# Copies the Video Studio from the repo into ./studio (the Docker build context) before `docker compose build`.
set -eu
here=$(cd "$(dirname "$0")" && pwd)
repo=$(cd "$here/../../.." && pwd)
rm -rf "$here/studio"
mkdir -p "$here/studio/app/video_studio" "$here/studio/app/voice" "$here/studio/app/resources/video_studio"
cp "$repo/app/video_studio/__init__.py" "$repo/app/video_studio/__main__.py" "$repo/app/video_studio/engine.py" \
   "$repo/app/video_studio/template.html" "$here/studio/app/video_studio/"
cp "$repo/app/voice/kiara_style.py" "$here/studio/app/voice/"
cp -r "$repo/app/resources/video_studio/shots" "$here/studio/app/resources/video_studio/"
printf '"""Kiara (Video Studio subset for the video server)."""\n' > "$here/studio/app/__init__.py"
printf '"""Kiara voice style (subset)."""\n' > "$here/studio/app/voice/__init__.py"
echo "studio ready"
