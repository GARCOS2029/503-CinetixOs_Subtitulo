"""Traduccion a castellano con Ollama local ($0.00, offline).

Envia los textos de los subtitulos por lotes al modelo local y recupera la
traduccion manteniendo el mismo numero de lineas (los tiempos no se tocan).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

import requests

from .srt import Cue

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
DEFAULT_MODEL = os.getenv("OLLAMA_TRANSLATE_MODEL", "mistral-nemo:latest")
PREFERRED = [
    "mistral-nemo:latest",
    "gemma2:9b",
    "llama3.1:8b",
    "qwen3.6:27b",
    "hermes3:8b",
]

SYSTEM = (
    "Eres un traductor profesional de subtitulos de cine. Traduce cada linea al "
    "espanol de Espana (castellano), de forma natural, breve y apta para lectura "
    "rapida en pantalla. No anadas comentarios ni numeracion. Devuelve EXACTAMENTE "
    "un array JSON de cadenas con el mismo numero de elementos que la entrada."
)


class TranslationError(RuntimeError):
    pass


@dataclass
class TranslationResult:
    target: str
    model: str
    texts: list[str]

    def as_dict(self) -> dict:
        return {"target": self.target, "model": self.model, "texts": self.texts}


def available_models() -> list[str]:
    try:
        resp = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        resp.raise_for_status()
        return [m["name"] for m in resp.json().get("models", [])]
    except requests.RequestException as exc:
        raise TranslationError(f"Ollama no responde en {OLLAMA_URL}: {exc}") from exc


def pick_model(model: str | None = None) -> str:
    if model:
        return model
    models = available_models()
    for candidate in PREFERRED:
        if candidate in models:
            return candidate
    if models:
        return models[0]
    raise TranslationError("Ollama no tiene modelos instalados. Ejecuta 'ollama pull mistral-nemo'.")


def _call_ollama(model: str, texts: list[str], target: str) -> list[str]:
    user = json.dumps({"target": target, "lines": texts}, ensure_ascii=False)
    payload = {
        "model": model,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.2},
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
        ],
    }
    resp = requests.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=600)
    resp.raise_for_status()
    content = resp.json().get("message", {}).get("content", "").strip()
    return _extract_array(content, len(texts))


def _extract_array(content: str, expected: int) -> list[str]:
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        start, end = content.find("["), content.rfind("]")
        if start == -1 or end == -1:
            raise TranslationError(f"Respuesta no parseable: {content[:200]}")
        data = json.loads(content[start : end + 1])

    if isinstance(data, dict):
        for key in ("translations", "lines", "result", "output"):
            if key in data and isinstance(data[key], list):
                data = data[key]
                break
        else:
            data = list(data.values())

    if not isinstance(data, list):
        raise TranslationError(f"Se esperaba un array, llego: {type(data)}")
    if len(data) != expected:
        raise TranslationError(f"Se esperaban {expected} lineas y llegaron {len(data)}")
    return [str(x).strip() for x in data]


def translate_texts(
    texts: list[str],
    model: str | None = None,
    target: str = "es",
    batch_size: int = 20,
) -> TranslationResult:
    model = pick_model(model)
    out: list[str] = []
    for i in range(0, len(texts), batch_size):
        chunk = texts[i : i + batch_size]
        try:
            out.extend(_call_ollama(model, chunk, target))
        except TranslationError:
            out.extend(_call_ollama(model, chunk, target))
    return TranslationResult(target=target, model=model, texts=out)


def translate_cues(cues: list[Cue], model: str | None = None, target: str = "es") -> tuple[list[Cue], str]:
    non_empty = [c.text for c in cues if c.text.strip()]
    if not non_empty:
        return cues, model or DEFAULT_MODEL
    result = translate_texts(non_empty, model=model, target=target)
    it = iter(result.texts)
    translated = [
        Cue(start=c.start, end=c.end, text=next(it) if c.text.strip() else c.text, index=c.index)
        for c in cues
    ]
    return translated, result.model
