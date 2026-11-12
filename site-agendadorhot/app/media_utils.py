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
    Extrai duração (em segundos), largura, altura (considerando rotação),
    codec de vídeo, pixel format e presença/codec de áudio via ffmpeg.
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
    pix_fmt = ""
    for line in stderr.splitlines():
        if "Video:" in line:
            codec_match = re.search(r"Video:\s*([a-zA-Z0-9_]+)", line)
            if codec_match:
                vcodec = codec_match.group(1).lower()
            pix_match = re.search(r",\s*(yuv[a-zA-Z0-9]+)", line)
            if pix_match:
                pix_fmt = pix_match.group(1).lower()
            dim_match = re.search(r"(?:,\s*|\s)(\d{2,5})x(\d{2,5})(?:\s|,|\[|$)", line)
            if dim_match:
                width = int(dim_match.group(1))
                height = int(dim_match.group(2))
            break

    # Detecta metadado de rotação de vídeo de celular (-90 / 90 / 270)
    rot_match = re.search(r"rotation of\s*([-+]?\d+(?:\.\d+)?)\s*degrees|rotate\s*:\s*([-+]?\d+)", stderr, re.IGNORECASE)
    if rot_match:
        rot_str = rot_match.group(1) or rot_match.group(2)
        try:
            rot_val = int(round(abs(float(rot_str)))) % 360
            if rot_val in (90, 270):
                width, height = height, width
        except ValueError:
            pass

    has_audio = "Audio:" in stderr
    acodec = ""
    if has_audio:
        audio_match = re.search(r"Audio:\s*([a-zA-Z0-9_]+)", stderr)
        if audio_match:
            acodec = audio_match.group(1).lower()

    return {
        "duration": duration,
        "width": width,
        "height": height,
        "vcodec": vcodec,
        "pix_fmt": pix_fmt,
        "has_audio": has_audio,
        "acodec": acodec,
    }


