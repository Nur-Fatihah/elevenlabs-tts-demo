# Malaysia voice gateway

A small text-to-speech integration built on the [ElevenLabs Python SDK](https://github.com/elevenlabs/elevenlabs-python). It generates speech in the four main languages used in Malaysia (English, Malay, Mandarin and Tamil) through a command-line tool and a small web service.

It is shaped like a customer integration a Solutions Engineer might build: the customer's app calls one endpoint, and the gateway handles the ElevenLabs API key, input checks, language support and caching.

## How it works

```
customer app ──POST /tts──▶  gateway (server.py)  ──SDK──▶  ElevenLabs API
                               │
                               ├─ validate text (empty / too long)
                               ├─ check the model supports the language (models.list)
                               ├─ cache hit?  → return saved audio, no API call
                               └─ cache miss → text_to_speech.convert / .stream
```

| File | What it does |
|---|---|
| `tts_demo/core.py` | All ElevenLabs logic: client setup, language check, voice lookup, synthesis, cache |
| `cli.py` | Command-line tool: `models`, `voices`, `say` |
| `server.py` | FastAPI web service: `GET /health`, `POST /tts` (whole file or streamed) |
| `tests/test_core.py` | Tests with a fake client, so they run without an API key |

## Design choices

- **The API key stays on the server.** The customer's app never sees it, so it can't leak from a phone or browser.
- **Language support is checked against the live model list**, not a hard-coded table. If ElevenLabs changes a model's languages, the gateway gives a clear error instead of producing wrong-language audio.
- **Repeated prompts are cached.** Phone greetings and announcements repeat often, so the same text, voice, model and language are generated once and then served from disk (`X-Cache: HIT`).
- **Streaming is optional.** `"stream": true` returns audio chunks as they're generated, which cuts the wait before playback starts. That matters for live use, like a voice agent.
- **Errors are safe to show.** `GatewayError` messages contain no secrets or stack traces and come back as HTTP 400.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env          # then add your ElevenLabs API key
```

## Try it

```bash
.venv/bin/python cli.py models                   # which Malaysian languages the model supports
.venv/bin/python cli.py voices --lang ms         # voices for Malay
.venv/bin/python cli.py say "Selamat pagi, terima kasih kerana menelefon." --lang ms --out greeting_ms.mp3
.venv/bin/python cli.py say "早上好，欢迎光临。" --lang zh --out greeting_zh.mp3
.venv/bin/python cli.py say "Selamat pagi, terima kasih kerana menelefon." --lang ms --out again.mp3   # served from cache

.venv/bin/uvicorn server:app --reload
curl -X POST localhost:8000/tts -H 'content-type: application/json' \
  -d '{"text": "Good morning, thank you for calling.", "language": "en"}' --output hello_en.mp3

.venv/bin/python -m pytest -q
```

## What I would add next

- Per-customer API keys and usage logging, so each client's spend can be reported
- A pronunciation dictionary for local names and places (for example, "Johor Bahru", "Petaling Jaya")
- Code-switching tests (Manglish: English and Malay in one sentence)
