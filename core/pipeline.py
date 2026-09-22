"""Orquestador del pipeline CinetixOS 503.

Flujo:
  analizar -> quitar subtitulos existentes -> transcribir -> traducir a castellano
  -> generar .srt -> incrustar como pista blanda.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from dataclasses import dataclass, field
from typing import Callable

from . import detector, probe, stripper, transcribe as transcriber, translate as translator
from .srt import cues_from_segments, write_srt

ProgressFn = Callable[[str, float], None]


@dataclass
class ProcessOptions:
    target_lang: str = "es"
    whisper_model: str | None = None
    translate_model: str | None = None
    strip_soft: bool = True
    remove_burned: str = "auto"
    subtitle_box: tuple[int, int, int, int] | None = None
    force: bool = False
    output_dir: str | None = None


@dataclass
class ProcessReport:
    source: str
    final: str | None = None
    srt: str | None = None
    media: dict = field(default_factory=dict)
    burned_in: dict = field(default_factory=dict)
    language: str | None = None
    translated: bool = False
    skipped: bool = False
    message: str = ""
    steps: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "source": self.source,
            "final": self.final,
            "srt": self.srt,
            "media": self.media,
            "burned_in": self.burned_in,
            "language": self.language,
            "translated": self.translated,
            "skipped": self.skipped,
            "message": self.message,
            "steps": self.steps,
        }


def _out_dir(video: str, options: ProcessOptions) -> str:
    return options.output_dir or os.path.dirname(os.path.abspath(video))


def _step(progress: ProgressFn | None, msg: str, pct: float, report: ProcessReport) -> None:
    report.steps.append(msg)
    if progress:
        progress(msg, pct)


def process(video: str, options: ProcessOptions | None = None, progress: ProgressFn | None = None) -> ProcessReport:
    options = options or ProcessOptions()
    video = os.path.abspath(video)
    report = ProcessReport(source=video)
    outdir = _out_dir(video, options)
    os.makedirs(outdir, exist_ok=True)

    _step(progress, "Analizando contenedor (ffprobe)...", 0.05, report)
    info = probe.probe(video)
    report.media = info.as_dict()

    workdir = tempfile.mkdtemp(prefix="cinetix503_")
    working = video
    try:
        _step(progress, "Detectando subtitulos quemados...", 0.15, report)
        burned = detector.detect_burned_in(video, info.duration)
        report.burned_in = burned.as_dict()

        if options.strip_soft and info.has_soft_subtitles:
            _step(progress, "Eliminando pistas de subtitulo existentes (remux)...", 0.25, report)
            working = stripper.strip_soft_subtitles(working, os.path.join(workdir, "nosubs" + os.path.splitext(video)[1]))

        burn_mode = options.remove_burned
        if burn_mode == "auto":
            burn_mode = "delogo" if burned.detected else "none"

        if burn_mode not in ("none", "delogo", "blur", "cover"):
            raise ValueError(f"remove_burned invalido: {burn_mode}")

        box = options.subtitle_box or burned.box
        if burn_mode != "none":
            if not box:
                _step(progress, "Subtitulo quemado sin caja detectable: se omite el parcheo.", 0.32, report)
            else:
                _step(progress, f"Parcheando subtitulo quemado ({burn_mode})...", 0.35, report)
                working = stripper.remove_burned_in(
                    working, box, info.width, info.height,
                    out=os.path.join(workdir, "clean" + os.path.splitext(video)[1]),
                    mode=burn_mode,
                )

        _step(progress, "Transcribiendo con Whisper local...", 0.5, report)
        result = transcriber.transcribe(working, model=options.whisper_model)
        report.language = result.language

        target = options.target_lang
        already_target = result.language and result.language.lower().startswith(target[:2])
        if already_target and not options.force:
            report.skipped = True
            report.final = working if working != video else video
            report.message = f"El audio ya esta en '{result.language}': no requiere subtitulado."
            _step(progress, "Sin cambios: idioma ya es castellano.", 1.0, report)
            return report

        cues = cues_from_segments(result.segments)
        if not cues:
            raise RuntimeError("Whisper no produjo segmentos de texto.")

        if not already_target:
            _step(progress, f"Traduciendo a castellano con Ollama...", 0.7, report)
            cues, used_model = translator.translate_cues(cues, model=options.translate_model, target=target)
            report.translated = True
            report.message = f"Traducido {result.language} -> {target} con {used_model}."

        srt_path = os.path.join(outdir, os.path.splitext(os.path.basename(video))[0] + "_ES.srt")
        write_srt(cues, srt_path)
        report.srt = srt_path

        _step(progress, "Incrustando subtitulo en castellano (pista blanda)...", 0.9, report)
        final = stripper.mux_soft_subtitles(working, srt_path, out=os.path.join(outdir, os.path.splitext(os.path.basename(video))[0] + "_ES.mkv"))
        report.final = final

        _step(progress, "Completado.", 1.0, report)
        return report
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