def extract_video_thumbnail(video_path: Path) -> Optional[Path]:
    """
    Extrai uma miniatura JPEG pequena do vídeo para envio ao Telegram Story.
    """
    ffmpeg_exe = _get_ffmpeg_exe()
    thumb_path = video_path.with_name(f"{video_path.stem}_thumb.jpg")
    for seek in ("00:00:00.100", None):
        cmd = [ffmpeg_exe, "-y"]
        if seek:
            cmd += ["-ss", seek]
        cmd += [
            "-i", str(video_path),
            "-vframes", "1",
            "-vf", "scale=320:-2",
            "-q:v", "5",
            str(thumb_path),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        if res.returncode == 0 and thumb_path.exists() and thumb_path.stat().st_size > 0:
            return thumb_path

    if thumb_path.exists():
        thumb_path.unlink(missing_ok=True)
    return None


def prepare_story_video(
    video_path: Path,
    remove_audio: bool = False,
    force_reencode: bool = False,
    allow_reencode: bool = True,
) -> Path:
    """
    Prepara o vídeo para Stories do Telegram com baixíssimo consumo de memória (ideal para 512MB RAM):

    - Fast Path (-c:v copy): Se já for H.264 8-bit dentro de 1080x1920 e <= 60s (ou quando
      allow_reencode=False no upload HTTP), copia a trilha de vídeo sem recodificar (< 0.2s, ~12MB RAM),
      removendo/silenciando o áudio ou mantendo AAC.
    - Low-RAM Encode Path: Apenas quando force_reencode=True ou codec/dimensão incompatíveis
      (ex: .mov HEVC do iPhone, 4K, >60s), recodifica em 720x1280 H.264 com -threads 1 e zerolatency.
    """
    ffmpeg_exe = _get_ffmpeg_exe()
    meta = inspect_video_metadata(video_path)

    is_standard_h264 = (
        meta["vcodec"] == "h264"
        and (meta["pix_fmt"] == "" or ("yuv420p" in meta["pix_fmt"] and "10" not in meta["pix_fmt"]))
        and meta["width"] <= 1080
        and meta["height"] <= 1920
        and meta["width"] % 2 == 0
        and meta["height"] % 2 == 0
        and meta["duration"] <= 60
    )

    use_copy = (not force_reencode) and (is_standard_h264 or not allow_reencode)
    use_silent_audio = remove_audio or (not meta["has_audio"])

    # No upload rápido (allow_reencode=False), preserva .mov se não for H.264 para não quebrar mux
    target_suffix = ".mp4" if (is_standard_h264 or not use_copy) else video_path.suffix.lower()
    final_path = video_path.with_suffix(target_suffix)
    tmp_path = video_path.with_name(f"{video_path.stem}_tgstory{target_suffix}")

    # Fast return se já está 100% pronto e não precisa tirar áudio nem converter contêiner
    if (
        use_copy
        and not use_silent_audio
        and (not allow_reencode or (video_path.suffix.lower() == ".mp4" and meta["acodec"] == "aac"))
    ):
        return video_path

    try:
        if use_copy:
            # Cópia direta da faixa de vídeo (instantâneo e ~12MB RAM)
            if use_silent_audio:
                cmd = [
                    ffmpeg_exe,
                    "-y",
                    "-i", str(video_path),
                    "-f", "lavfi",
                    "-i", "anullsrc=channel_layout=mono:sample_rate=44100",
                    "-map", "0:v:0",
                    "-map", "1:a:0",
                    "-c:v", "copy",
                    "-c:a", "aac",
                    "-b:a", "32k",
                    "-shortest",
                    "-movflags", "+faststart",
                    str(tmp_path),
                ]
            else:
                audio_codec_args = ["-c:a", "copy"] if meta["acodec"] == "aac" else ["-c:a", "aac", "-b:a", "128k", "-ac", "2", "-ar", "44100"]
                cmd = [
                    ffmpeg_exe,
                    "-y",
                    "-i", str(video_path),
                    "-map", "0:v:0",
                    "-map", "0:a:0",
                    "-c:v", "copy",
                    *audio_codec_args,
                    "-movflags", "+faststart",
                    str(tmp_path),
                ]
        else:
            # Recodificação segura com consumo mínimo de memória para servidores 512MB RAM
            vf_filter = (
                "scale=720:1280:force_original_aspect_ratio=decrease,"
                "pad=720:1280:(ow-iw)/2:(oh-ih)/2:black,"
                "setsar=1"
            )
            encode_video_args = [
                "-vf", vf_filter,
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-tune", "zerolatency",
                "-crf", "24",
                "-x264-params", "rc-lookahead=5:ref=1:bframes=0",
                "-pix_fmt", "yuv420p",
                "-profile:v", "main",
                "-level", "4.0",
                "-r", "30",
                "-g", "30",
                "-t", "60",
                "-threads", "1",
            ]
            if use_silent_audio:
                cmd = [
                    ffmpeg_exe,
                    "-y",
                    "-i", str(video_path),
                    "-f", "lavfi",
                    "-i", "anullsrc=channel_layout=mono:sample_rate=44100",
                    "-map", "0:v:0",
                    "-map", "1:a:0",
                    *encode_video_args,
                    "-c:a", "aac",
                    "-b:a", "32k",
                    "-shortest",
                    "-movflags", "+faststart",
                    str(tmp_path),
                ]
            else:
                cmd = [
                    ffmpeg_exe,
                    "-y",
                    "-i", str(video_path),
                    "-map", "0:v:0",
                    "-map", "0:a:0",
                    *encode_video_args,
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


def prepare_story_photo(photo_path: Path) -> Path:
    """
    Normaliza fotos (PNG/RGBA/WEBP/HEIC/JPEG grande) para RGB JPEG <= 1080x1920,
    evitando erro MEDIA_FILE_INVALID no Telegram Stories (ex: PNGs >10MB ou com transparência).
    """
    try:
        from PIL import Image, ImageOps, UnidentifiedImageError
    except ImportError:
        return photo_path

    try:
        with Image.open(photo_path) as im:
            im = ImageOps.exif_transpose(im)
            needs_convert = (
                photo_path.suffix.lower() not in (".jpg", ".jpeg")
                or im.mode != "RGB"
                or im.width > 1080
                or im.height > 1920
                or photo_path.stat().st_size > 4 * 1024 * 1024
            )
            if not needs_convert:
                return photo_path

            if im.mode in ("RGBA", "LA", "P"):
                bg = Image.new("RGB", im.size, (0, 0, 0))
                alpha = im.convert("RGBA").split()[-1]
                bg.paste(im.convert("RGBA"), mask=alpha)
                im = bg
            elif im.mode != "RGB":
                im = im.convert("RGB")

            if im.width > 1080 or im.height > 1920:
                im.thumbnail((1080, 1920), Image.Resampling.LANCZOS)

            final_path = photo_path.with_suffix(".jpg")
            tmp_path = photo_path.with_name(f"{photo_path.stem}_tgphoto.jpg")
            im.save(tmp_path, format="JPEG", quality=90, optimize=True)
    except (UnidentifiedImageError, OSError):
        return photo_path

    os.replace(tmp_path, final_path)
    if photo_path != final_path and photo_path.exists():
        photo_path.unlink(missing_ok=True)
    return final_path
