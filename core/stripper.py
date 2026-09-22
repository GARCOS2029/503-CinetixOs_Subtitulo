"""Cirugia sobre el contenedor: eliminar pistas de subtitulo e incrustar la nueva.

- Pistas BLANDAS (MKV/MP4 mov_text/ASS...): se eliminan por remux, sin recodificar.
- Subtitulos QUEMADOS: se parchean con `delogo`/`boxblur` sobre la zona detectada
  (recodifica el video). Para inpainting real con IA existe el hook ProPainter.
"""

from __future__ import annotations

import os
import platform
import shutil

from .probe import _require, run


def _is_apple_silicon() -> bool:
    return platform.system() == "Darwin" and platform.machine() in ("arm64", "aarch64")


def _video_encoder() -> list[str]:
    if _is_apple_silicon() and shutil.which("ffmpeg"):
        return ["-c:v", "h264_videotoolbox", "-b:v", "8M"]
    return ["-c:v", "libx264", "-preset", "medium", "-crf", "18"]


def output_path(video: str, suffix: str, ext: str | None = None) -> str:
    root, current_ext = os.path.splitext(video)
    ext = ext or current_ext
    if not ext.startswith("."):
        ext = "." + ext
    return f"{root}{suffix}{ext}"


def strip_soft_subtitles(video: str, out: str | None = None) -> str:
    """Remux sin pistas de subtitulo. Sin perdida de calidad (copia de codecs)."""
    ffmpeg = _require("ffmpeg")
    out = out or output_path(video, "_nosubs")
    run(
        [
            ffmpeg,
            "-v",
            "error",
            "-y",
            "-i",
            video,
            "-map",
            "0",
            "-map",
            "-0:s",
            "-c",
            "copy",
            out,
        ]
    )
    return out


def _clamp_box(box: tuple[int, int, int, int], width: int, height: int) -> tuple[int, int, int, int]:
    x, y, w, h = box
    x = max(1, min(x, width - 3))
    y = max(1, min(y, height - 3))
    w = max(2, min(w, width - x - 2))
    h = max(2, min(h, height - y - 2))
    return x, y, w, h


def remove_burned_in(
    video: str,
    box: tuple[int, int, int, int],
    width: int,
    height: int,
    out: str | None = None,
    mode: str = "delogo",
) -> str:
    """Parchea la zona del subtitulo quemado. mode: 'delogo' | 'blur' | 'cover'."""
    ffmpeg = _require("ffmpeg")
    out = out or output_path(video, "_clean")
    x, y, w, h = _clamp_box(box, width, height)

    if mode == "blur":
        vf = f"split[main][bl];[bl]crop={w}:{h}:{x}:{y},boxblur=20:2[blur];[main][blur]overlay={x}:{y}"
    elif mode == "cover":
        vf = f"drawbox=x={x}:y={y}:w={w}:h={h}:color=black@1.0:t=fill"
    else:
        vf = f"delogo=x={x}:y={y}:w={w}:h={h}:show=0"

    run(
        [
            ffmpeg,
            "-v",
            "error",
            "-y",
            "-i",
            video,
            "-vf",
            vf,
            *_video_encoder(),
            "-c:a",
            "copy",
            out,
        ]
    )
    return out


def mux_soft_subtitles(
    video: str,
    srt: str,
    out: str | None = None,
    language: str = "spa",
    title: str = "Castellano",
) -> str:
    """Incrusta un .srt como pista blanda (mov_text en MP4, srt en MKV)."""
    ffmpeg = _require("ffmpeg")
    in_ext = os.path.splitext(video)[1].lower()
    default_ext = in_ext if in_ext in (".mp4", ".m4v", ".mov", ".mkv") else ".mkv"
    out = out or output_path(video, "_ES", default_ext)
    out_ext = os.path.splitext(out)[1].lower()
    sub_codec = "mov_text" if out_ext in (".mp4", ".m4v", ".mov") else "srt"

    run(
        [
            ffmpeg,
            "-v",
            "error",
            "-y",
            "-i",
            video,
            "-i",
            srt,
            "-map",
            "0:v",
            "-map",
            "0:a?",
            "-map",
            "1:0",
            "-c:v",
            "copy",
            "-c:a",
            "copy",
            "-c:s",
            sub_codec,
            "-metadata:s:s:0",
            f"language={language}",
            "-metadata:s:s:0",
            f"title={title}",
            out,
        ]
    )
    return out


def inpaint_propainter(video: str, box: tuple[int, int, int, int], out: str | None = None) -> str:
    """Hook opcional para inpainting real con IA (ProPainter). No autoinstalado."""
    raise RuntimeError(
        "Inpainting IA no disponible. Instala ProPainter (https://github.com/sczhou/ProPainter) "
        "en un venv aparte con PyTorch MPS y expone su CLI, o usa mode='delogo'/'blur'/'cover'."
    )
