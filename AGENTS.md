# AGENTS.md — CinetixOS 503 Subtítulos

## Principios
1. **Zero-Cloud First ($0.00)**: `ffmpeg` + Whisper local + Ollama local. Prohibido gastar tokens en la nube sin autorización explícita.
2. **No destructivo**: nunca se sobreescribe el original. Las salidas llevan sufijos `_nosubs`, `_clean`, `_ES`.
3. **Cirugía láser**: pasos verificables con `python main.py analyze` y `process`.
4. **Ponytail Lazy Senior**: cero abstracciones innecesarias; apoyarse en ffmpeg/Whisper/Ollama.
5. **Memoria persistente**: decisiones en `.agents/memory/decision_journal.md`.

## Convenciones
- Responder y documentar en español.
- Sin comentarios inline salvo docstrings breves.
- Los binarios de vídeo/audio y las salidas no se versionan (ver `.gitignore`).

## Comandos
- Arrancar: `./run.sh` (puerto 5030).
- CLI: `python main.py {analyze,process,strip,transcribe,translate,models}`.
- No hay linter ni tests: la verificación es ejecutar el CLI sobre un corto real.

## Dependencias externas
- `ffmpeg`/`ffprobe` (obligatorio), `ollama` (traducción), `tesseract` (OCR opcional).
- Whisper: `faster-whisper` (CPU) o `mlx-whisper` (Apple Silicon).
