"""
Tkinter GUI for Video Splitter.
Launched via: python main.py --gui
"""

import os
import queue
import threading
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox

from core import (
    check_ffmpeg, get_video_summary, split_video,
    FfmpegNotFoundError, VideoInfoError, SplitProgress,
)


class VideoSplitterGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Video Splitter")
        self.root.resizable(True, True)
        self.root.minsize(600, 580)

        self.video_summary = None
        self.progress_queue = queue.Queue()
        self.cancel_event = threading.Event()
        self.split_thread = None

        self._check_ffmpeg()
        self._build_ui()

    # ── FFmpeg Check ──────────────────────────────────────────────────────

    def _check_ffmpeg(self):
        try:
            check_ffmpeg()
        except FfmpegNotFoundError as e:
            messagebox.showerror("FFmpeg Not Found", str(e))
            self.root.destroy()
            raise SystemExit(1)

    # ── UI Construction ───────────────────────────────────────────────────

    def _build_ui(self):
        pad = {"padx": 8, "pady": 4}
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # -- Input Video --
        input_frame = ttk.LabelFrame(main_frame, text="Input Video", padding=6)
        input_frame.pack(fill=tk.X, **pad)

        self.input_var = tk.StringVar()
        ttk.Entry(input_frame, textvariable=self.input_var, state="readonly").pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        ttk.Button(input_frame, text="Browse...", command=self._browse_input).pack(side=tk.RIGHT)

        # -- Video Info --
        info_frame = ttk.LabelFrame(main_frame, text="Video Info", padding=6)
        info_frame.pack(fill=tk.X, **pad)

        self.info_labels = {}
        fields = [
            ("Codec", "codec"), ("Duration", "duration_str"),
            ("Resolution", "resolution"), ("FPS", "fps"),
            ("Bitrate", "bitrate_str"), ("Audio", "audio_codec"),
            ("File Size", "file_size_str"),
        ]
        for row, (label, key) in enumerate(fields):
            ttk.Label(info_frame, text=f"{label}:", anchor=tk.W, width=12).grid(
                row=row, column=0, sticky=tk.W, padx=(0, 6))
            val_label = ttk.Label(info_frame, text="-", anchor=tk.W)
            val_label.grid(row=row, column=1, sticky=tk.W)
            self.info_labels[key] = val_label

        # -- Split Settings --
        settings_frame = ttk.LabelFrame(main_frame, text="Split Settings", padding=6)
        settings_frame.pack(fill=tk.X, **pad)

        dur_row = ttk.Frame(settings_frame)
        dur_row.pack(fill=tk.X)
        ttk.Label(dur_row, text="Segment duration (minutes):").pack(side=tk.LEFT)
        self.minutes_var = tk.StringVar(value="10")
        self.minutes_spin = ttk.Spinbox(
            dur_row, from_=1, to=9999, textvariable=self.minutes_var, width=8)
        self.minutes_spin.pack(side=tk.LEFT, padx=6)

        self.convert_var = tk.BooleanVar(value=False)
        self.convert_check = ttk.Checkbutton(
            settings_frame, text="Convert AV1 to H.264",
            variable=self.convert_var)
        # Hidden by default, shown when AV1 is detected
        self.convert_check.pack(anchor=tk.W, pady=(4, 0))
        self.convert_check.pack_forget()

        # -- Output Directory --
        output_frame = ttk.LabelFrame(main_frame, text="Output Directory", padding=6)
        output_frame.pack(fill=tk.X, **pad)

        self.output_var = tk.StringVar()
        ttk.Entry(output_frame, textvariable=self.output_var).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        ttk.Button(output_frame, text="Browse...", command=self._browse_output).pack(side=tk.RIGHT)

        # -- Progress --
        progress_frame = ttk.LabelFrame(main_frame, text="Progress", padding=6)
        progress_frame.pack(fill=tk.BOTH, expand=True, **pad)

        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(progress_frame, textvariable=self.status_var, anchor=tk.W).pack(fill=tk.X)

        self.progressbar = ttk.Progressbar(progress_frame, mode="determinate")
        self.progressbar.pack(fill=tk.X, pady=4)

        self.log_text = scrolledtext.ScrolledText(
            progress_frame, height=8, state=tk.DISABLED, wrap=tk.WORD, font=("Consolas", 9))
        self.log_text.pack(fill=tk.BOTH, expand=True)

        # -- Action Buttons --
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, **pad)

        self.start_btn = ttk.Button(btn_frame, text="Start Splitting", command=self._start_split)
        self.start_btn.pack(side=tk.LEFT, padx=(0, 6))
        self.start_btn.state(["disabled"])

        self.cancel_btn = ttk.Button(btn_frame, text="Cancel", command=self._cancel_split)
        self.cancel_btn.pack(side=tk.LEFT)
        self.cancel_btn.state(["disabled"])

    # ── File Browsing ─────────────────────────────────────────────────────

    def _browse_input(self):
        path = filedialog.askopenfilename(
            title="Select Video File",
            filetypes=[
                ("Video files", "*.mp4 *.mkv *.avi *.mov *.webm *.flv *.wmv *.ts"),
                ("All files", "*.*"),
            ]
        )
        if not path:
            return
        self.input_var.set(path)
        self._load_video_info(path)

    def _browse_output(self):
        path = filedialog.askdirectory(title="Select Output Directory")
        if path:
            self.output_var.set(path)

    # ── Video Info Loading ────────────────────────────────────────────────

    def _load_video_info(self, filepath):
        self.status_var.set("Reading video info...")
        self.root.update_idletasks()

        try:
            summary = get_video_summary(filepath)
        except (VideoInfoError, Exception) as e:
            messagebox.showerror("Error", str(e))
            self.status_var.set("Ready")
            return

        self.video_summary = summary

        for key, label in self.info_labels.items():
            val = summary.get(key, "-")
            if key == "codec":
                val = val.upper()
            elif key == "audio_codec":
                val = val.upper()
            label.config(text=str(val))

        # Show/hide AV1 conversion checkbox
        if summary["is_av1"]:
            self.convert_check.pack(anchor=tk.W, pady=(4, 0))
            self.convert_var.set(True)
        else:
            self.convert_check.pack_forget()
            self.convert_var.set(False)

        # Set default output directory
        input_dir = os.path.dirname(os.path.abspath(filepath))
        default_output = os.path.join(input_dir, "output_split")
        self.output_var.set(default_output)

        self.start_btn.state(["!disabled"])
        self.status_var.set("Ready - video loaded")

    # ── Input Validation ──────────────────────────────────────────────────

    def _validate_inputs(self):
        if not self.input_var.get() or not os.path.isfile(self.input_var.get()):
            messagebox.showwarning("Invalid Input", "Please select a valid video file.")
            return False

        try:
            minutes = float(self.minutes_var.get())
        except ValueError:
            messagebox.showwarning("Invalid Duration", "Segment duration must be a number.")
            return False

        if minutes <= 0:
            messagebox.showwarning("Invalid Duration", "Segment duration must be greater than 0.")
            return False

        if self.video_summary and minutes * 60 >= self.video_summary["duration"]:
            messagebox.showwarning(
                "Invalid Duration",
                "Segment duration must be less than the total video duration.")
            return False

        if not self.output_var.get().strip():
            messagebox.showwarning("Invalid Output", "Please specify an output directory.")
            return False

        return True

    # ── Splitting ─────────────────────────────────────────────────────────

    def _start_split(self):
        if not self._validate_inputs():
            return

        self.start_btn.state(["disabled"])
        self.cancel_btn.state(["!disabled"])
        self.cancel_event.clear()
        self._clear_log()

        minutes = float(self.minutes_var.get())
        total_segments = __import__("math").ceil(self.video_summary["duration"] / (minutes * 60))
        self.progressbar["maximum"] = total_segments
        self.progressbar["value"] = 0

        self.split_thread = threading.Thread(
            target=self._split_worker,
            args=(self.input_var.get(), minutes,
                  self.convert_var.get(), self.output_var.get()),
            daemon=True,
        )
        self.split_thread.start()
        self.root.after(100, self._poll_progress)

    def _split_worker(self, input_path, minutes, convert, output_dir):
        def callback(progress):
            self.progress_queue.put(progress)

        try:
            split_video(
                input_path, minutes, convert, output_dir,
                progress_callback=callback,
                cancel_event=self.cancel_event,
            )
        except Exception as e:
            self.progress_queue.put(SplitProgress(
                segment_index=0, total_segments=0,
                start_label="", end_label="", filename="",
                status="failed", error=str(e),
                message=f"Error: {e}"
            ))

    def _poll_progress(self):
        try:
            while True:
                progress = self.progress_queue.get_nowait()
                self._handle_progress(progress)
        except queue.Empty:
            pass

        if self.split_thread and self.split_thread.is_alive():
            self.root.after(100, self._poll_progress)
        else:
            self._on_split_finished()

    def _handle_progress(self, progress):
        self._log(progress.message)
        self.status_var.set(progress.message)

        if progress.status == "done" and progress.segment_index > 0:
            self.progressbar["value"] = progress.segment_index
        elif progress.status == "failed" and progress.error:
            self._log(f"  Error: {progress.error}")
        elif progress.status == "cancelled":
            self.status_var.set("Cancelled")

    def _on_split_finished(self):
        self.start_btn.state(["!disabled"])
        self.cancel_btn.state(["disabled"])

        if self.cancel_event.is_set():
            self.status_var.set("Cancelled by user")
        elif self.progressbar["value"] >= self.progressbar["maximum"]:
            self.status_var.set("Splitting complete!")
            messagebox.showinfo("Complete", "Video splitting finished successfully!")

    def _cancel_split(self):
        self.cancel_event.set()
        self.status_var.set("Cancelling...")
        self._log("Cancelling...")

    # ── Log Helpers ───────────────────────────────────────────────────────

    def _log(self, text):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, text + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def _clear_log(self):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.config(state=tk.DISABLED)
