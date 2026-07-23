"""ffmpeg helpers for WAV→MP3 and concat merges."""

from __future__ import annotations

import asyncio
import shutil
import tempfile
from pathlib import Path


class FfmpegError(RuntimeError):
    """Raised when ffmpeg fails or is missing."""


def ffmpeg_path() -> str:
    """Resolve ffmpeg binary on PATH."""
    path = shutil.which("ffmpeg")
    if path is None:
        raise FfmpegError("ffmpeg not found on PATH")
    return path


async def wav_to_mp3(wav_bytes: bytes) -> bytes:
    """Convert WAV bytes to MP3 via ffmpeg."""
    return await _run_ffmpeg_convert(wav_bytes, ".wav", ["-codec:a", "libmp3lame", "-q:a", "4"])


async def concat_mp3(parts: list[bytes]) -> bytes:
    """Concatenate MP3 parts into one seekable MP3."""
    if not parts:
        raise FfmpegError("no audio parts to merge")
    if len(parts) == 1:
        return parts[0]
    return await _concat_many(parts)


async def _run_ffmpeg_convert(data: bytes, suffix: str, codec_args: list[str]) -> bytes:
    binary = ffmpeg_path()
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / f"in{suffix}"
        dst = Path(tmp) / "out.mp3"
        src.write_bytes(data)
        cmd = [binary, "-y", "-i", str(src), *codec_args, str(dst)]
        await _exec(cmd)
        return dst.read_bytes()


async def _concat_many(parts: list[bytes]) -> bytes:
    binary = ffmpeg_path()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        list_file = root / "list.txt"
        lines: list[str] = []
        for index, part in enumerate(parts):
            path = root / f"part-{index}.mp3"
            path.write_bytes(part)
            lines.append(f"file '{path.as_posix()}'")
        list_file.write_text("\n".join(lines), encoding="utf-8")
        out = root / "combined.mp3"
        cmd = [
            binary,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_file),
            "-codec:a",
            "libmp3lame",
            "-q:a",
            "4",
            str(out),
        ]
        await _exec(cmd)
        return out.read_bytes()


async def _exec(cmd: list[str]) -> None:
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        detail = stderr.decode("utf-8", errors="replace")[-500:]
        raise FfmpegError(f"ffmpeg failed: {detail}")
