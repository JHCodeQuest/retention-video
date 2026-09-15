"""Stitches frames and narration clips into a single MP4 with ffmpeg: one
still-image clip per segment (held for the clip's audio plus a short pause),
then a lossless concat."""
import subprocess
from pathlib import Path

PAUSE_SECONDS = 0.5


def audio_seconds(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        check=True, capture_output=True, text=True,
    )
    return float(out.stdout.strip())


def _segment_clip(frame: Path, audio: Path, dest: Path) -> None:
    duration = audio_seconds(audio) + PAUSE_SECONDS
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error",
         "-loop", "1", "-framerate", "30", "-i", str(frame),
         "-i", str(audio),
         "-af", f"apad=pad_dur={PAUSE_SECONDS}",
         "-t", f"{duration:.3f}",
         "-c:v", "libx264", "-tune", "stillimage", "-pix_fmt", "yuv420p", "-r", "30",
         "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-ac", "2",
         str(dest)],
        check=True,
    )


def assemble(frames: list[Path], audios: list[Path], dest: Path, work_dir: Path) -> Path:
    work_dir.mkdir(parents=True, exist_ok=True)
    clips = []
    for i, (frame, audio) in enumerate(zip(frames, audios, strict=True)):
        clip = work_dir / f"clip_{i:02d}.mp4"
        _segment_clip(frame, audio, clip)
        clips.append(clip)

    concat_list = work_dir / "concat.txt"
    concat_list.write_text("".join(f"file '{c.resolve().as_posix()}'\n" for c in clips), encoding="utf-8")

    dest.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
         "-i", str(concat_list), "-c", "copy", "-movflags", "+faststart", str(dest)],
        check=True,
    )
    return dest
