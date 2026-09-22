# 🎬 CinetixOS 503 — Subtítulos para proyección

Módulo de la serie **CinetixOs** para preparar los cortometrajes de un festival antes de la proyección: recibe el vídeo que envía un participante, **elimina los subtítulos existentes** (pista blanda o quemados sobre la imagen) y **añade una pista blanda en castellano**.

Todo el procesado es **local-first ($0.00)**: `ffmpeg` + Whisper local + Ollama local. Sin nube.

---

## ✨ Qué hace

1. **Analiza** el contenedor con `ffprobe` (vídeo, audio y pistas de subtítulo).
2. **Detecta** subtítulos:
   - **Pista blanda** (MKV/MP4 `mov_text`/ASS): fiable al 100%.
   - **Quemados** (hardcoded): muestreo de fotogramas + OCR (`tesseract`) o heurística de bordes.
3. **Elimina** lo existente:
   - Pista blanda → remux sin recodificar (`-map -0:s -c copy`), **sin pérdida**.
   - Quemados → parcheo de la zona con `delogo` / `blur` / `cover` (recodifica). Para inpainting real con IA queda el hook `inpaint_propainter` (opcional).
4. **Transcribe** con Whisper local y detecta el idioma.
5. Si el audio **no está en castellano**, **traduce** los subtítulos con Ollama local.
6. Genera un `.srt` y lo **incrusta como pista blanda** (activable/desactivable en el reproductor).

> Si el audio ya está en castellano, el módulo **no hace nada** (salvo `--force`).

---

## 🚀 Uso rápido (web)

```bash
chmod +x run.sh
./run.sh
```

Abre `http://127.0.0.1:5030`, arrastra el corto y pulsa **Procesar**.

## 💻 Uso por CLI

```bash
source .venv/bin/activate

python main.py analyze    corto.mp4                       # ver pistas
python main.py process    corto.mp4                       # pipeline completo
python main.py process    corto.mp4 --burned delogo --box 100,900,1720,140
python main.py strip      corto.mkv                       # quitar pistas blandas
python main.py transcribe corto.mp4 --model medium --srt corto.srt
python main.py translate  corto.srt --target es
python main.py models                                     # modelos Ollama
```

---

## 🧩 Estructura

```
503 CinetixOs_Subtitulo/
├── main.py                 # CLI
├── run.sh                  # arranque 1 clic (puerto 5030)
├── requirements.txt
├── core/
│   ├── probe.py            # ffprobe: pistas y metadatos
│   ├── detector.py         # detección de quemados (OCR / heurística)
│   ├── stripper.py         # borrado de pistas / parcheo / mux
│   ├── transcribe.py       # Whisper local (mlx o faster-whisper)
│   ├── translate.py        # traducción vía Ollama
│   ├── srt.py              # I/O SRT
│   └── pipeline.py         # orquestador
├── backend/app.py          # API FastAPI (puerto 5030)
├── frontend/               # UI (index.html + app.js)
├── uploads/                # vídeos subidos (ignorado por git)
└── data/                   # salidas / temporales
```

---

## 🛠️ Requisitos

- **ffmpeg** (`brew install ffmpeg`). Nota: el ffmpeg de Homebrew sin `libass` **no** puede quemar subtítulos; este módulo usa pista blanda, así que no lo necesita.
- **Python 3.12**.
- **Ollama** en marcha (`ollama serve`) con un modelo multilingüe, p. ej. `ollama pull mistral-nemo`.
- **Whisper local**: `faster-whisper` (CPU, incluido en `requirements.txt`) o `mlx-whisper` (más rápido en Apple Silicon).
- **OCR de quemados** (opcional): `brew install tesseract`. Sin él, la detección de quemados es heurística y de baja confianza.

### Instalación manual

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

---

## ⚠️ Límites conocidos

- El borrado de subtítulos **quemados** con `delogo`/`blur` es un parche de imagen, no inpainting real. Para calidad de cine, usar el hook ProPainter (no autoinstalado).
- La detección de quemados sin `tesseract` es orientativa: para forzar, pasar `--box x,y,w,h`.
- `mlx-whisper` solo en Apple Silicon; en el resto se usa `faster-whisper` (CPU).
