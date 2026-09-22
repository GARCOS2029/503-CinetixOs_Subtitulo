#!/usr/bin/env python3
"""CinetixOS 503 — Subtitulos para proyeccion.

CLI del pipeline: analiza un corto, quita subtitulos existentes (pistas blandas o
quemados) y le incrusta una pista blanda en castellano.

Uso rapido:
  python main.py analyze   corto.mp4
  python main.py process   corto.mp4
  python main.py strip     corto.mkv
  python main.py transcribe corto.mp4 --model small
"""

from __future__ import annotations

import argparse
import json
import sys

from core import pipeline, probe, stripper, transcribe as transcriber, translate as translator
from core.srt import cues_from_segments, read_srt, write_srt


def _box(value: str) -> tuple[int, int, int, int]:
    try:
        parts = [int(p) for p in value.replace(" ", "").split(",")]
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Formato de caja: x,y,w,h") from exc
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("Formato de caja: x,y,w,h")
    return tuple(parts)  # type: ignore[return-value]


def cmd_analyze(args) -> int:
    info = probe.probe(args.video)
    print(json.dumps(info.as_dict(), indent=2, ensure_ascii=False))
    return 0


def cmd_process(args) -> int:
    options = pipeline.ProcessOptions(
        target_lang=args.target,
        whisper_model=args.model,
        translate_model=args.translate_model,
        strip_soft=not args.keep_subs,
        remove_burned=args.burned,
        subtitle_box=args.box,
        force=args.force,
        output_dir=args.outdir,
    )

    def progress(msg: str, pct: float) -> None:
        print(f"[{int(pct * 100):3d}%] {msg}")

    report = pipeline.process(args.video, options, progress)
    print(json.dumps(report.as_dict(), indent=2, ensure_ascii=False))
    return 0


def cmd_strip(args) -> int:
    out = stripper.strip_soft_subtitles(args.video, args.out)
    print(out)
    return 0


def cmd_transcribe(args) -> int:
    result = transcriber.transcribe(args.video, model=args.model)
    payload = result.as_dict()
    if args.srt:
        write_srt(cues_from_segments(result.segments), args.srt)
        payload["srt"] = args.srt
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


def cmd_translate(args) -> int:
    cues = read_srt(args.srt)
    translated, model = translator.translate_cues(cues, model=args.translate_model, target=args.target)
    out = args.out or args.srt.replace(".srt", f"_{args.target}.srt")
    write_srt(translated, out)
    print(json.dumps({"model": model, "output": out, "cues": len(translated)}, indent=2, ensure_ascii=False))
    return 0


def cmd_models(args) -> int:
    print(json.dumps({"ollama": translator.available_models()}, indent=2, ensure_ascii=False))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cinetix503", description="Subtitulado para proyeccion (local-first)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("analyze", help="Analiza pistas de video/audio/subtitulo")
    p.add_argument("video")
    p.set_defaults(func=cmd_analyze)

    p = sub.add_parser("process", help="Pipeline completo")
    p.add_argument("video")
    p.add_argument("--target", default="es", help="Idioma destino (por defecto es)")
    p.add_argument("--model", default=None, help="Modelo Whisper (small, medium, large-v3...)")
    p.add_argument("--translate-model", default=None, help="Modelo Ollama para traducir")
    p.add_argument("--burned", default="auto", choices=["auto", "none", "delogo", "blur", "cover"])
    p.add_argument("--box", type=_box, default=None, help="Caja del subtitulo quemado x,y,w,h")
    p.add_argument("--keep-subs", action="store_true", help="No borrar pistas de subtitulo existentes")
    p.add_argument("--force", action="store_true", help="Subtitular aunque ya este en el idioma destino")
    p.add_argument("--outdir", default=None)
    p.set_defaults(func=cmd_process)

    p = sub.add_parser("strip", help="Elimina pistas de subtitulo (remux sin perdida)")
    p.add_argument("video")
    p.add_argument("--out", default=None)
    p.set_defaults(func=cmd_strip)

    p = sub.add_parser("transcribe", help="Transcribe con Whisper local")
    p.add_argument("video")
    p.add_argument("--model", default=None)
    p.add_argument("--srt", default=None, help="Ruta donde volcar el .srt")
    p.set_defaults(func=cmd_transcribe)

    p = sub.add_parser("translate", help="Traduce un .srt con Ollama")
    p.add_argument("srt")
    p.add_argument("--target", default="es")
    p.add_argument("--translate-model", default=None)
    p.add_argument("--out", default=None)
    p.set_defaults(func=cmd_translate)

    p = sub.add_parser("models", help="Lista modelos Ollama disponibles")
    p.set_defaults(func=cmd_models)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
