"""
Core logic for Video Splitter.
Extracted from main.py for reuse by both CLI and GUI.
"""

import subprocess
import os
import json
import math
from dataclasses import dataclass
from datetime import datetime


# ── Exceptions ────────────────────────────────────────────────────────────────

class FfmpegNotFoundError(Exception):
    """Raised when ffmpeg or ffprobe is not found."""

    def __init__(self, tool):
        self.tool = tool
        super().__init__(f"'{tool}' not found. Install ffmpeg: https://ffmpeg.org/download.html")


class VideoInfoError(Exception):
    """Raised when video info cannot be read."""

    def __init__(self, filepath, detail=""):
        self.filepath = filepath
        msg = f"Failed to read file: {filepath}"
        if detail:
            msg += f" ({detail})"
        super().__init__(msg)


# ── Data Classes ──────────────────────────────────────────────────────────────

@dataclass
class SplitProgress:
    """Progress information for a single segment."""
    segment_index: int
    total_segments: int
    start_label: str
    end_label: str
    filename: str
    status: str  # "started", "done", "failed", "cancelled"
    size_str: str = ""
    error: str = ""
    message: str = ""


# ── Stream Helpers ────────────────────────────────────────────────────────────

def get_video_stream(info):
    for s in info.get("streams", []):
        if s.get("codec_type") == "video":
            return s
    return {}


def get_audio_stream(info):
    for s in info.get("streams", []):
        if s.get("codec_type") == "audio":
            return s
    return {}


def detect_codec(info):
    return get_video_stream(info).get("codec_name", "unknown").lower()


def get_audio_codec(info):
    return get_audio_stream(info).get("codec_name", "unknown").lower()


def get_duration(info):
    d = info.get("format", {}).get("duration")
    if d:
        return float(d)
    for s in info.get("streams", []):
        if s.get("codec_type") == "video" and s.get("duration"):
            return float(s["duration"])
    return 0.0


def get_framerate(stream):
    fr = stream.get("r_frame_rate", "0/1")
    try:
        num, den = fr.split("/")
        return round(float(num) / float(den), 2)
    except Exception:
        return 0.0


def get_bitrate(info):
    br = info.get("format", {}).get("bit_rate")
    return int(br) // 1000 if br else 0


# ── Formatting Helpers ────────────────────────────────────────────────────────

