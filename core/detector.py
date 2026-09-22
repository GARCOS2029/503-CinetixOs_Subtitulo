"""Deteccion de subtitulos QUEMADOS (hardcoded/burned-in) sobre la imagen.

Estrategia:
1. Extrae N fotogramas muestreados y recorta la banda inferior (donde suelen ir los subtitulos).
2. Si `pytesseract` + binario `tesseract` estan disponibles, hace OCR y mide en cuantos
   fotogramas aparece texto.
3. Si no hay OCR, aplica una heuristica de densidad de bordes (texto = alto contraste
   con bordes nitidos) comparando la banda inferior contra una banda de control superior.

Nunca lanza excepcion por falta de dependencias: degrada a `detected=None` (desconocido).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field

from .probe import _require, run


@dataclass
class BurnedInResult:
    detected: bool | None
    confidence: float
    method: str
    box: tuple[int, int, int, int] | None = None
    frames_analyzed: int = 0
    frames_with_text: int = 0
    samples: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "detected": self.detected,
            "confidence": round(self.confidence, 3),
            "method": self.method,
            "box": self.box,
            "frames_analyzed": self.frames_analyzed,
            "frames_with_text": self.frames_with_text,
            "samples": self.samples[:10],
        }


def _tesseract_available() -> bool:
    if not shutil.which("tesseract"):
        return False
    try:
        import pytesseract  # noqa: F401
        from PIL import Image  # noqa: F401
    except Exception:
        return False
    return True


def _extract_band(
    video: str,
    band_top_ratio: float,
    n_frames: int,
    outdir: str,
) -> tuple[list[str], int, int, int]:
    """Extrae la banda inferior recortada. Devuelve (rutas, ancho, alto, offset_y)."""
    ffmpeg = _require("ffmpeg")
    band_h = max(1.0 - band_top_ratio, 0.05)
    crop = f"crop=iw:ih*{band_h}:0:ih*{band_top_ratio}"
    pattern = os.path.join(outdir, "band_%04d.png")
    run(
        [
            ffmpeg,
            "-v",
            "error",
            "-i",
            video,
            "-vf",
            crop,
            "-frames:v",
            str(n_frames),
            pattern,
        ]
    )
    files = sorted(
        os.path.join(outdir, f) for f in os.listdir(outdir) if f.startswith("band_")
    )
    if not files:
        return [], 0, 0, 0
    from PIL import Image

    with Image.open(files[0]) as im:
        w, h = im.size
    offset_y = int(h / band_h * band_top_ratio) if band_h else 0
    return files, w, h, offset_y


def _ocr_band(files: list[str]) -> tuple[list[str], list[tuple[int, int, int, int]], int, int]:
    """Devuelve (textos, cajas, frames_con_texto, frames_analizados)."""
    import pytesseract
    from PIL import Image

    texts: list[str] = []
    boxes: list[tuple[int, int, int, int]] = []
    frames_with_text = 0

    for path in files:
        with Image.open(path) as im:
            gray = im.convert("L")
            data = pytesseract.image_to_data(
                gray, config="--psm 6", output_type=pytesseract.Output.DICT
            )
        words = []
        for i, txt in enumerate(data.get("text", [])):
            txt = (txt or "").strip()
            try:
                conf = float(data["conf"][i])
            except (KeyError, ValueError, TypeError):
                conf = -1.0
            if len(txt) >= 2 and conf >= 55:
                words.append(txt)
                boxes.append(
                    (
                        int(data["left"][i]),
                        int(data["top"][i]),
                        int(data["width"][i]),
                        int(data["height"][i]),
                    )
                )
        if len(words) >= 2:
            frames_with_text += 1
            texts.append(" ".join(words))

    return texts, boxes, frames_with_text, len(files)


def _edge_heuristic(files: list[str], band_h: int) -> float:
    """Ratio de pixeles de borde en la banda (proxy de texto). 0..1."""
    from PIL import Image, ImageFilter

    if not files:
        return 0.0
    total = 0.0
    for path in files:
        with Image.open(path) as im:
            gray = im.convert("L")
            edges = gray.filter(ImageFilter.FIND_EDGES)
            hist = edges.histogram()
            bright = sum(hist[40:])
            total += bright / float(gray.width * gray.height)
    return total / len(files)


def detect_burned_in(
    video: str,
    duration: float,
    band_top_ratio: float = 0.72,
    n_frames: int = 12,
) -> BurnedInResult:
    if duration <= 0:
        n_frames = min(n_frames, 3)

    tmp = tempfile.mkdtemp(prefix="cinetix503_band_")
    try:
        files, _w, _h, offset_y = _extract_band(video, band_top_ratio, n_frames, tmp)
        if not files:
            return BurnedInResult(None, 0.0, "sin-fotogramas")

        if _tesseract_available():
            texts, boxes, with_text, analyzed = _ocr_band(files)
            ratio = with_text / analyzed if analyzed else 0.0
            detected = ratio >= 0.4
            box = None
            if boxes:
                x0 = min(b[0] for b in boxes)
                y0 = min(b[1] for b in boxes) + offset_y
                x1 = max(b[0] + b[2] for b in boxes)
                y1 = max(b[1] + b[3] for b in boxes) + offset_y
                pad = 8
                box = (max(0, x0 - pad), max(0, y0 - pad), (x1 - x0) + 2 * pad, (y1 - y0) + 2 * pad)
            return BurnedInResult(
                detected=detected,
                confidence=ratio,
                method="ocr-tesseract",
                box=box,
                frames_analyzed=analyzed,
                frames_with_text=with_text,
                samples=texts,
            )

        score = _edge_heuristic(files, 0)
        return BurnedInResult(
            detected=None,
            confidence=score,
            method="heuristica-bordes (sin tesseract)",
            frames_analyzed=len(files),
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
