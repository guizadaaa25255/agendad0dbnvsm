import io
import re
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from fastapi.testclient import TestClient

from app.main import app
from app.config import APP_TIMEZONE, UPLOAD_DIR
from app.media_utils import (
    _get_ffmpeg_exe,
    extract_video_thumbnail,
    inspect_video_metadata,
    prepare_story_video,
    strip_video_audio,
)

client = TestClient(app)


def _create_sample_video_with_audio(dest: Path, size: str = "640x480", duration: int = 2) -> None:
    """Gera um vídeo real curto com faixa de vídeo e som audível (tom 440Hz)."""
    ffmpeg_exe = _get_ffmpeg_exe()
    cmd = [
        ffmpeg_exe,
        "-y",
        "-f", "lavfi", "-i", f"color=c=blue:s={size}:d={duration}",
        "-f", "lavfi", "-i", f"sine=frequency=440:duration={duration}",
        "-c:v", "libx264", "-preset", "ultrafast",
        "-c:a", "aac",
        "-shortest",
        str(dest),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    assert res.returncode == 0, f"Erro ao gerar vídeo de teste: {res.stderr}"


def _get_max_audio_db(video_path: Path) -> float:
    """Usa o filtro volumedetect do ffmpeg para medir o volume máximo real do áudio."""
    ffmpeg_exe = _get_ffmpeg_exe()
    res = subprocess.run(
        [ffmpeg_exe, "-i", str(video_path), "-af", "volumedetect", "-f", "null", "-"],
        capture_output=True,
        text=True,
        timeout=20,
    )
    match = re.search(r"max_volume:\s*([-\d.]+)\s*dB", res.stderr or "")
    assert match is not None, f"volumedetect não encontrou áudio em {video_path}: {res.stderr}"
    return float(match.group(1))


def test_prepare_story_video_fast_path_and_strict_reencode(tmp_path):
    video_file = tmp_path / "sample.mov"
    _create_sample_video_with_audio(video_file, size="640x480", duration=2)
    assert _get_max_audio_db(video_file) > -30.0

    # 1. Fast Path: tira o áudio e remuxa .mov -> .mp4 sem gastar CPU/RAM re-encodando
    out_file = strip_video_audio(video_file)
    assert out_file.suffix == ".mp4"
    assert out_file.exists()

    meta = inspect_video_metadata(out_file)
    assert meta["width"] == 640
    assert meta["height"] == 480
    assert meta["vcodec"] == "h264"
    assert meta["has_audio"] is True
    assert 1.5 <= meta["duration"] <= 2.5
    assert _get_max_audio_db(out_file) <= -80.0

    # 2. Fallback Strict Re-encode (force_reencode=True): gera 720x1280 estrito para Stories
    strict_file = prepare_story_video(out_file, remove_audio=True, force_reencode=True)
    strict_meta = inspect_video_metadata(strict_file)
    assert strict_meta["width"] == 720
    assert strict_meta["height"] == 1280
    assert strict_meta["vcodec"] == "h264"
    assert _get_max_audio_db(strict_file) <= -80.0

    # Miniatura extraída corretamente
    thumb = extract_video_thumbnail(strict_file)
    assert thumb is not None and thumb.exists() and thumb.stat().st_size > 0
    thumb.unlink(missing_ok=True)


def test_create_video_story_remove_audio_true_and_false(account_id, tmp_path):
    src_video = tmp_path / "input.mp4"
    _create_sample_video_with_audio(src_video, size="480x854", duration=2)
    video_bytes = src_video.read_bytes()
    future_time = datetime.now(APP_TIMEZONE) + timedelta(minutes=15)

    # 1. Mantendo áudio (remove_audio=false) - fast path preserva dimensões válidas e mantém som audível
    res_keep = client.post(
        "/api/stories",
        data={
            "account_id": account_id,
            "scheduled_time": future_time.strftime("%Y-%m-%dT%H:%M"),
            "period": 172800,
            "pinned": True,
            "privacy": "all",
            "remove_audio": "false",
        },
        files={"file": ("clip_keep.mp4", io.BytesIO(video_bytes), "video/mp4")},
    )
    assert res_keep.status_code == 201
    data_keep = res_keep.json()
    kept_path = UPLOAD_DIR / Path(data_keep["media_url"]).name
    kept_meta = inspect_video_metadata(kept_path)
    assert kept_meta["width"] == 480 and kept_meta["height"] == 854
    assert _get_max_audio_db(kept_path) > -30.0
    assert "Áudio removido" not in data_keep["logs"][0]["message"]

    # 2. Removendo áudio (remove_audio=true) - fast path com -c:v copy deixa 100% mudo em <1s
    res_mute = client.post(
        "/api/stories",
        data={
            "account_id": account_id,
            "scheduled_time": future_time.strftime("%Y-%m-%dT%H:%M"),
            "period": 172800,
            "pinned": True,
            "privacy": "all",
            "remove_audio": "true",
        },
        files={"file": ("clip_mute.mp4", io.BytesIO(video_bytes), "video/mp4")},
    )
    assert res_mute.status_code == 201
    data_mute = res_mute.json()
    muted_path = UPLOAD_DIR / Path(data_mute["media_url"]).name
    muted_meta = inspect_video_metadata(muted_path)
    assert muted_meta["width"] == 480 and muted_meta["height"] == 854
    assert _get_max_audio_db(muted_path) <= -80.0
    assert "Áudio removido" in data_mute["logs"][0]["message"]

    # Limpeza
    client.delete(f"/api/stories/{data_keep['id']}")
    client.delete(f"/api/stories/{data_mute['id']}")
