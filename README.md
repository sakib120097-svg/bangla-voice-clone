# 🇧🇩 বাংলা ভয়েস ক্লোনিং — Bangla Voice Clone

> Zero-shot Bangla voice cloning powered by Coqui XTTS v2 · 100% Free · Open Source · Google Colab Ready

![Bangla Voice Clone](https://img.shields.io/badge/Language-Bangla%20Only-green?style=for-the-badge)
![Model](https://img.shields.io/badge/Model-XTTS%20v2-blue?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-orange?style=for-the-badge)
![Colab](https://img.shields.io/badge/Google%20Colab-Ready-yellow?style=for-the-badge)

---

## ✨ Features

| Feature | Details |
|---|---|
| 🎙️ Voice Cloning | Zero-shot cloning with 5–30s sample |
| 🇧🇩 Bangla Only | Optimized Bengali phonetics & prosody |
| 🤖 Model | Coqui XTTS v2 (multilingual, state-of-the-art) |
| 📈 Auto-Learning | Stores samples, improves over time |
| 🎨 Web UI | Beautiful dark Bengali-themed frontend |
| ☁️ Colab Support | One-click Google Colab notebook |
| 🆓 100% Free | No paid APIs, fully open source |

---

## 📁 Project Structure

```
bangla-voice-clone/
├── frontend/
│   ├── index.html          # Main web UI (Bengali-themed)
│   ├── style.css           # Dark industrial aesthetic
│   └── app.js              # Frontend logic, drag-drop, preview
├── backend/
│   ├── app.py              # Flask API (XTTS v2 inference)
│   └── trainer.py          # Auto-learning / periodic retraining
├── model/
│   ├── voice_samples/      # Uploaded speaker samples (auto-saved)
│   ├── outputs/            # Generated audio files
│   ├── dataset/            # Auto-built Bangla dataset
│   └── generation_log.jsonl # Training metadata log
├── colab/
│   └── Bangla_Voice_Clone.ipynb  # Google Colab notebook
├── requirements.txt
└── README.md
```

---

## 🚀 Quick Start

### Option A: Google Colab (Easiest)

1. Open [`colab/Bangla_Voice_Clone.ipynb`](colab/Bangla_Voice_Clone.ipynb) in Google Colab
2. Enable GPU: `Runtime → Change runtime type → T4 GPU`
3. Click `Runtime → Run all`
4. Upload your WAV/MP3 voice sample when prompted
5. Edit `BANGLA_TEXT` variable with your text
6. Download the generated audio!

### Option B: Local Setup

#### Prerequisites
- Python 3.9–3.11
- pip
- 4GB+ RAM (8GB recommended)
- NVIDIA GPU optional (CPU works, slower)

#### Installation

```bash
# 1. Clone the repo
git clone https://github.com/yourusername/bangla-voice-clone.git
cd bangla-voice-clone

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Start the backend API
python backend/app.py
# API starts at http://localhost:8000

# 5. Open the frontend
# Simply open frontend/index.html in your browser
# Or serve it: python -m http.server 3000 --directory frontend
```

#### First Run
- The XTTS v2 model (~1.8 GB) downloads automatically on first request
- This takes 5–10 minutes depending on your internet speed
- Subsequent runs use the cached model

---

## 🎙️ Usage

### Web UI

1. **Upload Voice Sample** — Drag & drop a 5–30 second WAV/MP3 recording
2. **Enter Bangla Text** — Type or paste Bangla script (বাংলা লিখুন)
3. **Click "ভয়েস ক্লোন করুন"** — Wait ~30s–5min depending on hardware
4. **Play & Download** — Preview and save the generated audio

### API Direct Usage

```python
import requests

with open('my_voice.wav', 'rb') as f:
    response = requests.post(
        'http://localhost:8000/clone',
        files={'voice_sample': f},
        data={'text': 'আমি বাংলায় কথা বলতে ভালোবাসি।', 'language': 'bn'}
    )

with open('output.wav', 'wb') as f:
    f.write(response.content)
```

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Server + model status |
| POST | `/clone` | Generate cloned speech |
| GET | `/samples` | List stored samples |
| POST | `/retrain` | Trigger auto-retraining |

---

## 🧠 Auto-Learning System

The system automatically:

1. **Stores** every uploaded voice sample in `model/voice_samples/`
2. **Logs** each generation to `model/generation_log.jsonl`
3. **Analyzes** voice quality (pitch, energy, duration)
4. **Retrains** speaker embeddings when 50+ samples collected

### Manual Retraining

```bash
python backend/trainer.py
```

### Scheduled Retraining (cron)

```bash
# Run every 6 hours
0 */6 * * * cd /path/to/bangla-voice-clone && python backend/trainer.py
```

---

## 🔧 Configuration

Edit `backend/app.py` to customize:

```python
# GPU support (default: auto-detect)
use_gpu = True  # Force GPU

# Model selection
tts = TTS(model_name="tts_models/multilingual/multi-dataset/xtts_v2")

# Max text length
if len(text) > 500:  # Increase if needed
```

Edit `frontend/app.js` to change:

```javascript
const API_BASE = 'http://localhost:8000';  // Change for remote deployment
```

---

## 📊 Voice Quality Tips

For best Bangla cloning results:

- ✅ Use a **quiet room** with no background noise
- ✅ Record **10–20 seconds** of natural Bangla speech
- ✅ Use **22kHz or higher** sample rate
- ✅ Speak **clearly and naturally** (no whispering)
- ✅ Use a **good microphone** (even phone mic works)
- ❌ Avoid music in background
- ❌ Avoid very short clips (<5 seconds)

---

## 🤝 Contributing

Pull requests welcome! Areas to improve:

- Bangla text normalization (numbers → words)
- Real-time streaming audio generation
- Mobile-responsive UI enhancements
- Fine-tuning pipeline for Bangla-specific dataset

---

## 📜 License

MIT License. See [LICENSE](LICENSE) for details.

---

## 🙏 Acknowledgments

- [Coqui TTS](https://github.com/coqui-ai/TTS) — XTTS v2 model
- [Hugging Face](https://huggingface.co) — Model hosting
- [librosa](https://librosa.org) — Audio processing
- Bengali font support via Google Fonts (Hind Siliguri)
