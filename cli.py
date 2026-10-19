"""Command-line entry point.

Examples:
    python cli.py models
    python cli.py voices --lang ms
    python cli.py say "Selamat pagi, terima kasih kerana menelefon." --lang ms --out greeting_ms.mp3
"""

import argparse
import sys
import time

from tts_demo.core import (
    DEFAULT_MODEL_ID,
    SUPPORTED_LANGUAGES,
    GatewayError,
    SpeechRequest,
    check_language,
    default_voice_id,
    list_voices,
    make_client,
    model_languages,
    synthesize,
    validate_text,
)


def cmd_models(client, args):
    for lang, name in SUPPORTED_LANGUAGES.items():
        ok = lang in model_languages(client, args.model)
        print(f"{'✓' if ok else '✗'} {lang} ({name}) on {args.model}")


def cmd_voices(client, args):
    for v in list_voices(client, language=args.lang, limit=args.limit):
        print(f"{v['voice_id']}  {v['name']}  [{v['category']}]")


def cmd_say(client, args):
    text = validate_text(args.text)
    check_language(client, args.lang, args.model)
    request = SpeechRequest(text=text, language=args.lang, voice_id=args.voice or default_voice_id(client), model_id=args.model)
    started = time.perf_counter()
    audio, cached = synthesize(client, request, use_cache=not args.no_cache)
    elapsed = time.perf_counter() - started
    with open(args.out, "wb") as f:
        f.write(audio)
    source = "cache" if cached else "ElevenLabs"
    print(f"Wrote {args.out} ({len(audio):,} bytes) from {source} in {elapsed:.2f}s")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Malaysia voice gateway (ElevenLabs TTS demo)")
    parser.add_argument("--model", default=DEFAULT_MODEL_ID)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("models", help="Check which Malaysian languages the model supports")

    p_voices = sub.add_parser("voices", help="List voices")
    p_voices.add_argument("--lang", choices=SUPPORTED_LANGUAGES)
    p_voices.add_argument("--limit", type=int, default=10)

    p_say = sub.add_parser("say", help="Generate speech to an MP3 file")
    p_say.add_argument("text")
    p_say.add_argument("--lang", choices=SUPPORTED_LANGUAGES, default="en")
    p_say.add_argument("--voice", help="Voice ID (defaults to VOICE_ID in .env or the first voice)")
    p_say.add_argument("--out", default="output.mp3")
    p_say.add_argument("--no-cache", action="store_true")

    args = parser.parse_args(argv)
    try:
        client = make_client()
        {"models": cmd_models, "voices": cmd_voices, "say": cmd_say}[args.command](client, args)
    except GatewayError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
