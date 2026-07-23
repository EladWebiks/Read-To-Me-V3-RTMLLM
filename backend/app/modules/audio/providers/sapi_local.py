"""Local Windows SAPI via PowerShell System.Speech."""

from __future__ import annotations

import asyncio
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

from app.core.ffmpeg import wav_to_mp3
from app.modules.audio.providers.base import VoiceInfo

DEFAULT_SAPI_VOICE = "Microsoft Zira Desktop"


class LocalSapiProvider:
    """True Windows desktop voices (Zira, etc.)."""

    @property
    def name(self) -> str:
        return "sapi"

    @staticmethod
    def is_available() -> bool:
        return sys.platform == "win32"

    async def list_voices(self) -> list[VoiceInfo]:
        if not self.is_available():
            return []
        names = await asyncio.to_thread(_list_voices_sync)
        return [
            VoiceInfo(provider=self.name, id=name, name=name, locale="en-US") for name in names
        ]

    async def synthesize(self, text: str, voice: str, rate: float) -> bytes:
        if not self.is_available():
            raise RuntimeError("Local SAPI requires Windows")
        wav = await asyncio.to_thread(_speak_wav_sync, text, voice, rate)
        return await wav_to_mp3(wav)


def _sapi_rate(rate: float) -> int:
    clamped = max(0.5, min(2.0, rate))
    return max(-10, min(10, round((clamped - 1.0) * 10)))


def _list_voices_sync() -> list[str]:
    script = (
        "Add-Type -AssemblyName System.Speech\n"
        "$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer\n"
        "foreach ($v in $synth.GetInstalledVoices()) "
        "{ Write-Output $v.VoiceInfo.Name }\n"
        "$synth.Dispose()\n"
    )
    return [line for line in _run_ps(script).splitlines() if line.strip()]


def _speak_wav_sync(text: str, voice: str, rate: float) -> bytes:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        txt = root / "in.txt"
        wav = root / "out.wav"
        txt.write_text(text, encoding="utf-8")
        safe_voice = voice.replace("'", "''")
        safe_txt = str(txt).replace("\\", "\\\\")
        safe_wav = str(wav).replace("\\", "\\\\")
        script = (
            "Add-Type -AssemblyName System.Speech\n"
            "$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer\n"
            f"$synth.SelectVoice('{safe_voice}')\n"
            f"$synth.Rate = {_sapi_rate(rate)}\n"
            f"$synth.SetOutputToWaveFile('{safe_wav}')\n"
            f"$text = [System.IO.File]::ReadAllText('{safe_txt}', "
            "[System.Text.Encoding]::UTF8)\n"
            "$synth.Speak($text)\n"
            "$synth.Dispose()\n"
        )
        _run_ps(script, timeout=300)
        return wav.read_bytes()


def _run_ps(script: str, timeout: int = 60) -> str:
    powershell = shutil.which("powershell") or shutil.which("pwsh")
    if powershell is None:
        raise RuntimeError("PowerShell not found")
    with tempfile.TemporaryDirectory() as tmp:
        ps_file = Path(tmp) / f"{uuid.uuid4()}.ps1"
        ps_file.write_text(script, encoding="utf-8")
        completed = subprocess.run(  # noqa: S603 — fixed argv, no shell
            [
                powershell,
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(ps_file),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr[-500:] or "PowerShell SAPI failed")
        return completed.stdout.strip()
