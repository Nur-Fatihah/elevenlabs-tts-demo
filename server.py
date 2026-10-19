"""A tiny web service that sits between a customer's app and ElevenLabs.

Why a service at all? The customer's app (a website, a kiosk, a call-centre
system) calls this endpoint, and only this server holds the ElevenLabs API
key. That keeps the key off end-user devices and gives one place to validate
input, cache repeated prompts and log usage.

Run:  uvicorn server:app --reload
Try:  curl -X POST localhost:8000/tts -H 'content-type: application/json' \
        -d '{"text": "早上好，欢迎光临。", "language": "zh"}' --output hello_zh.mp3
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel

from tts_demo.core import (
    DEFAULT_MODEL_ID,
    SUPPORTED_LANGUAGES,
    GatewayError,
    SpeechRequest,
    check_language,
    default_voice_id,
    make_client,
    stream_speech,
    synthesize,
    validate_text,
)

app = FastAPI(title="Malaysia voice gateway")
_client = None


def client():
    global _client
    if _client is None:
        _client = make_client()
    return _client


class TTSBody(BaseModel):
    text: str
    language: str = "en"
    voice_id: str | None = None
    stream: bool = False


@app.get("/health")
def health():
    return {"status": "ok", "languages": SUPPORTED_LANGUAGES, "model": DEFAULT_MODEL_ID}


@app.post("/tts")
def tts(body: TTSBody):
    try:
        c = client()
        text = validate_text(body.text)
        check_language(c, body.language, DEFAULT_MODEL_ID)
        request = SpeechRequest(text=text, language=body.language, voice_id=body.voice_id or default_voice_id(c))
        if body.stream:
            return StreamingResponse(stream_speech(c, request), media_type="audio/mpeg")
        audio, cached = synthesize(c, request)
        return Response(audio, media_type="audio/mpeg", headers={"X-Cache": "HIT" if cached else "MISS"})
    except GatewayError as e:
        raise HTTPException(status_code=400, detail=str(e))
