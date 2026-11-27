#!/usr/bin/env bash
# Instala dependencias y descarga la voz en español (una sola vez).
set -e
cd "$(dirname "$0")"
command -v ffmpeg >/dev/null || sudo apt-get install -y ffmpeg
fc-list | grep -qi "Noto Color Emoji" || sudo apt-get install -y fonts-noto-color-emoji
pip install -q piper-tts numpy pillow
mkdir -p assets/voices && cd assets/voices
for v in vits-piper-es_MX-ald-medium vits-piper-es_MX-claude-high; do
  [ -d "$v" ] || curl -sSL "https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/$v.tar.bz2" | tar xj
done
echo "Listo. Genera un video con: python3 generar_short.py guiones/<guion>.json"
