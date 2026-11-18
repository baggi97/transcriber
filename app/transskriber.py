import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
import traceback
import tkinter as tk
from tkinter import filedialog, messagebox

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    HAS_DND_LIB = True
except Exception:
    HAS_DND_LIB = False

BASE = os.path.expanduser("~/Library/Application Support/Transskriber")
os.environ["PATH"] = os.path.join(BASE, "bin") + os.pathsep + os.environ.get("PATH", "")
os.environ["HF_HUB_OFFLINE"] = "1"  # modellen ligger allerede lokalt
SETTINGS_FILE = os.path.join(BASE, "settings.json")
CONFIG_FILE = os.path.join(BASE, "config.env")
VERSION_FILE = os.path.join(BASE, "version.txt")
APP_PATH = os.path.expanduser("~/Applications/Transskriber.app")
UPDATE_CHECK_INTERVAL_MS = 6 * 60 * 60 * 1000  # tjek for opdateringer hver 6. time


def read_config():
    """Læser config.env (linjer på formen NØGLE="værdi")."""
    cfg = {}
    try:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    cfg[key.strip()] = value.strip().strip('"').strip("'")
    except Exception:
        pass
    return cfg


CONFIG = read_config()
MODEL = CONFIG.get("MODEL", "mlx-community/whisper-large-v3-turbo")
GITHUB_REPO = CONFIG.get("GITHUB_REPO", "")
AUDIO_TYPES = [
    ("Lyd og video", "*.mp3 *.m4a *.wav *.aac *.flac *.ogg *.opus *.mp4 *.mov *.m4v *.webm"),
    ("Alle filer", "*.*"),
]


# ---------- hjælpefunktioner ----------

def load_settings():
    try:
        with open(SETTINGS_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_settings(data):
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception:
        pass


def fmt_ts(seconds):
    s = int(seconds)
    return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}"


def unique_path(path):
    root, ext = os.path.splitext(path)
    candidate, n = path, 2
    while os.path.exists(candidate):
        candidate = f"{root} ({n}){ext}"
        n += 1
    return candidate


def make_paragraphs(segments, short=False):
    """Samler korte segmenter til afsnit ud fra pauser og længde.
    Returnerer en liste af (starttid i sekunder, tekst).
    Med short=True bliver afsnittene kortere, så tidsstempler er mere brugbare."""
    min_len, max_len = (120, 400) if short else (200, 600)
    paragraphs, current, cur_start, last_end = [], "", 0.0, 0.0
    for seg in segments:
        text = seg["text"].strip()
        if not text:
            continue
        gap = seg["start"] - last_end
        long_pause = gap >= 1.5 and len(current) >= min_len
        too_long = len(current) >= max_len and current.rstrip().endswith((".", "?", "!"))
        if current and (long_pause or too_long):
            paragraphs.append((cur_start, current))
            current = ""
        if not current:
            cur_start = seg["start"]
        current = (current + " " + text).strip()
        last_end = seg["end"]
    if current:
        paragraphs.append((cur_start, current))
    return paragraphs


def write_docx(paragraphs, out_path, timestamps=False):
    from docx import Document

    doc = Document()
    for start, text in paragraphs:
        p = doc.add_paragraph()
        if timestamps:
            run = p.add_run(f"[{fmt_ts(start)}] ")
            run.bold = True
        p.add_run(text)
    doc.save(out_path)


def output_path_for(audio_path):
    base = os.path.splitext(audio_path)[0] + ".docx"
    folder = os.path.dirname(base)
    if not os.access(folder, os.W_OK):
        base = os.path.join(os.path.expanduser("~/Documents"), os.path.basename(base))
    return unique_path(base)


def notify(message):
    """Lyd og notifikation. Lyden virker altid; notifikationen er et ekstra."""
    try:
        subprocess.Popen(["afplay", "/System/Library/Sounds/Glass.aiff"])
    except Exception:
        pass
    try:
        subprocess.Popen([
            "osascript",
            "-e", "on run argv",
            "-e", 'display notification (item 1 of argv) with title "Transskriber"',
            "-e", "end run",
            message,
        ])
    except Exception:
        pass


# ---------- opdateringer via GitHub Releases ----------

REPO_RE = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
TAG_RE = re.compile(r"v?(\d+(?:\.\d+){0,3})")


