#!/usr/bin/env python3
"""
Video Splitter dengan deteksi codec AV1 + auto generate README.txt
Memotong video panjang menjadi bagian-bagian kecil
Requirement: ffmpeg & ffprobe harus sudah terinstall
"""

import subprocess
import os
import sys
import json
import math
from datetime import datetime


def check_ffmpeg():
    for tool in ["ffmpeg", "ffprobe"]:
        try:
            subprocess.run([tool, "-version"], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            print(f"❌ ERROR: '{tool}' tidak ditemukan!")
            print("   Install ffmpeg: https://ffmpeg.org/download.html")
            sys.exit(1)


def get_video_info(filepath):
    cmd = [
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_streams", "-show_format",
        filepath
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"❌ Gagal membaca file: {filepath}")
        sys.exit(1)
    return json.loads(result.stdout)


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

    # ── Header ────────────────────────────────────────────────────
    L.append(DIV)
    L.append("  VIDEO SPLITTER — README")
    L.append(f"  Dibuat   : {now}")
    L.append(f"  Output   : {os.path.abspath(output_dir)}")
    L.append(DIV)
    L.append("")

    # ── Source Video ──────────────────────────────────────────────
    L.append("[ SOURCE VIDEO ]")
    L.append(DIV2)
    L.append(f"  File             : {os.path.basename(source_path)}")
    L.append(f"  Path             : {source_path}")
    L.append(f"  Ukuran File      : {format_size(src_size)}")
    L.append(f"  Durasi Total     : {duration_label(duration)}  ({seconds_to_hhmmss(duration)})")
    L.append(f"  Resolusi         : {src_w} x {src_h}")
    L.append(f"  Frame Rate       : {src_fps} fps")
    L.append(f"  Pixel Format     : {src_pix}")
    L.append(f"  Codec Video      : {src_codec.upper()}")
    L.append(f"  Codec Audio      : {src_audio.upper()}")
    L.append(f"  Sample Rate      : {src_sr} Hz")
    L.append(f"  Audio Channel    : {src_ch} ch  ({src_chlay})")
    L.append(f"  Bitrate Total    : {src_br} kbps")
    L.append("")

    # ── Pengaturan Split ──────────────────────────────────────────
    L.append("[ PENGATURAN SPLIT ]")
    L.append(DIV2)
    L.append(f"  Durasi per clip      : {segment_minutes} menit")
    L.append(f"  Jumlah clip          : {len(clip_entries)} file")
    L.append(f"  Konversi             : {'AV1 → H.264 (re-encode)' if convert_to_h264 else 'Tidak (stream copy, lebih cepat)'}")
    L.append(f"  Output Codec Video   : {out_vcodec}")
    L.append(f"  Output Codec Audio   : {out_acodec}")
    if convert_to_h264:
        L.append(f"  CRF (kualitas)       : 23  (skala 0–51, nilai kecil = kualitas lebih baik)")
        L.append(f"  Preset Encode        : medium")
    L.append("")

    # ── Tabel Ringkasan ───────────────────────────────────────────
    L.append("[ RINGKASAN CLIP ]")
    L.append(DIV2)

    W = [4, 36, 14, 13, 9, 9]
    hdr = (
        f"  {'No':<{W[0]}} "
        f"{'Nama File':<{W[1]}} "
        f"{'Durasi':<{W[2]}} "
        f"{'Resolusi':<{W[3]}} "
        f"{'FPS':<{W[4]}} "
        f"{'Ukuran':<{W[5]}}"
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

    # ── Detail per Clip ───────────────────────────────────────────
    L.append("[ DETAIL LENGKAP PER CLIP ]")
    L.append(DIV2)

    for i, c in enumerate(clip_entries, 1):
        L.append(f"  Clip #{i:02d}  ──  {c['start_label']} → {c['end_label']}")
        L.append(f"    Nama File      : {c['filename']}")
        L.append(f"    Timestamp      : {c['start_label']} → {c['end_label']}")
        L.append(f"    Durasi         : {duration_label(c['duration_sec'])}  ({seconds_to_hhmmss(c['duration_sec'])})")
        if c["width"]:
            L.append(f"    Resolusi       : {c['width']} x {c['height']}")
        L.append(f"    Frame Rate     : {c['fps']} fps")
        L.append(f"    Codec Video    : {c['codec_video']}")
        L.append(f"    Codec Audio    : {c['codec_audio']}")
        L.append(f"    Bitrate        : {c['bitrate']} kbps")
        L.append(f"    Ukuran File    : {c['size_str']}")
        L.append("")

    L.append(DIV)
    L.append("  Generated by video_splitter.py  |  Powered by FFmpeg")
    L.append(DIV)

    readme_path = os.path.join(output_dir, "README.txt")
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write("\n".join(L))

    return readme_path


def split_video(input_path, segment_duration_minutes, convert_to_h264, output_dir):
    segment_seconds = segment_duration_minutes * 60

    print(f"\n📂 Membaca file: {input_path}")
    info     = get_video_info(input_path)
    codec    = detect_codec(info)
    duration = get_duration(info)

    if duration == 0:
        print("❌ Tidak bisa membaca durasi video.")
        sys.exit(1)

    vs           = get_video_stream(info)
    num_segments = math.ceil(duration / segment_seconds)

    print(f"🎬 Codec    : {codec.upper()}")
    print(f"📐 Resolusi : {vs.get('width','?')}x{vs.get('height','?')} @ {get_framerate(vs)} fps")
    print(f"⏱️  Durasi   : {seconds_to_hhmmss(duration)} ({duration/60:.1f} menit)")
    print(f"✂️  Segmen   : {num_segments} bagian @ {segment_duration_minutes} menit")
    print(f"📁 Output   : {output_dir}")
    if convert_to_h264:
        print("🔄 Konversi : AV1 → H.264")
    print()

    os.makedirs(output_dir, exist_ok=True)

    base_name    = os.path.splitext(os.path.basename(input_path))[0]
    clip_entries = []

    for i in range(num_segments):
        start_sec    = i * segment_seconds
        end_sec      = min(start_sec + segment_seconds, duration)
        seg_duration = end_sec - start_sec
        start_label  = seconds_to_hm(start_sec)
        end_label    = seconds_to_hm(end_sec)
        out_filename = f"{base_name}_{sanitize_filename(start_label)} - {sanitize_filename(end_label)}.mp4"
        out_path     = os.path.join(output_dir, out_filename)

        print(f"[{i+1}/{num_segments}] ✂️  {start_label} → {end_label}  |  {out_filename}")

        cmd = [
            "ffmpeg", "-y",
            "-ss", seconds_to_hhmmss(start_sec),
            "-i", input_path,
            "-t", str(seg_duration),
        ]
        if convert_to_h264:
            cmd += ["-c:v", "h264_nvenc", "-preset", "p5", "-cq", "23","-c:a", "aac", "-b:a", "192k"]
        else:
            cmd += ["-c:v", "copy", "-c:a", "copy"]
        cmd.append(out_path)

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            size_bytes = os.path.getsize(out_path)
            size_str   = format_size(size_bytes)
            print(f"         ✅ Selesai ({size_str})")

            ci  = get_video_info(out_path)
            cvs = get_video_stream(ci)
            cas = get_audio_stream(ci)
            clip_entries.append({
                "filename"    : out_filename,
                "start_label" : start_label,
                "end_label"   : end_label,
                "duration_sec": seg_duration,
                "width"       : cvs.get("width"),
                "height"      : cvs.get("height"),
                "fps"         : get_framerate(cvs),
                "codec_video" : cvs.get("codec_name", "?").upper(),
                "codec_audio" : cas.get("codec_name", "?").upper(),
                "bitrate"     : get_bitrate(ci),
                "size_bytes"  : size_bytes,
                "size_str"    : size_str,
            })
        else:
            print(f"         ❌ GAGAL!")
            print(result.stderr[-500:])

    # ── Generate README.txt ────────────────────────────────────────
    if clip_entries:
        print(f"\n📝 Membuat README.txt ...")
        readme_path = generate_readme(
            output_dir, input_path, info,
            clip_entries, segment_duration_minutes, convert_to_h264
        )
        print(f"   ✅ README.txt: {readme_path}")

    print(f"\n🎉 Semua selesai! File tersimpan di: {os.path.abspath(output_dir)}")


def main():
    print("=" * 55)
    print("       🎬  VIDEO SPLITTER  |  Python + FFmpeg")
    print("=" * 55)

    check_ffmpeg()

    # ── Input file ────────────────────────────────────────────────
    while True:
        input_path = input("\n📂 Masukkan path file video: ").strip().strip('"').strip("'")
        if os.path.isfile(input_path):
            break
        print(f"   ❌ File tidak ditemukan: {input_path}")

    print("\n⏳ Membaca info video...")
    info     = get_video_info(input_path)
    codec    = detect_codec(info)
    duration = get_duration(info)
    vs       = get_video_stream(info)

    print(f"   Codec    : {codec.upper()}")
    print(f"   Resolusi : {vs.get('width','?')}x{vs.get('height','?')} @ {get_framerate(vs)} fps")
    print(f"   Durasi   : {seconds_to_hhmmss(duration)}  ({duration/60:.1f} menit)")

    # ── Durasi per segmen ─────────────────────────────────────────
    while True:
        try:
            menit = float(input("\n✂️  Potong setiap berapa menit? (contoh: 10): ").strip())
            if menit <= 0:
                print("   ❌ Harus lebih dari 0."); continue
            if menit * 60 >= duration:
                print(f"   ⚠️  Durasi segmen lebih panjang dari video. Coba nilai lebih kecil."); continue
            break
        except ValueError:
            print("   ❌ Masukkan angka yang valid.")

    # ── Deteksi AV1 ───────────────────────────────────────────────
    convert_to_h264 = False
    if codec == "av1":
        print("\n⚠️  DETEKSI: Video menggunakan encoding AV1.")
        print("   AV1 kurang kompatibel dengan banyak device & player.")
        jawab = input("   Mau sekalian dikonversi ke H.264? (y/n): ").strip().lower()
        if jawab in ("y", "ya", "yes"):
            convert_to_h264 = True
            print("   ✅ Video akan dikonversi ke H.264.")
        else:
            print("   ➡️  Video dipotong tanpa konversi (tetap AV1).")

    # ── Output directory ──────────────────────────────────────────
    default_dir = os.path.join(os.path.dirname(os.path.abspath(input_path)), "output_split")
    print(f"\n📁 Folder output default: {default_dir}")
    custom = input("   Enter = pakai default, atau ketik path lain: ").strip().strip('"').strip("'")
    output_dir = custom if custom else default_dir

    # ── Konfirmasi ────────────────────────────────────────────────
    num_seg = math.ceil(duration / (menit * 60))
    print(f"\n{'='*55}")
    print(f"  File        : {os.path.basename(input_path)}")
    print(f"  Durasi      : {seconds_to_hhmmss(duration)}")
    print(f"  Per segmen  : {menit} menit  →  {num_seg} file")
    print(f"  Konversi    : {'AV1 → H.264' if convert_to_h264 else 'Tidak (stream copy)'}")
    print(f"  Output      : {output_dir}")
    print(f"  README.txt  : Otomatis dibuat di folder output ✅")
    print(f"{'='*55}")

    ok = input("\n▶️  Mulai proses? (y/n): ").strip().lower()
    if ok not in ("y", "ya", "yes"):
        print("❌ Dibatalkan.")
        sys.exit(0)

    split_video(input_path, menit, convert_to_h264, output_dir)


if __name__ == "__main__":
    main()