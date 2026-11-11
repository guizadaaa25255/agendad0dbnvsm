import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Optional


def _get_ffmpeg_exe() -> str:
    """Localiza o executável do ffmpeg no sistema ou via imageio-ffmpeg."""
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg

    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:
        raise RuntimeError(
            "FFmpeg não encontrado no servidor para processar o vídeo."
        ) from exc


def inspect_video_metadata(video_path: Path) -> dict:
    """
    Extrai duração (em segundos), largura, altura, codec e presença de áudio via ffmpeg.
    """
    ffmpeg_exe = _get_ffmpeg_exe()
    res = subprocess.run(
        [ffmpeg_exe, "-i", str(video_path)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=20,
    )
    stderr = res.stderr or ""

    duration = 15.0
    dur_match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", stderr)
    if dur_match:
        h, m, s = int(dur_match.group(1)), int(dur_match.group(2)), float(dur_match.group(3))
        duration = max(1.0, round(h * 3600 + m * 60 + s, 2))

    width, height = 720, 1280
    vcodec = ""
    for line in stderr.splitlines():
        if "Video:" in line:
            codec_match = re.search(r"Video:\s*([a-zA-Z0-9_]+)", line)
            if codec_match:
                vcodec = codec_match.group(1).lower()
            dim_match = re.search(r"(?:,\s*|\s)(\d{2,5})x(\d{2,5})(?:\s|,|\[|$)", line)
            if dim_match:
                width = int(dim_match.group(1))
                height = int(dim_match.group(2))
            break

    has_audio = "Audio:" in stderr

    return {
        "duration": duration,
        "width": width,
        "height": height,
        "vcodec": vcodec,
        "has_audio": has_audio,
    }


def extract_video_thumbnail(video_path: Path) -> Optional[Path]:
    """
    Extrai uma miniatura JPEG pequena do vídeo para envio ao Telegram Story.
    """
    ffmpeg_exe = _get_ffmpeg_exe()
    thumb_path = video_path.with_name(f"{video_path.stem}_thumb.jpg")
    cmd = [
        ffmpeg_exe,
        "-y",
        "-i", str(video_path),
        "-ss", "00:00:00.100",
        "-vframes", "1",
        "-vf", "scale=320:-2",
        "-q:v", "5",
        str(thumb_path),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
    if res.returncode == 0 and thumb_path.exists() and thumb_path.stat().st_size > 0:
        return thumb_path

    # Fallback para o frame 0 caso o vídeo seja muito curto (<0.1s)
    cmd_fallback = [
        ffmpeg_exe,
        "-y",
        "-i", str(video_path),
        "-vframes", "1",
        "-vf", "scale=320:-2",
        "-q:v", "5",
        str(thumb_path),
    ]
    res2 = subprocess.run(cmd_fallback, capture_output=True, text=True, timeout=20)
    if res2.returncode == 0 and thumb_path.exists() and thumb_path.stat().st_size > 0:
        return thumb_path

    if thumb_path.exists():
        thumb_path.unlink(missing_ok=True)
    return None


def prepare_story_video(video_path: Path, remove_audio: bool = False) -> Path:
    """
    Normaliza qualquer vídeo (.mp4, .mov, HEVC, etc.) para o padrão oficial exigido
    pelos Stories do Telegram (MP4, H.264 yuv420p, 720x1280, até 30fps, até 60s, faststart).

    Se remove_audio=True (ou se o vídeo não tiver áudio), injeta uma faixa AAC 100% silenciosa
    para garantir som totalmente mudo sem acionar MEDIA_FILE_INVALID na API do Telegram.
    """
    ffmpeg_exe = _get_ffmpeg_exe()
    meta = inspect_video_metadata(video_path)

    final_path = video_path.with_suffix(".mp4")
    tmp_path = video_path.with_name(f"{video_path.stem}_tgstory.mp4")

    vf_filter = (
        "scale=720:1280:force_original_aspect_ratio=decrease,"
        "pad=720:1280:(ow-iw)/2:(oh-ih)/2:black,"
        "setsar=1"
    )

    use_silent_audio = remove_audio or (not meta["has_audio"])

    try:
        if use_silent_audio:
            # Descarta o áudio original e adiciona uma trilha AAC digitalmente muda (0 dB silêncio absoluto)
            cmd = [
                ffmpeg_exe,
                "-y",
                "-i", str(video_path),
                "-f", "lavfi",
                "-i", "anullsrc=channel_layout=mono:sample_rate=44100",
                "-map", "0:v:0",
                "-map", "1:a:0",
                "-vf", vf_filter,
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-crf", "23",
                "-pix_fmt", "yuv420p",
                "-profile:v", "main",
                "-level", "4.0",
                "-r", "30",
                "-t", "60",
                "-threads", "2",
                "-c:a", "aac",
                "-b:a", "32k",
                "-shortest",
                "-movflags", "+faststart",
                str(tmp_path),
            ]
        else:
            # Mantém o áudio original recodificado para AAC padrão do Telegram
            cmd = [
                ffmpeg_exe,
                "-y",
                "-i", str(video_path),
                "-map", "0:v:0",
                "-map", "0:a:0",
                "-vf", vf_filter,
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-crf", "23",
                "-pix_fmt", "yuv420p",
                "-profile:v", "main",
                "-level", "4.0",
                "-r", "30",
                "-t", "60",
                "-threads", "2",
                "-c:a", "aac",
                "-b:a", "128k",
                "-ac", "2",
                "-ar", "44100",
                "-movflags", "+faststart",
                str(tmp_path),
            ]

        res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
        if res.returncode != 0 or not tmp_path.exists() or tmp_path.stat().st_size == 0:
            err_detail = (res.stderr or "").strip()[-400:]
            raise RuntimeError(f"Falha ao preparar vídeo para Story do Telegram: {err_detail}")

        os.replace(tmp_path, final_path)
        if video_path != final_path and video_path.exists():
            video_path.unlink(missing_ok=True)

        return final_path
    finally:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


def strip_video_audio(video_path: Path) -> Path:
    """Remove a faixa de áudio do vídeo mantendo compatibilidade total com Stories do Telegram."""
    return prepare_story_video(video_path, remove_audio=True)
