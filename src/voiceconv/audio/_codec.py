"""ffmpeg-backed audio decode and encode.

FfmpegLoader  — implements the PcmLoader protocol; decodes any ffmpeg-supported
               format to float32 mono PCM via a pipe.
FfmpegEncoder — encodes float32 mono PCM to WAV or FLAC via a pipe; output
               format is inferred from the file extension.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Optional

import numpy as np

from voiceconv.audio._provenance import ffmpeg_metadata_args
from voiceconv.platform_support.ffmpeg import get_ffmpeg_path


class FfmpegLoader:
    """Decode any ffmpeg-supported audio file to float32 mono PCM.

    Implements the ``PcmLoader`` protocol (``load(path) -> (pcm, sample_rate)``).

    Parameters
    ----------
    ffmpeg_path:
        Absolute path to the ffmpeg binary. ``None`` → resolved via
        ``get_ffmpeg_path()`` (env var then PATH).
    target_sample_rate:
        If given, ffmpeg resamples during decode and the returned sample rate
        equals this value. ``None`` → native rate is returned.
    """

    def __init__(
        self,
        ffmpeg_path: Optional[str] = None,
        target_sample_rate: Optional[int] = None,
    ) -> None:
        self._ffmpeg = ffmpeg_path or get_ffmpeg_path()
        self._target_sr = target_sample_rate

    def load(self, path: str) -> tuple[np.ndarray, int]:
        """Decode *path* → ``(float32 mono PCM, sample_rate_hz)``."""
        cmd = [self._ffmpeg, "-v", "error", "-i", path, "-f", "f32le", "-ac", "1"]
        if self._target_sr is not None:
            cmd += ["-ar", str(self._target_sr)]
        cmd.append("pipe:1")

        result = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True
        )
        pcm = np.frombuffer(result.stdout, dtype=np.float32).copy()

        if self._target_sr is not None:
            sr = self._target_sr
        else:
            sr = _probe_sample_rate(self._ffmpeg, path)

        return pcm, sr


class FfmpegEncoder:
    """Encode float32 mono PCM to a WAV or FLAC file via ffmpeg.

    The output format is inferred from the file extension.

    Parameters
    ----------
    ffmpeg_path:
        Absolute path to the ffmpeg binary. ``None`` → resolved via
        ``get_ffmpeg_path()``.
    """

    def __init__(self, ffmpeg_path: Optional[str] = None) -> None:
        self._ffmpeg = ffmpeg_path or get_ffmpeg_path()

    def encode(self, pcm: np.ndarray, sample_rate: int, path: str) -> None:
        """Write float32 mono *pcm* to *path* via ffmpeg."""
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        raw = np.clip(pcm, -1.0, 1.0).astype(np.float32).tobytes()
        cmd = [
            self._ffmpeg, "-v", "error", "-y",
            "-f", "f32le", "-ar", str(sample_rate), "-ac", "1",
            "-i", "pipe:0",
            # Output provenance: mark the file as AI voice-converted (M2).
            *ffmpeg_metadata_args(),
            path,
        ]
        subprocess.run(
            cmd, input=raw, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True
        )


def _probe_sample_rate(ffmpeg_path: str, path: str) -> int:
    """Return the native sample rate of *path* using ffprobe (or ffmpeg -i fallback)."""
    # ffprobe ships alongside ffmpeg in all standard distributions
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        # Try replacing the binary name in the same directory
        candidate = Path(ffmpeg_path).parent / "ffprobe"
        if candidate.is_file():
            ffprobe = str(candidate)
        candidate_exe = Path(ffmpeg_path).parent / "ffprobe.exe"
        if candidate_exe.is_file():
            ffprobe = str(candidate_exe)

    if ffprobe:
        result = subprocess.run(
            [
                ffprobe, "-v", "error",
                "-select_streams", "a:0",
                "-show_entries", "stream=sample_rate",
                "-of", "default=noprint_wrappers=1:nokey=1",
                path,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        text = result.stdout.decode().strip()
        if text.isdigit():
            return int(text)

    # Fallback: run `ffmpeg -i <path>` (exits non-zero; info is in stderr)
    result = subprocess.run(
        [ffmpeg_path, "-i", path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stderr = result.stderr.decode(errors="replace")
    # Look for the pattern "NNN Hz" in the audio stream line
    for segment in stderr.split(","):
        segment = segment.strip()
        if segment.endswith(" Hz"):
            hz_str = segment[:-3].strip().split()[-1]
            if hz_str.isdigit():
                return int(hz_str)

    raise RuntimeError(
        f"Cannot determine native sample rate of {path!r}. "
        "Install ffprobe (ships with ffmpeg) or pass target_sample_rate to FfmpegLoader."
    )
