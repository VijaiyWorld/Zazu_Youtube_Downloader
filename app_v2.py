import os
import queue
import shutil
import subprocess
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import yt_dlp


class DownloadCancelled(Exception):
    pass


class DownloaderApp(tk.Tk):
    VIDEO_QUALITIES = ("Best", "2160p", "1440p", "1080p", "720p", "480p", "360p")
    AUDIO_QUALITIES = ("320 kbps", "256 kbps", "192 kbps", "128 kbps")

    def __init__(self):
        super().__init__()
        self.title("Zazu - YouTube Media Downloader")
        self.geometry("780x650")
        self.minsize(700, 600)
        self.configure(bg="#f4f6f8")

        self.events = queue.Queue()
        self.worker = None
        self.cancel_event = threading.Event()

        self.url_var = tk.StringVar()
        self.output_var = tk.StringVar(value=str(Path.home() / "Downloads"))
        self.download_type_var = tk.StringVar(value="Single video")
        self.media_format_var = tk.StringVar(value="Video (MP4)")
        self.quality_var = tk.StringVar(value="1080p")
        self.range_enabled_var = tk.BooleanVar(value=False)
        self.range_start_var = tk.StringVar(value="1")
        self.range_end_var = tk.StringVar(value="10")
        self.status_var = tk.StringVar(value="Ready")
        self.item_status_var = tk.StringVar(value="")
        self.progress_var = tk.DoubleVar(value=0)

        self._build_ui()
        self._update_range_state()
        self.after(100, self._process_events)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TButton", padding=8, font=("Segoe UI", 10))
        style.configure("Accent.TButton", background="#2563eb", foreground="white")
        style.map("Accent.TButton", background=[("active", "#1d4ed8"), ("disabled", "#93c5fd")])
        style.configure("Horizontal.TProgressbar", troughcolor="#e5e7eb", background="#2563eb")

        outer = tk.Frame(self, bg="#f4f6f8", padx=28, pady=24)
        outer.pack(fill="both", expand=True)

        tk.Label(
            outer,
            text="Zazu - YouTube Video / MP3 Downloader",
            font=("Segoe UI", 20, "bold"),
            bg="#f4f6f8",
            fg="#111827",
        ).pack(anchor="w")
        tk.Label(
            outer,
            text="Download a single item or playlist in video or audio format.",
            font=("Segoe UI", 10),
            bg="#f4f6f8",
            fg="#6b7280",
        ).pack(anchor="w", pady=(4, 20))

        card = tk.Frame(
            outer,
            bg="white",
            padx=22,
            pady=20,
            highlightthickness=1,
            highlightbackground="#e5e7eb",
        )
        card.pack(fill="both", expand=True)

        self._field_label(card, "YouTube URL").pack(anchor="w")
        self.url_entry = ttk.Entry(card, textvariable=self.url_var, font=("Segoe UI", 11))
        self.url_entry.pack(fill="x", pady=(6, 16), ipady=5)
        self.url_entry.focus_set()

        self._field_label(card, "Save folder").pack(anchor="w")
        folder_row = tk.Frame(card, bg="white")
        folder_row.pack(fill="x", pady=(6, 16))
        self.output_entry = ttk.Entry(folder_row, textvariable=self.output_var, font=("Segoe UI", 10))
        self.output_entry.pack(side="left", fill="x", expand=True, ipady=5)
        self.browse_button = ttk.Button(folder_row, text="Browse", command=self._browse_folder)
        self.browse_button.pack(side="left", padx=(8, 0))

        options_row = tk.Frame(card, bg="white")
        options_row.pack(fill="x", pady=(0, 15))

        type_frame = tk.Frame(options_row, bg="white")
        format_frame = tk.Frame(options_row, bg="white")
        quality_frame = tk.Frame(options_row, bg="white")
        type_frame.pack(side="left", fill="x", expand=True, padx=(0, 7))
        format_frame.pack(side="left", fill="x", expand=True, padx=7)
        quality_frame.pack(side="left", fill="x", expand=True, padx=(7, 0))

        self._field_label(type_frame, "Download type").pack(anchor="w")
        self.type_box = ttk.Combobox(
            type_frame,
            textvariable=self.download_type_var,
            values=("Single video", "Playlist"),
            state="readonly",
        )
        self.type_box.pack(fill="x", pady=(6, 0), ipady=4)
        self.type_box.bind("<<ComboboxSelected>>", self._download_type_changed)

        self._field_label(format_frame, "Format").pack(anchor="w")
        self.format_box = ttk.Combobox(
            format_frame,
            textvariable=self.media_format_var,
            values=("Video (MP4)", "Audio (MP3)"),
            state="readonly",
        )
        self.format_box.pack(fill="x", pady=(6, 0), ipady=4)
        self.format_box.bind("<<ComboboxSelected>>", self._format_changed)

        self._field_label(quality_frame, "Quality").pack(anchor="w")
        self.quality_box = ttk.Combobox(
            quality_frame,
            textvariable=self.quality_var,
            values=self.VIDEO_QUALITIES,
            state="readonly",
        )
        self.quality_box.pack(fill="x", pady=(6, 0), ipady=4)

        self.range_frame = tk.Frame(card, bg="#f9fafb", padx=12, pady=10)
        self.range_frame.pack(fill="x", pady=(0, 16))
        self.range_checkbox = ttk.Checkbutton(
            self.range_frame,
            text="Download only a playlist range",
            variable=self.range_enabled_var,
            command=self._update_range_state,
        )
        self.range_checkbox.pack(side="left")
        tk.Label(self.range_frame, text="Start", bg="#f9fafb", fg="#374151").pack(side="left", padx=(22, 5))
        self.start_entry = ttk.Entry(self.range_frame, textvariable=self.range_start_var, width=7)
        self.start_entry.pack(side="left")
        tk.Label(self.range_frame, text="End", bg="#f9fafb", fg="#374151").pack(side="left", padx=(12, 5))
        self.end_entry = ttk.Entry(self.range_frame, textvariable=self.range_end_var, width=7)
        self.end_entry.pack(side="left")

        ttk.Progressbar(card, variable=self.progress_var, maximum=100).pack(fill="x", pady=(4, 7))
        tk.Label(
            card,
            textvariable=self.item_status_var,
            bg="white",
            fg="#2563eb",
            anchor="w",
            font=("Segoe UI", 9, "bold"),
        ).pack(fill="x")
        tk.Label(
            card,
            textvariable=self.status_var,
            bg="white",
            fg="#4b5563",
            anchor="w",
            justify="left",
            wraplength=680,
        ).pack(fill="x", pady=(3, 0))

        actions = tk.Frame(card, bg="white")
        actions.pack(fill="x", pady=(20, 0))
        self.download_button = ttk.Button(
            actions,
            text="Download",
            style="Accent.TButton",
            command=self._start_download,
        )
        self.download_button.pack(side="left")
        self.cancel_button = ttk.Button(actions, text="Cancel", command=self._cancel_download, state="disabled")
        self.cancel_button.pack(side="left", padx=(8, 0))
        self.open_button = ttk.Button(actions, text="Open Folder", command=self._open_folder)
        self.open_button.pack(side="right")

        tk.Label(
            card,
            text="Use only for content you own or have permission to download.",
            font=("Segoe UI", 9),
            bg="white",
            fg="#9ca3af",
        ).pack(anchor="w", pady=(18, 0))

    @staticmethod
    def _field_label(parent, text):
        return tk.Label(parent, text=text, font=("Segoe UI", 10, "bold"), bg="white", fg="#374151")

    def _browse_folder(self):
        folder = filedialog.askdirectory(initialdir=self.output_var.get() or str(Path.home()))
        if folder:
            self.output_var.set(folder)

    def _format_changed(self, _event=None):
        if self.media_format_var.get() == "Audio (MP3)":
            self.quality_box.configure(values=self.AUDIO_QUALITIES)
            self.quality_var.set("320 kbps")
        else:
            self.quality_box.configure(values=self.VIDEO_QUALITIES)
            self.quality_var.set("1080p")

    def _download_type_changed(self, _event=None):
        if self.download_type_var.get() != "Playlist":
            self.range_enabled_var.set(False)
        self._update_range_state()

    def _update_range_state(self):
        is_playlist = self.download_type_var.get() == "Playlist"
        self.range_checkbox.configure(state="normal" if is_playlist else "disabled")
        entry_state = "normal" if is_playlist and self.range_enabled_var.get() else "disabled"
        self.start_entry.configure(state=entry_state)
        self.end_entry.configure(state=entry_state)

    def _validate_inputs(self):
        url = self.url_var.get().strip()
        if not url.startswith(("https://", "http://")):
            raise ValueError("Enter a valid YouTube URL beginning with http:// or https://.")

        output_folder = Path(self.output_var.get().strip()).expanduser()
        if not str(output_folder).strip():
            raise ValueError("Select a save folder.")
        output_folder.mkdir(parents=True, exist_ok=True)

        if not shutil.which("ffmpeg"):
            raise ValueError(
                "FFmpeg was not found in PATH. Install FFmpeg, restart the terminal, and run the app again."
            )

        playlist_range = None
        if self.download_type_var.get() == "Playlist" and self.range_enabled_var.get():
            try:
                start = int(self.range_start_var.get())
                end = int(self.range_end_var.get())
            except ValueError as exc:
                raise ValueError("Playlist Start and End must be whole numbers.") from exc
            if start < 1 or end < 1:
                raise ValueError("Playlist Start and End must be at least 1.")
            if end < start:
                raise ValueError("Playlist End must be greater than or equal to Start.")
            if end - start > 999:
                raise ValueError("For safety, select a range containing no more than 1,000 items.")
            playlist_range = (start, end)

        return url, output_folder, playlist_range

    def _progress_hook(self, data):
        if self.cancel_event.is_set():
            raise DownloadCancelled("Download cancelled by user")

        status = data.get("status")
        info = data.get("info_dict") or {}
        playlist_index = info.get("playlist_index")
        playlist_count = info.get("playlist_count") or info.get("n_entries")
        title = info.get("title") or "Current item"

        if playlist_index:
            item_text = f"Playlist item {playlist_index}"
            if playlist_count:
                item_text += f" of {playlist_count}"
            item_text += f": {title}"
        else:
            item_text = title

        if status == "downloading":
            total = data.get("total_bytes") or data.get("total_bytes_estimate") or 0
            downloaded = data.get("downloaded_bytes") or 0
            percent = (downloaded / total * 100) if total else 0
            speed = (data.get("_speed_str") or "").strip()
            eta = (data.get("_eta_str") or "").strip()
            parts = [f"Downloading: {percent:.1f}%"]
            if speed:
                parts.append(f"Speed: {speed}")
            if eta:
                parts.append(f"ETA: {eta}")
            self.events.put(("progress", percent, item_text, "   ".join(parts)))
        elif status == "finished":
            self.events.put(("progress", 100, item_text, "Download finished. Processing with FFmpeg..."))

    def _build_download_options(self, output_folder, playlist_range, config):
        is_playlist = config["download_type"] == "Playlist"
        is_audio = config["media_format"] == "Audio (MP3)"

        if is_playlist:
            output_template = str(
                output_folder
                / "%(playlist_title,playlist,id)s"
                / "%(playlist_index)03d - %(title).180B [%(id)s].%(ext)s"
            )
        else:
            output_template = str(output_folder / "%(title).180B [%(id)s].%(ext)s")

        options = {
            "outtmpl": output_template,
            "noplaylist": not is_playlist,
            "windowsfilenames": os.name == "nt",
            "progress_hooks": [self._progress_hook],
            "quiet": True,
            "no_warnings": True,
            "ignoreerrors": False,
            "continuedl": True,
            "retries": 10,
            "fragment_retries": 10,
            "concurrent_fragment_downloads": 4,
        }

        if playlist_range:
            start, end = playlist_range
            options["playliststart"] = start
            options["playlistend"] = end

        if is_audio:
            bitrate = config["quality"].split()[0]
            options.update(
                {
                    "format": "bestaudio/best",
                    "postprocessors": [
                        {
                            "key": "FFmpegExtractAudio",
                            "preferredcodec": "mp3",
                            "preferredquality": bitrate,
                        },
                        {"key": "FFmpegMetadata", "add_metadata": True},
                    ],
                }
            )
        else:
            selected_quality = config["quality"]
            if selected_quality == "Best":
                format_selector = "bestvideo*+bestaudio/best"
            else:
                max_height = selected_quality.removesuffix("p")
                format_selector = (
                    f"bestvideo*[height<={max_height}]+bestaudio/"
                    f"best[height<={max_height}]"
                )
            options.update(
                {
                    "format": format_selector,
                    "merge_output_format": "mp4",
                }
            )

        return options

    def _set_controls_downloading(self, downloading):
        normal_state = "disabled" if downloading else "normal"
        readonly_state = "disabled" if downloading else "readonly"
        self.download_button.configure(state=normal_state)
        self.cancel_button.configure(state="normal" if downloading else "disabled")
        self.url_entry.configure(state=normal_state)
        self.output_entry.configure(state=normal_state)
        self.browse_button.configure(state=normal_state)
        self.type_box.configure(state=readonly_state)
        self.format_box.configure(state=readonly_state)
        self.quality_box.configure(state=readonly_state)
        self.open_button.configure(state=normal_state)
        if not downloading:
            self._update_range_state()
        else:
            self.range_checkbox.configure(state="disabled")
            self.start_entry.configure(state="disabled")
            self.end_entry.configure(state="disabled")

    def _start_download(self):
        if self.worker and self.worker.is_alive():
            return
        try:
            url, output_folder, playlist_range = self._validate_inputs()
        except Exception as exc:
            messagebox.showerror("Cannot start", str(exc))
            return

        config = {
            "download_type": self.download_type_var.get(),
            "media_format": self.media_format_var.get(),
            "quality": self.quality_var.get(),
        }
        self.cancel_event.clear()
        self.progress_var.set(0)
        self.item_status_var.set("")
        self.status_var.set("Preparing download...")
        self._set_controls_downloading(True)
        self.worker = threading.Thread(
            target=self._download_worker,
            args=(url, output_folder, playlist_range, config),
            daemon=True,
        )
        self.worker.start()

    def _download_worker(self, url, output_folder, playlist_range, config):
        try:
            options = self._build_download_options(output_folder, playlist_range, config)
            with yt_dlp.YoutubeDL(options) as ydl:
                result_code = ydl.download([url])
            if self.cancel_event.is_set():
                raise DownloadCancelled()
            if result_code not in (None, 0):
                raise RuntimeError(f"yt-dlp finished with error code {result_code}")
            self.events.put(("done", str(output_folder)))
        except DownloadCancelled:
            self.events.put(("cancelled",))
        except Exception as exc:
            self.events.put(("error", f"{type(exc).__name__}: {exc}"))

    def _cancel_download(self):
        self.cancel_event.set()
        self.status_var.set("Cancelling after the current network operation...")
        self.cancel_button.configure(state="disabled")

    def _process_events(self):
        try:
            while True:
                event = self.events.get_nowait()
                kind = event[0]
                if kind == "progress":
                    self.progress_var.set(event[1])
                    self.item_status_var.set(event[2])
                    self.status_var.set(event[3])
                elif kind == "done":
                    self.progress_var.set(100)
                    self.status_var.set("Download completed successfully.")
                    self._set_controls_downloading(False)
                    messagebox.showinfo("Complete", f"Download completed.\n\nSaved to:\n{event[1]}")
                elif kind == "cancelled":
                    self.status_var.set("Download cancelled.")
                    self._set_controls_downloading(False)
                elif kind == "error":
                    self.status_var.set("Download failed.")
                    self._set_controls_downloading(False)
                    messagebox.showerror("Download failed", event[1])
        except queue.Empty:
            pass
        self.after(100, self._process_events)

    def _open_folder(self):
        folder = Path(self.output_var.get()).expanduser()
        folder.mkdir(parents=True, exist_ok=True)
        try:
            if os.name == "nt":
                os.startfile(str(folder))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(folder)])
            else:
                subprocess.Popen(["xdg-open", str(folder)])
        except Exception as exc:
            messagebox.showerror("Cannot open folder", str(exc))

    def _on_close(self):
        if self.worker and self.worker.is_alive():
            if not messagebox.askyesno("Exit", "A download is running. Cancel it and exit?"):
                return
            self.cancel_event.set()
        self.destroy()


if __name__ == "__main__":
    import sys
    DownloaderApp().mainloop()
