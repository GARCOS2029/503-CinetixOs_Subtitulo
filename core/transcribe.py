"""Transcripcion local con Whisper ($0.00, offline).

Motores soportados (se autodetectan):
- `mlx-whisper`  -> rapido en Apple Silicon (Metal).
- `faster-whisper` -> CTranslate2, funciona en CPU (int8).

Ambos devuelven idioma detectado + segmentos con timestamps, que es lo que
necesitamos para decidir si hay que subtitular y en que idioma esta.
"""

from __future__ import annotations

import os
import platform
import tempfile
from dataclasses import dataclass, field

from .probe import _require, run

DEFAULT_FASTER_MODEL = os.getenv("WHISPER_MODEL", "small")
DEFAULT_MLX_MODEL = os.getenv("WHISPER_MLX_MODEL", "mlx-community/whisper-small-mlx")


class TranscriptionError(RuntimeError):
    pass


@dataclass
class Transcription:
    language: str
    language_probability: float
    segments: list[dict] = field(default_factory=list)
    engine: str = ""

    @property
    def text(self) -> str:
        return " ".join(s["text"].strip() for s in self.segments).strip()

    def as_dict(self) -> dict:
        return {
            "language": self.language,
            "language_probability": round(self.language_probability, 3),
            "engine": self.engine,
            "segments": self.segments,
            "text": self.text,
        }


def extract_audio(video: str, out: str | None = None) -> str:
    ffmpeg = _require("ffmpeg")
    if out is None:
        fd, out = tempfile.mkstemp(suffix=".wav", prefix="cinetix503_audio_")
        os.close(fd)
    run(
        [
            ffmpeg,
            "-v",
            "error",
            "-y",
            "-i",
            video,
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            out,
        ]
    )
    return out


def _transcribe_mlx(audio: str, model: str) -> Transcription:
    import mlx_whisper

    result = mlx_whisper.transcribe(audio, path_or_hf_repo=model, word_timestamps=False)
    segments = [
        {"start": float(s["start"]), "end": float(s["end"]), "text": s["text"].strip()}
        for s in result.get("segments", [])
    ]
    return Transcription(
        language=result.get("language", "und"),
        language_probability=1.0,
        segments=segments,
        engine=f"mlx-whisper:{model}",
    )


def _transcribe_faster(audio: str, model: str) -> Transcription:
    from faster_whisper import WhisperModel

    compute = "int8"
    whisper = WhisperModel(model, device="auto", compute_type=compute)
    segments_iter, info = whisper.transcribe(audio, beam_size=5, vad_filter=True)
    segments = [
        {"start": float(s.start), "end": float(s.end), "text": s.text.strip()}
        for s in segments_iter
    ]
    return Transcription(
        language=info.language,
        language_probability=float(getattr(info, "language_probability", 1.0)),
        segments=segments,
        engine=f"faster-whisper:{model}",
    )


def _has_mlx() -> bool:
    if platform.machine() not in ("arm64", "aarch64"):
        return False
    try:
        import mlx_whisper  # noqa: F401

        return True
    except Exception:
        return False


def _has_faster() -> bool:
    try:
        import faster_whisper  # noqa: F401

        return True
    except Exception:
        return False


def transcribe(video: str, model: str | None = None, audio: str | None = None) -> Transcription:
    audio_path = audio or extract_audio(video)
    cleanup = audio is None
    try:
        if _has_mlx():
            return _transcribe_mlx(audio_path, model or DEFAULT_MLX_MODEL)
        if _has_faster():
            return _transcribe_faster(audio_path, model or DEFAULT_FASTER_MODEL)
        raise TranscriptionError(
            "No hay motor Whisper instalado. Instala 'faster-whisper' o 'mlx-whisper' "
            "dentro del .venv del modulo (ver requirements.txt / run.sh)."
        )
    finally:
        if cleanup:
            try:
                os.remove(audio_path)
            except OSError:
                pass