def local_version():
    try:
        with open(VERSION_FILE, encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return ""


def version_key(text):
    """'v1.2.3' -> (1, 2, 3, 0). Returnerer None, hvis det ikke ligner et versionsnummer."""
    m = TAG_RE.fullmatch((text or "").strip())
    if not m:
        return None
    parts = [int(x) for x in m.group(1).split(".")]
    return tuple(parts + [0] * (4 - len(parts)))


def fetch_latest_release(repo):
    """Henter seneste udgivne release fra GitHub. Returnerer None ved fejl eller ingen release."""
    if not REPO_RE.fullmatch(repo or ""):
        return None
    try:
        r = subprocess.run(
            ["curl", "-fsSL", "--max-time", "10", "-H", "Accept: application/vnd.github+json",
             f"https://api.github.com/repos/{repo}/releases/latest"],
            capture_output=True, text=True, timeout=20,
        )
        if r.returncode != 0:
            return None
        data = json.loads(r.stdout)
        tag = str(data.get("tag_name", "")).strip()
        key = version_key(tag)
        if key is None:
            return None
        return {"tag": tag, "key": key, "notes": (data.get("body") or "").strip()}
    except Exception:
        return None


def tail_of(path, lines=12):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return "".join(f.readlines()[-lines:]).strip()
    except Exception:
        return ""


# ---------- udseende ----------

BG = "#F4F6FB"
CARD = "#FFFFFF"
CARD_BORDER = "#E6EAF3"
ACCENT = "#3B6FE0"
ACCENT_HOVER = "#2F5FCB"
ACCENT_OFF = "#B9C6E6"
TEXT = "#1B2437"
MUTED = "#6B7690"
FAINT = "#9AA3B8"
TRACK = "#E1E7F2"
GREEN = "#2FB171"
BOX_BORDER = "#B8C2D9"
FONT = "Helvetica Neue"

TRACK_X0, TRACK_X1, TRACK_Y = 48, 472, 246


def round_rect(c, x1, y1, x2, y2, r, **kw):
    pts = [
        x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
        x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
        x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
    ]
    return c.create_polygon(pts, smooth=True, **kw)


class App:
    W, H = 520, 340

    def __init__(self, root, dnd=False):
        self.root = root
        self.busy = False
        self.start_time = 0.0
        self.base_status = "Klar."
        self.anim_pos = 0
        self.last_shown = ""
        self.caffeinate = None
        self.settings = load_settings()
        self.timestamps = bool(self.settings.get("timestamps", False))
        self.update_info = None

        self.version = local_version()
        root.title(f"Transskriber {self.version}" if self.version else "Transskriber")
        root.configure(bg=BG)
        root.geometry(f"{self.W}x{self.H}")
        root.resizable(False, False)

        self.icon = None
        self.small_icon = None
        try:
            self.icon = tk.PhotoImage(file=os.path.join(BASE, "icon512.png"))
            root.iconphoto(True, self.icon)
            self.small_icon = self.icon.subsample(8, 8)
        except Exception:
            pass

        c = tk.Canvas(root, width=self.W, height=self.H, bg=BG, highlightthickness=0, bd=0)
        c.pack()
        self.canvas = c

        # Hoved
        if self.small_icon:
            c.create_image(26, 22, image=self.small_icon, anchor="nw")
        c.create_text(104, 34, text="Transskriber", anchor="nw", fill=TEXT, font=(FONT, 22, "bold"))
        c.create_text(104, 70, text="Lyd til dansk tekst", anchor="nw", fill=MUTED, font=(FONT, 13))

        # Kort
        self.card = round_rect(c, 24, 108, 496, 304, 18, fill=CARD, outline=CARD_BORDER)
        if dnd:
            intro = "Træk en lydfil hertil, eller vælg den med knappen.\nDer laves et Word-dokument. Alt sker lokalt."
        else:
            intro = "Vælg en lydfil med knappen.\nDer laves et Word-dokument. Alt sker lokalt."
        c.create_text(48, 130, anchor="nw", fill=MUTED, font=(FONT, 12), text=intro, width=424)

        # Knap
        self.btn_rect = round_rect(c, 48, 184, 216, 228, 12, fill=ACCENT, outline="", tags="btn")
        c.create_text(132, 206, text="Vælg lydfil…", fill="white", font=(FONT, 13, "bold"), tags="btn")
        c.tag_bind("btn", "<Enter>", self.on_enter)
        c.tag_bind("btn", "<Leave>", self.on_leave)
        c.tag_bind("btn", "<Button-1>", lambda e: self.choose())

        # Afkrydsning: tidsstempler
        self.chk_box = round_rect(c, 240, 197, 258, 215, 5, fill=CARD, outline=BOX_BORDER, width=1.5, tags="chk")
        self.chk_tick = c.create_line(244, 206, 248, 210, 254, 201, fill="white", width=2,
                                      capstyle="round", joinstyle="round", tags="chk")
        c.create_text(266, 206, anchor="w", text="Tidsstempler", fill=TEXT, font=(FONT, 12), tags="chk")
        c.tag_bind("chk", "<Button-1>", lambda e: self.toggle_timestamps())
        c.tag_bind("chk", "<Enter>", lambda e: c.config(cursor="pointinghand"))
        c.tag_bind("chk", "<Leave>", lambda e: c.config(cursor=""))
        self.update_check()

        # Statuslinje
        round_rect(c, TRACK_X0, TRACK_Y, TRACK_X1, TRACK_Y + 6, 3, fill=TRACK, outline="")
        self.status_id = c.create_text(48, 264, anchor="nw", fill=MUTED, font=(FONT, 11),
                                       text=self.base_status, width=424)

        # Underskrift
        c.create_text(self.W - 16, self.H - 12, anchor="se", fill=FAINT, font=(FONT, 10),
                      text="Lavet af Rasmus Lolk Andersen")

        # Opdateringsbesked (vises kun, når der findes en nyere release)
        self.update_id = c.create_text(24, self.H - 12, anchor="sw", fill=ACCENT, font=(FONT, 10, "bold"),
                                       text="", state="hidden", tags="upd")
        c.tag_bind("upd", "<Button-1>", lambda e: self.ask_update())
        c.tag_bind("upd", "<Enter>", lambda e: c.config(cursor="pointinghand"))
        c.tag_bind("upd", "<Leave>", lambda e: c.config(cursor=""))
        root.after(3000, self.check_updates)

        # Træk og slip i vinduet
        if dnd:
            c.drop_target_register(DND_FILES)
            c.dnd_bind("<<DropEnter>>", self.on_drag_enter)
            c.dnd_bind("<<DropLeave>>", self.on_drag_leave)
            c.dnd_bind("<<Drop>>", self.on_drop)

        # Filer sluppet på appens ikon (Dock/Finder) eller åbnet med "Åbn med"
        try:
            root.createcommand("::tk::mac::OpenDocument", self.on_open_docs)
        except Exception:
            pass

    # ---------- afkrydsning ----------
    def update_check(self):
        c = self.canvas
        if self.timestamps:
            c.itemconfig(self.chk_box, fill=ACCENT, outline=ACCENT)
            c.itemconfig(self.chk_tick, state="normal")
        else:
            c.itemconfig(self.chk_box, fill=CARD, outline=BOX_BORDER)
            c.itemconfig(self.chk_tick, state="hidden")

    def toggle_timestamps(self):
        self.timestamps = not self.timestamps
        self.settings["timestamps"] = self.timestamps
        save_settings(self.settings)
        self.update_check()

    # ---------- knap ----------
    def on_enter(self, _e):
        if not self.busy:
            self.canvas.itemconfig(self.btn_rect, fill=ACCENT_HOVER)
            self.canvas.config(cursor="pointinghand")

    def on_leave(self, _e):
        if not self.busy:
            self.canvas.itemconfig(self.btn_rect, fill=ACCENT)
        self.canvas.config(cursor="")

    # ---------- træk og slip ----------
    def on_drag_enter(self, event):
        self.canvas.itemconfig(self.card, outline=ACCENT, width=2)
        return "copy"

    def on_drag_leave(self, event):
        self.canvas.itemconfig(self.card, outline=CARD_BORDER, width=1)
        return "copy"

    def on_drop(self, event):
        self.canvas.itemconfig(self.card, outline=CARD_BORDER, width=1)
        try:
            paths = list(self.root.tk.splitlist(event.data))
        except Exception:
            paths = []
        self.start(paths)
        return "copy"

    def on_open_docs(self, *paths):
        self.root.after(150, lambda: self.start(list(paths)))

    # ---------- status ----------
    def set_status(self, text):
        self.root.after(0, lambda: self._set_status(text))

    def _set_status(self, text):
        self.base_status = text
        self.last_shown = ""
        self.canvas.itemconfig(self.status_id, text=text)

    def set_bar(self, color):
        self.canvas.delete("seg")
        round_rect(self.canvas, TRACK_X0, TRACK_Y, TRACK_X1, TRACK_Y + 6, 3, fill=color, outline="", tags="seg")

    def animate(self):
        if not self.busy:
            return
        seg = 110
        span = (TRACK_X1 - TRACK_X0) + seg
        self.anim_pos = (self.anim_pos + 5) % span
        x0 = max(TRACK_X0, TRACK_X0 + self.anim_pos - seg)
        x1 = min(TRACK_X1, TRACK_X0 + self.anim_pos)
        self.canvas.delete("seg")
        if x1 - x0 >= 6:
            round_rect(self.canvas, x0, TRACK_Y, x1, TRACK_Y + 6, 3, fill=ACCENT, outline="", tags="seg")
        secs = int(time.time() - self.start_time)
        shown = f"{self.base_status}  ·  {secs // 60}:{secs % 60:02d}"
        if shown != self.last_shown:
            self.last_shown = shown
            self.canvas.itemconfig(self.status_id, text=shown)
        self.root.after(20, self.animate)

    # ---------- opdatering ----------
    def check_updates(self):
        threading.Thread(target=self._check_worker, daemon=True).start()
        self.root.after(UPDATE_CHECK_INTERVAL_MS, self.check_updates)

    def _check_worker(self):
        info = fetch_latest_release(GITHUB_REPO)
        if not info:
            return
        mine = version_key(self.version) or (0, 0, 0, 0)
        if info["key"] > mine:
            self.root.after(0, lambda: self.show_update(info))

    def show_update(self, info):
        self.update_info = info
        self.canvas.itemconfig(self.update_id, text=f"Ny version {info['tag']} – Opdater nu", state="normal")

    def ask_update(self):
        info = self.update_info
        if not info:
            return
        if self.busy:
            self.root.bell()
            return
        notes = info["notes"][:400]
        msg = f"Der er en ny version af Transskriber ({info['tag']})."
        if notes:
            msg += f"\n\n{notes}"
        msg += "\n\nProgrammet henter opdateringen og starter derefter forfra. Det tager et par minutter."
        if messagebox.askyesno("Opdater Transskriber", msg):
            self.begin_update(info)

    def begin_update(self, info):
        self.busy = True
        self.canvas.itemconfig(self.btn_rect, fill=ACCENT_OFF)
        self.canvas.itemconfig(self.update_id, state="hidden")
        self.start_time = time.time()
        self.anim_pos = 0
        self._set_status(f"Henter version {info['tag']}...")
        self.keep_awake()
        self.animate()
        threading.Thread(target=self.update_work, args=(info,), daemon=True).start()

    def update_work(self, info):
        tag = info["tag"]
        tmp = tempfile.mkdtemp(prefix="transskriber-update-")
        try:
            if not REPO_RE.fullmatch(GITHUB_REPO or "") or version_key(tag) is None:
                raise RuntimeError("Opdateringskilden er ikke gyldig.")
            archive = os.path.join(tmp, "release.tar.gz")
            url = f"https://github.com/{GITHUB_REPO}/archive/refs/tags/{tag}.tar.gz"
            r = subprocess.run(["curl", "-fsSL", "--max-time", "180", "-o", archive, url],
                               capture_output=True, text=True)
            if r.returncode != 0:
                raise RuntimeError("Kunne ikke hente opdateringen. Tjek internetforbindelsen.")
            src = os.path.join(tmp, "src")
            os.makedirs(src)
            r = subprocess.run(["tar", "-xzf", archive, "-C", src, "--strip-components=1"],
                               capture_output=True, text=True)
            if r.returncode != 0:
                raise RuntimeError("Kunne ikke pakke opdateringen ud.")
            for needed in ("install.sh", "app/transskriber.py", "VERSION", "config.env", "requirements.txt"):
                if not os.path.isfile(os.path.join(src, needed)):
                    raise RuntimeError("Opdateringen ligner ikke en gyldig Transskriber-version.")

            self.set_status("Installerer opdateringen...\nDet kan tage et par minutter")
            env = os.environ.copy()
            env.pop("HF_HUB_OFFLINE", None)  # installeren skal kunne hente en evt. ny model
            env["TRANSSKRIBER_UPDATE"] = "1"
            env["TRANSSKRIBER_VERSION"] = tag.lstrip("vV")
            log = os.path.join(BASE, "update.log")
            with open(log, "w", encoding="utf-8") as lf:
                r = subprocess.run(["/bin/bash", os.path.join(src, "install.sh")], cwd=src, env=env,
                                   stdout=lf, stderr=subprocess.STDOUT, timeout=3600)
            if r.returncode != 0:
                raise RuntimeError("Installationen mislykkedes. Den gamle version er stadig i brug.\n\n" + tail_of(log))
            self.root.after(0, self.restart)
        except Exception as e:
            msg = str(e)
            self.root.after(0, lambda: self.update_failed(msg))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def update_failed(self, msg):
        self.finish_ui()
        self._set_status("Opdateringen mislykkedes.")
        if self.update_info:
            self.canvas.itemconfig(self.update_id, state="normal")
        messagebox.showerror("Opdatering mislykkedes", msg[-900:])

    def restart(self):
        """Starter den nye version op og lukker denne."""
        self.release_awake()
        try:
            subprocess.Popen(
                ["/bin/bash", "-c", 'sleep 1.5; /usr/bin/open "$1"', "_", APP_PATH],
                start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        except Exception:
            pass
        self.root.destroy()

    # ---------- arbejde ----------
    def choose(self):
        if self.busy:
            self.root.bell()
            return
        paths = filedialog.askopenfilenames(title="Vælg lydfil(er)", filetypes=AUDIO_TYPES)
        if paths:
            self.start(list(paths))

    def start(self, paths):
        if self.busy:
            self.root.bell()
            return
        files = [p for p in paths if os.path.isfile(p)]
        if not files:
            self._set_status("Det skal være en fil, ikke en mappe.")
            return
        self.busy = True
        self.canvas.itemconfig(self.btn_rect, fill=ACCENT_OFF)
        self.start_time = time.time()
        self.anim_pos = 0
        self._set_status("Starter motoren...")
        self.keep_awake()
        self.animate()
        threading.Thread(target=self.work, args=(files, self.timestamps), daemon=True).start()

    def keep_awake(self):
        """Forhindrer, at Macen går i dvale, mens der transskriberes."""
        try:
            self.caffeinate = subprocess.Popen(["caffeinate", "-i", "-w", str(os.getpid())])
        except Exception:
            self.caffeinate = None

    def release_awake(self):
        if self.caffeinate:
            try:
                self.caffeinate.terminate()
            except Exception:
                pass
            self.caffeinate = None

    def work(self, paths, timestamps):
        outputs = []
        try:
            import mlx_whisper

            for i, path in enumerate(paths, 1):
                name = os.path.basename(path)
                if len(name) > 42:
                    name = name[:39] + "..."
                self.set_status(f"Fil {i} af {len(paths)}: {name}\nTranskriberer, kan tage et par minutter")
                result = mlx_whisper.transcribe(
                    path,
                    path_or_hf_repo=MODEL,
                    language="da",
                    condition_on_previous_text=False,
                    verbose=None,
                )
                paragraphs = make_paragraphs(result.get("segments", []), short=timestamps)
                if not paragraphs:
                    paragraphs = [(0.0, result.get("text", "").strip())]
                out = output_path_for(path)
                write_docx(paragraphs, out, timestamps)
                outputs.append(out)
            self.root.after(0, lambda: self.done(outputs))
        except Exception:
            err = traceback.format_exc()
            self.root.after(0, lambda: self.fail(err))

    def finish_ui(self):
        self.busy = False
        self.release_awake()
        self.canvas.delete("seg")
        self.canvas.itemconfig(self.btn_rect, fill=ACCENT)

    def done(self, outputs):
        self.finish_ui()
        self.set_bar(GREEN)
        self._set_status(f"Færdig! {len(outputs)} Word-dokument(er) lavet.")
        if len(outputs) == 1:
            notify(f"{os.path.basename(outputs[0])} er klar")
        else:
            notify(f"{len(outputs)} dokumenter er klar")
        for out in outputs:
            subprocess.run(["open", out])

    def fail(self, err):
        self.finish_ui()
        self._set_status("Noget gik galt.")
        messagebox.showerror(
            "Fejl",
            "Transskriberingen mislykkedes.\n\nPrøv en anden fil, eller send denne tekst til support:\n\n" + err[-800:],
        )


if __name__ == "__main__":
    use_dnd = False
    root = None
    if HAS_DND_LIB:
        try:
            root = TkinterDnD.Tk()
            use_dnd = True
        except Exception:
            root = None
    if root is None:
        root = tk.Tk()
    App(root, dnd=use_dnd)
    root.mainloop()