def seconds_to_hm(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    return f"{h:02d}:{m:02d}"


def seconds_to_hhmmss(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def duration_label(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    parts = []
    if h > 0: parts.append(f"{h}h")
    if m > 0: parts.append(f"{m}m")
    if s > 0 or not parts: parts.append(f"{s}s")
    return " ".join(parts)


def duration_label_id(seconds):
    """Indonesian duration label for README compatibility."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    parts = []
    if h > 0: parts.append(f"{h} jam")
    if m > 0: parts.append(f"{m} mnt")
    if s > 0 or not parts: parts.append(f"{s} dtk")
    return " ".join(parts)


def sanitize_filename(name):
    return name.replace(":", "-")


def format_size(size_bytes):
    if size_bytes >= 1024 ** 3:
        return f"{size_bytes / (1024**3):.2f} GB"
    return f"{size_bytes / (1024**2):.1f} MB"


# ── Core Functions ────────────────────────────────────────────────────────────

def check_ffmpeg():
    """Check that ffmpeg and ffprobe are available. Raises FfmpegNotFoundError."""
    for tool in ["ffmpeg", "ffprobe"]:
        try:
            subprocess.run(
                [tool, "-version"],
                capture_output=True,
                check=True,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise FfmpegNotFoundError(tool)


def get_video_info(filepath):
    """Read video info via ffprobe. Raises VideoInfoError on failure."""
    cmd = [
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_streams", "-show_format",
        filepath
    ]
    result = subprocess.run(
        cmd, capture_output=True, text=True,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    if result.returncode != 0:
        raise VideoInfoError(filepath, result.stderr.strip()[-200:] if result.stderr else "")
    return json.loads(result.stdout)


def get_video_summary(filepath):
    """Return a dict of displayable video metadata."""
    info = get_video_info(filepath)
    vs = get_video_stream(info)
    aus = get_audio_stream(info)
    duration = get_duration(info)
    codec = detect_codec(info)
    audio_codec = get_audio_codec(info)
    fps = get_framerate(vs)
    bitrate = get_bitrate(info)
    width = vs.get("width", "?")
    height = vs.get("height", "?")
    file_size = os.path.getsize(filepath) if os.path.isfile(filepath) else 0

    return {
        "info": info,
        "codec": codec,
        "audio_codec": audio_codec,
        "duration": duration,
        "duration_str": seconds_to_hhmmss(duration),
        "duration_label": duration_label(duration),
        "resolution": f"{width}x{height}",
        "width": width,
        "height": height,
        "fps": fps,
        "bitrate": bitrate,
        "bitrate_str": f"{bitrate} kbps",
        "file_size": file_size,
        "file_size_str": format_size(file_size),
        "is_av1": codec == "av1",
    }


def build_ffmpeg_cmd(input_path, out_path, start_sec, seg_duration, convert_to_h264):
    """Build the ffmpeg command list for one segment."""
    cmd = [
        "ffmpeg", "-y",
        "-ss", seconds_to_hhmmss(start_sec),
        "-i", input_path,
        "-t", str(seg_duration),
    ]
    if convert_to_h264:
        cmd += ["-c:v", "h264_nvenc", "-preset", "p5", "-cq", "23",
                "-c:a", "aac", "-b:a", "192k"]
    else:
        cmd += ["-c:v", "copy", "-c:a", "copy"]
    cmd.append(out_path)
    return cmd


def split_video(input_path, segment_duration_minutes, convert_to_h264, output_dir,
                progress_callback=None, cancel_event=None):
    """
    Split a video into segments.

    Args:
        input_path: Path to the input video file.
        segment_duration_minutes: Duration of each segment in minutes.
        convert_to_h264: Whether to re-encode AV1 to H.264.
        output_dir: Output directory for segments.
        progress_callback: Optional callable(SplitProgress) for progress updates.
        cancel_event: Optional threading.Event to signal cancellation.

    Returns:
        List of clip entry dicts.

    Raises:
        VideoInfoError: If video info cannot be read.
    """
    segment_seconds = segment_duration_minutes * 60
    info = get_video_info(input_path)
    codec = detect_codec(info)
    duration = get_duration(info)

    if duration == 0:
        raise VideoInfoError(input_path, "Cannot read video duration")

    vs = get_video_stream(info)
    num_segments = math.ceil(duration / segment_seconds)
    base_name = os.path.splitext(os.path.basename(input_path))[0]

    def notify(progress):
        if progress_callback:
            progress_callback(progress)

    notify(SplitProgress(
        segment_index=0, total_segments=num_segments,
        start_label="", end_label="", filename="",
        status="started",
        message=f"Splitting into {num_segments} segments..."
    ))

    os.makedirs(output_dir, exist_ok=True)
    clip_entries = []

    for i in range(num_segments):
        if cancel_event and cancel_event.is_set():
            notify(SplitProgress(
                segment_index=i + 1, total_segments=num_segments,
                start_label="", end_label="", filename="",
                status="cancelled",
                message="Cancelled by user."
            ))
            return clip_entries

        start_sec = i * segment_seconds
        end_sec = min(start_sec + segment_seconds, duration)
        seg_duration = end_sec - start_sec
        start_label = seconds_to_hm(start_sec)
        end_label = seconds_to_hm(end_sec)
        out_filename = f"{base_name}_{sanitize_filename(start_label)} - {sanitize_filename(end_label)}.mp4"
        out_path = os.path.join(output_dir, out_filename)

        notify(SplitProgress(
            segment_index=i + 1, total_segments=num_segments,
            start_label=start_label, end_label=end_label,
            filename=out_filename, status="started",
            message=f"[{i+1}/{num_segments}] {start_label} -> {end_label} | {out_filename}"
        ))

        cmd = build_ffmpeg_cmd(input_path, out_path, start_sec, seg_duration, convert_to_h264)

        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )

        while proc.poll() is None:
            if cancel_event and cancel_event.is_set():
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                notify(SplitProgress(
                    segment_index=i + 1, total_segments=num_segments,
                    start_label=start_label, end_label=end_label,
                    filename=out_filename, status="cancelled",
                    message="Cancelled by user."
                ))
                return clip_entries
            try:
                proc.wait(timeout=0.5)
            except subprocess.TimeoutExpired:
                pass

        if proc.returncode == 0:
            size_bytes = os.path.getsize(out_path)
            size_str = format_size(size_bytes)

            ci = get_video_info(out_path)
            cvs = get_video_stream(ci)
            cas = get_audio_stream(ci)
            entry = {
                "filename": out_filename,
                "start_label": start_label,
                "end_label": end_label,
                "duration_sec": seg_duration,
                "width": cvs.get("width"),
                "height": cvs.get("height"),
                "fps": get_framerate(cvs),
                "codec_video": cvs.get("codec_name", "?").upper(),
                "codec_audio": cas.get("codec_name", "?").upper(),
                "bitrate": get_bitrate(ci),
                "size_bytes": size_bytes,
                "size_str": size_str,
            }
            clip_entries.append(entry)

            notify(SplitProgress(
                segment_index=i + 1, total_segments=num_segments,
                start_label=start_label, end_label=end_label,
                filename=out_filename, status="done",
                size_str=size_str,
                message=f"[{i+1}/{num_segments}] Done ({size_str})"
            ))
        else:
            stderr = proc.stderr.read().decode(errors="replace") if proc.stderr else ""
            notify(SplitProgress(
                segment_index=i + 1, total_segments=num_segments,
                start_label=start_label, end_label=end_label,
                filename=out_filename, status="failed",
                error=stderr[-500:],
                message=f"[{i+1}/{num_segments}] FAILED!"
            ))

    # Generate README.txt
    if clip_entries:
        readme_path = generate_readme(
            output_dir, input_path, info,
            clip_entries, segment_duration_minutes, convert_to_h264
        )
        notify(SplitProgress(
            segment_index=num_segments, total_segments=num_segments,
            start_label="", end_label="", filename="README.txt",
            status="done",
            message=f"README.txt generated: {readme_path}"
        ))

    notify(SplitProgress(
        segment_index=num_segments, total_segments=num_segments,
        start_label="", end_label="", filename="",
        status="done",
        message=f"All done! Files saved to: {os.path.abspath(output_dir)}"
    ))

    return clip_entries


# ── CLI Progress Callback ────────────────────────────────────────────────────

def cli_progress_callback(progress):
    """Default print-based progress callback for CLI usage."""
    print(progress.message)


# ── README Generator ──────────────────────────────────────────────────────────

def generate_readme(output_dir, source_path, source_info, clip_entries, segment_minutes, convert_to_h264):
    now       = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    vs        = get_video_stream(source_info)
    aus       = get_audio_stream(source_info)
    duration  = get_duration(source_info)
    src_codec = detect_codec(source_info)
    src_audio = get_audio_codec(source_info)
    src_fps   = get_framerate(vs)
    src_br    = get_bitrate(source_info)
    src_pix   = vs.get("pix_fmt", "?")
    src_sr    = aus.get("sample_rate", "?")
    src_ch    = aus.get("channels", "?")
    src_chlay = aus.get("channel_layout", "")
    src_w     = vs.get("width", "?")
    src_h     = vs.get("height", "?")
    src_size  = os.path.getsize(source_path) if os.path.isfile(source_path) else 0

    out_vcodec = "H.264 (libx264)" if convert_to_h264 else src_codec.upper()
    out_acodec = "AAC 192kbps"     if convert_to_h264 else src_audio.upper()

    DIV  = "=" * 65
    DIV2 = "-" * 65
    L    = []

    L.append(DIV)
    L.append("  VIDEO SPLITTER — README")
    L.append(f"  Created  : {now}")
    L.append(f"  Output   : {os.path.abspath(output_dir)}")
    L.append(DIV)
    L.append("")

    L.append("[ SOURCE VIDEO ]")
    L.append(DIV2)
    L.append(f"  File             : {os.path.basename(source_path)}")
    L.append(f"  Path             : {source_path}")
    L.append(f"  File Size        : {format_size(src_size)}")
    L.append(f"  Total Duration   : {duration_label_id(duration)}  ({seconds_to_hhmmss(duration)})")
    L.append(f"  Resolution       : {src_w} x {src_h}")
    L.append(f"  Frame Rate       : {src_fps} fps")
    L.append(f"  Pixel Format     : {src_pix}")
    L.append(f"  Video Codec      : {src_codec.upper()}")
    L.append(f"  Audio Codec      : {src_audio.upper()}")
    L.append(f"  Sample Rate      : {src_sr} Hz")
    L.append(f"  Audio Channel    : {src_ch} ch  ({src_chlay})")
    L.append(f"  Total Bitrate    : {src_br} kbps")
    L.append("")

    L.append("[ SPLIT SETTINGS ]")
    L.append(DIV2)
    L.append(f"  Duration per clip    : {segment_minutes} min")
    L.append(f"  Number of clips      : {len(clip_entries)} files")
    L.append(f"  Conversion           : {'AV1 -> H.264 (re-encode)' if convert_to_h264 else 'None (stream copy, faster)'}")
    L.append(f"  Output Video Codec   : {out_vcodec}")
    L.append(f"  Output Audio Codec   : {out_acodec}")
    if convert_to_h264:
        L.append(f"  CRF (quality)        : 23  (scale 0-51, lower = better quality)")
        L.append(f"  Encode Preset        : medium")
    L.append("")

    L.append("[ CLIP SUMMARY ]")
    L.append(DIV2)

    W = [4, 36, 14, 13, 9, 9]
    hdr = (
        f"  {'No':<{W[0]}} "
        f"{'Filename':<{W[1]}} "
        f"{'Duration':<{W[2]}} "
        f"{'Resolution':<{W[3]}} "
        f"{'FPS':<{W[4]}} "
        f"{'Size':<{W[5]}}"
    )
    L.append(hdr)
    L.append("  " + "-" * (sum(W) + len(W) - 1))

    total_size = 0
    for i, c in enumerate(clip_entries, 1):
        fname = c["filename"]
        if len(fname) > W[1]:
            fname = fname[:W[1]-3] + "..."
        res = f"{c['width']}x{c['height']}" if c["width"] else "?"
        row = (
            f"  {str(i)+'.':<{W[0]}} "
            f"{fname:<{W[1]}} "
            f"{duration_label(c['duration_sec']):<{W[2]}} "
            f"{res:<{W[3]}} "
            f"{str(c['fps'])+' fps':<{W[4]}} "
            f"{c['size_str']:<{W[5]}}"
        )
        L.append(row)
        total_size += c["size_bytes"]

    L.append("  " + "-" * (sum(W) + len(W) - 1))
    pad = sum(W[:5]) + 5
    L.append(f"  {'':<{pad}} Total : {format_size(total_size)}")
    L.append("")

    L.append("[ DETAILED CLIP INFO ]")
    L.append(DIV2)

    for i, c in enumerate(clip_entries, 1):
        L.append(f"  Clip #{i:02d}  --  {c['start_label']} -> {c['end_label']}")
        L.append(f"    Filename       : {c['filename']}")
        L.append(f"    Timestamp      : {c['start_label']} -> {c['end_label']}")
        L.append(f"    Duration       : {duration_label(c['duration_sec'])}  ({seconds_to_hhmmss(c['duration_sec'])})")
        if c["width"]:
            L.append(f"    Resolution     : {c['width']} x {c['height']}")
        L.append(f"    Frame Rate     : {c['fps']} fps")
        L.append(f"    Video Codec    : {c['codec_video']}")
        L.append(f"    Audio Codec    : {c['codec_audio']}")
        L.append(f"    Bitrate        : {c['bitrate']} kbps")
        L.append(f"    File Size      : {c['size_str']}")
        L.append("")

    L.append(DIV)
    L.append("  Generated by video_splitter.py  |  Powered by FFmpeg")
    L.append(DIV)

    readme_path = os.path.join(output_dir, "README.txt")
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write("\n".join(L))

    return readme_path
