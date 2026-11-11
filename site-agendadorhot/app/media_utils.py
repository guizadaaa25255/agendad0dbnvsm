import os
import shutil
import subprocess
from pathlib import Path


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
            "FFmpeg não encontrado no servidor para remover áudio do vídeo."
        ) from exc


def strip_video_audio(video_path: Path) -> None:
    """
    Remove a faixa de áudio de um arquivo de vídeo no local, preservando a imagem original.
    Usa stream copy (-c:v copy) primeiro para ser instantâneo e, se necessário, recodifica para H.264.
    """
    ffmpeg_exe = _get_ffmpeg_exe()
    tmp_path = video_path.with_name(f"{video_path.stem}_noaudio{video_path.suffix}")

    try:
        # 1. Tentativa rápida sem perda de qualidade (cópia direta da faixa de vídeo)
        cmd_copy = [
            ffmpeg_exe,
            "-y",
            "-i", str(video_path),
            "-c:v", "copy",
            "-an",
            "-movflags", "+faststart",
            str(tmp_path),
        ]
        res = subprocess.run(cmd_copy, capture_output=True, text=True, timeout=120)

        if res.returncode != 0 or not tmp_path.exists() or tmp_path.stat().st_size == 0:
            # 2. Fallback recodificando para H.264 caso o contêiner exija
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)
            cmd_encode = [
                ffmpeg_exe,
                "-y",
                "-i", str(video_path),
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-an",
                "-movflags", "+faststart",
                str(tmp_path),
            ]
            res = subprocess.run(cmd_encode, capture_output=True, text=True, timeout=180)

        if res.returncode != 0 or not tmp_path.exists() or tmp_path.stat().st_size == 0:
            err_detail = (res.stderr or "").strip()[-300:]
            raise RuntimeError(f"Falha ao remover áudio do vídeo: {err_detail}")

        os.replace(tmp_path, video_path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
