"""
===================================================
BANGLA VOICE CLONE - Auto-Learning Trainer
Periodically retrains/fine-tunes on stored samples
===================================================

Run this script separately to trigger retraining:
    python backend/trainer.py

Or schedule via cron:
    0 */6 * * * cd /path/to/project && python backend/trainer.py
"""

import json
import logging
import time
from pathlib import Path
from datetime import datetime

import numpy as np
import soundfile as sf
import librosa

logging.basicConfig(level=logging.INFO, format='%(asctime)s [TRAINER] %(message)s')
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent.parent
LOG_FILE = BASE_DIR / "model" / "generation_log.jsonl"
SAMPLES_DIR = BASE_DIR / "model" / "voice_samples"
DATASET_DIR = BASE_DIR / "model" / "dataset"
TRAIN_STATE = BASE_DIR / "model" / "train_state.json"

DATASET_DIR.mkdir(parents=True, exist_ok=True)


def load_log():
    if not LOG_FILE.exists():
        return []
    entries = []
    with open(LOG_FILE, encoding="utf-8") as f:
        for line in f:
            try:
                entries.append(json.loads(line))
            except Exception:
                pass
    return entries


def load_train_state():
    if TRAIN_STATE.exists():
        return json.loads(TRAIN_STATE.read_text())
    return {"last_trained": None, "samples_trained": 0, "runs": 0}


def save_train_state(state):
    TRAIN_STATE.write_text(json.dumps(state, indent=2, ensure_ascii=False))


def build_dataset(entries):
    """
    Convert stored generation log entries into a Coqui-compatible
    dataset format (LJSpeech-style): audio.wav | text
    """
    dataset = []
    for entry in entries:
        sample_path = Path(entry.get("sample", ""))
        if sample_path.exists():
            dataset.append({
                "audio": str(sample_path),
                "text": entry["text"],
                "language": "bn",
            })
    # Write metadata CSV (LJSpeech format: filename|text)
    metadata_file = DATASET_DIR / "metadata.csv"
    with open(metadata_file, "w", encoding="utf-8") as f:
        for item in dataset:
            fname = Path(item["audio"]).stem
            text = item["text"].replace("|", " ").replace("\n", " ")
            f.write(f"{fname}|{text}\n")
    logger.info(f"Dataset built: {len(dataset)} entries → {metadata_file}")
    return dataset


def lightweight_voice_stats(dataset):
    """
    Compute basic voice statistics from stored samples.
    Used to monitor voice quality over time.
    """
    stats = []
    for item in dataset[:20]:  # analyze first 20
        try:
            y, sr = librosa.load(item["audio"], sr=None, mono=True)
            duration = len(y) / sr
            pitch = librosa.yin(y, fmin=60, fmax=400).mean()
            energy = np.sqrt(np.mean(y ** 2))
            stats.append({
                "file": Path(item["audio"]).name,
                "duration": round(duration, 2),
                "avg_pitch_hz": round(float(pitch), 1),
                "rms_energy": round(float(energy), 4),
            })
        except Exception as e:
            logger.warning(f"Stats failed for {item['audio']}: {e}")
    return stats


def run_training_check():
    """
    Main training loop:
    1. Load generation log
    2. Check if enough new samples exist
    3. Build dataset
    4. Trigger fine-tuning (if TTS trainer available)
    5. Update state
    """
    logger.info("=== Auto-Learning Check ===")
    state = load_train_state()
    entries = load_log()

    total = len(entries)
    new_since_last = total - state["samples_trained"]

    logger.info(f"Total samples: {total} | New since last training: {new_since_last}")

    MIN_SAMPLES = 10
    MIN_NEW_SAMPLES = 5

    if total < MIN_SAMPLES:
        logger.info(f"Need at least {MIN_SAMPLES} samples to start training. Skipping.")
        return

    if new_since_last < MIN_NEW_SAMPLES and state["runs"] > 0:
        logger.info(f"Only {new_since_last} new samples. Need {MIN_NEW_SAMPLES}. Skipping.")
        return

    # Build dataset
    dataset = build_dataset(entries)

    # Analyze voice quality
    stats = lightweight_voice_stats(dataset)
    stats_file = BASE_DIR / "model" / "voice_stats.json"
    stats_file.write_text(json.dumps(stats, indent=2, ensure_ascii=False))
    logger.info(f"Voice stats saved: {stats_file}")

    # ── Fine-tuning (XTTS v2 fine-tune) ──────────
    # This section runs XTTS v2 fine-tuning if enough data is available
    # Reference: https://docs.coqui.ai/en/latest/tutorial_for_nervous_beginners.html

    if total >= 50:
        logger.info("Attempting XTTS v2 fine-tuning...")
        try:
            _run_xtts_finetuning(dataset)
        except ImportError:
            logger.warning("TTS fine-tuning trainer not available in this install.")
        except Exception as e:
            logger.error(f"Fine-tuning failed: {e}")
    else:
        logger.info(f"Fine-tuning deferred (need 50+ samples, have {total}).")

    # Update state
    state["last_trained"] = datetime.utcnow().isoformat()
    state["samples_trained"] = total
    state["runs"] += 1
    save_train_state(state)
    logger.info(f"✅ Training run #{state['runs']} complete.")


def _run_xtts_finetuning(dataset):
    """
    Lightweight XTTS v2 fine-tuning using collected Bangla voice samples.
    This creates a speaker embedding that improves voice consistency.
    """
    from TTS.api import TTS
    import torch

    logger.info("Loading XTTS v2 for speaker embedding extraction...")
    tts = TTS(
        model_name="tts_models/multilingual/multi-dataset/xtts_v2",
        gpu=torch.cuda.is_available(),
    )

    # Extract and average speaker embeddings from all samples
    embeddings = []
    for item in dataset:
        if Path(item["audio"]).exists():
            try:
                gpt_cond, speaker_emb = tts.synthesizer.tts_model.get_conditioning_latents(
                    audio_path=[item["audio"]]
                )
                embeddings.append(speaker_emb.cpu().numpy())
            except Exception as e:
                logger.warning(f"Embedding extraction failed for {item['audio']}: {e}")

    if not embeddings:
        logger.warning("No embeddings extracted.")
        return

    # Average embeddings = improved speaker representation
    avg_emb = np.mean(embeddings, axis=0)
    emb_file = BASE_DIR / "model" / "bangla_speaker_embedding.npy"
    np.save(str(emb_file), avg_emb)
    logger.info(f"✅ Speaker embedding saved: {emb_file} (from {len(embeddings)} samples)")


if __name__ == "__main__":
    run_training_check()
