#!/bin/bash
# Henter den nyeste udgivne version af Transskriber fra GitHub og installerer den.
# Køres med én linje i Terminal:
#
#   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/baggi97/transcriber/main/hent.sh)"
#
# Scriptet henter altid en udgivet release (ikke det, der ligger på main lige nu)
# og kører install.sh fra den. Det hele står i en funktion, så intet køres,
# hvis scriptet kun blev hentet halvt.

main() {
  set -e
  local repo="baggi97/transcriber"

  echo "==> Finder den nyeste version af Transskriber"
  # github.com/…/releases/latest viderestiller til …/releases/tag/vX.Y.Z (uden at bruge GitHubs API-kvote)
  local url tag
  url="$(curl -fsSLI -o /dev/null -w '%{url_effective}' "https://github.com/$repo/releases/latest")" || url=""
  tag="${url##*/}"
  if ! [[ "$tag" =~ ^v[0-9]+(\.[0-9]+){0,3}$ ]]; then
    echo "Kunne ikke finde en udgivet version. Tjek internetforbindelsen, og prøv igen."
    exit 1
  fi

  # Global (ikke local), så oprydningen ved EXIT stadig kender mappen, når funktionen er slut
  HENT_TMP="$(mktemp -d "${TMPDIR:-/tmp}/transskriber.XXXXXX")"
  trap 'rm -rf "$HENT_TMP"' EXIT
  local tmp="$HENT_TMP"

  echo "==> Henter Transskriber ${tag#v}"
  curl -fsSL "https://github.com/$repo/archive/refs/tags/$tag.tar.gz" -o "$tmp/release.tar.gz"
  mkdir "$tmp/src"
  tar -xzf "$tmp/release.tar.gz" -C "$tmp/src" --strip-components=1

  TRANSSKRIBER_VERSION="${tag#v}" /bin/bash "$tmp/src/install.sh" </dev/null
}

main "$@"
