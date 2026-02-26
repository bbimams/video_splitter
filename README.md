# Video Splitter

Python tool to split long videos into smaller clips with FFmpeg.
Supports both an interactive CLI and a tkinter GUI. The tool can detect AV1 videos and optionally convert them to H.264 for better playback compatibility.

## Features

- Split videos by custom segment length (in minutes)
- Auto-detect video and audio codec with `ffprobe`
- Optional AV1 to H.264 conversion during split
- Auto-generate detailed `README.txt` in the output folder
- Show clip summary (duration, resolution, FPS, codec, file size)
- **GUI mode** with file browser, video info panel, progress bar, and cancel support

## Requirements

- Python 3.8+
- FFmpeg and FFprobe installed and available in `PATH`

```bash
ffmpeg -version
ffprobe -version
```

## Usage

### CLI Mode

Run the interactive CLI:

```bash
python main.py
```

You will be prompted to:

1. Enter the input video path
2. Choose segment duration (minutes)
3. Confirm AV1 to H.264 conversion (only shown for AV1 sources)
4. Choose output directory (or use default)
5. Confirm and start processing

### GUI Mode

Launch the graphical interface:

```bash
python main.py --gui
```

The GUI provides:

- File browser to select input video
- Video info panel (codec, duration, resolution, FPS, bitrate, audio, file size)
- Segment duration setting with AV1 conversion option
- Output directory picker
- Progress bar with log output
- Cancel button to stop mid-split

## Output

The tool creates:

- Split video clips named like `original_00-00 - 00-10.mp4`
- A generated `README.txt` containing:
  - source video details
  - split settings
  - clip summary table
  - per-clip technical details

Default output folder:

- `output_split` (next to the source video), unless a custom path is provided

## Project Structure

- `main.py` - entry point (CLI and `--gui` flag)
- `core.py` - shared logic (ffmpeg helpers, splitting, progress callbacks)
- `gui.py` - tkinter GUI

## Notes

- If AV1 conversion is disabled, the script uses stream copy (`-c:v copy -c:a copy`) for faster processing.
- If conversion is enabled, video is encoded with `h264_nvenc` (NVIDIA GPU) and audio with AAC.
- The GUI requires no extra dependencies — it uses Python's built-in `tkinter`.

## Troubleshooting

- `ffmpeg` or `ffprobe` not found: install FFmpeg and ensure binaries are in `PATH`.
- Invalid file path: use full path to the source video.
- Slow processing: expected when conversion to H.264 is enabled.
