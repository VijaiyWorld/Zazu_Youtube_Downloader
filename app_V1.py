import os
import queue
import shutil
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import yt_dlp


class Cancelled(Exception):
    pass


class DownloaderApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Zazu Youtube Media Downloader")
        self.geometry("720x520")
        self.minsize(650, 480)
        self.configure(bg="#f4f6f8")

        self.events = queue.Queue()
        self.worker = None
        self.cancel_event = threading.Event()

        self.url_var = tk.StringVar()
        self.output_var = tk.StringVar(value=str(Path.home() / "Downloads"))
        self.mode_var = tk.StringVar(value="Video (MP4)")
        self.quality_var = tk.StringVar(value="1080p")
        self.status_var = tk.StringVar(value="Ready")
        self.percent_var = tk.DoubleVar(value=0)

        self._build_ui()
        self.after(100, self._drain_events)

    def _build_ui(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TButton", padding=8)
        style.configure("Accent.TButton", background="#2563eb", foreground="white")
        style.map("Accent.TButton", background=[("active", "#1d4ed8")])

        outer = tk.Frame(self, bg="#f4f6f8", padx=28, pady=24)
        outer.pack(fill="both", expand=True)

        tk.Label(outer, text="Zazu YouTube Video / MP3 Downloader",
                 font=("Segoe UI", 20, "bold"), bg="#f4f6f8", fg="#111827").pack(anchor="w")
        tk.Label(outer, text="Download media you own or have permission to save.",
                 font=("Segoe UI", 10), bg="#f4f6f8", fg="#6b7280").pack(anchor="w", pady=(4, 22))

        card = tk.Frame(outer, bg="white", padx=20, pady=20, highlightthickness=1, highlightbackground="#e5e7eb")
        card.pack(fill="both", expand=True)

        self._label(card, "Video URL").pack(anchor="w")
        self.url_entry = ttk.Entry(card, textvariable=self.url_var, font=("Segoe UI", 11))
        self.url_entry.pack(fill="x", pady=(6, 16), ipady=5)

        self._label(card, "Save folder").pack(anchor="w")
        folder_row = tk.Frame(card, bg="white")
        folder_row.pack(fill="x", pady=(6, 16))
        ttk.Entry(folder_row, textvariable=self.output_var, font=("Segoe UI", 10)).pack(side="left", fill="x", expand=True, ipady=5)
        ttk.Button(folder_row, text="Browse", command=self._browse).pack(side="left", padx=(8, 0))

        options = tk.Frame(card, bg="white")
        options.pack(fill="x", pady=(0, 16))
        left = tk.Frame(options, bg="white")
        right = tk.Frame(options, bg="white")
        left.pack(side="left", fill="x", expand=True, padx=(0, 8))
        right.pack(side="left", fill="x", expand=True, padx=(8, 0))

        self._label(left, "Format").pack(anchor="w")
        self.mode_box = ttk.Combobox(left, textvariable=self.mode_var, state="readonly",
                                     values=["Video (MP4)", "Audio (MP3)"])
        self.mode_box.pack(fill="x", pady=(6, 0), ipady=4)
        self.mode_box.bind("<<ComboboxSelected>>", self._mode_changed)

        self._label(right, "Quality").pack(anchor="w")
        self.quality_box = ttk.Combobox(right, textvariable=self.quality_var, state="readonly",
                                        values=["Best", "1080p", "720p", "480p", "360p"])
        self.quality_box.pack(fill="x", pady=(6, 0), ipady=4)

        ttk.Progressbar(card, variable=self.percent_var, maximum=100).pack(fill="x", pady=(8, 6))
        tk.Label(card, textvariable=self.status_var, bg="white", fg="#4b5563", anchor="w").pack(fill="x")

        actions = tk.Frame(card, bg="white")
        actions.pack(fill="x", pady=(18, 0))
        self.download_btn = ttk.Button(actions, text="Download", style="Accent.TButton", command=self._start)
        self.download_btn.pack(side="left")
        self.cancel_btn = ttk.Button(actions, text="Cancel", command=self._cancel, state="disabled")
        self.cancel_btn.pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="Open Folder", command=self._open_folder).pack(side="right")

    @staticmethod
    def _label(parent, text):
        return tk.Label(parent, text=text, font=("Segoe UI", 10, "bold"), bg="white", fg="#374151")

    def _browse(self):
        folder = filedialog.askdirectory(initialdir=self.output_var.get())
        if folder:
            self.output_var.set(folder)

    def _mode_changed(self, _event=None):
        if self.mode_var.get() == "Audio (MP3)":
            self.quality_box.configure(values=["320 kbps", "256 kbps", "192 kbps", "128 kbps"])
            self.quality_var.set("320 kbps")
        else:
            self.quality_box.configure(values=["Best", "1080p", "720p", "480p", "360p"])
            self.quality_var.set("1080p")

    def _validate(self):
        url = self.url_var.get().strip()
        if not url.startswith(("https://", "http://")):
            raise ValueError("Enter a valid http:// or https:// URL.")
        out = Path(self.output_var.get()).expanduser()
        out.mkdir(parents=True, exist_ok=True)
        if not shutil.which("ffmpeg"):
            raise ValueError("FFmpeg was not found. Install it and add it to your system PATH.")
        return url, out

    def _start(self):
        if self.worker and self.worker.is_alive():
            return
        try:
            url, out = self._validate()
        except Exception as exc:
            messagebox.showerror("Cannot start", str(exc))
            return
        self.cancel_event.clear()
        self.percent_var.set(0)
        self.status_var.set("Starting...")
        self.download_btn.configure(state="disabled")
        self.cancel_btn.configure(state="normal")
        self.worker = threading.Thread(target=self._download, args=(url, out), daemon=True)
        self.worker.start()

    def _build_download_options(self, out):
        out = Path(out)
        def hook(data):
            if self.cancel_event.is_set():
                raise Cancelled("Download cancelled")
            status = data.get("status")
            if status == "downloading":
                total = data.get("total_bytes") or data.get("total_bytes_estimate") or 0
                downloaded = data.get("downloaded_bytes", 0)
                pct = (downloaded / total * 100) if total else 0
                speed = data.get("_speed_str", "").strip()
                eta = data.get("_eta_str", "").strip()
                self.events.put(("progress", pct, f"Downloading: {pct:.1f}%  Speed: {speed}  ETA: {eta}"))
            elif status == "finished":
                self.events.put(("progress", 100, "Processing with FFmpeg..."))

        common = {
            "outtmpl": str(out / "%(title).180B [%(id)s].%(ext)s"),
            "noplaylist": True,
            "windowsfilenames": os.name == "nt",
            "progress_hooks": [hook],
            "quiet": True,
            "no_warnings": True,
        }
        if self.mode_var.get() == "Audio (MP3)":
            bitrate = self.quality_var.get().split()[0]
            common.update({
                "format": "bestaudio/best",
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": bitrate,
                }, {
                    "key": "FFmpegMetadata",
                    "add_metadata": True,
                }],
            })
        else:
            q = self.quality_var.get()
            if q == "Best":
                fmt = "bestvideo+bestaudio/best"
            else:
                height = q.removesuffix("p")
                fmt = f"bestvideo[height<={height}]+bestaudio/best[height<={height}]"
            common.update({"format": fmt, "merge_output_format": "mp4"})
        return common

           
    def _download(self, url, out):
        try:
            out = Path(out).expanduser().resolve()
            out.mkdir(parents=True, exist_ok=True)

            options = self._build_download_options(out)

            with yt_dlp.YoutubeDL(options) as ydl:
                ydl.download([url])

            self.events.put(
                ("done", "Download completed successfully.")
            )

        except Cancelled:
            self.events.put(
                ("cancelled", "Download cancelled.")
            )

        except Exception as exc:
            self.events.put(
                ("error", f"{type(exc).__name__}: {exc}")
            )

    def _cancel(self):
        self.cancel_event.set()
        self.status_var.set("Cancelling...")
        self.cancel_btn.configure(state="disabled")

    def _drain_events(self):
        try:
            while True:
                item = self.events.get_nowait()
                kind = item[0]
                if kind == "progress":
                    self.percent_var.set(item[1])
                    self.status_var.set(item[2])
                elif kind in {"done", "cancelled", "error"}:
                    self.download_btn.configure(state="normal")
                    self.cancel_btn.configure(state="disabled")
                    self.status_var.set(item[1])
                    if kind == "done":
                        messagebox.showinfo("Complete", item[1])
                    elif kind == "error":
                        messagebox.showerror("Download failed", item[1])
        except queue.Empty:
            pass
        self.after(100, self._drain_events)

    def _open_folder(self):
        folder = Path(self.output_var.get()).expanduser()
        folder.mkdir(parents=True, exist_ok=True)
        if os.name == "nt":
            os.startfile(folder)
        elif shutil.which("open"):
            os.system(f'open "{folder}"')
        else:
            os.system(f'xdg-open "{folder}"')


if __name__ == "__main__":
    DownloaderApp().mainloop()
