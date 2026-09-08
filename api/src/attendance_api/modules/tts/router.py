"""Server-side TTS (edge-tts) fallback: guarantees audible rollcall on any browser
(e.g. desktop Chrome in mainland China cannot fetch Google network voices and is silent)."""

from __future__ import annotations

import asyncio
import hashlib
import re
from pathlib import Path
from typing import Annotated

import edge_tts
from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse

from attendance_api.errors import ApiError
from attendance_api.models import User
from attendance_api.modules.auth.dependencies import require_password_changed, require_teacher

router = APIRouter(prefix="/api/v1/tts", tags=["tts"])

VOICES: dict[str, str] = {
    "xiaoxiao": "zh-CN-XiaoxiaoNeural",  # 晓晓 · 女声 · 温暖
    "yunxi": "zh-CN-YunxiNeural",  # 云希 · 男声 · 阳光
    "xiaoyi": "zh-CN-XiaoyiNeural",  # 晓伊 · 女声 · 活泼
}
DEFAULT_VOICE_KEY = "xiaoxiao"
_TEXT_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
CACHE_DIR = Path("/tmp/attendance-tts")
CACHE_TTL_SECONDS = 60 * 60 * 24 * 30  # 30 天（按姓名+语速+音色 hash，点名轮询基本全命中）
_cache: dict[str, bytes] = {}


def _rate_str(rate: float) -> str:
    percent = int(round((rate - 1.0) * 100))
    return f"{percent:+d}%"


def _voice(name: str) -> str:
    if name not in VOICES:
        raise ApiError(400, "INVALID_REQUEST", "不支持的音色，可选：xiaoxiao / yunxi / xiaoyi")
    return VOICES[name]


@router.get("/speak", operation_id="speakText")
async def speak(
    teacher: Annotated[User, Depends(require_teacher)],
    password_changed: Annotated[User, Depends(require_password_changed)],
    text: Annotated[str, Query(min_length=1, max_length=40)],
    rate: Annotated[float, Query(ge=0.5, le=2)] = 1.0,
    voice: Annotated[str, Query()] = DEFAULT_VOICE_KEY,
) -> FileResponse:
    cleaned = _TEXT_RE.sub("", text).strip()
    if not cleaned:
        raise ApiError(400, "INVALID_REQUEST", "播报文本为空")
    edge_voice = _voice(voice)
    key = hashlib.sha1(f"{edge_voice}|{_rate_str(rate)}|{cleaned}".encode()).hexdigest()
    cache_path = CACHE_DIR / f"{key}.mp3"

    if cache_path.is_file():
        return _audio_response(cache_path)

    cached = _cache.get(key)
    if cached is not None:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_path.write_bytes(cached)
        return _audio_response(cache_path)

    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        communicate = edge_tts.Communicate(cleaned, edge_voice, rate=_rate_str(rate))
        await asyncio.wait_for(communicate.save(str(cache_path)), timeout=25)
        data = cache_path.read_bytes()
        _cache[key] = data
        return _audio_response(cache_path)
    except asyncio.TimeoutError as exc:
        raise ApiError(502, "TTS_UNAVAILABLE", "语音合成超时，请稍后重试") from exc
    except Exception as exc:  # 网络/上游异常
        raise ApiError(502, "TTS_UNAVAILABLE", "语音合成服务暂不可用，请稍后重试") from exc


def _audio_response(path: Path) -> FileResponse:
    return FileResponse(
        path,
        media_type="audio/mpeg",
        headers={
            "Cache-Control": "public, max-age=86400",
            "X-Content-Type-Options": "nosniff",
        },
    )
