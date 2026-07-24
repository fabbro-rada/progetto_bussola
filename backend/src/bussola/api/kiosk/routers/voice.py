"""Person-facing voice endpoints (kiosk). Wraps the synchronous S7 services in a
timeout so slow/unavailable voice degrades to a clear HTTP signal (503 = write
instead; 204 = read instead) — this realizes the "voce lenta -> testo" half of
§3 that S7 delegated to the API layer."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, Form, HTTPException, Response, UploadFile, status
from pydantic import BaseModel

from bussola.api.kiosk import config
from bussola.api.kiosk.deps import require_kiosk
from bussola.voice.errors import VoiceUnavailable
from bussola.voice.stt import SpeechToText
from bussola.voice.tts import TextToSpeech

router = APIRouter(prefix="/kiosk/voice", tags=["kiosk"], dependencies=[Depends(require_kiosk)])

_stt_singleton: SpeechToText | None = None
_tts_singleton: TextToSpeech | None = None


def _stt() -> SpeechToText:
    global _stt_singleton
    if _stt_singleton is None:
        _stt_singleton = SpeechToText()
    return _stt_singleton


def _tts() -> TextToSpeech:
    global _tts_singleton
    if _tts_singleton is None:
        _tts_singleton = TextToSpeech()
    return _tts_singleton


class TranscribeResponse(BaseModel):
    text: str


class SynthesizeRequest(BaseModel):
    text: str
    language: str


@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe(audio: UploadFile, language: str = Form(...)) -> TranscribeResponse:
    data = await audio.read()
    try:
        text = await asyncio.wait_for(
            asyncio.to_thread(lambda: _stt().transcribe(data, language).text),
            timeout=config.VOICE_TIMEOUT,
        )
    except (VoiceUnavailable, asyncio.TimeoutError):
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "voice unavailable, use text")
    return TranscribeResponse(text=text)


@router.post("/synthesize")
async def synthesize(body: SynthesizeRequest) -> Response:
    try:
        audio = await asyncio.wait_for(
            asyncio.to_thread(lambda: _tts().synthesize(body.text, body.language)),
            timeout=config.VOICE_TIMEOUT,
        )
    except (VoiceUnavailable, asyncio.TimeoutError):
        audio = None
    if audio is None:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    return Response(content=audio, media_type="audio/wav")
