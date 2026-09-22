"""Lectura/escritura de SRT y conversion de segmentos de Whisper."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_TIME_RE = re.compile(
    r"(\d{1,2}):(\d{2}):(\d{2})[,.](\d{1,3})\s*-->\s*(\d{1,2}):(\d{2}):(\d{2})[,.](\d{1,3})"
)


@dataclass
class Cue:
    start: float
    end: float
    text: str
    index: int = 0

    def as_dict(self) -> dict:
        return {"index": self.index, "start": self.start, "end": self.end, "text": self.text}


def format_timestamp(seconds: float) -> str:
    if seconds < 0:
        seconds = 0.0
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _parse_timestamp(h: str, m: str, s: str, ms: str) -> float:
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms.ljust(3, "0")) / 1000.0


def parse_srt(content: str) -> list[Cue]:
    cues: list[Cue] = []
    blocks = re.split(r"\n\s*\n", content.strip())
    idx = 0
    for block in blocks:
        lines = [ln for ln in block.splitlines() if ln.strip()]
        if not lines:
            continue
        time_line_i = None
        for i, ln in enumerate(lines):
            if _TIME_RE.search(ln):
                time_line_i = i
                break
        if time_line_i is None:
            continue
        m = _TIME_RE.search(lines[time_line_i])
        start = _parse_timestamp(m.group(1), m.group(2), m.group(3), m.group(4))
        end = _parse_timestamp(m.group(5), m.group(6), m.group(7), m.group(8))
        text = " ".join(lines[time_line_i + 1 :]).strip()
        idx += 1
        cues.append(Cue(start=start, end=end, text=text, index=idx))
    return cues


def read_srt(path: str) -> list[Cue]:
    with open(path, encoding="utf-8-sig") as fh:
        return parse_srt(fh.read())


def write_srt(cues: list[Cue], path: str) -> str:
    parts = []
    for i, cue in enumerate(cues, start=1):
        parts.append(
            f"{i}\n{format_timestamp(cue.start)} --> {format_timestamp(cue.end)}\n{cue.text}\n"
        )
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(parts))
    return path


def cues_from_segments(segments: list[dict]) -> list[Cue]:
    cues = []
    for i, seg in enumerate(segments, start=1):
        cues.append(
            Cue(
                start=float(seg["start"]),
                end=float(seg["end"]),
                text=str(seg["text"]).strip(),
                index=i,
            )
        )
    return cues
