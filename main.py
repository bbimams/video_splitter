#!/usr/bin/env python3
"""
Video Splitter - split long videos into smaller clips using FFmpeg.
Supports CLI (interactive) and GUI (--gui) modes.
"""

import os
import sys
import math

from core import (
    check_ffmpeg, get_video_info, get_video_stream, detect_codec,
    get_duration, get_framerate, seconds_to_hhmmss, duration_label,
    split_video, cli_progress_callback, FfmpegNotFoundError,
)


def main():
    print("=" * 55)
    print("       VIDEO SPLITTER  |  Python + FFmpeg")
    print("=" * 55)

    try:
        check_ffmpeg()
    except FfmpegNotFoundError as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    # ── Input file ────────────────────────────────────────────────
    while True:
        input_path = input("\nEnter video file path: ").strip().strip('"').strip("'")
        if os.path.isfile(input_path):
            break
        print(f"   File not found: {input_path}")

    print("\nReading video info...")
    info     = get_video_info(input_path)
    codec    = detect_codec(info)
    duration = get_duration(info)
    vs       = get_video_stream(info)

    print(f"   Codec      : {codec.upper()}")
    print(f"   Resolution : {vs.get('width','?')}x{vs.get('height','?')} @ {get_framerate(vs)} fps")
    print(f"   Duration   : {seconds_to_hhmmss(duration)}  ({duration/60:.1f} min)")

    # ── Segment duration ──────────────────────────────────────────
    while True:
        try:
            minutes = float(input("\nSegment duration in minutes (e.g. 10): ").strip())
            if minutes <= 0:
                print("   Must be greater than 0."); continue
            if minutes * 60 >= duration:
                print("   Segment duration exceeds video length. Try a smaller value."); continue
            break
        except ValueError:
            print("   Enter a valid number.")

    # ── AV1 detection ─────────────────────────────────────────────
    convert_to_h264 = False
    if codec == "av1":
        print("\nWARNING: Video uses AV1 encoding.")
        print("   AV1 has limited compatibility with some devices and players.")
        answer = input("   Convert to H.264? (y/n): ").strip().lower()
        if answer in ("y", "ya", "yes"):
            convert_to_h264 = True
            print("   Video will be converted to H.264.")
        else:
            print("   Video will be split without conversion (keeping AV1).")

    # ── Output directory ──────────────────────────────────────────
    default_dir = os.path.join(os.path.dirname(os.path.abspath(input_path)), "output_split")
    print(f"\nDefault output folder: {default_dir}")
    custom = input("   Press Enter for default, or type a custom path: ").strip().strip('"').strip("'")
    output_dir = custom if custom else default_dir

    # ── Confirmation ──────────────────────────────────────────────
    num_seg = math.ceil(duration / (minutes * 60))
    print(f"\n{'='*55}")
    print(f"  File        : {os.path.basename(input_path)}")
    print(f"  Duration    : {seconds_to_hhmmss(duration)}")
    print(f"  Per segment : {minutes} min  ->  {num_seg} files")
    print(f"  Conversion  : {'AV1 -> H.264' if convert_to_h264 else 'None (stream copy)'}")
    print(f"  Output      : {output_dir}")
    print(f"  README.txt  : Auto-generated in output folder")
    print(f"{'='*55}")

    ok = input("\nStart processing? (y/n): ").strip().lower()
    if ok not in ("y", "ya", "yes"):
        print("Cancelled.")
        sys.exit(0)

    split_video(input_path, minutes, convert_to_h264, output_dir,
                progress_callback=cli_progress_callback)


if __name__ == "__main__":
    if "--gui" in sys.argv:
        from gui import VideoSplitterGUI
        import tkinter as tk
        root = tk.Tk()
        app = VideoSplitterGUI(root)
        root.mainloop()
    else:
        main()
