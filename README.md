# Video Splitter

Interactive Python CLI tool to split long videos into smaller clips with FFmpeg.
The script can detect AV1 videos and optionally convert them to H.264 for better playback compatibility.

## Features

- Split videos by custom segment length (in minutes)
- Auto-detect video and audio codec with `ffprobe`
- Optional AV1 to H.264 conversion during split
- Auto-generate detailed `README.txt` in the output folder
- Show clip summary (duration, resolution, FPS, codec, file size)

## Requirements

- Python 3.8+
- FFmpeg and FFprobe installed and available in `PATH`

You can verify your setup with:

```bash
ffmpeg -version
ffprobe -version
```

## Usage

Run the script:

```bash
python main.py
```

You will be prompted to:

1. Enter the input video path
2. Choose segment duration (minutes)
3. Confirm AV1 to H.264 conversion (only shown for AV1 sources)
4. Choose output directory (or use default)
5. Confirm and start processing

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

- `main.py` - interactive splitter script

## Notes

- If AV1 conversion is disabled, the script uses stream copy (`-c:v copy -c:a copy`) for faster processing.
- If conversion is enabled, video is encoded with `libx264` and audio with AAC.
- CLI prompts are currently in Indonesian.

## Troubleshooting

- `ffmpeg` or `ffprobe` not found: install FFmpeg and ensure binaries are in `PATH`.
- Invalid file path: use full path to the source video.
- Slow processing: expected when conversion to H.264 is enabled.
