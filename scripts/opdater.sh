#!/bin/bash
# Opdaterer motoren (mlx-whisper m.m.) til de nyeste versioner og tjekker sprogmodellen.
# Selve appen opdateres via GitHub-opdateringen i appen (eller ved at køre install.sh igen).

set -e

BASE="$HOME/Library/Application Support/Transskriber"
PY="$BASE/venv/bin/python"
MODEL="mlx-community/whisper-large-v3-turbo"
export PATH="$HOME/.local/bin:$PATH"

if [ ! -x "$PY" ]; then
  echo "Transskriber er ikke installeret endnu. Kør install.sh først."
  exit 1
fi
if ! command -v uv >/dev/null 2>&1; then
  echo "Værktøjet 'uv' kunne ikke findes. Kør install.sh igen, så bliver det sat op."
  exit 1
fi
if [ -f "$BASE/config.env" ]; then
  # shellcheck disable=SC1091
  . "$BASE/config.env"
fi

version() {
  "$PY" -c "import importlib.metadata as m; print(m.version('mlx-whisper'))" 2>/dev/null || echo "ukendt"
}

BEFORE="$(version)"
echo "==> 1/3 Opdaterer motoren (nuværende version: $BEFORE)"
uv pip install --python "$PY" --upgrade -r "$BASE/requirements.txt"

FFMPEG="$("$PY" -c 'import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())')"
ln -sf "$FFMPEG" "$BASE/bin/ffmpeg"

echo "==> 2/3 Tjekker om sprogmodellen har en ny version"
env -u HF_HUB_OFFLINE "$PY" -c "from huggingface_hub import snapshot_download; snapshot_download('$MODEL')"

AFTER="$(version)"
echo "==> 3/3 Færdig"
if [ "$BEFORE" = "$AFTER" ]; then
  echo "Motoren var allerede nyeste version ($AFTER)."
else
  echo "Motoren er opdateret fra $BEFORE til $AFTER."
fi
