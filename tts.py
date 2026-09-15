"""Narration audio via the ElevenLabs text-to-speech API.

Clips are cached on disk keyed by voice + model + text, so re-rendering a
video after a visual tweak doesn't spend characters again. Without an API
key it falls back to silent clips timed to an estimated reading speed, so
the whole pipeline (and the tests) run offline.
"""
import hashlib
import os
import subprocess
from pathlib import Path

import requests

API_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
DEFAULT_VOICE_ID = "JBFqnCBsd6RMkjVDRZzb"  # "George", one of ElevenLabs' premade voices
DEFAULT_MODEL_ID = "eleven_multilingual_v2"
WORDS_PER_SECOND = 2.6


def estimate_seconds(text: str) -> float:
    return max(1.5, len(text.split()) / WORDS_PER_SECOND)


def synthesize(text: str, cache_dir: Path, api_key: str | None = None,
               voice_id: str | None = None, model_id: str | None = None) -> Path:
    api_key = api_key if api_key is not None else os.environ.get("ELEVENLABS_API_KEY")
    voice_id = voice_id or os.environ.get("ELEVENLABS_VOICE_ID") or DEFAULT_VOICE_ID
    model_id = model_id or os.environ.get("ELEVENLABS_MODEL_ID") or DEFAULT_MODEL_ID
    cache_dir.mkdir(parents=True, exist_ok=True)

    if not api_key:
        digest = hashlib.sha256(f"silent|{text}".encode()).hexdigest()[:16]
        path = cache_dir / f"silent-{digest}.m4a"
        if not path.exists():
            subprocess.run(
                ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
                 "-i", "anullsrc=r=44100:cl=mono", "-t", f"{estimate_seconds(text):.2f}",
                 "-c:a", "aac", str(path)],
                check=True,
            )
        return path

    digest = hashlib.sha256(f"{voice_id}|{model_id}|{text}".encode()).hexdigest()[:16]
    path = cache_dir / f"el-{digest}.mp3"
    if path.exists():
        return path

    resp = requests.post(
        API_URL.format(voice_id=voice_id),
        params={"output_format": "mp3_44100_128"},
        headers={"xi-api-key": api_key, "accept": "audio/mpeg"},
        json={"text": text, "model_id": model_id},
        timeout=60,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"ElevenLabs TTS failed ({resp.status_code}): {resp.text[:300]}")
    path.write_bytes(resp.content)
    return path
