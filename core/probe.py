"""Analisis de contenedores con ffprobe: pistas de video, audio y subtitulos."""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass, field


class FFToolError(RuntimeError):
    pass


def _require(tool: str) -> str:
    path = shutil.which(tool)
    if not path:
        raise FFToolError(f"No se encontro '{tool}' en el PATH. Instala ffmpeg (brew install ffmpeg).")
    return path


def run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise FFToolError(f"Fallo el comando: {' '.join(cmd)}\n{proc.stderr.strip()}")
    return proc


@dataclass
class Stream:
    index: int
    codec_type: str
    codec_name: str
    language: str = "und"
    title: str = ""
    duration: float | None = None

    def as_dict(self) -> dict:
        return {
            "index": self.index,
            "codec_type": self.codec_type,
            "codec_name": self.codec_name,
            "language": self.language,
            "title": self.title,
        }


@dataclass
class MediaInfo:
    path: str
    duration: float
    width: int = 0
    height: int = 0
    video: list[Stream] = field(default_factory=list)
    audio: list[Stream] = field(default_factory=list)
    subtitles: list[Stream] = field(default_factory=list)

    @property
    def has_soft_subtitles(self) -> bool:
        return len(self.subtitles) > 0

    def as_dict(self) -> dict:
        return {
            "path": self.path,
            "duration": self.duration,
            "width": self.width,
            "height": self.height,
            "video": [s.as_dict() for s in self.video],
            "audio": [s.as_dict() for s in self.audio],
            "subtitles": [s.as_dict() for s in self.subtitles],
            "has_soft_subtitles": self.has_soft_subtitles,
        }


def probe(path: str) -> MediaInfo:
    ffprobe = _require("ffprobe")
    proc = run(
        [
            ffprobe,
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            path,
        ]
    )
    data = json.loads(proc.stdout)

    fmt = data.get("format", {})
    duration = float(fmt.get("duration") or 0.0)

    info = MediaInfo(path=path, duration=duration)

    for raw in data.get("streams", []):
        tags = raw.get("tags", {}) or {}
        stream = Stream(
            index=int(raw.get("index", 0)),
            codec_type=raw.get("codec_type", ""),
            codec_name=raw.get("codec_name", ""),
            language=(tags.get("language") or "und").lower(),
            title=tags.get("title") or "",
            duration=float(raw["duration"]) if raw.get("duration") else None,
        )
        if stream.codec_type == "video":
            info.video.append(stream)
            info.width = info.width or int(raw.get("width") or 0)
            info.height = info.height or int(raw.get("height") or 0)
        elif stream.codec_type == "audio":
            info.audio.append(stream)
        elif stream.codec_type == "subtitle":
            info.subtitles.append(stream)

    return info
