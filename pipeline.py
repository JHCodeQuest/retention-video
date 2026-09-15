"""Library entry point: narrate an already-built retention report PDF.

Used by main.py and by slack-file-bot's /client-report, which passes in the
analysis results it has just rendered so the video matches the PDF exactly.
"""
import tempfile
from pathlib import Path

from dotenv import load_dotenv

import frames
import report
import script
import tts
import video

ROOT = Path(__file__).resolve().parent
TTS_CACHE = ROOT / ".tts-cache"


def render_video(results, urgency: str, pdf_path: Path, dest: Path,
                 work_dir: Path | None = None, template: Path = script.TEMPLATE_PATH):
    """Returns (mp4_path, segments). Frames and per-segment clips go in
    `work_dir` (kept) or a temporary directory (discarded)."""
    load_dotenv(ROOT / ".env")  # ELEVENLABS_* - never overrides variables already set
    segments = script.build_script(results, urgency, report.format_gbp, template)

    with tempfile.TemporaryDirectory() as tmp:
        work = Path(work_dir) if work_dir else Path(tmp)
        frame_paths = frames.render_frames(Path(pdf_path), segments, work / "frames")
        audios = [tts.synthesize(seg.spoken, TTS_CACHE) for seg in segments]
        video.assemble(frame_paths, audios, Path(dest), work / "clips")

    return Path(dest), segments
