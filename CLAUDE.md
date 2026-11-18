# Transskriber – project context for Claude Code

This file is a handoff from a claude.ai chat. Read it first.

## What this is

A small macOS app (Apple Silicon only) that turns audio files into Danish Word documents (.docx), entirely offline after install. Built for a non-technical person to use, set up by the owner (Rasmus Lolk Andersen). UI text is **Danish** and should stay Danish. The owner chats in Danish or English.

- Engine: `mlx-whisper` with `mlx-community/whisper-large-v3-turbo`, language fixed to `da`
- UI: Tkinter, drawn on a single Canvas (custom rounded button, checkbox, progress bar)
- Output: `.docx` next to the audio file, same name (`møde.mp3` -> `møde.docx`, never overwrites: `møde (2).docx`), opened automatically afterwards
- Repo: https://github.com/baggi97/transcriber (public)

## Repo layout

```
install.sh            installs OR updates (idempotent); builds the .app locally
config.env            GITHUB_REPO and MODEL, read by bash AND by the app (KEY="value" lines only)
VERSION               version number, must match the release tag (v + VERSION)
requirements.txt      mlx-whisper, imageio-ffmpeg, huggingface_hub, python-docx, tkinterdnd2
app/transskriber.py   the whole app
assets/icon1024.png   app icon (waveform turning into text lines)
scripts/afinstaller.sh, scripts/opdater.sh   copied to ~/Library/Application Support/Transskriber/ as *.command
```

## Key design decisions (keep unless there is a reason)

- **Install location:** engine, venv, model settings in `~/Library/Application Support/Transskriber`; app bundle in `~/Applications/Transskriber.app`. The .app is created locally by `install.sh`, so there is no Gatekeeper warning and no signing.
- **Python:** `uv` installs Python 3.12 (python-build-standalone, includes Tk). No Homebrew needed. ffmpeg comes from `imageio-ffmpeg` and is symlinked into `~/Library/Application Support/Transskriber/bin`.
- **Offline:** model is downloaded during install; the app sets `HF_HUB_OFFLINE=1`. Subprocesses that must download (the updater) unset it.
- **Launcher:** `Contents/MacOS/Transskriber` is a tiny bash script that `exec`s the venv Python on `transskriber.py`.
- **Paragraphs:** segments are merged into paragraphs by pauses (>= 1.5 s) and length; shorter paragraphs when timestamps are on. Optional `[HH:MM:SS]` bold prefix per paragraph; the setting persists in `settings.json`.
- **Drag and drop:** via `tkinterdnd2`, with automatic fallback to the button if it cannot load. Files can also be dropped on the app icon (`CFBundleDocumentTypes` + `::tk::mac::OpenDocument`).
- **While working:** `caffeinate -i -w <pid>` prevents idle sleep; on finish: `afplay` sound plus an `osascript` notification (arguments passed via argv, never interpolated).
- **Self-update from GitHub Releases:** the app checks `releases/latest` at start and every 6 hours (via `curl`). If the tag is newer than `version.txt`, a link appears bottom-left. Only after the user confirms does it download the tag tarball, run its `install.sh` with `TRANSSKRIBER_UPDATE=1` and `TRANSSKRIBER_VERSION=<tag>`, then relaunch. `install.sh` copies app files last, so a failed update leaves the old version working. The tag is validated with a regex before use.

## Status: what was and was NOT tested

Everything was developed in a Linux sandbox, so **nothing has run on a real Mac yet.**

Tested in the sandbox (stubs for uv, sips, iconutil, open, curl, a fake `mlx_whisper`): syntax of all scripts, install and update-mode install, the `.docx` output and paragraph logic, drag-drop path parsing, timestamps, caffeinate/notify calls, six update scenarios against a fake GitHub (new release, up to date, older release, placeholder repo, invalid archive, failing install), window rendering under Xvfb.

**Verified on a real Mac (2026-11-18, macOS 26.7.2, Apple Silicon):**
1. `install.sh` end to end with real `uv`, `sips`, `iconutil`, `lsregister` (Python 3.12 / Tk 9.0, ffmpeg 9.0 from imageio-ffmpeg)
2. Offline transcription with `mlx-whisper` on a synthetic Danish clip (macOS voice "Sara"): word-perfect, `.docx` with timestamps correct
3. Window look, Dock icon and menu bar name show "Transskriber"
4. `tkinterdnd2` loads; transcription via the window works
5. Finish sound and `osascript` notification both work

**Still not tested:**
- Quality and paragraph breaks on a real (non-synthetic) Danish recording
- Dropping files on the Dock/Finder icon
- The updater against real GitHub Releases

**Known pitfall:** a previous install run with `sudo` leaves root-owned `~/Library/Application Support/Transskriber`, `~/Applications/Transskriber.app` and `~/.cache/huggingface`, which used to make `install.sh` fail with "Permission denied". `install.sh` now refuses to run as root, detects root-owned folders before doing anything, and prints the exact `sudo chown -R` command to fix them (in Danish).

## Constraints

- The owner's employer has an IT policy; they did **not** want an AI agent driving their browser or publishing to GitHub on their behalf. Do git operations through the local `git` CLI only when the owner asks, and prefer showing the commands.
- The repo is public: never commit secrets, tokens, personal data or real audio.
- The updater runs code from the repo on other people's Macs. Keep the confirmation step. If asked, add an option to disable update checks entirely.
- Keep `VERSION` equal to the release tag without the `v`. The app's window title shows the installed version.
- Run `bash -n` on shell scripts and `python3 -m py_compile app/transskriber.py` before committing.

## Suggested first steps

1. Run `bash install.sh` on this Mac, fix whatever breaks, and try a short Danish audio clip.
2. Push to GitHub and create release `v1.0.0`.
3. Bump to 1.0.1, publish a second release, and confirm the update banner and relaunch work for real.
4. Optional: setting or switch to turn off update checks (IT policy), a real progress indicator (chunk the audio), speaker separation (hard; extra model, Hugging Face account).
