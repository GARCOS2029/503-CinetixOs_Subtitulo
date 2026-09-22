# 🧠 Diario de Decisiones (ADRs) — CinetixOS 503 Subtítulos

### ADR-001: Salida como pista blanda (no quemada)
- **Contexto:** El ffmpeg de Homebrew instalado no incluye `libass` (sin filtro `subtitles`).
- **Decisión:** Incrustar el castellano como pista blanda (`mov_text` en MP4, `srt` en MKV). No destructivo, editable y activable en el reproductor de proyección (501 Playout / mpv).

### ADR-002: Local-first estricto ($0.00)
- **Contexto:** Regla de coste del usuario.
- **Decisión:** Transcripción con Whisper local (`faster-whisper` CPU o `mlx-whisper` Apple Silicon) y traducción con Ollama local. Sin APIs de pago.

### ADR-003: Borrado de subtítulos según tipo
- **Contexto:** Los cortos llegan con pista blanda o con subtítulos quemados.
- **Decisión:** Pista blanda → remux sin pérdida (`-map -0:s -c copy`). Quemados → parcheo `delogo`/`blur`/`cover` sobre caja detectada (OCR) o indicada por el usuario. Hook ProPainter reservado para inpainting real.

### ADR-004: Puerto 5030 y CLI + Web
- **Contexto:** Serie CinetixOS (501 Playout=5010, 502 DaVinci=5020).
- **Decisión:** Puerto dedicado `5030`. Se ofrece CLI (`main.py`) para batch y UI web (FastAPI) para uso puntual.
