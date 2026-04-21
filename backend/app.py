"""
===================================================
BANGLA VOICE CLONE - Backend API (Flask)
Uses Coqui XTTS v2 for zero-shot voice cloning
Optimized for Bangla (Bengali) language
===================================================
"""

import os
import io
import time
import uuid
import logging
import threading
from pathlib import Path
from datetime import datetime

import numpy as np
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import soundfile as sf
import librosa

# ── Logging ────────────────────────────────────
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# ── App setup ──────────────────────────────────
app = Flask(__name__)
CORS(app, origins=["*"])

BASE_DIR = Path(__file__).parent.parent
SAMPLES_DIR = BASE_DIR / "model" / "voice_samples"
OUTPUT_DIR = BASE_DIR / "model" / "outputs"
MODEL_DIR = BASE_DIR / "model" / "tts_model"

for d in [SAMPLES_DIR, OUTPUT_DIR, MODEL_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ── Model state ────────────────────────────────
model_state = {
    "tts": None,
    "loaded": False,
    "loading": False,
    "error": None,
}

# ── Model loader ───────────────────────────────
def load_model():
    """Load Coqui XTTS v2 model in background thread."""
    if model_state["loading"] or model_state["loaded"]:
        return
    model_state["loading"] = True
    try:
        logger.info("Loading XTTS v2 model...")
        from TTS.api import TTS
        tts = TTS(
            model_name="tts_models/multilingual/multi-dataset/xtts_v2",
            progress_bar=True,
            gpu=False,   # CPU-safe; change to True if GPU available
        )
        model_state["tts"] = tts
        model_state["loaded"] = True
        model_state["loading"] = False
        logger.info("✅ XTTS v2 model loaded successfully.")
    except ImportError:
        model_state["error"] = "TTS library not installed. Run: pip install TTS"
        model_state["loading"] = False
        logger.error(model_state["error"])
    except Exception as e:
        model_state["error"] = str(e)
        model_state["loading"] = False
        logger.error(f"Model load failed: {e}")


def ensure_model():
    """Block until model is loaded or raises if failed."""
    if model_state["loaded"]:
        return True
    if model_state["error"]:
        raise RuntimeError(f"Model unavailable: {model_state['error']}")
    if not model_state["loading"]:
        t = threading.Thread(target=load_model, daemon=True)
        t.start()
    # Wait up to 300s (model download can take time)
    deadline = time.time() + 300
    while time.time() < deadline:
        if model_state["loaded"]:
            return True
        if model_state["error"]:
            raise RuntimeError(f"Model failed: {model_state['error']}")
        time.sleep(2)
    raise RuntimeError("Model load timeout. Please wait and retry.")


# ── Audio preprocessing ────────────────────────
def preprocess_audio(input_path: Path, output_path: Path, target_sr=22050) -> Path:
    """
    Normalize, denoise, resample audio to a format XTTS expects.
    Returns path to processed file.
    """
    logger.info(f"Preprocessing audio: {input_path.name}")
    y, sr = librosa.load(str(input_path), sr=None, mono=True)

    # Resample
    if sr != target_sr:
        y = librosa.resample(y, orig_sr=sr, target_sr=target_sr)

    # Trim silence
    y, _ = librosa.effects.trim(y, top_db=25)

    # Normalize to -3 dBFS
    peak = np.abs(y).max()
    if peak > 0:
        y = y / peak * 0.7

    # Enforce 5–30 seconds
    min_samples = 5 * target_sr
    max_samples = 30 * target_sr
    if len(y) < min_samples:
        repeats = int(np.ceil(min_samples / len(y)))
        y = np.tile(y, repeats)[:max_samples]
    elif len(y) > max_samples:
        y = y[:max_samples]

    sf.write(str(output_path), y, target_sr, subtype='PCM_16')
    logger.info(f"Preprocessed: {len(y)/target_sr:.1f}s @ {target_sr}Hz → {output_path.name}")
    return output_path


def save_voice_sample(file_bytes: bytes, ext: str, session_id: str) -> Path:
    """Save uploaded voice sample for auto-learning dataset."""
    raw_path = SAMPLES_DIR / f"sample_{session_id}_raw{ext}"
    proc_path = SAMPLES_DIR / f"sample_{session_id}_clean.wav"
    raw_path.write_bytes(file_bytes)
    preprocess_audio(raw_path, proc_path)
    raw_path.unlink(missing_ok=True)
    return proc_path


# ── Auto-learning metadata ─────────────────────
def log_generation(session_id: str, text: str, sample_path: str, output_path: str):
    """Append generation metadata for future fine-tuning."""
    log_file = BASE_DIR / "model" / "generation_log.jsonl"
    import json
    entry = {
        "id": session_id,
        "timestamp": datetime.utcnow().isoformat(),
        "text": text,
        "language": "bn",
        "sample": str(sample_path),
        "output": str(output_path),
    }
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ── Routes ─────────────────────────────────────

@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "model_loaded": model_state["loaded"],
        "model_loading": model_state["loading"],
        "model_error": model_state["error"],
        "language": "bn",
    })


