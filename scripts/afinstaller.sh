#!/bin/bash
# Fjerner Transskriber helt fra denne Mac.
# Dine lydfiler og Word-dokumenter bliver ikke rørt.

main() {
  BASE="$HOME/Library/Application Support/Transskriber"
  APP="$HOME/Applications/Transskriber.app"
  MODEL="mlx-community/whisper-large-v3-turbo"
  if [ -f "$BASE/config.env" ]; then
    # shellcheck disable=SC1091
    . "$BASE/config.env"
  fi
  MODEL_CACHE="$HOME/.cache/huggingface/hub/models--${MODEL//\//--}"

  echo "Dette fjerner Transskriber fra denne Mac:"
  echo "  - Programmet:                 $APP"
  echo "  - Motor og indstillinger:     $BASE"
  echo "  - Sprogmodellen (ca. 1,5 GB): $MODEL_CACHE"
  echo ""
  echo "Dine lydfiler og Word-dokumenter bliver IKKE rørt."
  echo ""
  read -r -p "Vil du fortsætte? Skriv 'ja' og tryk Enter: " svar
  case "$svar" in
    ja|Ja|JA) ;;
    *) echo "Afbrudt. Intet er slettet."; return 0 ;;
  esac

  rm -rf "$APP"
  rm -rf "$BASE"
  rm -rf "$MODEL_CACHE"

  echo ""
  echo "Færdig. Transskriber er fjernet."
  echo "Er programmet lagt i Dock'en, så træk dets ikon væk derfra."
  echo "Python-værktøjet 'uv' (i ~/.local/bin) er ladt tilbage, da andre programmer kan bruge det."
}

main "$@"; exit $?
