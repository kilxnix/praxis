"""Ingestion — turn REAL material (documents, recordings) into text Discovery can map.

Three kinds of source:
- documents  (.txt .md .pdf .docx)     -> extracted text. Light, always available.
- images     (.png .jpg .jpeg .webp …) -> OCR'd with RapidOCR (offline, bundled models, no
  external binary) — reads photos of forms, tickets, handwritten notes, whiteboards.
- audio      (.wav .mp3 .m4a .flac …)  -> transcribed with WhisperX. WhisperX is a heavy, GPU-
  leaning dependency (PyTorch + faster-whisper + ffmpeg), so its import is GUARDED: the app
  runs without it and raises a clear, actionable error only if you actually feed it audio.

Strictly offline: every model runs locally. We deliberately do NOT enable WhisperX
speaker-diarization (that needs a gated HuggingFace model + token, which would break the
offline principle) — plain transcription only.

    pip install whisperx        # + install ffmpeg on PATH   (audio)
    pip install rapidocr-onnxruntime                          (images)
"""
import os
import shutil
import tempfile

DOC_EXTS = {".txt", ".md", ".markdown", ".pdf", ".docx"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}
AUDIO_EXTS = {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".mp4"}
SUPPORTED_EXTS = DOC_EXTS | IMAGE_EXTS | AUDIO_EXTS

_OCR = None

# Overridable via env so a user can pick a smaller/larger model without code changes.
WHISPER_MODEL = os.environ.get("PRAXIS_WHISPER_MODEL", "base")
WHISPER_DEVICE = os.environ.get("PRAXIS_WHISPER_DEVICE", "cpu")
WHISPER_COMPUTE = os.environ.get("PRAXIS_WHISPER_COMPUTE", "int8")


def _read_txt(path):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def _read_pdf(path):
    from pypdf import PdfReader
    return "\n".join((page.extract_text() or "") for page in PdfReader(path).pages)


def _read_docx(path):
    import docx
    return "\n".join(p.text for p in docx.Document(path).paragraphs)


def extract_text(path):
    """Text from a document. Raises ValueError on an unsupported extension."""
    ext = os.path.splitext(path)[1].lower()
    if ext in (".txt", ".md", ".markdown"):
        return _read_txt(path)
    if ext == ".pdf":
        return _read_pdf(path)
    if ext == ".docx":
        return _read_docx(path)
    raise ValueError(f"unsupported document type: {ext}")


def ocr_image(path):
    """Read text out of an image (form, ticket, handwritten note, whiteboard) with RapidOCR —
    offline, CPU, bundled models. Guarded import with a clear install message."""
    global _OCR
    try:
        from rapidocr_onnxruntime import RapidOCR
    except ImportError as e:
        raise RuntimeError(
            "Image ingest needs RapidOCR:\n    pip install rapidocr-onnxruntime\n"
            "then retry. Or upload a text/PDF/DOCX document instead."
        ) from e
    if _OCR is None:
        _OCR = RapidOCR()      # load once, reuse
    result, _ = _OCR(path)
    if not result:
        return ""
    return "\n".join(line[1] for line in result if len(line) > 1 and line[1])


def _ensure_ffmpeg():
    """WhisperX loads audio by shelling out to `ffmpeg`. If none is on PATH, fall back to the
    binary bundled by imageio-ffmpeg — copied once to a cache dir as `ffmpeg` and prepended to
    PATH so the subprocess call resolves. Keeps audio working out of the box, no manual install."""
    if shutil.which("ffmpeg"):
        return
    try:
        import imageio_ffmpeg
    except ImportError as e:
        raise RuntimeError(
            "Audio ingest needs ffmpeg. Install it on PATH, or:\n"
            "    pip install imageio-ffmpeg\n"
        ) from e
    cache = os.path.join(tempfile.gettempdir(), "praxis_ffmpeg")
    os.makedirs(cache, exist_ok=True)
    name = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
    dst = os.path.join(cache, name)
    if not os.path.exists(dst):
        shutil.copy2(imageio_ffmpeg.get_ffmpeg_exe(), dst)
    os.environ["PATH"] = cache + os.pathsep + os.environ.get("PATH", "")


def transcribe(path):
    """Transcribe an audio file to text with WhisperX (local, offline, no diarization).
    Raises a clear RuntimeError if WhisperX/ffmpeg aren't installed, so the app can tell the
    user exactly what to do instead of crashing obscurely."""
    try:
        import whisperx
    except ImportError as e:
        raise RuntimeError(
            "Audio ingest needs WhisperX. Install it:\n"
            "    pip install whisperx\n"
            "then retry. Or upload a text/PDF/DOCX/image instead."
        ) from e
    _ensure_ffmpeg()
    model = whisperx.load_model(WHISPER_MODEL, WHISPER_DEVICE, compute_type=WHISPER_COMPUTE)
    audio = whisperx.load_audio(path)
    result = model.transcribe(audio)
    return " ".join(seg.get("text", "").strip() for seg in result.get("segments", [])).strip()


def ingest_file(path):
    """Text from any supported source — document extracted, image OCR'd, audio transcribed."""
    ext = os.path.splitext(path)[1].lower()
    if ext in AUDIO_EXTS:
        return transcribe(path)
    if ext in IMAGE_EXTS:
        return ocr_image(path)
    if ext in DOC_EXTS:
        return extract_text(path)
    raise ValueError(f"unsupported file type: {ext} (supported: {sorted(SUPPORTED_EXTS)})")


def ingest_files(paths):
    """Combine several uploaded sources into one text blob, labelled per source."""
    parts = []
    for p in paths:
        text = ingest_file(p).strip()
        if text:
            parts.append(f"[from {os.path.basename(p)}]\n{text}")
    return "\n\n".join(parts)


def ingest_files_with_fixtures(paths):
    """Like ingest_files, but also returns each source as a (basename, text) pair — REAL sample
    data (an OCR'd ticket, a real document) that becomes ground-truth fixtures SP2 verifies
    against. Returns (combined_text, [(source, sample), ...])."""
    parts, fixtures = [], []
    for p in paths:
        text = ingest_file(p).strip()
        if text:
            base = os.path.basename(p)
            parts.append(f"[from {base}]\n{text}")
            fixtures.append((base, text))
    return "\n\n".join(parts), fixtures
