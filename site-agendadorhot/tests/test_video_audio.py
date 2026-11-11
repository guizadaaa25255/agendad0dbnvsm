import io
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from fastapi.testclient import TestClient

from app.main import app
from app.config import APP_TIMEZONE, UPLOAD_DIR
from app.media_utils import _get_ffmpeg_exe, strip_video_audio

client = TestClient(app)


def _create_sample_mp4_with_audio(dest: Path) -> None:
    """Gera um MP4 real curto (1s) com faixa de vídeo e faixa de áudio usando ffmpeg."""
    ffmpeg_exe = _get_ffmpeg_exe()
    cmd = [
        ffmpeg_exe,
        "-y",
        "-f", "lavfi", "-i", "color=c=blue:s=320x240:d=1",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
        "-c:v", "libx264", "-preset", "ultrafast",
        "-c:a", "aac",
        "-shortest",
        str(dest),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    assert res.returncode == 0, f"Erro ao gerar vídeo de teste: {res.stderr}"


def _has_audio_stream(video_path: Path) -> bool:
    """Inspeciona os streams via stderr do ffmpeg -i."""
    ffmpeg_exe = _get_ffmpeg_exe()
    res = subprocess.run([ffmpeg_exe, "-i", str(video_path)], capture_output=True, text=True, timeout=15)
    return "Audio:" in (res.stderr or "")


def test_strip_video_audio_removes_audio_stream(tmp_path):
    video_file = tmp_path / "sample.mp4"
    _create_sample_mp4_with_audio(video_file)
    assert _has_audio_stream(video_file) is True

    strip_video_audio(video_file)
    assert video_file.exists()
    assert video_file.stat().st_size > 0
    assert _has_audio_stream(video_file) is False


def test_create_video_story_remove_audio_true_and_false(account_id, tmp_path):
    src_video = tmp_path / "input.mp4"
    _create_sample_mp4_with_audio(src_video)
    video_bytes = src_video.read_bytes()
    future_time = datetime.now(APP_TIMEZONE) + timedelta(minutes=15)

    # 1. Mantendo áudio (remove_audio=false)
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
    kept_filename = Path(data_keep["media_url"]).name
    kept_path = UPLOAD_DIR / kept_filename
    assert _has_audio_stream(kept_path) is True
    assert "Áudio removido" not in data_keep["logs"][0]["message"]

    # 2. Removendo áudio (remove_audio=true)
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
    muted_filename = Path(data_mute["media_url"]).name
    muted_path = UPLOAD_DIR / muted_filename
    assert _has_audio_stream(muted_path) is False
    assert "Áudio removido" in data_mute["logs"][0]["message"]

    # Limpeza
    client.delete(f"/api/stories/{data_keep['id']}")
    client.delete(f"/api/stories/{data_mute['id']}")