@app.route("/clone", methods=["POST"])
def clone_voice():
    """
    POST /clone
    Form data:
      voice_sample: audio file (WAV/MP3)
      text: Bangla text string
      language: 'bn' (default)
    Returns: WAV audio file (streamed)
    """
    try:
        # ── Validate inputs ────────────────────
        if "voice_sample" not in request.files:
            return jsonify({"detail": "voice_sample ফাইল প্রয়োজন।"}), 400

        file = request.files["voice_sample"]
        text = request.form.get("text", "").strip()

        if not text:
            return jsonify({"detail": "বাংলা টেক্সট প্রয়োজন।"}), 400

        if len(text) > 500:
            return jsonify({"detail": "টেক্সট সর্বোচ্চ 500 অক্ষর হতে পারে।"}), 400

        ext = Path(file.filename).suffix.lower()
        if ext not in [".wav", ".mp3"]:
            return jsonify({"detail": "শুধু WAV বা MP3 ফাইল গ্রহণযোগ্য।"}), 400

        # ── Load model ─────────────────────────
        ensure_model()
        tts = model_state["tts"]

        # ── Save & preprocess voice sample ─────
        session_id = str(uuid.uuid4())[:8]
        file_bytes = file.read()
        speaker_path = save_voice_sample(file_bytes, ext, session_id)

        # ── Generate speech ────────────────────
        output_path = OUTPUT_DIR / f"output_{session_id}.wav"
        logger.info(f"Generating Bangla speech [{session_id}]: '{text[:50]}...'")

        tts.tts_to_file(
            text=text,
            speaker_wav=str(speaker_path),
            language="bn",
            file_path=str(output_path),
        )

        # ── Log for auto-learning ──────────────
        log_generation(session_id, text, speaker_path, output_path)

        logger.info(f"✅ Generated: {output_path.name}")

        return send_file(
            str(output_path),
            mimetype="audio/wav",
            as_attachment=False,
            download_name=f"bangla_clone_{session_id}.wav",
        )

    except RuntimeError as e:
        logger.error(f"Runtime error: {e}")
        return jsonify({"detail": str(e)}), 503
    except Exception as e:
        logger.exception("Unexpected error during cloning")
        return jsonify({"detail": f"ত্রুটি হয়েছে: {str(e)}"}), 500


@app.route("/samples", methods=["GET"])
def list_samples():
    """Return stored voice sample metadata for auto-learning dashboard."""
    import json
    log_file = BASE_DIR / "model" / "generation_log.jsonl"
    if not log_file.exists():
        return jsonify({"samples": [], "count": 0})
    entries = []
    with open(log_file, encoding="utf-8") as f:
        for line in f:
            try:
                entries.append(json.loads(line))
            except Exception:
                pass
    return jsonify({"samples": entries[-50:], "count": len(entries)})


@app.route("/retrain", methods=["POST"])
def retrain():
    """
    Trigger lightweight fine-tuning on stored voice samples.
    This endpoint is a placeholder for automated retraining pipeline.
    In production, integrate with a training queue (Celery, etc.)
    """
    log_file = BASE_DIR / "model" / "generation_log.jsonl"
    if not log_file.exists():
        return jsonify({"detail": "No samples collected yet."}), 400

    import json
    with open(log_file, encoding="utf-8") as f:
        count = sum(1 for _ in f)

    if count < 10:
        return jsonify({"detail": f"Only {count} samples. Need at least 10 for retraining."}), 400

    # In real deployment: kick off fine-tuning job here
    return jsonify({
        "status": "queued",
        "samples": count,
        "message": "Retraining queued. Check /health for progress.",
    })


# ── Startup model preload ──────────────────────
@app.before_request
def preload_model_once():
    """Trigger model load on first request."""
    if not model_state["loaded"] and not model_state["loading"]:
        t = threading.Thread(target=load_model, daemon=True)
        t.start()


if __name__ == "__main__":
    logger.info("🚀 Starting Bangla Voice Clone API...")
    logger.info("📦 Pre-loading XTTS v2 model in background...")
    t = threading.Thread(target=load_model, daemon=True)
    t.start()
    app.run(host="0.0.0.0", port=8000, debug=False, threaded=True)
